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
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import uuid

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Text, ForeignKey,
    UniqueConstraint, CheckConstraint, Index
)

from attendsure.data.models import (
    Alert, AlertPriority, RecordSource, ReviewStatus, SessionRecord, WebcamStatus
)
from attendsure.data.storage import (
    DEFAULT_DB_PATH, AttendanceRepository, SESSION_COLUMNS, ALERT_COLUMNS, VALID_REVIEW_STATUSES
)
from attendsure.data.validation import validate_session_dict, validate_session_dataframe

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


def get_database_url(fallback_to_sqlite: bool = True) -> Optional[str]:
    """Retrieve the active database connection URL.

    Checks:
    1. ATTENDSURE_DATABASE_URL environment variable (e.g. postgresql://user:pass@host/db)
    2. DATABASE_URL standard cloud environment variable
    3. Streamlit Cloud Secrets (st.secrets)
    4. Local .env.local file if present
    5. Falls back to local SQLite path if fallback_to_sqlite is True
    """
    raw_url = os.environ.get("ATTENDSURE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not raw_url:
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                raw_url = st.secrets.get("ATTENDSURE_DATABASE_URL") or st.secrets.get("DATABASE_URL")
        except Exception:
            pass
    if not raw_url:
        try:
            from dotenv import dotenv_values
            for p in [Path(".env.local"), Path(__file__).resolve().parents[3] / ".env.local"]:
                if p.is_file():
                    vals = dotenv_values(p)
                    cand = vals.get("ATTENDSURE_DATABASE_URL") or vals.get("DATABASE_URL")
                    if cand and str(cand).strip():
                        raw_url = str(cand).strip()
                        break
        except Exception:
            pass

    if raw_url and str(raw_url).strip():
        return normalize_postgres_url(str(raw_url).strip())

    if not fallback_to_sqlite:
        return None

    # Fallback to SQLite URL
    db_path = os.environ.get("ATTENDSURE_DB_PATH")
    if db_path and db_path.strip():
        p = Path(db_path.strip()).resolve()
    else:
        p = DEFAULT_DB_PATH.resolve()

    # Form standard sqlite:/// URL
    return f"sqlite:///{p.as_posix()}"


def normalize_postgres_url(raw_url: str) -> str:
    """Normalize a PostgreSQL connection URL to explicitly use psycopg v3 dialect.

    Maps:
    - postgres://... -> postgresql+psycopg://...
    - postgresql://... -> postgresql+psycopg://...
    - postgresql+psycopg2://... -> postgresql+psycopg://...
    - postgresql+psycopg://... -> unchanged
    """
    if not raw_url:
        return raw_url
    url = str(raw_url).strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def is_production_mode() -> bool:
    """Return True if running in production mode."""
    env = os.environ.get("ATTENDSURE_ENVIRONMENT", "").strip().lower()
    is_prod = os.environ.get("ATTENDSURE_IS_PRODUCTION", "").strip().lower()
    if not env or not is_prod:
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                if not env:
                    env = str(st.secrets.get("ATTENDSURE_ENVIRONMENT", "")).strip().lower()
                if not is_prod:
                    is_prod = str(st.secrets.get("ATTENDSURE_IS_PRODUCTION", "")).strip().lower()
        except Exception:
            pass
    return env in ("production", "prod") or is_prod in ("1", "true", "yes")


def is_postgres_url(url: str) -> bool:
    """Return True if connection URL targets a PostgreSQL server."""
    if not url:
        return False
    u = str(url).strip()
    return u.startswith("postgresql://") or u.startswith("postgresql+") or u.startswith("postgres://")


def create_db_engine(url: Optional[str] = None) -> sa.Engine:
    """Create a configured SQLAlchemy Engine with connection pooling and timeouts."""
    target_url = url if url is not None else get_database_url()
    
    if is_postgres_url(target_url):
        target_url = normalize_postgres_url(target_url)
        # Configure pooling and timeout for cloud PostgreSQL with psycopg v3
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


# -----------------------------------------------------------------------------
# Enterprise Relational Repository (PostgreSQL / Neon & SQLAlchemy Core)
# -----------------------------------------------------------------------------

class RelationalRepository:
    """Enterprise relational repository implementing the AttendanceRepository interface.

    Backed by SQLAlchemy Core with pooled connections and ACID transaction guarantees.
    Supports PostgreSQL (e.g., Neon Cloud) and other relational backends.
    """

    def __init__(self, engine_or_url: Optional[Union[str, sa.Engine]] = None) -> None:
        """Initialize relational repository with connection engine."""
        if engine_or_url is None:
            self._engine: sa.Engine = create_db_engine()
        elif isinstance(engine_or_url, str):
            self._engine = create_db_engine(engine_or_url)
        else:
            self._engine = engine_or_url

        self._is_closed: bool = False
        init_relational_schema(self._engine)

    @property
    def db_path(self) -> str:
        """Return target database connection representation."""
        url_str = str(self._engine.url)
        if "@" in url_str:
            return f"postgresql://[credentials-hidden]@{url_str.split('@')[-1]}"
        return url_str

    def get_connection(self) -> sa.Connection:
        """Provide raw connection for compatibility."""
        return self._engine.connect()

    def close(self) -> None:
        """Close repository."""
        self._is_closed = True

    def __enter__(self) -> "RelationalRepository":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def init_schema(self) -> None:
        """Initialize all relational tables."""
        init_relational_schema(self._engine)

    def _prepare_session_record(self, session: Union[SessionRecord, dict]) -> SessionRecord:
        """Validate and construct contract-compliant SessionRecord."""
        if isinstance(session, SessionRecord):
            clean = asdict(session)
        elif isinstance(session, dict):
            clean = dict(session)
        else:
            raise TypeError(f"Expected SessionRecord or dict, got {type(session).__name__}")

        val_res = validate_session_dict(clean)
        if not val_res.is_valid:
            raise ValueError(f"Session validation failed: {'; '.join(val_res.errors)}")

        return SessionRecord(
            session_id=str(clean["session_id"]),
            class_id=str(clean["class_id"]),
            session_date=str(clean["session_date"]),
            expected_enrollment=int(clean["expected_enrollment"]),
            present_count=int(clean["present_count"]),
            absent_count=int(clean["absent_count"]),
            webcam_status=str(clean["webcam_status"]),
            webcam_count=int(clean["webcam_count"]) if clean.get("webcam_count") is not None else None,
            record_source=str(clean["record_source"]),
            created_at=str(clean["created_at"]),
        )

    def _prepare_session_batch(
        self, sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]]
    ) -> list[SessionRecord]:
        """Validate a batch of sessions for insertion."""
        if isinstance(sessions, pd.DataFrame):
            val_res = validate_session_dataframe(sessions)
            if not val_res.is_valid:
                raise ValueError(f"Batch validation failed: {'; '.join(val_res.errors)}")
            records = []
            for _, row in sessions.iterrows():
                r_dict = row.to_dict()
                records.append(self._prepare_session_record(r_dict))
            return records

        records = [self._prepare_session_record(s) for s in sessions]
        # Check intra-batch uniqueness
        seen_keys: set[tuple[str, str]] = set()
        seen_ids: set[str] = set()
        for r in records:
            key = (r.class_id, r.session_date)
            if key in seen_keys:
                raise ValueError(f"Duplicate class/date in batch: {key}")
            seen_keys.add(key)
            if r.session_id in seen_ids:
                raise ValueError(f"Duplicate session_id in batch: {r.session_id}")
            seen_ids.add(r.session_id)
        return records

    def save_session(self, session: Union[SessionRecord, dict]) -> SessionRecord:
        """Save a single session record, raising sqlite3.IntegrityError on collisions."""
        rec = self._prepare_session_record(session)
        with self._engine.begin() as conn:
            # Check unique constraint (class_id, session_date)
            exists = conn.execute(
                sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                    attendance_sessions_table.c.class_id == rec.class_id,
                    attendance_sessions_table.c.session_date == rec.session_date,
                )
            ).scalar()
            if exists:
                raise sqlite3.IntegrityError(
                    f"Record for class '{rec.class_id}' on date '{rec.session_date}' already exists."
                )

            # Check unique session_id
            id_exists = conn.execute(
                sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                    attendance_sessions_table.c.session_id == rec.session_id
                )
            ).scalar()
            if id_exists:
                raise sqlite3.IntegrityError(f"Record with session_id '{rec.session_id}' already exists.")

            conn.execute(attendance_sessions_table.insert().values(asdict(rec)))
        return rec

    def save_sessions(
        self, sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]]
    ) -> list[SessionRecord]:
        """Save batch of sessions in an atomic transaction."""
        records = self._prepare_session_batch(sessions)
        if not records:
            return []

        with self._engine.begin() as conn:
            for rec in records:
                exists = conn.execute(
                    sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                        attendance_sessions_table.c.class_id == rec.class_id,
                        attendance_sessions_table.c.session_date == rec.session_date,
                    )
                ).scalar()
                if exists:
                    raise sqlite3.IntegrityError(
                        f"Record for class '{rec.class_id}' on date '{rec.session_date}' already exists."
                    )
                conn.execute(attendance_sessions_table.insert().values(asdict(rec)))
        return records

    def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session record by its unique session_id."""
        stmt = sa.select(attendance_sessions_table).where(attendance_sessions_table.c.session_id == session_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().fetchone()
            if row is None:
                return None
            return SessionRecord(**dict(row))

    def get_sessions(
        self,
        class_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        as_df: bool = False,
    ) -> Union[list[SessionRecord], pd.DataFrame]:
        """Retrieve sessions with optional filtering and stable ordering."""
        stmt = sa.select(attendance_sessions_table)
        if class_id is not None:
            stmt = stmt.where(attendance_sessions_table.c.class_id == class_id)
        if start_date is not None:
            stmt = stmt.where(attendance_sessions_table.c.session_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(attendance_sessions_table.c.session_date <= end_date)

        stmt = stmt.order_by(
            attendance_sessions_table.c.session_date.asc(),
            attendance_sessions_table.c.class_id.asc(),
            attendance_sessions_table.c.session_id.asc(),
        )

        with self._engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(stmt).mappings().fetchall()]

        if as_df:
            df = pd.DataFrame(rows, columns=SESSION_COLUMNS)
            if "webcam_count" in df.columns:
                df["webcam_count"] = pd.Series(
                    [r["webcam_count"] if r["webcam_count"] is not None else None for r in rows],
                    dtype=object,
                )
            return df

        return [SessionRecord(**r) for r in rows]

    def _prepare_alerts(
        self, alerts: Sequence[Union[Alert, dict]]
    ) -> tuple[list[dict], list[Alert]]:
        """Validate and serialize alerts for insertion."""
        alert_dicts: list[dict] = []
        alert_objs: list[Alert] = []

        for a in alerts:
            if isinstance(a, Alert):
                ad = asdict(a)
                a_obj = a
            elif isinstance(a, dict):
                ad = dict(a)
                # Construct Alert object
                for f in ("observed_value", "baseline_reference", "threshold_applied"):
                    if isinstance(ad.get(f), str):
                        try:
                            ad[f] = json.loads(ad[f])
                        except Exception:
                            pass
                a_obj = Alert(**ad)
            else:
                raise TypeError(f"Invalid alert element type: {type(a).__name__}")

            if a_obj.review_status not in VALID_REVIEW_STATUSES:
                raise ValueError(f"Invalid review_status: {a_obj.review_status}")

            # Serialize dict values for Text column insertion
            raw_ad = asdict(a_obj)
            for f in ("observed_value", "baseline_reference", "threshold_applied"):
                if isinstance(raw_ad[f], (dict, list)):
                    raw_ad[f] = json.dumps(raw_ad[f])

            alert_dicts.append(raw_ad)
            alert_objs.append(a_obj)

        return alert_dicts, alert_objs

    def save_alerts(self, alerts: Sequence[Union[Alert, dict]]) -> list[Alert]:
        """Save a batch of alerts idempotently."""
        if not alerts:
            return []

        alert_dicts, alert_objs = self._prepare_alerts(alerts)

        with self._engine.begin() as conn:
            for ad in alert_dicts:
                # Enforce FK integrity: session must exist
                sess_exists = conn.execute(
                    sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                        attendance_sessions_table.c.session_id == ad["session_id"]
                    )
                ).scalar()
                if not sess_exists:
                    raise sqlite3.IntegrityError(
                        f"Referenced session_id '{ad['session_id']}' does not exist in attendance_sessions."
                    )

                # Check if alert already exists (idempotent, preserve existing review_status)
                exists = conn.execute(
                    sa.select(sa.func.count()).select_from(alerts_table).where(
                        alerts_table.c.alert_id == ad["alert_id"]
                    )
                ).scalar()
                if not exists:
                    conn.execute(alerts_table.insert().values(ad))

        return alert_objs

    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """Retrieve an alert by its unique alert_id."""
        stmt = sa.select(alerts_table).where(alerts_table.c.alert_id == alert_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().fetchone()
            if row is None:
                return None
            d = dict(row)
            for f in ("observed_value", "baseline_reference", "threshold_applied"):
                if isinstance(d[f], str):
                    try:
                        d[f] = json.loads(d[f])
                    except Exception:
                        pass
            return Alert(**d)

    def get_alerts(
        self,
        review_status: Optional[str] = None,
        class_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        as_df: bool = False,
    ) -> Union[list[Alert], pd.DataFrame]:
        """Retrieve alerts with optional filtering and stable chronological ordering."""
        stmt = sa.select(alerts_table)
        if review_status is not None:
            stmt = stmt.where(alerts_table.c.review_status == review_status)
        if class_id is not None:
            stmt = stmt.where(alerts_table.c.class_id == class_id)
        if rule_id is not None:
            stmt = stmt.where(alerts_table.c.rule_id == rule_id)
        if start_date is not None:
            stmt = stmt.where(alerts_table.c.session_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(alerts_table.c.session_date <= end_date)

        stmt = stmt.order_by(
            alerts_table.c.session_date.asc(),
            alerts_table.c.class_id.asc(),
            alerts_table.c.rule_id.asc(),
            alerts_table.c.alert_id.asc(),
        )

        with self._engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(stmt).mappings().fetchall()]

        for d in rows:
            for f in ("observed_value", "baseline_reference", "threshold_applied"):
                if isinstance(d[f], str):
                    try:
                        d[f] = json.loads(d[f])
                    except Exception:
                        pass

        if as_df:
            if not rows:
                return pd.DataFrame(columns=ALERT_COLUMNS)
            return pd.DataFrame(rows, columns=ALERT_COLUMNS)

        return [Alert(**d) for d in rows]

    def update_alert_review_status(self, alert_id: str, new_status: str) -> bool:
        """Update an alert's review status."""
        if new_status not in VALID_REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status '{new_status}'.")

        with self._engine.begin() as conn:
            res = conn.execute(
                sa.update(alerts_table).where(alerts_table.c.alert_id == alert_id).values(review_status=new_status)
            )
            return bool(res.rowcount > 0)

    def add_alert_review(
        self,
        alert_id: str,
        new_status: str,
        notes: Optional[str] = None,
        reviewed_at: Optional[str] = None,
    ) -> bool:
        """Record an explicit human review decision with optional notes."""
        if new_status not in VALID_REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status '{new_status}'.")

        ts = reviewed_at or datetime.now(timezone.utc).isoformat()
        review_id = f"REV-{uuid.uuid4()}"

        with self._engine.begin() as conn:
            upd = conn.execute(
                sa.update(alerts_table).where(alerts_table.c.alert_id == alert_id).values(review_status=new_status)
            )
            if upd.rowcount == 0:
                return False

            conn.execute(
                alert_reviews_table.insert().values(
                    review_id=review_id,
                    alert_id=alert_id,
                    new_status=new_status,
                    notes=notes.strip() if notes else None,
                    reviewed_at=ts,
                )
            )
            return True

    def get_alert_reviews(self, alert_id: str) -> list[dict]:
        """Fetch all historical review decisions and notes for an alert."""
        stmt = sa.select(alert_reviews_table).where(
            alert_reviews_table.c.alert_id == alert_id
        ).order_by(alert_reviews_table.c.reviewed_at.asc())
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().fetchall()]

    def save_session_batch_with_alerts(
        self,
        sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]],
        alerts: Sequence[Union[Alert, dict]],
    ) -> tuple[list[SessionRecord], list[Alert]]:
        """Persist a batch of sessions and associated alerts in a single transaction."""
        session_records = self._prepare_session_batch(sessions) if sessions is not None else []
        alert_dicts, alert_objs = self._prepare_alerts(alerts) if alerts else ([], [])

        with self._engine.begin() as conn:
            for rec in session_records:
                exists = conn.execute(
                    sa.select(sa.func.count()).select_from(attendance_sessions_table).where(
                        attendance_sessions_table.c.class_id == rec.class_id,
                        attendance_sessions_table.c.session_date == rec.session_date,
                    )
                ).scalar()
                if exists:
                    raise sqlite3.IntegrityError(
                        f"Record for class '{rec.class_id}' on date '{rec.session_date}' already exists."
                    )
                conn.execute(attendance_sessions_table.insert().values(asdict(rec)))

            for ad in alert_dicts:
                exists = conn.execute(
                    sa.select(sa.func.count()).select_from(alerts_table).where(
                        alerts_table.c.alert_id == ad["alert_id"]
                    )
                ).scalar()
                if not exists:
                    conn.execute(alerts_table.insert().values(ad))

        return session_records, alert_objs

