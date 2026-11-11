"""Relational Database Engine Abstraction and PostgreSQL Support for AttendSure.

Provides an enterprise-ready database abstraction layer supporting both
local offline SQLite and managed PostgreSQL cloud databases (e.g. Neon, Supabase, Render).

Features:
- SQLAlchemy Core unified schema for attendance_sessions, alerts, and alert_reviews.
- Automatic handling of postgres:// to postgresql:// driver prefix mapping.
- Transactional batch migrations from SQLite to PostgreSQL with integrity checks.
- Connection pooling and reconnect resilience for managed cloud databases.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Text, ForeignKey,
    UniqueConstraint, CheckConstraint, Index
)

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository

# Canonical metadata and schema definitions
metadata = MetaData()

attendance_sessions_table = Table(
    "attendance_sessions",
    metadata,
    Column("session_id", String(64), primary_key=True),
    Column("class_id", String(32), nullable=False),
    Column("session_date", String(16), nullable=False),
    Column("expected_enrollment", Integer, nullable=False),
    Column("present_count", Integer, nullable=False),
    Column("absent_count", Integer, nullable=False),
    Column("webcam_status", String(32), nullable=False),
    Column("webcam_count", Integer, nullable=True),
    Column("record_source", String(32), nullable=False),
    Column("created_at", String(64), nullable=False),
    UniqueConstraint("class_id", "session_date", name="uq_sessions_class_date"),
    CheckConstraint("expected_enrollment >= 1", name="chk_sessions_enrollment"),
    CheckConstraint("present_count >= 0 AND present_count <= expected_enrollment", name="chk_sessions_present"),
    CheckConstraint("absent_count >= 0 AND absent_count <= expected_enrollment", name="chk_sessions_absent"),
    CheckConstraint("present_count + absent_count = expected_enrollment", name="chk_sessions_count_invariant"),
    CheckConstraint(
        "webcam_status IN ('SUCCESS', 'NOT_ATTEMPTED', 'CAMERA_UNAVAILABLE', 'DETECTION_FAILED')",
        name="chk_sessions_webcam_status",
    ),
    CheckConstraint(
        "record_source IN ('SYNTHETIC', 'MANUAL_ENTRY', 'CSV_IMPORT')",
        name="chk_sessions_record_source",
    ),
)

alerts_table = Table(
    "alerts",
    metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("session_id", String(64), ForeignKey("attendance_sessions.session_id", ondelete="CASCADE"), nullable=False),
    Column("class_id", String(32), nullable=False),
    Column("session_date", String(16), nullable=False),
    Column("rule_id", String(64), nullable=False),
    Column("rule_title", String(128), nullable=False),
    Column("priority", String(32), nullable=False),
    Column("observed_value", Text, nullable=False),
    Column("baseline_reference", Text, nullable=False),
    Column("threshold_applied", Text, nullable=False),
    Column("explanation", Text, nullable=False),
    Column("review_status", String(32), nullable=False),
    Column("created_at", String(64), nullable=False),
    CheckConstraint("priority IN ('INFO', 'REVIEW_REQUIRED')", name="chk_alerts_priority"),
    CheckConstraint(
        "review_status IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')",
        name="chk_alerts_review_status",
    ),
    CheckConstraint(
        "rule_id IN ('RULE_ATTENDANCE_DROP', 'RULE_REPEATED_HEADCOUNT', 'RULE_WEBCAM_DISCREPANCY')",
        name="chk_alerts_rule_id",
    ),
)

alert_reviews_table = Table(
    "alert_reviews",
    metadata,
    Column("review_id", String(64), primary_key=True),
    Column("alert_id", String(64), ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False),
    Column("new_status", String(32), nullable=False),
    Column("notes", Text, nullable=True),
    Column("reviewed_at", String(64), nullable=False),
    CheckConstraint(
        "new_status IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')",
        name="chk_reviews_status",
    ),
)

# Relational Indexes
idx_sessions_class_date = Index("idx_sessions_class_date", attendance_sessions_table.c.class_id, attendance_sessions_table.c.session_date)
idx_sessions_date = Index("idx_sessions_date", attendance_sessions_table.c.session_date)
idx_alerts_session_id = Index("idx_alerts_session_id", alerts_table.c.session_id)
idx_alerts_class_date = Index("idx_alerts_class_date", alerts_table.c.class_id, alerts_table.c.session_date)
idx_alerts_review_status = Index("idx_alerts_review_status", alerts_table.c.review_status)
idx_alerts_rule_id = Index("idx_alerts_rule_id", alerts_table.c.rule_id)
idx_reviews_alert_id = Index("idx_reviews_alert_id", alert_reviews_table.c.alert_id)


def get_database_url() -> str:
    """Retrieve the active database connection URL.

    Checks:
    1. ATTENDSURE_DATABASE_URL environment variable (e.g. postgresql://user:pass@host/db)
    2. DATABASE_URL standard cloud environment variable
    3. Falls back to local SQLite path (ATTENDSURE_DB_PATH or DEFAULT_DB_PATH)
    """
    raw_url = os.environ.get("ATTENDSURE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if raw_url and raw_url.strip():
        url = raw_url.strip()
        # Normalise legacy postgres:// prefix to postgresql:// for SQLAlchemy compatibility
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # Fallback to SQLite URL
    db_path = os.environ.get("ATTENDSURE_DB_PATH")
    if db_path and db_path.strip():
        p = Path(db_path.strip()).resolve()
    else:
        p = DEFAULT_DB_PATH.resolve()

    # Form standard sqlite:/// URL
    return f"sqlite:///{p.as_posix()}"


def is_postgres_url(url: str) -> bool:
    """Return True if connection URL targets a PostgreSQL server."""
    return url.startswith("postgresql://") or url.startswith("postgresql+") or url.startswith("postgres://")


def create_db_engine(url: Optional[str] = None) -> sa.Engine:
    """Create a configured SQLAlchemy Engine with connection pooling and timeouts."""
    target_url = url if url is not None else get_database_url()
    
    if is_postgres_url(target_url):
        # Configure pooling and timeout for cloud PostgreSQL
        return sa.create_engine(
            target_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
    else:
        # SQLite engine
        return sa.create_engine(
            target_url,
            connect_args={"timeout": 15},
        )


def init_relational_schema(engine: sa.Engine) -> None:
    """Create all relational tables and constraints idempotently."""
    metadata.create_all(engine)


def migrate_sqlite_to_target(
    source_sqlite_path: Union[str, Path],
    target_engine: sa.Engine,
) -> Dict[str, Any]:
    """Safely migrate all data from an existing SQLite database into the target relational engine.

    Args:
        source_sqlite_path: Path to existing SQLite database file.
        target_engine: Active SQLAlchemy Engine (e.g., PostgreSQL).

    Returns:
        Dictionary summarizing migrated row counts and verification status.
    """
    src_repo = AttendanceRepository(db_path=source_sqlite_path)
    try:
        # Extract all records from source
        sessions = src_repo.get_sessions(as_df=False)
        alerts = src_repo.get_alerts(as_df=False)
        
        # Read reviews
        conn = src_repo.get_connection()
        review_rows = []
        has_reviews = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='alert_reviews';"
        ).fetchone()[0]
        if has_reviews:
            cursor = conn.execute("SELECT review_id, alert_id, new_status, notes, reviewed_at FROM alert_reviews;")
            for r in cursor.fetchall():
                review_rows.append(dict(r))
    finally:
        src_repo.close()

    # Initialize tables on target
    init_relational_schema(target_engine)

    # Perform transactional insert on target
    with target_engine.begin() as target_conn:
        # Insert sessions
        if sessions:
            session_dicts = [asdict(s) for s in sessions]
            # Upsert / insert ignore behavior
            for s_dict in session_dicts:
                # Check existence
                exists = target_conn.execute(
                    sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                        attendance_sessions_table.c.session_id == s_dict["session_id"]
                    )
                ).scalar()
                if not exists:
                    target_conn.execute(attendance_sessions_table.insert().values(s_dict))

        # Insert alerts
        if alerts:
            alert_dicts = []
            for a in alerts:
                import json
                ad = asdict(a)
                # Serialize JSON fields if string
                for f in ("observed_value", "baseline_reference", "threshold_applied"):
                    if isinstance(ad[f], (dict, list)):
                        ad[f] = json.dumps(ad[f])
                alert_dicts.append(ad)

            for a_dict in alert_dicts:
                exists = target_conn.execute(
                    sa.select(sa.func.count()).select_from(alerts_table).where(
                        alerts_table.c.alert_id == a_dict["alert_id"]
                    )
                ).scalar()
                if not exists:
                    target_conn.execute(alerts_table.insert().values(a_dict))

        # Insert reviews
        for r_dict in review_rows:
            exists = target_conn.execute(
                sa.select(sa.func.count()).select_from(alert_reviews_table).where(
                    alert_reviews_table.c.review_id == r_dict["review_id"]
                )
            ).scalar()
            if not exists:
                target_conn.execute(alert_reviews_table.insert().values(r_dict))

    # Verify counts on target
    with target_engine.connect() as check_conn:
        t_sessions = check_conn.execute(sa.select(sa.func.count()).select_from(attendance_sessions_table)).scalar()
        t_alerts = check_conn.execute(sa.select(sa.func.count()).select_from(alerts_table)).scalar()
        t_reviews = check_conn.execute(sa.select(sa.func.count()).select_from(alert_reviews_table)).scalar()

    return {
        "status": "SUCCESS",
        "migrated_sessions": t_sessions,
        "migrated_alerts": t_alerts,
        "migrated_reviews": t_reviews,
        "source_sessions": len(sessions),
        "source_alerts": len(alerts),
        "source_reviews": len(review_rows),
        "integrity_verified": (t_sessions >= len(sessions)) and (t_alerts >= len(alerts)),
    }

