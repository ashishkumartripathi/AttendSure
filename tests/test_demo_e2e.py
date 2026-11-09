"""End-to-End Validation of Core Workflows for AttendSure Demonstration.

Covers:
- Workflow 1: Manual attendance session recording and count invariants.
- Workflow 2: Anomaly detection pipeline execution, explanations, and idempotency.
- Workflow 3: Human review triage status lifecycle and preservation across scans.
- Workflow 4: CSV ingestion boundaries (preview vs commit), all-or-nothing rollback, and export round-trips.
- Workflow 5: Algorithm Laboratory scenario evaluation and database isolation.
- Workflow 6: Provenance tracking, empty-state behavior, and database path isolation.
"""

from datetime import datetime, timezone
import io
from pathlib import Path
import sqlite3
import uuid
import pytest

import pandas as pd

from attendsure.data.csv_io import (
    REQUIRED_CSV_COLUMNS,
    export_alerts_to_csv,
    export_sessions_to_csv,
    import_sessions_from_csv,
    preview_sessions_from_csv,
)
from attendsure.data.generator import generate_scenario_sessions
from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository
from attendsure.detection.rules import (
    RULE_ATTENDANCE_DROP,
    RULE_REPEATED_HEADCOUNT,
    RULE_WEBCAM_DISCREPANCY,
    detect_anomalies,
)
from attendsure.evaluation.metrics import (
    evaluate_detector_performance,
    evaluate_sequence_events,
    evaluate_webcam_estimation,
)
from attendsure.services.attendance_service import (
    commit_csv_import,
    preview_csv_import,
    record_session_with_detection,
    run_full_detection_pipeline,
    update_alert_status,
)


@pytest.fixture
def isolated_repo(tmp_path):
    """Provides an isolated AttendanceRepository backed by a temporary SQLite file."""
    db_file = tmp_path / "test_isolated.db"
    repo = AttendanceRepository(db_path=db_file)
    yield repo
    repo.close()


class TestWorkflow1ManualAttendance:
    """Workflow 1: Manual attendance session recording and invariants."""

    def test_record_valid_session_and_invariants(self, isolated_repo):
        """Recording a valid manual session persists and satisfies enrollment invariant."""
        session_data = {
            "class_id": "CLASS-W1",
            "session_date": "2026-09-01",
            "expected_enrollment": 35,
            "present_count": 30,
            "absent_count": 5,
        }

        rec, alerts = record_session_with_detection(isolated_repo, session_data, run_detection=False)

        assert rec.class_id == "CLASS-W1"
        assert rec.present_count + rec.absent_count == rec.expected_enrollment
        assert rec.record_source == "MANUAL_ENTRY"
        assert rec.webcam_status == "NOT_ATTEMPTED"
        assert rec.webcam_count is None

        # Verify database query
        stored = isolated_repo.get_sessions(class_id="CLASS-W1")
        assert len(stored) == 1
        assert stored[0].session_id == rec.session_id

    def test_record_rejects_count_invariant_violation(self, isolated_repo):
        """Must reject session when present + absent != expected_enrollment."""
        invalid_data = {
            "class_id": "CLASS-W1-FAIL",
            "session_date": "2026-09-01",
            "expected_enrollment": 30,
            "present_count": 25,
            "absent_count": 10,  # 25 + 10 = 35 != 30
        }

        with pytest.raises(ValueError, match="Session validation failed"):
            record_session_with_detection(isolated_repo, invalid_data, run_detection=False)

        # Confirm 0 records were saved
        assert len(isolated_repo.get_sessions(class_id="CLASS-W1-FAIL")) == 0

    def test_rejects_duplicate_class_and_date(self, isolated_repo):
        """Enforces database unique constraint on (class_id, session_date)."""
        valid_data = {
            "class_id": "CLASS-DUP",
            "session_date": "2026-09-02",
            "expected_enrollment": 25,
            "present_count": 20,
            "absent_count": 5,
        }

        record_session_with_detection(isolated_repo, valid_data, run_detection=False)

        # Attempt duplicate insertion
        with pytest.raises(Exception):
            record_session_with_detection(isolated_repo, valid_data, run_detection=False)


class TestWorkflow2AnomalyDetection:
    """Workflow 2: Anomaly detection pipeline, explanation completeness, and idempotency."""

    def test_pipeline_detects_and_explains_anomalies(self, isolated_repo):
        """Detects attendance drop with complete explainable context."""
        # Seed 5 normal sessions followed by a drop
        sessions = []
        for i in range(5):
            sessions.append(
                SessionRecord(
                    session_id=str(uuid.uuid4()),
                    class_id="CLASS-ANOM",
                    session_date=f"2026-09-1{i}",
                    expected_enrollment=30,
                    present_count=28,
                    absent_count=2,
                    webcam_status="SUCCESS",
                    webcam_count=28,
                    record_source="SYNTHETIC",
                    created_at="2026-09-10T09:00:00Z",
                )
            )
        # Drop session
        drop_sid = str(uuid.uuid4())
        sessions.append(
            SessionRecord(
                session_id=drop_sid,
                class_id="CLASS-ANOM",
                session_date="2026-09-15",
                expected_enrollment=30,
                present_count=10,  # steep drop
                absent_count=20,
                webcam_status="SUCCESS",
                webcam_count=10,
                record_source="SYNTHETIC",
                created_at="2026-09-15T09:00:00Z",
            )
        )
        isolated_repo.save_sessions(sessions)

        # Execute detection
        alerts = run_full_detection_pipeline(isolated_repo, class_id="CLASS-ANOM")
        assert len(alerts) >= 1

        drop_alert = [a for a in alerts if a.session_id == drop_sid and a.rule_id == RULE_ATTENDANCE_DROP][0]
        assert drop_alert.priority in ("INFO", "REVIEW_REQUIRED")
        assert drop_alert.review_status == "PENDING_REVIEW"
        assert "observed_value" in drop_alert.__dict__
        assert "baseline_reference" in drop_alert.__dict__
        assert "threshold_applied" in drop_alert.__dict__
        assert len(drop_alert.explanation) > 10

    def test_detection_idempotency_prevents_duplicate_alerts(self, isolated_repo):
        """Running detection repeatedly does not generate duplicate alerts."""
        s1_id = str(uuid.uuid4())
        s2_id = str(uuid.uuid4())
        sessions = [
            SessionRecord(
                session_id=s1_id,
                class_id="CLASS-IDEM",
                session_date="2026-09-01",
                expected_enrollment=30,
                present_count=28,
                absent_count=2,
                webcam_status="SUCCESS",
                webcam_count=28,
                record_source="SYNTHETIC",
                created_at="2026-09-01T09:00:00Z",
            ),
            SessionRecord(
                session_id=s2_id,
                class_id="CLASS-IDEM",
                session_date="2026-09-02",
                expected_enrollment=30,
                present_count=10,
                absent_count=20,
                webcam_status="SUCCESS",
                webcam_count=10,
                record_source="SYNTHETIC",
                created_at="2026-09-02T09:00:00Z",
            ),
        ]
        isolated_repo.save_sessions(sessions)

        run_full_detection_pipeline(isolated_repo, class_id="CLASS-IDEM")
        alerts_run_1 = isolated_repo.get_alerts(class_id="CLASS-IDEM")

        run_full_detection_pipeline(isolated_repo, class_id="CLASS-IDEM")
        alerts_run_2 = isolated_repo.get_alerts(class_id="CLASS-IDEM")

        assert len(alerts_run_1) == len(alerts_run_2)


class TestWorkflow3HumanReviewTriage:
    """Workflow 3: Human review status updates and persistence across detection runs."""

    def test_status_transitions_and_persistence(self, isolated_repo):
        """Updating status persists and is not overwritten by subsequent detection scans."""
        session = SessionRecord(
            session_id=str(uuid.uuid4()),
            class_id="CLASS-REV",
            session_date="2026-09-01",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="SUCCESS",
            webcam_count=15,  # Cam discrepancy: 28 vs 15 (diff=13)
            record_source="SYNTHETIC",
            created_at="2026-09-01T09:00:00Z",
        )
        isolated_repo.save_sessions([session])
        alerts = run_full_detection_pipeline(isolated_repo, class_id="CLASS-REV")
        assert len(alerts) >= 1
        target_alert = alerts[0]
        assert target_alert.review_status == "PENDING_REVIEW"

        # Triage status update: ACKNOWLEDGED
        updated = update_alert_status(isolated_repo, target_alert.alert_id, "ACKNOWLEDGED")
        assert updated is True

        reloaded = isolated_repo.get_alert_by_id(target_alert.alert_id)
        assert reloaded.review_status == "ACKNOWLEDGED"

        # Re-run detection pipeline; verify status is preserved, not reset to PENDING_REVIEW
        run_full_detection_pipeline(isolated_repo, class_id="CLASS-REV")
        after_scan = isolated_repo.get_alert_by_id(target_alert.alert_id)
        assert after_scan.review_status == "ACKNOWLEDGED"


class TestWorkflow4CsvIngestionAndExport:
    """Workflow 4: CSV preview isolation, commit behavior, rollback, and export."""

    def test_preview_causes_zero_writes(self, isolated_repo):
        """Previewing a CSV file causes 0 rows to be written to storage."""
        csv_content = (
            "session_id,class_id,session_date,expected_enrollment,present_count,absent_count,webcam_status,webcam_count,record_source,created_at\n"
            "10000000-0000-4000-8000-000000000001,CLASS-CSV,2026-09-01,30,28,2,NOT_ATTEMPTED,,CSV_IMPORT,2026-09-01T09:00:00Z\n"
        )
        result = preview_csv_import(isolated_repo, io.StringIO(csv_content))
        assert result.failed_count == 0
        assert result.total_rows == 1
        assert len(result.imported_sessions) == 1

        # Check database: must be empty
        assert len(isolated_repo.get_sessions()) == 0

    def test_commit_persists_valid_csv(self, isolated_repo):
        """Committing persists validated CSV sessions."""
        csv_content = (
            "session_id,class_id,session_date,expected_enrollment,present_count,absent_count,webcam_status,webcam_count,record_source,created_at\n"
            "10000000-0000-4000-8000-000000000002,CLASS-CSV2,2026-09-01,30,28,2,NOT_ATTEMPTED,,CSV_IMPORT,2026-09-01T09:00:00Z\n"
        )
        result = commit_csv_import(isolated_repo, io.StringIO(csv_content))
        assert result.failed_count == 0
        assert result.imported_count == 1
        assert len(result.imported_sessions) == 1

        stored = isolated_repo.get_sessions(class_id="CLASS-CSV2")
        assert len(stored) == 1
        assert stored[0].session_id == "10000000-0000-4000-8000-000000000002"

    def test_all_or_nothing_rollback_on_invalid_row(self, isolated_repo):
        """Default CSV import rolls back all rows if any row is invalid."""
        csv_content = (
            "session_id,class_id,session_date,expected_enrollment,present_count,absent_count,webcam_status,webcam_count,record_source,created_at\n"
            "10000000-0000-4000-8000-000000000003,CLASS-CSV3,2026-09-01,30,28,2,NOT_ATTEMPTED,,CSV_IMPORT,2026-09-01T09:00:00Z\n"
            "10000000-0000-4000-8000-000000000004,CLASS-CSV3,2026-09-02,30,999,2,NOT_ATTEMPTED,,CSV_IMPORT,2026-09-02T09:00:00Z\n"
        )
        result = commit_csv_import(isolated_repo, io.StringIO(csv_content), allow_partial=False)
        assert result.failed_count > 0
        assert result.imported_count == 0
        assert len(result.errors) > 0

        # Entire batch must be rolled back
        assert len(isolated_repo.get_sessions(class_id="CLASS-CSV3")) == 0

    def test_export_round_trip_compatibility(self, isolated_repo):
        """Exporting sessions to CSV and reading back produces identical fields."""
        sid = "10000000-0000-4000-8000-000000000005"
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-RT",
            session_date="2026-09-01",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="SUCCESS",
            webcam_count=28,
            record_source="MANUAL_ENTRY",
            created_at="2026-09-01T09:00:00Z",
        )
        isolated_repo.save_sessions([rec])

        exported_csv = export_sessions_to_csv(isolated_repo)
        df = pd.read_csv(io.StringIO(exported_csv))

        for col in REQUIRED_CSV_COLUMNS:
            assert col in df.columns

        assert len(df) == 1
        assert df.iloc[0]["session_id"] == sid
        assert int(df.iloc[0]["expected_enrollment"]) == 30
        assert int(df.iloc[0]["present_count"]) == 28


class TestWorkflow5AlgorithmLaboratory:
    """Workflow 5: Scenario generation, benchmarking, and database isolation."""

    def test_scenario_generation_database_isolation(self, isolated_repo):
        """Algorithm Laboratory runs in-memory and never writes to SQLite database."""
        initial_sessions = len(isolated_repo.get_sessions())
        initial_alerts = len(isolated_repo.get_alerts())

        # Generate each scenario
        for sc in ["NOMINAL", "ATTENDANCE_DROP", "REPEATED_HEADCOUNT", "WEBCAM_DISCREPANCY"]:
            df = generate_scenario_sessions(scenario_type=sc, num_days=15, random_seed=42)
            assert not df.empty
            assert "ground_truth_is_anomaly" in df.columns

            alerts = detect_anomalies(df)
            metrics = evaluate_detector_performance(df, alerts)
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1_score" in metrics
            assert "confusion_matrix" in metrics

        # Confirm repository remains untouched
        assert len(isolated_repo.get_sessions()) == initial_sessions
        assert len(isolated_repo.get_alerts()) == initial_alerts

    def test_sequence_event_evaluation_distinction(self):
        """Verifies distinction between session-level and event-level metrics."""
        df = generate_scenario_sessions(scenario_type="REPEATED_HEADCOUNT", num_days=15, random_seed=42)
        alerts = detect_anomalies(df)

        session_metrics = evaluate_detector_performance(df, alerts)
        event_metrics = evaluate_sequence_events(df, alerts, target_rule_id=RULE_REPEATED_HEADCOUNT)

        # In a 4-day repeated sequence, session-level recall evaluates each day (1/4 = 0.25)
        # while event-level recall evaluates the 1 event as a whole (1/1 = 1.0)
        assert event_metrics["total_events"] >= 1
        assert event_metrics["recall"] >= session_metrics["recall"]


class TestWorkflow6StorageAndProvenance:
    """Workflow 6: Database diagnostics, provenance categorization, and empty states."""

    def test_empty_database_diagnostics_and_zero_state(self, isolated_repo):
        """Empty database returns zero counts and clean empty state."""
        sessions_df = isolated_repo.get_sessions(as_df=True)
        alerts_df = isolated_repo.get_alerts(as_df=True)
        assert len(sessions_df) == 0
        assert len(alerts_df) == 0

    def test_provenance_categorization(self, isolated_repo):
        """Correctly categorizes sessions by provenance source."""
        s1 = SessionRecord(
            session_id=str(uuid.uuid4()),
            class_id="C-P",
            session_date="2026-09-01",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="MANUAL_ENTRY",
            created_at="2026-09-01T09:00:00Z",
        )
        s2 = SessionRecord(
            session_id=str(uuid.uuid4()),
            class_id="C-P",
            session_date="2026-09-02",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="CSV_IMPORT",
            created_at="2026-09-02T09:00:00Z",
        )
        s3 = SessionRecord(
            session_id=str(uuid.uuid4()),
            class_id="C-P",
            session_date="2026-09-03",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="SYNTHETIC",
            created_at="2026-09-03T09:00:00Z",
        )
        isolated_repo.save_sessions([s1, s2, s3])

        sessions_df = isolated_repo.get_sessions(as_df=True)
        counts = sessions_df["record_source"].value_counts().to_dict()
        assert counts["MANUAL_ENTRY"] == 1
        assert counts["CSV_IMPORT"] == 1
        assert counts["SYNTHETIC"] == 1
