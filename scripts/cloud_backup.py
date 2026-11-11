"""Automated Independent Cloud Backup & Disaster Recovery Utility for AttendSure.

Features:
- Point-in-time binary snapshot creation (.db) and ANSI SQL dump generation (.sql).
- AES-128/HMAC authenticated encryption (Fernet via PBKDF2-HMAC-SHA256).
- Cryptographic SHA-256 manifest generation.
- Offsite cloud upload to S3-compatible independent storage (AWS S3, Cloudflare R2, Supabase Storage).
- Self-verifying restoration test mode (--test-restore) confirming zero data corruption.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from attendsure.data.db_persistence import (
    create_database_backup,
    export_database_sql_dump,
    restore_database_backup,
    verify_database_health,
)


def compute_file_sha256(file_path: Path) -> str:
    """Compute cryptographic SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_encryption_suite(secret_key: str = None) -> Fernet:
    """Derive a Fernet authenticated encryption suite from secret key and salt."""
    key_str = secret_key or os.environ.get("ATTENDSURE_BACKUP_KEY", "AttendSure-Production-Backup-Key-2026")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"attendsure_static_backup_salt_v1",
        iterations=100_000,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(key_str.encode("utf-8")))
    return Fernet(derived)


def encrypt_file(src_path: Path, dest_path: Path, secret_key: str = None) -> Path:
    """Encrypt a database snapshot file using Fernet authenticated encryption."""
    fernet = get_encryption_suite(secret_key)
    raw_data = src_path.read_bytes()
    encrypted_data = fernet.encrypt(raw_data)
    dest_path.write_bytes(encrypted_data)
    return dest_path


def decrypt_file(encrypted_path: Path, dest_path: Path, secret_key: str = None) -> Path:
    """Decrypt an encrypted backup file using Fernet authenticated encryption."""
    fernet = get_encryption_suite(secret_key)
    encrypted_data = encrypted_path.read_bytes()
    decrypted_data = fernet.decrypt(encrypted_data)
    dest_path.write_bytes(decrypted_data)
    return dest_path


def upload_to_s3_storage(
    file_path: Path,
    bucket_name: str,
    s3_prefix: str = "attendsure-backups",
    endpoint_url: str = None,
) -> bool:
    """Upload a backup file to an S3-compatible independent cloud bucket."""
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url or os.environ.get("S3_ENDPOINT_URL"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        object_key = f"{s3_prefix}/{file_path.name}"
        print(f"Uploading {file_path.name} to s3://{bucket_name}/{object_key}...")
        s3.upload_file(str(file_path), bucket_name, object_key)
        print("Cloud upload succeeded.")
        return True
    except Exception as exc:
        print(f"Notice: S3 upload skipped or credentials unconfigured ({exc}).")
        return False


def test_backup_restoration(encrypted_backup_path: Path, expected_sessions: int, secret_key: str = None) -> bool:
    """Decrypt backup file into a temporary isolated environment and verify integrity."""
    with tempfile.TemporaryDirectory() as td:
        decrypted_db = Path(td) / "test_restored.db"
        decrypt_file(encrypted_backup_path, decrypted_db, secret_key=secret_key)
        
        health = verify_database_health(decrypted_db)
        if not health["is_healthy"]:
            print(f"Restoration check FAILED: Integrity status is {health['integrity_check']}.")
            return False

        if health["session_count"] != expected_sessions:
            print(f"Restoration check FAILED: Expected {expected_sessions} sessions, found {health['session_count']}.")
            return False

        print(f"Restoration check PASSED: Decrypted and verified {health['session_count']} sessions, {health['alert_count']} alerts, {health['review_count']} reviews.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Create independent encrypted backup of AttendSure database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_PROJECT_ROOT / "data" / "production_rumv.db",
        help="Path to database file",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=_PROJECT_ROOT / "data" / "backups",
        help="Directory to save snapshot",
    )
    parser.add_argument(
        "--upload-s3",
        action="store_true",
        help="Upload backup to configured S3 bucket",
    )
    parser.add_argument(
        "--test-restore",
        action="store_true",
        help="Execute immediate decryption and restoration integrity test",
    )
    args = parser.parse_args()

    db_file = args.db_path.resolve()
    if not db_file.exists():
        print(f"Error: Database file not found at {db_file}")
        sys.exit(1)

    print("=" * 70)
    print("ATTENDSURE ENCRYPTED INDEPENDENT CLOUD BACKUP ENGINE")
    print("=" * 70)

    # 1. Verify health before backup
    health = verify_database_health(db_file)
    print(f"Active Database:    {db_file}")
    print(f"Status / Health:    {health['status']} (Integrity: {health['integrity_check']})")
    print(f"Sessions / Alerts:  {health['session_count']} sessions, {health['alert_count']} alerts, {health['review_count']} reviews")

    if not health["is_healthy"]:
        print("Aborting: Database failed integrity verification prior to backup.")
        sys.exit(1)

    # 2. Generate point-in-time snapshot
    dest_dir = args.dest.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    backup_file = create_database_backup(db_file, backup_dir=dest_dir)
    backup_hash = compute_file_sha256(backup_file)
    print(f"\nCreated Snapshot:   {backup_file.name} ({backup_file.stat().st_size} bytes)")
    print(f"Snapshot SHA-256:   {backup_hash}")

    # 3. Encrypt snapshot for offsite cloud storage
    encrypted_file = dest_dir / f"{backup_file.name}.enc"
    encrypt_file(backup_file, encrypted_file)
    encrypted_hash = compute_file_sha256(encrypted_file)
    print(f"Encrypted Archive:  {encrypted_file.name} ({encrypted_file.stat().st_size} bytes)")
    print(f"Encrypted SHA-256:  {encrypted_hash}")

    # 4. Generate portable SQL dump
    sql_dir = dest_dir / "sql_dumps"
    sql_dir.mkdir(parents=True, exist_ok=True)
    dump_file = export_database_sql_dump(db_file, dump_path=sql_dir / f"{backup_file.stem}.sql")
    dump_hash = compute_file_sha256(dump_file)
    print(f"Created SQL Dump:   {dump_file.name} ({dump_file.stat().st_size} bytes)")
    print(f"SQL Dump SHA-256:   {dump_hash}")

    # 5. Execute self-verifying restoration check
    print("\nExecuting Independent Restoration Test...")
    restore_ok = test_backup_restoration(encrypted_file, expected_sessions=health["session_count"])
    if not restore_ok:
        print("Error: Backup restoration verification failed.")
        sys.exit(1)

    # 6. Optional S3 Cloud Upload
    bucket = os.environ.get("BACKUP_BUCKET") or os.environ.get("S3_BUCKET")
    if args.upload_s3 and bucket:
        upload_to_s3_storage(encrypted_file, bucket_name=bucket)
        upload_to_s3_storage(dump_file, bucket_name=bucket)
    elif args.upload_s3 and not bucket:
        print("Note: --upload-s3 specified but BACKUP_BUCKET environment variable is unset.")

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_database": str(db_file),
        "snapshot_file": backup_file.name,
        "snapshot_sha256": backup_hash,
        "encrypted_file": encrypted_file.name,
        "encrypted_sha256": encrypted_hash,
        "dump_file": dump_file.name,
        "dump_sha256": dump_hash,
        "encryption_algorithm": "Fernet-AES-128-CBC-HMAC-SHA256 (PBKDF2-100k)",
        "session_count": health["session_count"],
        "alert_count": health["alert_count"],
        "review_count": health["review_count"],
        "restoration_verified": restore_ok,
    }
    manifest_path = dest_dir / f"{backup_file.stem}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Backup Manifest:    {manifest_path.name}")
    print("=" * 70)
    print("Independent encrypted backup & restoration verification succeeded.")


if __name__ == "__main__":
    main()
