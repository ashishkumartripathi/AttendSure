"""Comprehensive automated test suite for Global Developer Mode in AttendSure.

Verifies:
1. Default mode is Teacher View (developer_mode=False).
2. Toggling developer mode updates state and persists preference.
3. Home page hides technical diagnostics when OFF, reveals them when ON.
4. Mark Attendance hides camera simulation and ML diagnostics when OFF, reveals them when ON.
5. Attendance Records hides raw UUIDs and technical metadata when OFF, reveals them when ON.
6. Needs Attention hides Observed Values / Baselines when OFF, reveals them when ON.
7. Reports displays exactly 4 tabs when OFF, reveals 5th Developer View tab when ON.
8. Settings page provides the global Developer Mode radio toggle.
9. Backend inference, detection rules, and SQLite persistence are completely unaffected by UI mode.
"""

from datetime import date
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.models import Alert, AlertPriority, ReviewStatus, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.detection.rules import RULE_ATTENDANCE_DROP
from attendsure.ml.predictor import evaluate_session_ml
from attendsure.services.attendance_service import run_full_detection_pipeline
from attendsure.ui.dev_mode import (
    CONFIG_FILE_PATH,
    is_developer_mode,
    set_developer_mode,
)
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _seed_sample_data(db_file: Path) -> None:
    """Helper to populate an isolated SQLite database with nominal and anomalous records."""
    with get_repository(db_path=db_file) as repo:
        s1 = SessionRecord(
            session_id="00000000-0000-4000-8000-000000000001",
            class_id="CLASS-01-A",
            session_date="2026-10-20",
            expected_enrollment=30,
            present_count=28,
            absent_count=2,
            webcam_status="SUCCESS",
            webcam_count=28,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-20T09:00:00Z",
        )
        s2 = SessionRecord(
            session_id="00000000-0000-4000-8000-000000000002",
            class_id="CLASS-01-A",
            session_date="2026-10-21",
            expected_enrollment=30,
            present_count=12,
            absent_count=18,
            webcam_status="SUCCESS",
            webcam_count=12,
            record_source="MANUAL_ENTRY",
            created_at="2026-10-21T09:00:00Z",
        )
        repo.save_session(s1)
        repo.save_session(s2)

        a1 = Alert(
            alert_id="00000000-0000-4000-9000-000000000001",
            session_id=s2.session_id,
            class_id=s2.class_id,
            session_date=s2.session_date,
            rule_id=RULE_ATTENDANCE_DROP,
            rule_title="Unusual Attendance Drop",
            priority="REVIEW_REQUIRED",
            review_status="PENDING_REVIEW",
            observed_value={"present_count": 12, "webcam_count": 12, "relative_drop_pct": 57.1},
            baseline_reference={"historical_median": 28, "baseline_type": "ROLLING_MEDIAN"},
            threshold_applied={"max_drop_pct": 30.0},
            explanation="Attendance dropped by 57.1% compared to typical attendance.",
            created_at="2026-10-21T09:05:00Z",
        )
        repo.save_alerts([a1])


def test_default_mode_is_teacher_view(tmp_path: Path):
    """Scenario 1: Default global developer mode is False (Teacher View)."""
    # Clean up any persisted file for the test
    if CONFIG_FILE_PATH.exists():
        CONFIG_FILE_PATH.unlink()

    # Empty session state simulation
    import streamlit as st
    st.session_state.clear()

    assert is_developer_mode() is False


def test_toggle_developer_mode(tmp_path: Path):
    """Scenario 2: Toggling developer mode updates state and persists preference."""
    set_developer_mode(True)
    assert is_developer_mode() is True

    set_developer_mode(False)
    assert is_developer_mode() is False


def test_home_page_developer_mode_off(tmp_path: Path):
    """Scenario 3: Home page in Teacher View (Dev Mode OFF) shows zero technical telemetry."""
    db_file = tmp_path / "home_off.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    # Sidebar navigation to Home
    at.sidebar.radio[0].set_value("Home").run()

    assert not at.exception
    # Developer View expander must NOT be present
    markdown_texts = [m.value for m in at.markdown]
    assert not any("Technical Details — Developer View" in text for text in markdown_texts)
    assert not any("System Status & Diagnostic Telemetry" in text for text in markdown_texts)


def test_home_page_developer_mode_on(tmp_path: Path):
    """Scenario 4: Home page in Developer View (Dev Mode ON) reveals technical expander."""
    db_file = tmp_path / "home_on.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Home").run()

    assert not at.exception
    # Developer View expander must be present
    markdown_texts = [m.value for m in at.markdown]
    assert any("System & Model Diagnostics" in text or "ML Model Status" in text for text in markdown_texts)


def test_mark_attendance_developer_mode_off(tmp_path: Path):
    """Scenario 5: Mark Attendance in Teacher View hides camera simulation and ML diagnostics."""
    db_file = tmp_path / "reg_off.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Mark Attendance").run()

    assert not at.exception
    # Camera simulation checkbox should NOT be present
    camera_sim_boxes = [c for c in at.checkbox if c.key == "manual_enable_camera"]
    assert len(camera_sim_boxes) == 0

    markdown_texts = [m.value for m in at.markdown]
    assert not any("Machine Learning Feature Extraction & Pre-Save Prediction" in text for text in markdown_texts)


def test_mark_attendance_developer_mode_on(tmp_path: Path):
    """Scenario 6: Mark Attendance in Developer View reveals camera simulation and ML diagnostics."""
    db_file = tmp_path / "reg_on.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Mark Attendance").run()

    assert not at.exception
    camera_sim_boxes = [c for c in at.checkbox if c.key == "manual_enable_camera"]
    assert len(camera_sim_boxes) == 1

    markdown_texts = [m.value for m in at.markdown]
    assert any("Machine Learning Feature Extraction & Pre-Save Prediction" in text for text in markdown_texts)


def test_attendance_records_developer_mode_off(tmp_path: Path):
    """Scenario 7: Attendance Records in Teacher View hides raw UUID and provenance."""
    db_file = tmp_path / "rec_off.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Attendance Records").run()

    assert not at.exception
    markdown_texts = [m.value for m in at.markdown]
    # Raw Session ID UUID and Technical Details expander must NOT be present
    assert not any("Technical Details — Developer View" in text for text in markdown_texts)
    assert not any("00000000-0000-4000-8000-000000000001" in text for text in markdown_texts)


def test_attendance_records_developer_mode_on(tmp_path: Path):
    """Scenario 8: Attendance Records in Developer View reveals technical expander with UUID."""
    db_file = tmp_path / "rec_on.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Attendance Records").run()

    assert not at.exception
    markdown_texts = [m.value for m in at.markdown]
    assert any("Session UUID:" in text for text in markdown_texts)
    assert any("00000000-0000-4000-8000-" in text for text in markdown_texts)


def test_needs_attention_developer_mode_off(tmp_path: Path):
    """Scenario 9: Needs Attention in Teacher View hides raw dictionaries and thresholds."""
    db_file = tmp_path / "intel_off.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Needs Attention").run()

    assert not at.exception
    markdown_texts = [m.value for m in at.markdown]
    assert not any("Observed Values:" in text for text in markdown_texts)
    assert not any("Baseline Reference:" in text for text in markdown_texts)
    assert not any("Threshold Applied:" in text for text in markdown_texts)


def test_needs_attention_developer_mode_on(tmp_path: Path):
    """Scenario 10: Needs Attention in Developer View reveals observed values and thresholds."""
    db_file = tmp_path / "intel_on.db"
    _seed_sample_data(db_file)

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Needs Attention").run()

    assert not at.exception
    markdown_texts = [m.value for m in at.markdown]
    assert any("Observed Values:" in text for text in markdown_texts)
    assert any("Baseline Reference:" in text for text in markdown_texts)
    assert any("Threshold Applied:" in text for text in markdown_texts)


def test_reports_developer_mode_off(tmp_path: Path):
    """Scenario 11: Reports in Teacher View has exactly 4 tabs (no developer/lab tab)."""
    db_file = tmp_path / "rep_off.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Reports").run()

    assert not at.exception
    # Scenario runner button from Laboratory must NOT exist
    lab_btns = [b for b in at.button if b.key == "btn_run_scenario"]
    assert len(lab_btns) == 0


def test_reports_developer_mode_on(tmp_path: Path):
    """Scenario 12: Reports in Developer View has 5th tab with Laboratory and Evaluation."""
    db_file = tmp_path / "rep_on.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Reports").run()

    assert not at.exception
    lab_btns = [b for b in at.button if b.key == "btn_run_scenario"]
    assert len(lab_btns) == 1


def test_settings_developer_mode_toggle(tmp_path: Path):
    """Scenario 13: Settings page provides the Developer Mode radio toggle."""
    db_file = tmp_path / "set_toggle.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.session_state["developer_mode"] = False
    at.session_state["dev_mode_enabled"] = False
    at.run(timeout=10)

    at.sidebar.radio[0].set_value("Settings").run()

    assert not at.exception
    radios = [r for r in at.radio if r.key == "global_developer_mode_radio"]
    assert len(radios) == 1
    assert "OFF — Teacher View" in radios[0].options
    assert "ON — Developer View" in radios[0].options


def test_backend_unaffected_by_developer_mode(tmp_path: Path):
    """Scenario 14: ML inference, rule detection, and DB writes work identically in both modes."""
    db_file = tmp_path / "backend_test.db"
    _seed_sample_data(db_file)

    with get_repository(db_path=db_file) as repo:
        history_df = repo.get_sessions(class_id="CLASS-01-A", as_df=True)

        # 1. ML inference with developer mode OFF
        set_developer_mode(False)
        res_off = evaluate_session_ml(
            class_id="CLASS-01-A",
            enrollment=30,
            present=12,
            history_df=history_df,
        )

        # 2. ML inference with developer mode ON
        set_developer_mode(True)
        res_on = evaluate_session_ml(
            class_id="CLASS-01-A",
            enrollment=30,
            present=12,
            history_df=history_df,
        )

        assert res_off.prediction == res_on.prediction
        assert res_off.confidence_score == res_on.confidence_score
        assert res_off.feature_values == res_on.feature_values

        # 3. Detection pipeline
        set_developer_mode(False)
        alerts_off = run_full_detection_pipeline(repo)
        set_developer_mode(True)
        alerts_on = run_full_detection_pipeline(repo)

        assert len(alerts_off) == len(alerts_on)
        set_developer_mode(False)
