"""Headless automated UI integration tests for AttendSure Algorithm Laboratory.

Tests Milestone M5.3.3.2 requirements using Streamlit's native headless AppTest framework:
1. Initial render without exceptions and clean empty state guidance.
2. Attendance-drop scenario generation, detection, and evidence breakdown.
3. Repeated-headcount scenario generation and sequential evidence explanation.
4. Webcam discrepancy simulation and database storage isolation.
5. Benchmark metric computation using the actual evaluation engine.
6. Confusion matrix display and formatting.
7. Per-rule metric availability and rendering.
8. Zero-denominator and missing-label safety.
9. Synthetic-data and academic evaluation disclaimers.
10. Ordinary reruns do not regenerate experiments or write to the database.
"""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.data.storage import AttendanceRepository
from attendsure.detection.rules import RULE_ATTENDANCE_DROP_TITLE
from attendsure.ui.state import get_repository

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def _navigate_to_laboratory(at: AppTest) -> None:
    """Helper to navigate the sidebar radio to Reports and run."""
    at.session_state["developer_mode"] = True
    at.session_state["dev_mode_enabled"] = True
    try:
        at.sidebar.radio[0].set_value("Reports").run()
    except Exception:
        try:
            at.sidebar.radio[0].set_value("Test & Learn").run()
        except Exception:
            at.sidebar.radio[0].set_value("Algorithm Laboratory").run()


def test_laboratory_initial_render_without_exceptions(tmp_path: Path):
    """Scenario 1: Verify Algorithm Laboratory renders cleanly on initial load."""
    db_file = tmp_path / "lab_initial.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    assert not at.exception
    assert len(at.error) == 0

    # Header and subheaders
    assert at.header[0].value in ("Reports", "Test & Learn", "Algorithm Laboratory")

    # Academic disclaimer is prominently rendered
    markdown_texts = [m.value for m in at.markdown]
    assert any("This section uses sample attendance records" in text or "Academic Research & Synthetic Evaluation Notice" in text for text in markdown_texts)
    assert any("Your saved attendance records will not be changed" in text or "never persisted to the active school attendance database" in text for text in markdown_texts)

    # Initial guidance info messages are displayed
    info_texts = [i.value for i in at.info]
    assert any("Select a scenario above and click" in text for text in info_texts)

    # Verify SQLite database has 0 sessions and 0 alerts
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_attendance_drop_scenario(tmp_path: Path):
    """Scenario 2: Verify attendance-drop scenario generation, detection, and evidence drilldown."""
    db_file = tmp_path / "lab_drop.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Select Attendance Drop scenario
    scenario_sb = [s for s in at.selectbox if s.key == "lab_scenario_choice"][0]
    scenario_sb.select("Unusual Attendance Drop (RULE_ATTENDANCE_DROP)").run()

    # Click Generate Scenario & Run Detectors
    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0

    # Timeline dataframe rendered
    assert len(at.dataframe) > 0
    df = at.dataframe[0].value
    assert len(df) == 15
    assert "Rate" in df.columns
    assert "Ground Truth Label" in df.columns
    assert "Detector Output" in df.columns

    # Verify drop alert is present in detected signals
    markdown_texts = [m.value for m in at.markdown]
    assert any(RULE_ATTENDANCE_DROP_TITLE in text for text in markdown_texts)
    assert any("Observed Values" in text for text in markdown_texts)
    assert any("Baseline Reference" in text for text in markdown_texts)
    assert any("Threshold Applied" in text for text in markdown_texts)

    # Verify database remains completely untouched (zero writes)
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_repeated_headcount_scenario_and_sequential_explanation(tmp_path: Path):
    """Scenario 3: Verify repeated-headcount scenario generation and sequential accumulation note."""
    db_file = tmp_path / "lab_repeat.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Select Repeated Headcount scenario
    scenario_sb = [s for s in at.selectbox if s.key == "lab_scenario_choice"][0]
    scenario_sb.select("Repeated Identical Headcounts (RULE_REPEATED_HEADCOUNT)").run()

    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    assert not at.exception

    # Verify Repeated Headcount alert is displayed
    markdown_texts = [m.value for m in at.markdown]
    assert any("Repeated Identical Headcounts" in text for text in markdown_texts)

    # Verify sequential evidence explanation note is displayed
    info_texts = [i.value for i in at.info]
    assert any("Sequential Evidence Accumulation Note" in text for text in info_texts)
    assert any("threshold (K ≥ 4)" in text for text in info_texts)

    # Storage isolation check
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_webcam_discrepancy_scenario_and_storage_isolation(tmp_path: Path):
    """Scenario 4: Verify webcam discrepancy simulation and database storage isolation."""
    db_file = tmp_path / "lab_webcam.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    scenario_sb = [s for s in at.selectbox if s.key == "lab_scenario_choice"][0]
    scenario_sb.select("Visible-Person Discrepancy (RULE_WEBCAM_DISCREPANCY)").run()

    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    assert not at.exception

    # Check alert and camera explanation
    markdown_texts = [m.value for m in at.markdown]
    assert any("Visible-Person Discrepancy" in text for text in markdown_texts)

    info_texts = [i.value for i in at.info]
    assert any("Camera Discrepancy Verification Note" in text for text in info_texts)

    # Strict storage isolation check
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_benchmark_metric_computation(tmp_path: Path):
    """Scenario 5: Verify benchmark metric computation across multi-class synthetic dataset."""
    db_file = tmp_path / "lab_benchmark.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Select Small Preset (3 classes, 15 days = 45 sessions)
    preset_sb = [s for s in at.selectbox if s.key == "lab_benchmark_preset"][0]
    preset_sb.select("Small Preset (3 Classes, 15 Days, 5% Anomalies)").run()

    # Click Run Benchmark Evaluation
    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0

    metrics_by_label = {m.label: m.value for m in at.metric}
    assert "Evaluated Sessions" in metrics_by_label
    assert metrics_by_label["Evaluated Sessions"] == "45"
    assert "Precision" in metrics_by_label
    assert "Recall" in metrics_by_label
    assert "F1-Score" in metrics_by_label

    # Storage isolation check
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_confusion_matrix_display(tmp_path: Path):
    """Scenario 6: Verify confusion matrix 2x2 presentation format."""
    db_file = tmp_path / "lab_cm.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    assert not at.exception

    # Locate the confusion matrix dataframe
    # The confusion matrix has columns 'Actual Positive' and 'Actual Negative'
    cm_dfs = [df.value for df in at.dataframe if "Actual Positive" in df.value.columns]
    assert len(cm_dfs) == 1
    cm = cm_dfs[0]
    assert "Actual Positive" in cm.columns
    assert "Actual Negative" in cm.columns
    assert "Pred Positive" in cm.index
    assert "Pred Negative" in cm.index


def test_laboratory_per_rule_metric_breakdown(tmp_path: Path):
    """Scenario 7: Verify per-rule evaluation breakdown availability and rendering."""
    db_file = tmp_path / "lab_rules.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    assert not at.exception

    # Find the per-rule table
    rule_dfs = [df.value for df in at.dataframe if "Rule ID" in df.value.columns]
    assert len(rule_dfs) == 1
    rdf = rule_dfs[0]
    rule_ids = set(rdf["Rule ID"].tolist())
    assert "RULE_ATTENDANCE_DROP" in rule_ids
    assert "RULE_REPEATED_HEADCOUNT" in rule_ids
    assert "RULE_WEBCAM_DISCREPANCY" in rule_ids

    # Sequential evidence note for repeated headcount
    caption_texts = [c.value for c in at.caption]
    assert any("RULE_REPEATED_HEADCOUNT Session Recall" in text for text in caption_texts)


def test_laboratory_zero_denominator_safety(tmp_path: Path):
    """Scenario 8: Verify zero-denominator handling when anomaly rate is 0.0%."""
    db_file = tmp_path / "lab_zd.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Set Custom Configuration with 0.0% anomaly rate
    preset_sb = [s for s in at.selectbox if s.key == "lab_benchmark_preset"][0]
    preset_sb.select("Custom Configuration").run()

    rate_input = [n for n in at.number_input if n.key == "lab_bench_rate"][0]
    rate_input.set_value(0.0).run()

    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    assert not at.exception
    assert len(at.error) == 0

    # Scores should safely default to 0.0% without crashing
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert metrics_by_label["Precision"] == "0.0%"
    assert metrics_by_label["Recall"] == "0.0%"

    # Zero-denominator policy callout is rendered
    info_texts = [i.value for i in at.info]
    assert any("Zero-Denominator Policy Applied" in text for text in info_texts)


def test_laboratory_academic_disclaimers_rendered(tmp_path: Path):
    """Scenario 9: Verify academic evaluation and synthetic data disclaimers."""
    db_file = tmp_path / "lab_disclaimers.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Top notice
    markdown_texts = [m.value for m in at.markdown]
    assert any("This section uses sample attendance records" in text or "Academic Research & Synthetic Evaluation Notice" in text for text in markdown_texts)

    # Run benchmark to verify bottom disclaimers
    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    markdown_texts_after = [m.value for m in at.markdown]
    assert any("Camera Metric Isolation" in text for text in markdown_texts_after)

    caption_texts = [c.value for c in at.caption]
    assert any("Academic Generalization Disclaimer" in text for text in caption_texts)


def test_laboratory_reruns_do_not_regenerate_or_write_db(tmp_path: Path):
    """Scenario 10: Verify ordinary reruns do not re-execute experiments or write to database."""
    db_file = tmp_path / "lab_rerun.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    # Run scenario
    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    assert "lab_scenario_data" in at.session_state
    first_df = at.session_state["lab_scenario_data"]["df"]

    # Re-run without button click
    at.run()
    assert not at.exception
    assert "lab_scenario_data" in at.session_state
    second_df = at.session_state["lab_scenario_data"]["df"]

    # Preserved identical in-memory dataframe
    assert first_df.equals(second_df)

    # Database remains pristine
    with get_repository(db_path=db_file) as repo:
        assert len(repo.get_sessions()) == 0
        assert len(repo.get_alerts()) == 0


def test_laboratory_benchmark_camera_metrics_displayed(tmp_path: Path):
    """Scenario 11: Verify simulated camera estimation metrics (MAE/MAPE) render in benchmark view."""
    db_file = tmp_path / "lab_cam_bench.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    preset_sb = [s for s in at.selectbox if s.key == "lab_benchmark_preset"][0]
    preset_sb.select("Small Preset (3 Classes, 15 Days, 5% Anomalies)").run()

    bench_btn = [b for b in at.button if b.key == "btn_run_benchmark"][0]
    bench_btn.click().run()

    assert not at.exception
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert "Evaluated Camera Pairs" in metrics_by_label
    assert "Mean Absolute Error (MAE)" in metrics_by_label
    assert "MAPE (Non-Zero Actuals)" in metrics_by_label
    assert "Zero-Actual Excluded" in metrics_by_label


def test_laboratory_scenario_sequence_event_metrics_displayed(tmp_path: Path):
    """Scenario 12: Verify sequence event detection metrics render in Scenario Inspector for repeated headcount."""
    db_file = tmp_path / "lab_seq_scenario.db"
    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    _navigate_to_laboratory(at)

    scenario_sb = [s for s in at.selectbox if s.key == "lab_scenario_choice"][0]
    scenario_sb.select("Repeated Identical Headcounts (RULE_REPEATED_HEADCOUNT)").run()

    gen_btn = [b for b in at.button if b.key == "btn_run_scenario"][0]
    gen_btn.click().run()

    assert not at.exception
    metrics_by_label = {m.label: m.value for m in at.metric}
    assert "Anomaly Events" in metrics_by_label
    assert metrics_by_label["Anomaly Events"] == "1"
    assert "Event Detected" in metrics_by_label
    assert metrics_by_label["Event Detected"] == "YES"
    assert "Event Recall" in metrics_by_label
    assert metrics_by_label["Event Recall"] == "100.0%"
    assert "Session Recall" in metrics_by_label
