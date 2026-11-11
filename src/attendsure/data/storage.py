"""SQLite persistence layer and repository operations for AttendSure.

Provides an offline-first, local SQLite repository for managing attendance
session records and explainable anomaly alerts conforming to docs/data-contract.md.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional, Sequence, Union
import uuid

import pandas as pd

from attendsure.data.models import (
    Alert,
    AlertPriority,
    RecordSource,
    ReviewStatus,
    SessionRecord,
    WebcamStatus,
)
from attendsure.data.validation import (
    validate_session_dataframe,
    validate_session_dict,
)

# Project root directory and default SQLite database path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "attendsure.db"

# Schema DDL statements
CREATE_TABLE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS attendance_sessions (
    session_id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL,
    session_date TEXT NOT NULL,
    expected_enrollment INTEGER NOT NULL,
    present_count INTEGER NOT NULL,
    absent_count INTEGER NOT NULL,
    webcam_status TEXT NOT NULL,
    webcam_count INTEGER,
    record_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CONSTRAINT uq_sessions_class_date UNIQUE (class_id, session_date),
    CONSTRAINT chk_sessions_enrollment CHECK (expected_enrollment >= 1),
    CONSTRAINT chk_sessions_present CHECK (present_count >= 0 AND present_count <= expected_enrollment),
    CONSTRAINT chk_sessions_absent CHECK (absent_count >= 0 AND absent_count <= expected_enrollment),
    CONSTRAINT chk_sessions_count_invariant CHECK (present_count + absent_count = expected_enrollment),
    CONSTRAINT chk_sessions_webcam_status CHECK (
        webcam_status IN ('SUCCESS', 'NOT_ATTEMPTED', 'CAMERA_UNAVAILABLE', 'DETECTION_FAILED')
    ),
    CONSTRAINT chk_sessions_webcam_mapping CHECK (
        (webcam_status = 'SUCCESS' AND webcam_count IS NOT NULL AND webcam_count >= 0)
        OR
        (webcam_status != 'SUCCESS' AND webcam_count IS NULL)
    ),
    CONSTRAINT chk_sessions_record_source CHECK (
        record_source IN ('SYNTHETIC', 'MANUAL_ENTRY', 'CSV_IMPORT')
    )
);
"""

CREATE_TABLE_ALERTS_SQL = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    session_date TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_title TEXT NOT NULL,
    priority TEXT NOT NULL,
    observed_value TEXT NOT NULL,
    baseline_reference TEXT NOT NULL,
    threshold_applied TEXT NOT NULL,
    explanation TEXT NOT NULL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT chk_alerts_priority CHECK (priority IN ('INFO', 'REVIEW_REQUIRED')),
    CONSTRAINT chk_alerts_review_status CHECK (
        review_status IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')
    ),
    CONSTRAINT chk_alerts_rule_id CHECK (
        rule_id IN ('RULE_ATTENDANCE_DROP', 'RULE_REPEATED_HEADCOUNT', 'RULE_WEBCAM_DISCREPANCY')
    )
);
"""

CREATE_TABLE_REVIEWS_SQL = """
CREATE TABLE IF NOT EXISTS alert_reviews (
    review_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL,
    new_status TEXT NOT NULL,
    notes TEXT,
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id) ON DELETE CASCADE,
    CONSTRAINT chk_reviews_status CHECK (
        new_status IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')
    )
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_class_date ON attendance_sessions(class_id, session_date);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_date ON attendance_sessions(session_date);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_session_id ON alerts(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_class_date ON alerts(class_id, session_date);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_review_status ON alerts(review_status);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_rule_id ON alerts(rule_id);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_alert_id ON alert_reviews(alert_id);",
]

VALID_REVIEW_STATUSES = {"PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"}
VALID_ALERT_PRIORITIES = {"INFO", "REVIEW_REQUIRED"}
VALID_RULE_IDS = {"RULE_ATTENDANCE_DROP", "RULE_REPEATED_HEADCOUNT", "RULE_WEBCAM_DISCREPANCY"}

SESSION_COLUMNS = [
    "session_id",
    "class_id",
    "session_date",
    "expected_enrollment",
    "present_count",
    "absent_count",
    "webcam_status",
    "webcam_count",
    "record_source",
    "created_at",
]

ALERT_COLUMNS = [
    "alert_id",
    "session_id",
    "class_id",
    "session_date",
    "rule_id",
    "rule_title",
    "priority",
    "observed_value",
    "baseline_reference",
    "threshold_applied",
    "explanation",
    "review_status",
    "created_at",
]

REQUIRED_ALERT_FIELDS = (
    "alert_id",
    "session_id",
    "class_id",
    "session_date",
    "rule_id",
    "rule_title",
    "priority",
    "observed_value",
    "baseline_reference",
    "threshold_applied",
    "explanation",
    "review_status",
    "created_at",
)


class AttendanceRepository:
    """SQLite repository for attendance sessions and explainable alerts.

    Features:
    - Standard library sqlite3 exclusively.
    - Foreign key constraints enabled on every connection.
    - Complete validation via data contract validators before persistence.
    - All-or-nothing batch transactions.
    - Idempotent alert insertion preserving existing educator review statuses.
    - Supports :memory: for isolated testing and file-based persistence.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize the repository.

        Args:
            db_path: Path to SQLite database file or ':memory:'. Defaults to
                'data/attendsure.db' resolved relative to project root.
        """
        if db_path is None:
            self._db_path: Union[str, Path] = DEFAULT_DB_PATH
            self._is_memory = False
        elif str(db_path) == ":memory:":
            self._db_path = ":memory:"
            self._is_memory = True
        else:
            self._db_path = Path(db_path).resolve()
            self._is_memory = False

        self._conn: Optional[sqlite3.Connection] = None
        self._is_closed: bool = False
        try:
            self.init_schema()
        except Exception:
            self.close()
            raise

    @property
    def db_path(self) -> Union[str, Path]:
        """Return the configured database path."""
        return self._db_path

    def get_connection(self) -> sqlite3.Connection:
        """Get an active database connection with row factory and foreign keys enabled.

        Raises:
            RuntimeError: If called on a closed in-memory repository.
        """
        if self._is_memory and self._is_closed:
            raise RuntimeError("Cannot perform operations on a closed in-memory repository.")

        if self._conn is None:
            if not self._is_memory:
                assert isinstance(self._db_path, Path)
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(self._db_path))
                self._is_closed = False
            else:
                self._conn = sqlite3.connect(":memory:")

            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")

            # Ensure tables and indexes are initialized on new or reconnected connection
            with self._conn:
                self._conn.execute(CREATE_TABLE_SESSIONS_SQL)
                self._conn.execute(CREATE_TABLE_ALERTS_SQL)
                self._conn.execute(CREATE_TABLE_REVIEWS_SQL)
                for index_sql in CREATE_INDEXES_SQL:
                    self._conn.execute(index_sql)

        return self._conn

    def close(self) -> None:
        """Close the active database connection if open."""
        self._is_closed = True
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "AttendanceRepository":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def init_schema(self) -> None:
        """Initialize database tables and indexes idempotently."""
        conn = self.get_connection()
        with conn:
            conn.execute(CREATE_TABLE_SESSIONS_SQL)
            conn.execute(CREATE_TABLE_ALERTS_SQL)
            for index_sql in CREATE_INDEXES_SQL:
                conn.execute(index_sql)

    # -------------------------------------------------------------------------
    # Attendance Session Operations
    # -------------------------------------------------------------------------

    def _prepare_session_record(self, session: Union[SessionRecord, dict]) -> SessionRecord:
        """Validate an individual session input and convert to SessionRecord."""
        if isinstance(session, SessionRecord):
            record_dict = asdict(session)
        elif isinstance(session, dict):
            record_dict = dict(session)
        else:
            raise TypeError(
                f"Expected SessionRecord or dict, got {type(session).__name__}."
            )

        val_result = validate_session_dict(record_dict)
        if not val_result.is_valid or val_result.cleaned_record is None:
            errors_str = "; ".join(val_result.errors)
            raise ValueError(f"Session validation failed: {errors_str}")

        clean = val_result.cleaned_record
        return SessionRecord(
            session_id=clean["session_id"],
            class_id=clean["class_id"],
            session_date=clean["session_date"],
            expected_enrollment=clean["expected_enrollment"],
            present_count=clean["present_count"],
            absent_count=clean["absent_count"],
            webcam_status=clean["webcam_status"],
            webcam_count=clean["webcam_count"],
            record_source=clean["record_source"],
            created_at=clean["created_at"],
        )

    def _prepare_session_batch(
        self, sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]]
    ) -> list[SessionRecord]:
        """Validate and prepare a batch of sessions without mutating input."""
        if isinstance(sessions, pd.DataFrame):
            df_to_validate = sessions
        elif isinstance(sessions, (list, tuple)):
            if not sessions:
                return []
            dict_rows = [
                asdict(s) if isinstance(s, SessionRecord) else dict(s)
                for s in sessions
            ]
            df_to_validate = pd.DataFrame(dict_rows)
            if "webcam_count" in df_to_validate.columns:
                df_to_validate["webcam_count"] = pd.Series(
                    [r.get("webcam_count") for r in dict_rows],
                    dtype=object,
                )
        else:
            raise TypeError(
                f"Expected pandas DataFrame or Sequence of records, got {type(sessions).__name__}."
            )

        if df_to_validate.empty:
            return []

        valid_df, rejected_df = validate_session_dataframe(df_to_validate)
        if not rejected_df.empty:
            error_details: list[str] = []
            for _, r in rejected_df.iterrows():
                errs = r.get("validation_errors", ["Invalid record"])
                sid = r.get("session_id", "unknown")
                error_details.append(f"[{sid}]: {', '.join(errs)}")
            raise ValueError(
                f"Batch validation failed for {len(rejected_df)} session(s): "
                + "; ".join(error_details)
            )

        records: list[SessionRecord] = []
        for r in valid_df.to_dict(orient="records"):
            records.append(
                SessionRecord(
                    session_id=str(r["session_id"]),
                    class_id=str(r["class_id"]),
                    session_date=str(r["session_date"]),
                    expected_enrollment=int(r["expected_enrollment"]),
                    present_count=int(r["present_count"]),
                    absent_count=int(r["absent_count"]),
                    webcam_status=r["webcam_status"],
                    webcam_count=int(r["webcam_count"]) if (r["webcam_count"] is not None and not pd.isna(r["webcam_count"])) else None,
                    record_source=r["record_source"],
                    created_at=str(r["created_at"]),
                )
            )
        return records

    def _insert_session_records(
        self, conn: sqlite3.Connection, records: Sequence[SessionRecord]
    ) -> None:
        """Execute parameterized INSERT statements for sessions without committing."""
        sql = """
        INSERT INTO attendance_sessions (
            session_id, class_id, session_date, expected_enrollment,
            present_count, absent_count, webcam_status, webcam_count,
            record_source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                r.session_id,
                r.class_id,
                r.session_date,
                r.expected_enrollment,
                r.present_count,
                r.absent_count,
                r.webcam_status,
                r.webcam_count,
                r.record_source,
                r.created_at,
            )
            for r in records
        ]
        conn.executemany(sql, params)

    def save_session(self, session: Union[SessionRecord, dict]) -> SessionRecord:
        """Validate and save a single attendance session.

        Args:
            session: SessionRecord or dictionary matching contract schema.

        Returns:
            The validated and persisted SessionRecord.

        Raises:
            ValueError: If validation rules are violated.
            sqlite3.IntegrityError: If session_id or (class_id, session_date) violates
                uniqueness or check constraints.
        """
        record = self._prepare_session_record(session)
        conn = self.get_connection()
        with conn:
            self._insert_session_records(conn, [record])
        return record

    def save_sessions(
        self, sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]]
    ) -> list[SessionRecord]:
        """Validate and save a batch of attendance sessions in an atomic transaction.

        Validates the entire batch before attempting insertion. If any record fails
        validation or any database constraint fails, rolls back all changes and raises
        an exception.

        Args:
            sessions: DataFrame or Sequence of SessionRecords/dicts.

        Returns:
            List of persisted SessionRecord objects.

        Raises:
            ValueError: If any record in the batch fails validation or batch uniqueness checks.
            sqlite3.IntegrityError: If database uniqueness or constraint checks fail.
        """
        records = self._prepare_session_batch(sessions)
        if not records:
            return []

        conn = self.get_connection()
        with conn:
            self._insert_session_records(conn, records)
        return records

    def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session by its unique session_id.

        Args:
            session_id: UUIDv4 session identifier.

        Returns:
            SessionRecord if found, None otherwise.
        """
        conn = self.get_connection()
        sql = """
        SELECT session_id, class_id, session_date, expected_enrollment,
               present_count, absent_count, webcam_status, webcam_count,
               record_source, created_at
        FROM attendance_sessions
        WHERE session_id = ?
        """
        cur = conn.execute(sql, (session_id,))
        row = cur.fetchone()
        if row is None:
            return None

        return SessionRecord(
            session_id=row["session_id"],
            class_id=row["class_id"],
            session_date=row["session_date"],
            expected_enrollment=row["expected_enrollment"],
            present_count=row["present_count"],
            absent_count=row["absent_count"],
            webcam_status=row["webcam_status"],
            webcam_count=row["webcam_count"],
            record_source=row["record_source"],
            created_at=row["created_at"],
        )

    def get_sessions(
        self,
        class_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        as_df: bool = False,
    ) -> Union[list[SessionRecord], pd.DataFrame]:
        """Retrieve sessions with optional filtering and stable chronological ordering.

        Ordered by: session_date ASC, class_id ASC, session_id ASC.

        Args:
            class_id: Optional classroom filter.
            start_date: Optional ISO 8601 start date (inclusive).
            end_date: Optional ISO 8601 end date (inclusive).
            as_df: If True, returns a pandas DataFrame; otherwise list of SessionRecord.

        Returns:
            List of SessionRecords or DataFrame.
        """
        conn = self.get_connection()
        query = [
            "SELECT session_id, class_id, session_date, expected_enrollment,",
            "       present_count, absent_count, webcam_status, webcam_count,",
            "       record_source, created_at",
            "FROM attendance_sessions",
            "WHERE 1=1",
        ]
        params: list[Any] = []

        if class_id is not None:
            query.append("AND class_id = ?")
            params.append(class_id)
        if start_date is not None:
            query.append("AND session_date >= ?")
            params.append(start_date)
        if end_date is not None:
            query.append("AND session_date <= ?")
            params.append(end_date)

        query.append("ORDER BY session_date ASC, class_id ASC, session_id ASC")
        sql = "\n".join(query)

        cur = conn.execute(sql, params)
        rows = cur.fetchall()

        if as_df:
            record_dicts = [dict(r) for r in rows]
            df = pd.DataFrame(record_dicts, columns=SESSION_COLUMNS)
            if "webcam_count" in df.columns:
                df["webcam_count"] = pd.Series(
                    [r["webcam_count"] if r["webcam_count"] is not None else None for r in record_dicts],
                    dtype=object,
                )
            return df

        return [
            SessionRecord(
                session_id=r["session_id"],
                class_id=r["class_id"],
                session_date=r["session_date"],
                expected_enrollment=r["expected_enrollment"],
                present_count=r["present_count"],
                absent_count=r["absent_count"],
                webcam_status=r["webcam_status"],
                webcam_count=r["webcam_count"],
                record_source=r["record_source"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # Alert Operations
    # -------------------------------------------------------------------------

    def _prepare_alerts(
        self, alerts: Sequence[Union[Alert, dict]]
    ) -> tuple[list[tuple[Any, ...]], list[Alert]]:
        """Validate and serialize alerts for parameterized insertion.

        Raises:
            TypeError: If an element is neither Alert nor dict, or if structured
                metrics contain non-JSON-serializable types.
            ValueError: If required fields are missing or domain rules are violated.
        """
        if not alerts:
            return [], []

        params: list[tuple[Any, ...]] = []
        alert_objects: list[Alert] = []

        for item in alerts:
            if isinstance(item, Alert):
                alert_obj = item
            elif isinstance(item, dict):
                missing_fields = [f for f in REQUIRED_ALERT_FIELDS if f not in item or item[f] is None]
                if missing_fields:
                    raise ValueError(
                        f"Alert dictionary is missing required fields: {', '.join(missing_fields)}"
                    )
                try:
                    alert_obj = Alert(**item)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Failed to instantiate Alert from dict: {exc}") from exc
            else:
                raise TypeError(f"Expected Alert or dict, got {type(item).__name__}.")

            # Validate domain constraints
            if not alert_obj.alert_id or not isinstance(alert_obj.alert_id, str):
                raise ValueError("alert_id must be a non-empty string.")
            if not alert_obj.session_id or not isinstance(alert_obj.session_id, str):
                raise ValueError("session_id must be a non-empty string.")
            if not alert_obj.class_id or not isinstance(alert_obj.class_id, str):
                raise ValueError("class_id must be a non-empty string.")
            if not alert_obj.session_date or not isinstance(alert_obj.session_date, str):
                raise ValueError("session_date must be a non-empty string.")
            if alert_obj.rule_id not in VALID_RULE_IDS:
                raise ValueError(
                    f"Invalid rule_id '{alert_obj.rule_id}'. Allowed: {sorted(VALID_RULE_IDS)}."
                )
            if alert_obj.priority not in VALID_ALERT_PRIORITIES:
                raise ValueError(
                    f"Invalid priority '{alert_obj.priority}'. Allowed: {sorted(VALID_ALERT_PRIORITIES)}."
                )
            if alert_obj.review_status not in VALID_REVIEW_STATUSES:
                raise ValueError(
                    f"Invalid review_status '{alert_obj.review_status}'. Allowed: {sorted(VALID_REVIEW_STATUSES)}."
                )
            if not isinstance(alert_obj.observed_value, dict):
                raise ValueError("observed_value must be a dictionary.")
            if not isinstance(alert_obj.baseline_reference, dict):
                raise ValueError("baseline_reference must be a dictionary.")
            if not isinstance(alert_obj.threshold_applied, dict):
                raise ValueError("threshold_applied must be a dictionary.")
            if not alert_obj.explanation or not isinstance(alert_obj.explanation, str):
                raise ValueError("explanation must be a non-empty string.")
            if not alert_obj.created_at or not isinstance(alert_obj.created_at, str):
                raise ValueError("created_at must be a non-empty string.")

            # Deterministic JSON serialization without silent stringification or default=str
            try:
                obs_json = json.dumps(alert_obj.observed_value, sort_keys=True)
                base_json = json.dumps(alert_obj.baseline_reference, sort_keys=True)
                thresh_json = json.dumps(alert_obj.threshold_applied, sort_keys=True)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    f"Alert '{alert_obj.alert_id}' contains non-JSON-serializable metric values: {exc}"
                ) from exc

            params.append(
                (
                    alert_obj.alert_id,
                    alert_obj.session_id,
                    alert_obj.class_id,
                    alert_obj.session_date,
                    alert_obj.rule_id,
                    alert_obj.rule_title,
                    alert_obj.priority,
                    obs_json,
                    base_json,
                    thresh_json,
                    alert_obj.explanation,
                    alert_obj.review_status,
                    alert_obj.created_at,
                )
            )
            alert_objects.append(alert_obj)

        return params, alert_objects

    def _verify_alert_session_consistency(
        self,
        conn: sqlite3.Connection,
        alerts: Sequence[Alert],
        known_sessions: Optional[dict[str, tuple[str, str]]] = None,
    ) -> None:
        """Verify that each alert references an existing session with matching class_id and session_date.

        Args:
            conn: Active database connection.
            alerts: Sequence of Alert objects to verify.
            known_sessions: Optional dictionary of session_id -> (class_id, session_date)
                for uncommitted sessions within the same transaction.

        Raises:
            ValueError: If a session does not exist, or if alert.class_id or
                alert.session_date does not match the referenced session.
        """
        if not alerts:
            return

        session_lookup: dict[str, tuple[str, str]] = dict(known_sessions) if known_sessions else {}

        # Find sessions not already known from the in-memory batch
        missing_ids = list({a.session_id for a in alerts if a.session_id not in session_lookup})
        if missing_ids:
            placeholders = ",".join("?" for _ in missing_ids)
            sql = (
                f"SELECT session_id, class_id, session_date "
                f"FROM attendance_sessions "
                f"WHERE session_id IN ({placeholders})"
            )
            cur = conn.execute(sql, missing_ids)
            for row in cur.fetchall():
                session_lookup[row["session_id"]] = (row["class_id"], row["session_date"])

        for alert in alerts:
            if alert.session_id not in session_lookup:
                raise ValueError(
                    f"Alert '{alert.alert_id}' references non-existent session '{alert.session_id}'."
                )

            expected_class_id, expected_date = session_lookup[alert.session_id]
            if alert.class_id != expected_class_id:
                raise ValueError(
                    f"Alert '{alert.alert_id}' class_id '{alert.class_id}' does not match "
                    f"referenced session '{alert.session_id}' class_id '{expected_class_id}'."
                )
            if alert.session_date != expected_date:
                raise ValueError(
                    f"Alert '{alert.alert_id}' session_date '{alert.session_date}' does not match "
                    f"referenced session '{alert.session_id}' session_date '{expected_date}'."
                )

    def _insert_alert_records(
        self, conn: sqlite3.Connection, params: Sequence[tuple[Any, ...]]
    ) -> None:
        """Insert alert records using targeted ON CONFLICT(alert_id) DO NOTHING.

        Preserves existing reviewer triage state and raises on foreign key or CHECK errors.
        """
        sql = """
        INSERT INTO alerts (
            alert_id, session_id, class_id, session_date, rule_id,
            rule_title, priority, observed_value, baseline_reference,
            threshold_applied, explanation, review_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(alert_id) DO NOTHING
        """
        conn.executemany(sql, params)

    def save_alerts(self, alerts: Sequence[Union[Alert, dict]]) -> list[Alert]:
        """Save a batch of alerts idempotently.

        Uses targeted ON CONFLICT(alert_id) DO NOTHING to ensure re-running
        detectors never resets manual educator review statuses. Enforces that all
        referenced sessions exist and that alert metadata (class_id, session_date)
        strictly matches the referenced session record.

        Args:
            alerts: Sequence of Alert objects or dicts.

        Returns:
            List of Alert objects submitted. Empty list if alerts is empty.

        Raises:
            TypeError: If invalid alert types or non-JSON metrics are provided.
            ValueError: If alert schema constraints or metadata mismatches occur.
            sqlite3.IntegrityError: If foreign key or database check constraints fail.
        """
        if not alerts:
            return []

        params, alert_objs = self._prepare_alerts(alerts)
        if not alert_objs:
            return []

        conn = self.get_connection()
        self._verify_alert_session_consistency(conn, alert_objs)
        with conn:
            self._insert_alert_records(conn, params)
        return alert_objs

    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """Retrieve an alert by its unique alert_id.

        Args:
            alert_id: Alert identifier.

        Returns:
            Alert with deserialized structured metrics if found, None otherwise.
        """
        conn = self.get_connection()
        sql = """
        SELECT alert_id, session_id, class_id, session_date, rule_id,
               rule_title, priority, observed_value, baseline_reference,
               threshold_applied, explanation, review_status, created_at
        FROM alerts
        WHERE alert_id = ?
        """
        cur = conn.execute(sql, (alert_id,))
        row = cur.fetchone()
        if row is None:
            return None

        return Alert(
            alert_id=row["alert_id"],
            session_id=row["session_id"],
            class_id=row["class_id"],
            session_date=row["session_date"],
            rule_id=row["rule_id"],
            rule_title=row["rule_title"],
            priority=row["priority"],
            observed_value=json.loads(row["observed_value"]),
            baseline_reference=json.loads(row["baseline_reference"]),
            threshold_applied=json.loads(row["threshold_applied"]),
            explanation=row["explanation"],
            review_status=row["review_status"],
            created_at=row["created_at"],
        )

    def get_alerts(
        self,
        review_status: Optional[str] = None,
        class_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        as_df: bool = False,
    ) -> Union[list[Alert], pd.DataFrame]:
        """Retrieve alerts with optional filtering and stable chronological ordering.

        Ordered by: session_date ASC, class_id ASC, rule_id ASC, alert_id ASC.

        Args:
            review_status: Optional review status filter.
            class_id: Optional class filter.
            rule_id: Optional rule filter.
            start_date: Optional start date filter (inclusive).
            end_date: Optional end date filter (inclusive).
            as_df: If True, returns a pandas DataFrame; otherwise list of Alert objects.

        Returns:
            List of Alerts or DataFrame.
        """
        conn = self.get_connection()
        query = [
            "SELECT alert_id, session_id, class_id, session_date, rule_id,",
            "       rule_title, priority, observed_value, baseline_reference,",
            "       threshold_applied, explanation, review_status, created_at",
            "FROM alerts",
            "WHERE 1=1",
        ]
        params: list[Any] = []

        if review_status is not None:
            query.append("AND review_status = ?")
            params.append(review_status)
        if class_id is not None:
            query.append("AND class_id = ?")
            params.append(class_id)
        if rule_id is not None:
            query.append("AND rule_id = ?")
            params.append(rule_id)
        if start_date is not None:
            query.append("AND session_date >= ?")
            params.append(start_date)
        if end_date is not None:
            query.append("AND session_date <= ?")
            params.append(end_date)

        query.append("ORDER BY session_date ASC, class_id ASC, rule_id ASC, alert_id ASC")
        sql = "\n".join(query)

        cur = conn.execute(sql, params)
        rows = cur.fetchall()

        alerts: list[Alert] = []
        for r in rows:
            alerts.append(
                Alert(
                    alert_id=r["alert_id"],
                    session_id=r["session_id"],
                    class_id=r["class_id"],
                    session_date=r["session_date"],
                    rule_id=r["rule_id"],
                    rule_title=r["rule_title"],
                    priority=r["priority"],
                    observed_value=json.loads(r["observed_value"]),
                    baseline_reference=json.loads(r["baseline_reference"]),
                    threshold_applied=json.loads(r["threshold_applied"]),
                    explanation=r["explanation"],
                    review_status=r["review_status"],
                    created_at=r["created_at"],
                )
            )

        if as_df:
            if not alerts:
                return pd.DataFrame(columns=ALERT_COLUMNS)
            return pd.DataFrame([asdict(a) for a in alerts], columns=ALERT_COLUMNS)

        return alerts

    def update_alert_review_status(self, alert_id: str, new_status: str) -> bool:
        """Update an alert's review status using only approved status values.

        Args:
            alert_id: Identifier of the alert to update.
            new_status: New review status (PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED).

        Returns:
            True if an alert was found and updated; False if alert_id does not exist.

        Raises:
            ValueError: If new_status is not an approved ReviewStatus value.
        """
        if new_status not in VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status '{new_status}'. Allowed values are: {sorted(VALID_REVIEW_STATUSES)}."
            )

        conn = self.get_connection()
        sql = "UPDATE alerts SET review_status = ? WHERE alert_id = ?"
        with conn:
            cur = conn.execute(sql, (new_status, alert_id))
            return cur.rowcount > 0

    def add_alert_review(
        self,
        alert_id: str,
        new_status: str,
        notes: Optional[str] = None,
        reviewed_at: Optional[str] = None,
    ) -> bool:
        """Record an explicit human review decision with optional notes.

        Updates the alert's review_status and appends an audit entry to alert_reviews.

        Args:
            alert_id: Identifier of the alert.
            new_status: New review status (PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED).
            notes: Optional explanatory notes explaining why the status was assigned.
            reviewed_at: Optional ISO 8601 timestamp string. Defaults to UTC now.

        Returns:
            True if review was recorded and alert was updated; False if alert does not exist.
        """
        if new_status not in VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status '{new_status}'. Allowed values are: {sorted(VALID_REVIEW_STATUSES)}."
            )

        ts = reviewed_at or datetime.now(timezone.utc).isoformat()
        review_id = f"REV-{uuid.uuid4()}"

        conn = self.get_connection()
        with conn:
            # Update parent alert review_status
            cur = conn.execute("UPDATE alerts SET review_status = ? WHERE alert_id = ?", (new_status, alert_id))
            if cur.rowcount == 0:
                return False

            # Insert review record
            conn.execute(
                "INSERT INTO alert_reviews (review_id, alert_id, new_status, notes, reviewed_at) VALUES (?, ?, ?, ?, ?)",
                (review_id, alert_id, new_status, notes.strip() if notes else None, ts),
            )
            return True

    def get_alert_reviews(self, alert_id: str) -> list[dict]:
        """Fetch all historical review decisions and notes for an alert.

        Args:
            alert_id: Identifier of the alert.

        Returns:
            List of review dicts sorted chronologically.
        """
        conn = self.get_connection()
        sql = """
        SELECT review_id, alert_id, new_status, notes, reviewed_at
        FROM alert_reviews
        WHERE alert_id = ?
        ORDER BY reviewed_at ASC
        """
        cur = conn.execute(sql, (alert_id,))
        return [dict(row) for row in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Combined Transaction Boundary
    # -------------------------------------------------------------------------

    def save_session_batch_with_alerts(
        self,
        sessions: Union[pd.DataFrame, Sequence[Union[SessionRecord, dict]]],
        alerts: Sequence[Union[Alert, dict]],
    ) -> tuple[list[SessionRecord], list[Alert]]:
        """Persist a batch of sessions and their associated alerts in a single transaction.

        Order of execution:
        1. Validates all sessions and alerts prior to writing.
        2. Within one transaction, inserts sessions first to satisfy the foreign
           key dependency (alerts.session_id -> attendance_sessions.session_id).
        3. Inserts alerts with idempotent ON CONFLICT(alert_id) DO NOTHING.
        4. If either sessions or alerts fail, rolls back all changes completely.

        Args:
            sessions: Sessions to save.
            alerts: Alerts to save.

        Returns:
            Tuple of (saved_sessions, saved_alerts).

        Raises:
            ValueError: If session or alert validation fails.
            sqlite3.IntegrityError: If uniqueness, check, or foreign key constraints fail.
        """
        session_records = self._prepare_session_batch(sessions)
        alert_params, alert_objs = self._prepare_alerts(alerts)

        if not session_records and not alert_objs:
            return [], []

        conn = self.get_connection()
        known_sessions = {s.session_id: (s.class_id, s.session_date) for s in session_records}
        self._verify_alert_session_consistency(conn, alert_objs, known_sessions=known_sessions)

        with conn:
            if session_records:
                self._insert_session_records(conn, session_records)
            if alert_params:
                self._insert_alert_records(conn, alert_params)

        return session_records, alert_objs
