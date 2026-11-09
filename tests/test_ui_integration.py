"""Comprehensive multi-screen integration tests for AttendSure UI.

Tests end-to-end workflows across all six screens:
1. Full manual roll-call lifecycle: Register -> Overview -> Settings.
2. Batch CSV import lifecycle: Reports -> Register History -> Export -> Settings Provenance.
3. Anomaly detection & review triage lifecycle: Register Drop -> Intelligence Triage -> Overview Metrics -> Reports Export.
4. Laboratory testbench strict storage isolation from operational database.
5. Consistent runtime database configuration across all six screens.
"""

from datetime import datetime
import io
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")

PAGE_MAP = {
    "Overview Dashboard": "Home",
    "Dashboard": "Home",
    "Home": "Home",
    "Attendance Register": "Mark Attendance",
    "Attendance": "Mark Attendance",
    "Mark Attendance": "Mark Attendance",
    "Attendance Records": "Attendance Records",
    "Intelligence Centre": "Needs Attention",
    "Alerts": "Needs Attention",
    "Needs Attention": "Needs Attention",
    "Algorithm Laboratory": "Reports",
    "Test & Learn": "Reports",
    "Reports & Export": "Reports",
    "Reports": "Reports",
    "Data & Settings": "Settings",
    "Settings": "Settings",
}


def _nav(at: AppTest, target: str) -> None:
    """Navigate sidebar radio with fallback between legacy and simplified names."""
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    try:
        at.sidebar.radio[0].set_value(target).run()
    except Exception:
        alt_target = PAGE_MAP.get(target, target)
        at.sidebar.radio[0].set_value(alt_target).run()


def test_e2e_manual_rollcall_across_screens(tmp_path: Path):
    """Workflow 1: Record roll-call in Register, verify reflected in Overview and Settings."""
    db_file = tmp_path / "e2e_manual.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    # 1. Attendance Register: record manual roll-call
    _nav(at, "Mark Attendance")
    assert at.header[0].value in ("Mark Attendance", "Attendance", "Attendance Register")

    class_input = [t for t in at.text_input if t.key == "manual_class_id"][0]
    class_input.set_value("CLASS-05-A").run()

    enrollment_input = [n for n in at.number_input if n.key == "manual_expected_enrollment"][0]
    enrollment_input.set_value(30).run()

    present_input = [n for n in at.number_input if n.key == "manual_present_count"][0]
    present_input.set_value(27).run()

    submit_btn = [b for b in at.button if b.key == "btn_save_roll_call"][0]
    submit_btn.click().run()

    # Success recorded
    assert any("Attendance session recorded successfully" in s.value for s in at.success)

    # 2. Overview Dashboard: verify metrics updated
    _nav(at, "Dashboard")
    assert at.header[0].value in ("Home", "Dashboard", "Overview Dashboard")
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label.get("Attendance Records", metrics_by_label.get("Total Sessions")) == "1"
    assert metrics_by_label.get("Classes", metrics_by_label.get("Monitored Cohorts")) == "1"
    assert metrics_by_label.get("Attendance Rate", metrics_by_label.get("Overall Attendance")) == "90.0%"

    # 3. Data & Settings: verify provenance and counts
    _nav(at, "Settings")
    assert at.header[0].value in ("Settings", "Data & Settings")
    settings_metrics = {m.label: m.value for m in at.metric}
    assert settings_metrics.get("Attendance Records", settings_metrics.get("Total Sessions")) == "1"
    assert settings_metrics.get("Entered by Hand", settings_metrics.get("Manual Roll-Call Entries")) == "1"
    assert settings_metrics.get("Uploaded from File", settings_metrics.get("Batch CSV Imports")) == "0"


def test_e2e_csv_import_and_export_lifecycle(tmp_path: Path):
    """Workflow 2: Import CSV in Reports, verify in Register History, and export in Reports."""
    db_file = tmp_path / "e2e_csv.db"
    csv_data = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,29,1
"""
    uploaded_file = io.StringIO(csv_data)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["test_uploaded_file"] = uploaded_file
    at.run()

    # 1. Reports & Export: Preview and Commit CSV
    _nav(at, "Reports")
    btn_prev = [b for b in at.button if b.key == "btn_preview_csv"][0]
    btn_prev.click().run()

    btn_commit = [b for b in at.button if b.key == "btn_commit_csv"][0]
    btn_commit.click().run()

    assert any("Import Successful" in s.value for s in at.success)

    # 2. Attendance Register: check Historical Register
    _nav(at, "Attendance")
    # Historical register dataframe should have 2 sessions
    hist_dfs = [df.value for df in at.dataframe if any(c in df.value.columns for c in ("Attendance Rate", "Rate", "Attendance"))]
    assert len(hist_dfs) > 0
    assert len(hist_dfs[0]) == 2

    # 3. Reports & Export: Export sessions should match 2 sessions
    _nav(at, "Reports")
    rep_metrics = {m.label: m.value for m in at.metric}
    assert rep_metrics["Matching Sessions"] == "2"

    # 4. Data & Settings: Record provenance should show 2 CSV imports
    _nav(at, "Settings")
    set_metrics = {m.label: m.value for m in at.metric}
    assert set_metrics.get("Attendance Records", set_metrics.get("Total Sessions")) == "2"
    assert set_metrics.get("Uploaded from File", set_metrics.get("Batch CSV Imports")) == "2"
    assert set_metrics.get("Entered by Hand", set_metrics.get("Manual Roll-Call Entries")) == "0"


def test_e2e_anomaly_detection_triage_and_audit(tmp_path: Path):
    """Workflow 3: Baseline + Drop session triggers alert, triage in Intelligence, export audit."""
    db_file = tmp_path / "e2e_triage.db"
    repository = AttendanceRepository(db_path=db_file)

    # Pre-populate 5 nominal baseline sessions for CLASS-01-A
    for day in range(1, 6):
        repository.save_session(
            SessionRecord(
                session_id=f"00000000-0000-4000-8000-00000000000{day}",
                class_id="CLASS-01-A",
                session_date=f"2026-10-1{day}",
                expected_enrollment=30,
                present_count=28,
                absent_count=2,
                webcam_status="NOT_ATTEMPTED",
                webcam_count=None,
                record_source="MANUAL_ENTRY",
                created_at=f"2026-10-1{day}T09:00:00Z",
            )
        )
    repository.close()

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    # 1. Register: record steep attendance drop on day 6
    _nav(at, "Attendance")
    class_input = [t for t in at.text_input if t.key == "manual_class_id"][0]
    class_input.set_value("CLASS-01-A").run()

    enrollment_input = [n for n in at.number_input if n.key == "manual_expected_enrollment"][0]
    enrollment_input.set_value(30).run()

    present_input = [n for n in at.number_input if n.key == "manual_present_count"][0]
    present_input.set_value(10).run()  # Steep drop (10 vs rolling median 28 -> >60% drop)

    submit_btn = [b for b in at.button if b.key == "btn_save_roll_call"][0]
    submit_btn.click().run()

    # 2. Intelligence Centre: verify alert is present and pending review
    _nav(at, "Alerts")
    intel_metrics = {m.label: m.value for m in at.metric}
    assert int(intel_metrics.get("Needs Attention", intel_metrics.get("Pending Review"))) >= 1

    # Update review status to ACKNOWLEDGED
    status_sb = [s for s in at.selectbox if s.key and s.key.startswith("target_status_")][0]
    status_sb.select("ACKNOWLEDGED").run()

    btn_update = [b for b in at.button if b.key and b.key.startswith("btn_apply_")][0]
    btn_update.click().run()

    assert any("Review determination updated to 'ACKNOWLEDGED'" in s.value for s in at.success)

    # 3. Overview Dashboard: verify alert is tracked in triage
    _nav(at, "Dashboard")
    overview_metrics = {m.label: m.value for m in at.metric}
    assert int(overview_metrics.get("Alerts", overview_metrics.get("Total Signals"))) >= 1

    # 4. Reports & Export: filter alerts by ACKNOWLEDGED status
    _nav(at, "Reports")
    alert_status_sb = [s for s in at.selectbox if s.key == "export_alerts_status_filter"][0]
    alert_status_sb.select("ACKNOWLEDGED").run()

    export_metrics = {m.label: m.value for m in at.metric}
    assert int(export_metrics["Matching Alerts"]) >= 1


def test_e2e_laboratory_isolation_from_operational_database(tmp_path: Path):
    """Workflow 4: Running scenarios and benchmarks in Laboratory never contaminates SQLite."""
    db_file = tmp_path / "e2e_lab_isolation.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    # 1. Run scenario in Laboratory
    _nav(at, "Test & Learn")
    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    # 2. Run benchmark evaluation in Laboratory
    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    # 3. Navigate through all other operational views
    for page in ["Dashboard", "Attendance", "Alerts", "Reports", "Settings"]:
        _nav(at, page)
        assert not at.exception
        assert len(at.error) == 0

    # 4. Strict SQLite verification: zero sessions or alerts persisted
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_e2e_all_six_views_accessible_and_consistent_db(tmp_path: Path):
    """Workflow 5: Seamless sequential navigation through all 6 screens with shared DB."""
    db_file = tmp_path / "e2e_nav.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    screen_sequence = [
        "Overview Dashboard",
        "Attendance Register",
        "Intelligence Centre",
        "Algorithm Laboratory",
        "Reports & Export",
        "Data & Settings",
    ]

    for screen in screen_sequence:
        _nav(at, screen)
        assert not at.exception
        assert len(at.error) == 0
        assert at.header[0].value in (screen, PAGE_MAP.get(screen))

    # Database remains pristine
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0
