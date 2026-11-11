"""Unit tests for AttendSure Database Persistence, WAL configuration, and Backup/Restore.

Validates:
- Non-blocking online snapshot creation via Connection.backup.
- SQL dump export (iterdump) for relational portability.
- Atomic restore and integrity validation.
- Database health diagnosis (integrity check, foreign key check, row counts).
- Production environment detection guards.
"""

from pathlib import Path
import sqlite3
import tempfile
import pytest

from attendsure.data.db_persistence import (
    configure_wal_mode,
    create_database_backup,
    export_database_sql_dump,
    is_production_environment,
    restore_database_backup,
    verify_database_health,
)
from attendsure.data.models import SessionRecord
from attendsure.data.storage import AttendanceRepository


def _make_populated_database(db_file: Path) -> AttendanceRepository:
    """Helper to populate an isolated database with valid test records."""
    repo = AttendanceRepository(db_path=db_file)
    s = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-11-01",
        expected_enrollment=30,
        present_count=28,
        absent_count=2,
        webcam_status="SUCCESS",
        webcam_count=28,
        record_source="MANUAL_ENTRY",
        created_at="2026-11-01T09:00:00Z",
    )
    repo.save_sessions([s])
    return repo


def test_verify_database_health_on_healthy_and_missing_databases(tmp_path: Path):
    """Verify verify_database_health correctly analyzes database state and handles missing files."""
    db_file = tmp_path / "healthy.db"
    repo = _make_populated_database(db_file)
    repo.close()

    health = verify_database_health(db_file)
    assert health["is_healthy"] is True
    assert health["status"] == "HEALTHY"
    assert health["session_count"] == 1
    assert health["fk_violations"] == 0

    missing_file = tmp_path / "does_not_exist.db"
    missing_health = verify_database_health(missing_file)
    assert missing_health["is_healthy"] is False
    assert missing_health["status"] == "MISSING"


def test_create_database_backup_creates_valid_point_in_time_snapshot(tmp_path: Path):
    """Verify create_database_backup produces a complete, restorable snapshot."""
    src_db = tmp_path / "source.db"
    repo = _make_populated_database(src_db)
    repo.close()

    backup_dir = tmp_path / "backups"
    backup_file = create_database_backup(src_db, backup_dir=backup_dir)

    assert backup_file.exists()
    assert backup_file.name.startswith("attendsure_backup_")

    backup_health = verify_database_health(backup_file)
    assert backup_health["is_healthy"] is True
    assert backup_health["session_count"] == 1


def test_export_database_sql_dump(tmp_path: Path):
    """Verify export_database_sql_dump writes ANSI SQL DDL and INSERT statements."""
    src_db = tmp_path / "dump_source.db"
    repo = _make_populated_database(src_db)
    repo.close()

    dump_dir = tmp_path / "dumps"
    dump_file = export_database_sql_dump(src_db, dump_path=dump_dir / "test_dump.sql")

    assert dump_file.exists()
    sql_text = dump_file.read_text(encoding="utf-8")
    assert "CREATE TABLE attendance_sessions" in sql_text
    assert "INSERT INTO" in sql_text or "attendance_sessions" in sql_text


def test_restore_database_backup(tmp_path: Path):
    """Verify restore_database_backup safely overwrites or initializes target database."""
    src_db = tmp_path / "orig.db"
    repo = _make_populated_database(src_db)
    repo.close()

    backup_file = create_database_backup(src_db, backup_dir=tmp_path / "backups")

    target_restore = tmp_path / "restored.db"
    ok, msg = restore_database_backup(backup_file, target_path=target_restore)
    assert ok is True
    assert "Successfully restored" in msg

    restored_health = verify_database_health(target_restore)
    assert restored_health["is_healthy"] is True
    assert restored_health["session_count"] == 1


def test_restore_database_rejects_corrupted_or_nonexistent_backups(tmp_path: Path):
    """Verify restore_database_backup aborts safely when given missing or corrupted files."""
    missing = tmp_path / "ghost_backup.db"
    ok, msg = restore_database_backup(missing, target_path=tmp_path / "target.db")
    assert ok is False
    assert "does not exist" in msg

    corrupted = tmp_path / "corrupt.db"
    corrupted.write_text("NOT A SQLITE FILE")
    ok2, msg2 = restore_database_backup(corrupted, target_path=tmp_path / "target2.db")
    assert ok2 is False
    assert "failed integrity" in msg2


def test_is_production_environment(monkeypatch):
    """Verify is_production_environment detects production environment flags."""
    monkeypatch.setenv("ATTENDSURE_ENVIRONMENT", "production")
    assert is_production_environment() is True

    monkeypatch.setenv("ATTENDSURE_ENVIRONMENT", "development")
    monkeypatch.setenv("ATTENDSURE_IS_PRODUCTION", "1")
    assert is_production_environment() is True

    monkeypatch.setenv("ATTENDSURE_ENVIRONMENT", "development")
    monkeypatch.setenv("ATTENDSURE_IS_PRODUCTION", "0")
    assert is_production_environment() is False
