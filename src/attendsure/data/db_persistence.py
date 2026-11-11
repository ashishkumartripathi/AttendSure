"""Production Database Persistence, WAL Configuration, and Backup/Restore Engine.

Provides enterprise-grade reliability and persistent storage operations for AttendSure:
- Write-Ahead Logging (WAL) and synchronous pragmas for ACID durability and crash resilience.
- Online, non-blocking database backups using sqlite3.Connection.backup.
- Standard SQL dump export (iterdump) for relational migration (e.g., to PostgreSQL).
- Atomic restore and integrity validation (PRAGMA integrity_check, foreign_key_check).
- Environment-level protection preventing demo seed scripts from overwriting production data.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Dict, Optional, Tuple, Union

from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository


def configure_wal_mode(conn: sqlite3.Connection) -> None:
    """Configure Write-Ahead Logging (WAL) and busy timeout for high concurrency and crash safety."""
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")


def is_production_environment() -> bool:
    """Return True if running in production mode, blocking destructive operations."""
    env = os.environ.get("ATTENDSURE_ENVIRONMENT", "").strip().lower()
    is_prod = os.environ.get("ATTENDSURE_IS_PRODUCTION", "").strip().lower()
    return env in ("production", "prod") or is_prod in ("1", "true", "yes")


def create_database_backup(
    db_path: Optional[Union[str, Path]] = None,
    backup_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Create a live, non-blocking point-in-time snapshot backup of the database.

    Args:
        db_path: Path to the active database. Defaults to configured DB path.
        backup_dir: Directory to store backup files. Defaults to 'data/backups'.

    Returns:
        Path to the generated backup database file.
    """
    src_path = Path(db_path if db_path is not None else DEFAULT_DB_PATH).resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Source database file does not exist: {src_path}")

    if backup_dir is None:
        target_dir = src_path.parent / "backups"
    else:
        target_dir = Path(backup_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"attendsure_backup_{timestamp}.db"
    dest_path = target_dir / backup_filename

    # Perform online snapshot backup using SQLite backup API (zero locking downtime)
    src_conn = sqlite3.connect(str(src_path))
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        with dest_conn:
            src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    return dest_path


def export_database_sql_dump(
    db_path: Optional[Union[str, Path]] = None,
    dump_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Export the complete database schema and data as standard SQL DDL and INSERT statements.

    Suitable for migrating records to PostgreSQL, MySQL, or long-term archiving.
    """
    src_path = Path(db_path if db_path is not None else DEFAULT_DB_PATH).resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Source database file does not exist: {src_path}")

    if dump_path is None:
        dump_dir = src_path.parent / "dumps"
        dump_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_path = dump_dir / f"attendsure_dump_{timestamp}.sql"
    else:
        dest_path = Path(dump_path).resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(src_path))
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            for line in src_conn.iterdump():
                f.write(f"{line}\n")
    finally:
        src_conn.close()

    return dest_path


def verify_database_health(db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Execute complete database health, consistency, and integrity diagnostics.

    Returns:
        Dictionary with integrity check status, row counts, and foreign key verification.
    """
    target = Path(db_path if db_path is not None else DEFAULT_DB_PATH).resolve()
    if not target.exists():
        return {
            "status": "MISSING",
            "is_healthy": False,
            "error": f"Database file not found at {target}",
            "file_size_bytes": 0,
            "session_count": 0,
            "alert_count": 0,
            "review_count": 0,
        }

    try:
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        try:
            # 1. Integrity check
            cursor = conn.execute("PRAGMA integrity_check;")
            integrity_rows = cursor.fetchall()
            integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"

            # 2. Foreign key check
            fk_cursor = conn.execute("PRAGMA foreign_key_check;")
            fk_violations = fk_cursor.fetchall()
            fk_ok = len(fk_violations) == 0

            # 3. Row counts
            session_count = conn.execute("SELECT COUNT(*) FROM attendance_sessions;").fetchone()[0]
            alert_count = conn.execute("SELECT COUNT(*) FROM alerts;").fetchone()[0]
            review_count = 0
            has_reviews = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='alert_reviews';"
            ).fetchone()[0]
            if has_reviews:
                review_count = conn.execute("SELECT COUNT(*) FROM alert_reviews;").fetchone()[0]

            file_size = target.stat().st_size

            return {
                "status": "HEALTHY" if (integrity_ok and fk_ok) else "CORRUPTED",
                "is_healthy": integrity_ok and fk_ok,
                "file_path": str(target),
                "file_size_bytes": file_size,
                "integrity_check": "ok" if integrity_ok else str(integrity_rows),
                "fk_violations": len(fk_violations),
                "session_count": session_count,
                "alert_count": alert_count,
                "review_count": review_count,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {
            "status": "ERROR",
            "is_healthy": False,
            "error": str(exc),
            "file_size_bytes": 0,
            "session_count": 0,
            "alert_count": 0,
            "review_count": 0,
        }


def restore_database_backup(
    backup_path: Union[str, Path],
    target_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, str]:
    """Safely restore the active database from a verified backup snapshot.

    Verifies the backup file's integrity BEFORE replacing the target database.
    """
    backup_file = Path(backup_path).resolve()
    if not backup_file.exists():
        return False, f"Backup file does not exist: {backup_file}"

    # Verify backup health before applying
    backup_health = verify_database_health(backup_file)
    if not backup_health["is_healthy"]:
        return False, f"Backup file failed integrity verification: {backup_health.get('error', 'corrupted')}"

    dest_file = Path(target_path if target_path is not None else DEFAULT_DB_PATH).resolve()
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    # Perform atomic replacement
    temp_target = dest_file.with_suffix(".tmp_restore")
    shutil.copy2(backup_file, temp_target)

    # Replace target
    if dest_file.exists():
        # Preserve temporary rollback copy
        rollback_target = dest_file.with_suffix(".pre_restore")
        shutil.copy2(dest_file, rollback_target)
        temp_target.replace(dest_file)
        if rollback_target.exists():
            rollback_target.unlink()
    else:
        temp_target.replace(dest_file)

    return True, f"Successfully restored database from {backup_file.name} ({backup_health['session_count']} sessions)."

