"""Migration utility to transfer AttendSure records from SQLite to managed PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_postgres.py --source data/production_rumv.db --target-url postgresql://user:pass@host:5432/dbname
    
Or set DATABASE_URL environment variable:
    $env:DATABASE_URL="postgresql://user:pass@host:5432/dbname"
    python scripts/migrate_sqlite_to_postgres.py --source data/production_rumv.db
"""

import argparse
import os
from pathlib import Path
import sys

# Ensure src is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from attendsure.data.db_engine import create_db_engine, get_database_url, is_postgres_url, migrate_sqlite_to_target


def main():
    parser = argparse.ArgumentParser(description="Migrate AttendSure SQLite records to managed PostgreSQL")
    parser.add_argument(
        "--source",
        type=Path,
        default=_PROJECT_ROOT / "data" / "production_rumv.db",
        help="Path to source SQLite database file",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default=None,
        help="Target PostgreSQL connection URL (e.g. postgresql://user:pass@host:5432/dbname)",
    )
    args = parser.parse_args()

    source_path = args.source.resolve()
    if not source_path.exists():
        print(f"Error: Source SQLite database not found at {source_path}")
        sys.exit(1)

    target_url = args.target_url or os.environ.get("ATTENDSURE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not target_url:
        print("Error: No target database URL provided. Pass --target-url or set ATTENDSURE_DATABASE_URL.")
        sys.exit(1)

    print("=" * 70)
    print("ATTENDSURE DATABASE MIGRATION ENGINE (SQLite -> Cloud Relational)")
    print("=" * 70)
    print(f"Source SQLite File:  {source_path}")
    print(f"Target Engine Type:  {'PostgreSQL' if is_postgres_url(target_url) else 'Relational'}")
    print(f"Target URL:          {target_url.split('@')[-1] if '@' in target_url else target_url}")

    try:
        target_engine = create_db_engine(target_url)
        print("Connecting to target database and initializing schema...")
        result = migrate_sqlite_to_target(source_path, target_engine)
        
        print("\nMigration Results:")
        print(f"  Sessions Migrated: {result['migrated_sessions']} / {result['source_sessions']}")
        print(f"  Alerts Migrated:   {result['migrated_alerts']} / {result['source_alerts']}")
        print(f"  Reviews Migrated:  {result['migrated_reviews']} / {result['source_reviews']}")
        print(f"  Integrity Check:   {'VERIFIED (Zero Data Loss)' if result['integrity_verified'] else 'FAILED'}")
        print("=" * 70)
        print("Migration completed successfully.")
    except Exception as exc:
        print(f"\nMigration failed with error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

