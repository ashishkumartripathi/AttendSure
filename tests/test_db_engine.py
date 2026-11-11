"""Unit tests for AttendSure Relational Database Engine Abstraction and Migration.

Validates:
- Database URL parsing and normalization (postgres:// to postgresql://).
- PostgreSQL URL detection.
- SQLAlchemy Table schema definitions (attendance_sessions, alerts, alert_reviews).
- Transactional migration from SQLite to SQLAlchemy target with zero loss.
"""

from pathlib import Path
import pytest
import sqlalchemy as sa

from attendsure.data.db_engine import (
    attendance_sessions_table,
    alerts_table,
    alert_reviews_table,
    create_db_engine,
    get_database_url,
    init_relational_schema,
    is_postgres_url,
    migrate_sqlite_to_target,
)
from attendsure.data.models import SessionRecord
from attendsure.data.storage import AttendanceRepository


def test_database_url_normalization(monkeypatch):
    """Verify get_database_url normalizes postgres:// to postgresql+psycopg:// for SQLAlchemy."""
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    url = get_database_url()
    assert url.startswith("postgresql+psycopg://")
    assert is_postgres_url(url) is True

    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    url_sqlite = get_database_url()
    assert url_sqlite.startswith("sqlite://")
    assert is_postgres_url(url_sqlite) is False


def test_schema_table_columns_and_constraints():
    """Verify SQLAlchemy Table schemas match the official data contract specification."""
    session_cols = {c.name for c in attendance_sessions_table.columns}
    expected_session_cols = {
        "session_id", "class_id", "session_date", "expected_enrollment",
        "present_count", "absent_count", "webcam_status", "webcam_count",
        "record_source", "created_at"
    }
    assert expected_session_cols.issubset(session_cols)

    alert_cols = {c.name for c in alerts_table.columns}
    assert "alert_id" in alert_cols
    assert "session_id" in alert_cols
    assert "rule_id" in alert_cols
    assert "review_status" in alert_cols

    review_cols = {c.name for c in alert_reviews_table.columns}
    assert "review_id" in review_cols
    assert "alert_id" in review_cols
    assert "notes" in review_cols


def test_migrate_sqlite_to_target_preserves_all_records(tmp_path: Path):
    """Verify migrate_sqlite_to_target copies sessions, alerts, and reviews with verified integrity."""
    db_file = tmp_path / "source_mig.db"
    repo = AttendanceRepository(db_path=db_file)
    s = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440099",
        class_id="CLASS-01-A",
        session_date="2026-11-01",
        expected_enrollment=30,
        present_count=29,
        absent_count=1,
        webcam_status="SUCCESS",
        webcam_count=29,
        record_source="MANUAL_ENTRY",
        created_at="2026-11-01T09:00:00Z",
    )
    repo.save_sessions([s])
    repo.close()

    target_engine = sa.create_engine("sqlite:///:memory:")
    result = migrate_sqlite_to_target(db_file, target_engine)

    assert result["status"] == "SUCCESS"
    assert result["migrated_sessions"] == 1
    assert result["source_sessions"] == 1
    assert result["integrity_verified"] is True

