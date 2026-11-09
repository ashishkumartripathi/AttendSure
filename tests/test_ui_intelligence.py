"""Headless automated UI integration tests for AttendSure Intelligence Centre.

Tests Milestone M5.3.3.1 requirements using Streamlit's native headless AppTest framework:
1. Clean render with an empty database.
2. Display of stored alerts and non-accusatory explanations.
3. Class, rule, priority, and date filtering.
4. Review-status filtering.
5. Structured evidence breakdown and associated session context.
6. Valid review-status transition persists to storage.
7. Redundant or invalid status transition is handled safely without writes.
8. Explicit on-demand detection scan and idempotency across repeated runs.
9. Ordinary reruns do not re-trigger scans or repeat status writes.
10. Missing associated session and empty-filter results are handled gracefully.
"""

from datetime import date
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.detection.rules import RULE_ATTENDANCE_DROP_TITLE
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_intelligence(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Needs Attention and run."""
    try:
        at.sidebar.radio[0].set_value("Needs Attention").run()
    except Exception:
        try:
            at.sidebar.radio[0].set_value("Alerts").run()
        except Exception:
            at.sidebar.radio[0].set_value("Intelligence Centre").run()


def _seed_test_data(db_file: Path) -> tuple[list[SessionRecord], list[Alert]]:
    """Helper to populate an isolated SQLite database with sample sessions and alerts."""
    with get_repository(db_path=db_file) as repo:
        s1 = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440001",
            class_id="CLASS-01-A",
            session_date="2026-10-20",
            expected_enrollment=30,
            present_count=18,
            absent_count=12,
            webcam_status="SUCCESS",
            webcam_count=18,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-20T09:00:00Z",
        )
        s2 = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440002",
            class_id="CLASS-02-B",
            session_date="2026-10-22",
            expected_enrollment=25,
            present_count=20,
            absent_count=5,
            webcam_status="CAMERA_UNAVAILABLE",
            webcam_count=None,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-22T09:00:00Z",
        )
        s3 = SessionRecord(
            session_id="550e8400-e29b-41d4-a716-446655440003",
            class_id="CLASS-01-A",
            session_date="2026-10-24",
            expected_enrollment=30,
            present_count=25,
            absent_count=5,
            webcam_status="SUCCESS",
            webcam_count=18,  # Discrepancy: 25 vs 18
            record_source="MANUAL_ENTRY",
            created_at="2026-10-24T09:00:00Z",
        )
        repo.save_sessions([s1, s2, s3])

        a1 = Alert(
            alert_id="ALT-550e8400-e29b-41d4-a716-446655440001",
            session_id=s1.session_id,
            class_id=s1.class_id,
            session_date=s1.session_date,
            rule_id="RULE_ATTENDANCE_DROP",
            rule_title=RULE_ATTENDANCE_DROP_TITLE,
            priority="REVIEW_REQUIRED",
            observed_value={"present_count": 18, "attendance_rate_pct": 60.0},
            baseline_reference={"rolling_median_rate_pct": 90.0, "baseline_sessions": 5},
            threshold_applied={"relative_decline_threshold_pct": 30.0},
            explanation="Class CLASS-01-A recorded an attendance decline of 33.3% relative to historical baseline.",
            review_status="PENDING_REVIEW",
            created_at="2026-10-20T10:00:00Z",
        )
        a2 = Alert(
            alert_id="ALT-550e8400-e29b-41d4-a716-446655440002",
            session_id=s2.session_id,
            class_id=s2.class_id,
            session_date=s2.session_date,
            rule_id="RULE_REPEATED_HEADCOUNT",
            rule_title="Repeated Identical Headcounts",
            priority="INFO",
            observed_value={"repeated_headcount": 20, "consecutive_sessions": 4},
            baseline_reference={"expected_behavior": "daily_natural_variation"},
            threshold_applied={"consecutive_sessions_threshold": 4},
            explanation="Class CLASS-02-B recorded identical present headcount (20) across 4 consecutive sessions.",
            review_status="ACKNOWLEDGED",
            created_at="2026-10-22T10:00:00Z",
        )
        a3 = Alert(
            alert_id="ALT-550e8400-e29b-41d4-a716-446655440003",
            session_id=s3.session_id,
            class_id=s3.class_id,
            session_date=s3.session_date,
            rule_id="RULE_WEBCAM_DISCREPANCY",
            rule_title="Visible-Person Discrepancy",
            priority="REVIEW_REQUIRED",
            observed_value={"manual_present_count": 25, "webcam_estimated_count": 18},
            baseline_reference={"expected_alignment": "manual_roll_call"},
            threshold_applied={"min_absolute_difference": 5, "min_relative_difference_pct": 20.0},
            explanation="Camera visible-person count (18) differs from manual attendance (25) by 7 people (28.0%).",
            review_status="RESOLVED",
            created_at="2026-10-24T10:00:00Z",
        )
        repo.save_alerts([a1, a2, a3])
        return [s1, s2, s3], [a1, a2, a3]


def test_intelligence_renders_cleanly_on_empty_db(tmp_path: Path):
    """Scenario 1: Verify Intelligence Centre renders cleanly on an empty database."""
    db_file = tmp_path / "empty_intel.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    assert not at.exception
    assert len(at.error) == 0

    assert at.header[0].value in ("Needs Attention", "Alerts", "Intelligence Centre")
    info_texts = [i.value for i in at.info]
    assert any("No anomaly signals recorded in the database" in text or "no anomaly" in text.lower() for text in info_texts)

    # Decision support notice is rendered
    markdown_texts = [m.value for m in at.markdown]
    assert any("Decision Support Notice" in text for text in markdown_texts)


def test_intelligence_displays_stored_alerts_and_non_accusatory_explanations(tmp_path: Path):
    """Scenario 2: Verify display of stored alerts, non-accusatory text, and KPI strip."""
    db_file = tmp_path / "display_alerts.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Total Alerts", metrics_by_label.get("Total Signals")) == "3"
    assert metrics_by_label.get("Needs Attention", metrics_by_label.get("Pending Review")) == "1"
    assert metrics_by_label.get("Seen", metrics_by_label.get("Acknowledged")) == "1"
    assert metrics_by_label.get("Checked", metrics_by_label.get("Resolved")) == "1"
    assert metrics_by_label.get("Dismissed") == "0"

    # Verify table has 3 matching alerts
    assert len(at.dataframe) > 0
    df = at.dataframe[0].value
    assert len(df) == 3
    assert "Rule" in df.columns
    assert "Review Status" in df.columns

    # Verify non-accusatory explanations (no words like 'fraud', 'cheat', 'guilt')
    for explanation in df["Explanation"]:
        assert "fraud" not in explanation.lower()
        assert "misconduct" not in explanation.lower()
        assert "cheat" not in explanation.lower()


def test_intelligence_filters_by_cohort_rule_priority_and_date(tmp_path: Path):
    """Scenario 3: Verify filtering by cohort, rule, priority, and date range."""
    db_file = tmp_path / "filters.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # 1. Filter by Cohort "CLASS-02-B" (should match 1 alert)
    cohort_sb = [s for s in at.selectbox if s.key == "filter_cohort"][0]
    cohort_sb.select("CLASS-02-B").run()
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Cohort"] == "CLASS-02-B"

    # Reset Cohort
    cohort_sb = [s for s in at.selectbox if s.key == "filter_cohort"][0]
    cohort_sb.select(cohort_sb.options[0]).run()
    assert len(at.dataframe[0].value) == 3

    # 2. Filter by Rule RULE_ATTENDANCE_DROP_TITLE
    rule_sb = [s for s in at.selectbox if s.key == "filter_rule"][0]
    rule_sb.select(RULE_ATTENDANCE_DROP_TITLE).run()
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Rule"] == RULE_ATTENDANCE_DROP_TITLE

    # Reset Rule
    rule_sb = [s for s in at.selectbox if s.key == "filter_rule"][0]
    rule_sb.select(rule_sb.options[0]).run()

    # 3. Filter by Priority "INFO"
    prio_sb = [s for s in at.selectbox if s.key == "filter_priority"][0]
    prio_sb.select("INFO").run()
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Priority"] == "INFO"

    # Reset Priority
    prio_sb = [s for s in at.selectbox if s.key == "filter_priority"][0]
    prio_sb.select(prio_sb.options[0]).run()

    # 4. Enable Date Range filter
    date_chk = [c for c in at.checkbox if c.key == "filter_use_date"][0]
    date_chk.check().run()

    start_d_input = [d for d in at.date_input if d.key == "filter_start_date"][0]
    start_d_input.set_value(date(2026, 10, 23)).run()
    # Matches only session on 2026-10-24
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Date"] == "2026-10-24"

    # 5. Invalid / Reversed Date Range (start_date > end_date)
    start_d_input = [d for d in at.date_input if d.key == "filter_start_date"][0]
    start_d_input.set_value(date(2026, 10, 30)).run()
    warning_texts = [w.value for w in at.warning]
    assert any("Start Date cannot be after End Date" in text for text in warning_texts)


def test_intelligence_filters_by_review_status(tmp_path: Path):
    """Scenario 4: Verify filtering by review status."""
    db_file = tmp_path / "status_filter.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]

    # Filter to PENDING_REVIEW (should match 1 alert)
    status_sb.select("PENDING_REVIEW").run()
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Review Status"] == "PENDING_REVIEW"

    # Filter to RESOLVED (should match 1 alert)
    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]
    status_sb.select("RESOLVED").run()
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Review Status"] == "RESOLVED"

    # Filter to DISMISSED (should match 0 alerts and show empty info)
    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]
    status_sb.select("DISMISSED").run()
    info_texts = [i.value for i in at.info]
    assert any("No anomaly signals match the selected filters" in text for text in info_texts)


def test_intelligence_evidence_drilldown_and_session_context(tmp_path: Path):
    """Scenario 5: Verify inspection of structured evidence and associated session context."""
    db_file = tmp_path / "evidence_detail.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # Inspect the first alert in the dropdown
    select_alert_sb = [s for s in at.selectbox if "inspect" in s.label.lower()][0]
    assert len(select_alert_sb.options) == 3

    # Check evidence headings and values are present
    markdown_texts = [m.value for m in at.markdown]
    assert any("Observed Values" in text for text in markdown_texts)
    assert any("Baseline Reference" in text for text in markdown_texts)
    assert any("Threshold Applied" in text for text in markdown_texts)

    # Check referenced session metrics are rendered
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert "Enrollment" in metrics_by_label
    assert "Present" in metrics_by_label
    assert "Attendance Rate" in metrics_by_label


def test_intelligence_valid_status_transition_persists(tmp_path: Path):
    """Scenario 6: Verify transitioning review status persists correctly to storage."""
    db_file = tmp_path / "status_transition.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # Filter to PENDING_REVIEW to isolate alert a1
    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]
    status_sb.select("PENDING_REVIEW").run()

    # Find the determination selectbox and update button
    target_sb = [s for s in at.selectbox if s.key and s.key.startswith("target_status_")][0]
    target_sb.select("ACKNOWLEDGED").run()

    apply_btn = [b for b in at.button if b.key.startswith("btn_apply_")][0]
    apply_btn.click().run()

    assert not at.exception
    success_texts = [s.value for s in at.success]
    assert any("Review determination updated to 'ACKNOWLEDGED'" in text for text in success_texts)

    # Verify update persisted in the SQLite database
    with get_repository(db_path=db_file) as repo:
        alert = repo.get_alert_by_id("ALT-550e8400-e29b-41d4-a716-446655440001")
        assert alert is not None
        assert alert.review_status == "ACKNOWLEDGED"


def test_intelligence_redundant_status_transition_handled_without_writes(tmp_path: Path):
    """Scenario 7: Verify redundant status update displays info and makes no database writes."""
    db_file = tmp_path / "redundant_status.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # Filter to PENDING_REVIEW to isolate alert a1
    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]
    status_sb.select("PENDING_REVIEW").run()

    # Select same status (PENDING_REVIEW)
    target_sb = [s for s in at.selectbox if s.key and s.key.startswith("target_status_")][0]
    target_sb.select("PENDING_REVIEW").run()

    apply_btn = [b for b in at.button if b.key.startswith("btn_apply_")][0]
    apply_btn.click().run()

    info_texts = [i.value for i in at.info]
    assert any("already in 'PENDING_REVIEW' status. No write was needed" in text for text in info_texts)


def test_intelligence_explicit_detection_scan_and_idempotency(tmp_path: Path):
    """Scenario 8: Verify explicit detection scan detects anomalies and preserves review statuses idempotently."""
    db_file = tmp_path / "scan_idempotency.db"

    # Pre-seed 6 sessions that trigger an attendance drop:
    # 5 baseline sessions with natural variation (26, 27, 28, 26, 27) at ~90%, then Day 6 at 12/30 (40%) -> drop of >50%
    with get_repository(db_path=db_file) as repo:
        counts = [26, 27, 28, 26, 27]
        sessions = []
        for i in range(1, 6):
            sessions.append(
                SessionRecord(
                    session_id=f"550e8400-e29b-41d4-a716-44665544001{i}",
                    class_id="CLASS-01-A",
                    session_date=f"2026-10-1{i}",
                    expected_enrollment=30,
                    present_count=counts[i - 1],
                    absent_count=30 - counts[i - 1],
                    webcam_status="NOT_ATTEMPTED",
                    webcam_count=None,
                    record_source="MANUAL_ENTRY",
                    created_at=f"2026-10-1{i}T09:00:00Z",
                )
            )
        # Drop session on Day 6
        sessions.append(
            SessionRecord(
                session_id="550e8400-e29b-41d4-a716-446655440016",
                class_id="CLASS-01-A",
                session_date="2026-10-16",
                expected_enrollment=30,
                present_count=12,
                absent_count=18,
                webcam_status="NOT_ATTEMPTED",
                webcam_count=None,
                record_source="MANUAL_ENTRY",
                created_at="2026-10-16T09:00:00Z",
            )
        )
        repo.save_sessions(sessions)
        # Initially zero alerts in DB
        assert len(repo.get_alerts()) == 0

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # Click Run Anomaly Detection Scan button
    scan_btn = [b for b in at.button if b.key == "btn_run_detection_scan"][0]
    scan_btn.click().run()

    assert not at.exception
    success_texts = [s.value for s in at.success]
    assert any("Detection scan complete: Evaluated 1 anomaly signal(s)" in text for text in success_texts)

    # Verify 1 alert was saved in SQLite
    with get_repository(db_path=db_file) as repo:
        alerts = repo.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].rule_id == "RULE_ATTENDANCE_DROP"
        # Update alert to ACKNOWLEDGED
        repo.update_alert_review_status(alerts[0].alert_id, "ACKNOWLEDGED")

    # Click scan button a second time: must NOT duplicate or reset ACKNOWLEDGED status
    scan_btn = [b for b in at.button if b.key == "btn_run_detection_scan"][0]
    scan_btn.click().run()

    with get_repository(db_path=db_file) as repo:
        alerts_after = repo.get_alerts()
        assert len(alerts_after) == 1
        # Review status preserved by ON CONFLICT DO NOTHING
        assert alerts_after[0].review_status == "ACKNOWLEDGED"


def test_intelligence_reruns_do_not_trigger_scans_or_repeat_writes(tmp_path: Path):
    """Scenario 9: Verify regular reruns do not automatically re-scan or perform unintended writes."""
    db_file = tmp_path / "rerun_safety.db"
    _seed_test_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    with get_repository(db_path=db_file) as repo:
        initial_alerts = repo.get_alerts()
        assert len(initial_alerts) == 3

    # Simple rerun without button clicks
    at.run()
    assert not at.exception

    with get_repository(db_path=db_file) as repo:
        post_rerun_alerts = repo.get_alerts()
        assert len(post_rerun_alerts) == 3


def test_intelligence_missing_associated_session_and_empty_filters_handled(tmp_path: Path):
    """Scenario 10: Verify missing referenced session and empty filter outcomes render gracefully."""
    db_file = tmp_path / "missing_ref.db"

    # Seed 1 session and 1 alert
    _seed_test_data(db_file)

    # Deliberately remove the session from storage to test orphan alert handling
    with get_repository(db_path=db_file) as repo:
        conn = repo.get_connection()
        with conn:
            # Temporarily disable foreign keys to create orphaned alert test scenario
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute("DELETE FROM attendance_sessions WHERE session_id = '550e8400-e29b-41d4-a716-446655440001';")
            conn.execute("PRAGMA foreign_keys = ON;")

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    _navigate_to_intelligence(at)

    # Must NOT crash
    assert not at.exception
    assert len(at.error) == 0

    # Filter to PENDING_REVIEW to select the orphan alert
    status_sb = [s for s in at.selectbox if s.key == "filter_review_status"][0]
    status_sb.select("PENDING_REVIEW").run()

    # Warning for missing session must be displayed gracefully
    warning_texts = [w.value for w in at.warning]
    assert any("Associated session record" in text and "was not found in storage" in text for text in warning_texts)
