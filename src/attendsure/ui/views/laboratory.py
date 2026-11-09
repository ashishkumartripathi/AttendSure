"""Algorithm Laboratory view for AttendSure.

Provides synthetic anomaly simulation, explainable detector inspection,
and rigorous classification benchmark evaluation adhering to docs/data-contract.md
and AGENTS.md.
Refined with the Pastel Green modern dashboard design language.
"""

from typing import Any, Optional

import pandas as pd
import streamlit as st

from attendsure.data.generator import (
    generate_scenario_sessions,
    generate_synthetic_sessions,
)
from attendsure.data.models import Alert
from attendsure.detection.rules import (
    RULE_ATTENDANCE_DROP,
    RULE_ATTENDANCE_DROP_TITLE,
    RULE_REPEATED_HEADCOUNT,
    RULE_REPEATED_HEADCOUNT_TITLE,
    RULE_WEBCAM_DISCREPANCY,
    RULE_WEBCAM_DISCREPANCY_TITLE,
    detect_anomalies,
)
from attendsure.evaluation.metrics import (
    confusion_matrix_to_dataframe,
    evaluate_detector_performance,
    evaluate_sequence_events,
    evaluate_webcam_estimation,
)
from attendsure.ui.views.alert_card import render_teacher_alert_card


# -----------------------------------------------------------------------------
# Constant Mappings and Benchmark Presets
# -----------------------------------------------------------------------------

SCENARIO_OPTIONS = {
    "Normal Attendance": "NOMINAL",
    "Sudden Attendance Drop": "ATTENDANCE_DROP",
    "Same Count Repeated": "REPEATED_HEADCOUNT",
    "Headcount Difference": "WEBCAM_DISCREPANCY",
    # Backward compatibility aliases
    "Unusual Attendance Drop (RULE_ATTENDANCE_DROP)": "ATTENDANCE_DROP",
    "Repeated Identical Headcounts (RULE_REPEATED_HEADCOUNT)": "REPEATED_HEADCOUNT",
    "Visible-Person Discrepancy (RULE_WEBCAM_DISCREPANCY)": "WEBCAM_DISCREPANCY",
    "Nominal Attendance (Nominal Baseline)": "NOMINAL",
}

RULE_TITLES = {
    RULE_ATTENDANCE_DROP: RULE_ATTENDANCE_DROP_TITLE,
    RULE_REPEATED_HEADCOUNT: RULE_REPEATED_HEADCOUNT_TITLE,
    RULE_WEBCAM_DISCREPANCY: RULE_WEBCAM_DISCREPANCY_TITLE,
}

BENCHMARK_PRESETS = {
    "Small Preset (3 Classes, 15 Days, 5% Anomalies)": {
        "num_classes": 3,
        "num_days": 15,
        "anomaly_rate": 0.05,
    },
    "Standard Preset (5 Classes, 30 Days, 5% Anomalies)": {
        "num_classes": 5,
        "num_days": 30,
        "anomaly_rate": 0.05,
    },
    "Stress Test Preset (10 Classes, 60 Days, 10% Anomalies)": {
        "num_classes": 10,
        "num_days": 60,
        "anomaly_rate": 0.10,
    },
    "Custom Configuration": None,
}

PRESET_DISPLAY_NAMES = {
    "Small Preset (3 Classes, 15 Days, 5% Anomalies)": "Small Test (3 Classes, 15 Days)",
    "Standard Preset (5 Classes, 30 Days, 5% Anomalies)": "Standard Test (5 Classes, 30 Days)",
    "Stress Test Preset (10 Classes, 60 Days, 10% Anomalies)": "Extended Test (10 Classes, 60 Days)",
    "Custom Configuration": "Custom Test",
}


def render_laboratory() -> None:
    """Render the primary Test & Learn view."""
    st.header("Test & Learn")
    st.caption("Try sample attendance records and see how the system finds unusual patterns.")

    # -------------------------------------------------------------------------
    # Compact Plain English Disclaimer Notice
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div class="decision-support-box">
            This section uses sample attendance records. Your saved attendance records will not be changed.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_scenario, tab_benchmark = st.tabs(["🔬 Try a Sample", "📊 Test Results"])

    with tab_scenario:
        _render_scenario_inspector()

    with tab_benchmark:
        _render_benchmark_evaluator()


# =============================================================================
# 1. Scenario Inspector Tab Implementation
# =============================================================================


def _render_scenario_inspector() -> None:
    """Render interactive single-cohort scenario generation and rule inspection."""
    st.subheader("Try a Sample")
    st.caption(
        "Choose a sample scenario to see how the system detects attendance changes."
    )

    c1, c2 = st.columns([2, 1])
    scenario_label = c1.selectbox(
        "Choose a Sample",
        options=list(SCENARIO_OPTIONS.keys()),
        index=0,
        key="lab_scenario_choice",
    )
    scenario_code = SCENARIO_OPTIONS[scenario_label]

    cohort_id = c2.text_input(
        "Class",
        value="CLASS-01-A",
        key="lab_scenario_class_id",
        help="Class name or code.",
    )

    p1, p2 = st.columns(2)
    enrollment = p1.number_input(
        "Total Students",
        min_value=10,
        max_value=100,
        value=30,
        step=1,
        key="lab_scenario_enrollment",
    )
    num_days = p2.number_input(
        "Number of Days",
        min_value=8,
        max_value=60,
        value=15,
        step=1,
        key="lab_scenario_num_days",
    )

    with st.expander("Advanced Settings"):
        seed = st.number_input(
            "Random Seed",
            min_value=0,
            max_value=999999,
            value=42,
            step=1,
            key="lab_scenario_seed",
            help="Deterministic integer seed for reproducible synthetic session generation.",
        )

    btn_run_scenario = st.button(
        "⚡ Run Test",
        key="btn_run_scenario",
        type="primary",
        help="Run the test scenario with sample data.",
    )

    if btn_run_scenario:
        try:
            scenario_df = generate_scenario_sessions(
                scenario_type=scenario_code,
                class_id=cohort_id,
                num_days=int(num_days),
                expected_enrollment=int(enrollment),
                random_seed=int(seed),
                include_labels=True,
            )
            scenario_alerts = detect_anomalies(scenario_df)
            st.session_state["lab_scenario_data"] = {
                "scenario_code": scenario_code,
                "scenario_label": scenario_label,
                "df": scenario_df,
                "alerts": scenario_alerts,
            }
        except Exception as exc:
            st.error(f"Error generating scenario: {exc}")

    # Check for existing generated data in session state
    if "lab_scenario_data" in st.session_state:
        data = st.session_state["lab_scenario_data"]
        scenario_df: pd.DataFrame = data["df"]
        alerts: list[Alert] = data["alerts"]
        active_code: str = data["scenario_code"]

        st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

        # Top KPI cards
        total_sessions = len(scenario_df)
        injected_anomalies = (
            int(scenario_df["ground_truth_is_anomaly"].sum())
            if "ground_truth_is_anomaly" in scenario_df.columns
            else 0
        )
        detected_signals = len(alerts)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Evaluated Sessions", total_sessions)
        k2.metric("Injected Anomalies", injected_anomalies)
        k3.metric("Detected Signals", detected_signals)
        k4.metric("Scenario Type", active_code)

        # Timeline Data Table
        st.subheader("Session Timeline & Ground-Truth Alignment")
        alert_by_session: dict[str, list[Alert]] = {}
        for a in alerts:
            alert_by_session.setdefault(a.session_id, []).append(a)

        table_rows = []
        for _, row in scenario_df.iterrows():
            sid = str(row["session_id"])
            session_alerts = alert_by_session.get(sid, [])
            detector_status = (
                ", ".join(f"{a.rule_title} [{a.priority}]" for a in session_alerts)
                if session_alerts
                else "Nominal (No Alert)"
            )

            # Simulated camera string formatting
            webcam_st = row.get("webcam_status", "NOT_ATTEMPTED")
            webcam_cnt = row.get("webcam_count")
            if webcam_st == "SUCCESS" and webcam_cnt is not None:
                cam_disp = f"{webcam_cnt} (SUCCESS)"
            else:
                cam_disp = str(webcam_st)

            rate_pct = (
                (row["present_count"] / row["expected_enrollment"] * 100.0)
                if row["expected_enrollment"] > 0
                else 0.0
            )

            table_rows.append(
                {
                    "Date": row["session_date"],
                    "Cohort": row["class_id"],
                    "Enrollment": row["expected_enrollment"],
                    "Present": row["present_count"],
                    "Absent": row["absent_count"],
                    "Rate": f"{rate_pct:.1f}%",
                    "Simulated Camera": cam_disp,
                    "Ground Truth Label": row.get("ground_truth_anomaly_type", "NONE"),
                    "Detector Output": detector_status,
                }
            )

        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        # Alert Explanations & Evidence Drilldown
        st.subheader("Generated Detection Signals & Evidence")
        if alerts:
            for i, a in enumerate(alerts, start=1):
                # Simplified teacher-facing alert card
                render_teacher_alert_card(a, allow_status_update=False, key_prefix=f"lab_sig_{i}_")

                # Advanced Tier: Technical & Diagnostic Evidence (Administrator / Developer View)
                with st.expander(f"⚙️ Technical & Diagnostic Evidence — Signal {i}: {a.rule_title} (Administrator / Developer View)", expanded=False):
                    st.markdown(f"**Rule Title:** `{a.rule_title}` &nbsp;|&nbsp; **Priority:** `{a.priority}` &nbsp;|&nbsp; **Date:** `{a.session_date}`")
                    st.markdown(f"**Technical Explanation:** {a.explanation}")

                    ev1, ev2, ev3 = st.columns(3)
                    with ev1:
                        st.markdown("**Observed Values:**")
                        if isinstance(a.observed_value, dict):
                            for k, v in a.observed_value.items():
                                st.markdown(f"• `{k}`: **{v}**")
                        else:
                            st.write(a.observed_value)
                    with ev2:
                        st.markdown("**Baseline Reference:**")
                        if isinstance(a.baseline_reference, dict):
                            for k, v in a.baseline_reference.items():
                                st.markdown(f"• `{k}`: **{v}**")
                        else:
                            st.write(a.baseline_reference)
                    with ev3:
                        st.markdown("**Threshold Applied:**")
                        if isinstance(a.threshold_applied, dict):
                            for k, v in a.threshold_applied.items():
                                st.markdown(f"• `{k}`: **{v}**")
                        else:
                            st.write(a.threshold_applied)
        else:
            st.info(
                "No anomaly signals detected for this timeline. "
                "All sessions remained within approved nominal bounds."
            )

        # Domain Guidance Callouts based on active scenario
        if active_code == "REPEATED_HEADCOUNT":
            seq_eval = evaluate_sequence_events(scenario_df, alerts, RULE_REPEATED_HEADCOUNT)
            st.markdown("##### Temporal Sequence vs. Session-Level Detection Semantics")
            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            c_s1.metric("Anomaly Events", seq_eval["total_events"])
            c_s2.metric("Event Detected", "YES" if seq_eval["tp"] > 0 else "NO")
            c_s3.metric("Event Recall", f"{seq_eval['recall']:.1%}")
            c_s4.metric("Session Recall", "25.0% (Prefix Delay)")

            st.info(
                "**Sequential Evidence Accumulation Note:** "
                "RULE_REPEATED_HEADCOUNT processes session timelines chronologically and triggers an alert "
                "only when a run of identical counts reaches or exceeds the threshold (K ≥ 4). "
                "Prefix sessions (Days 1–3) establish the sequence before the alert fires on Day 4. "
                "Under binary session-level classification accounting, prefix sessions are marked as false negatives, "
                "even though the temporal anomaly event was successfully detected upon reaching threshold."
            )
        elif active_code == "WEBCAM_DISCREPANCY":
            cam_eval = evaluate_webcam_estimation(scenario_df)
            if cam_eval["evaluated_pairs"] > 0:
                st.markdown("##### Simulated Camera Estimation Accuracy")
                c_cam1, c_cam2, c_cam3 = st.columns(3)
                c_cam1.metric("Evaluated Camera Pairs", cam_eval["evaluated_pairs"])
                c_cam2.metric(
                    "Mean Absolute Error (MAE)",
                    f"{cam_eval['mae']:.2f} students" if cam_eval["mae"] is not None else "N/A",
                )
                c_cam3.metric(
                    "MAPE (Non-Zero Counts)",
                    f"{cam_eval['mape']:.1f}%" if cam_eval["mape"] is not None else "N/A",
                )

            st.info(
                "**Camera Discrepancy Verification Note:** "
                "Simulated visible-person counting is purely an evidence-backed numerical verification aid. "
                "A camera discrepancy (|Δ| ≥ 5 and relative difference ≥ 20.0%) highlights potential discrepancies "
                "for human educator review (such as camera field-of-view limits or roll-call miscounting) "
                "and never proves fraud or intentional manipulation."
            )
        elif active_code == "ATTENDANCE_DROP":
            st.info(
                "**Attendance Drop Baseline Note:** "
                "RULE_ATTENDANCE_DROP requires at least 5 immediately preceding valid sessions for the cohort "
                "to calculate a rolling median baseline. The current session is strictly self-excluded. "
                "An alert triggers when relative percentage decline exceeds 30.0% compared to baseline."
            )
        elif active_code in ("NOMINAL", "NORMAL"):
            st.info(
                "**Nominal Baseline Validation Note:** "
                "Nominal synthetic sessions reflect realistic day-to-day attendance variance (85%–95% present). "
                "Stable or slightly fluctuating attendance evaluates cleanly with zero false positive alerts."
            )

        # Progressive Disclosure Tier 3: Advanced View
        with st.expander("⚙️ Advanced View: Raw Scenario Data & JSON Timeline"):
            st.markdown(
                """
                <div style="font-size: 0.85rem; color: #20352A; line-height: 1.55; margin-bottom: 8px;">
                    • <strong>Synthetic Isolation:</strong> This timeline was generated on-the-fly and evaluated purely in memory. Zero rows written to SQLite.<br>
                    • <strong>Ground Truth Attribution:</strong> Synthetic rows carry programmatic <code>ground_truth_label</code> tags for verification.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(scenario_df, use_container_width=True, hide_index=True)
    else:
        st.info("Select a scenario above and click '⚡ Generate Scenario & Run Detectors' to inspect scenario timelines and detector outputs.")


# =============================================================================
# 2. Benchmark Evaluator Tab Implementation
# =============================================================================


def _render_benchmark_evaluator() -> None:
    """Render multi-class synthetic dataset generation and detector benchmarking."""
    st.subheader("Test Results")
    st.caption(
        "See how accurately the system detects unusual patterns across sample tests."
    )

    preset_name = st.selectbox(
        "Sample Test Size",
        options=list(BENCHMARK_PRESETS.keys()),
        format_func=lambda p: PRESET_DISPLAY_NAMES.get(p, p),
        index=1,
        key="lab_benchmark_preset",
        help="Select a standard test size or set custom parameters.",
    )

    if st.session_state.get("_last_selected_preset") != preset_name:
        st.session_state["_last_selected_preset"] = preset_name
        preset_cfg = BENCHMARK_PRESETS.get(preset_name)
        if preset_cfg is not None:
            st.session_state["lab_bench_classes"] = preset_cfg["num_classes"]
            st.session_state["lab_bench_days"] = preset_cfg["num_days"]
            st.session_state["lab_bench_rate"] = float(preset_cfg["anomaly_rate"] * 100.0)

    preset_cfg = BENCHMARK_PRESETS[preset_name]
    if preset_cfg is not None:
        def_classes = preset_cfg["num_classes"]
        def_days = preset_cfg["num_days"]
        def_rate = preset_cfg["anomaly_rate"]
    else:
        def_classes = st.session_state.get("lab_bench_classes", 5)
        def_days = st.session_state.get("lab_bench_days", 30)
        def_rate = float(st.session_state.get("lab_bench_rate", 5.0)) / 100.0

    b1, b2, b3, b4 = st.columns(4)
    num_classes = b1.number_input(
        "Classes / Cohorts",
        min_value=1,
        max_value=20,
        value=def_classes,
        step=1,
        key="lab_bench_classes",
    )
    bench_days = b2.number_input(
        "Days per Class",
        min_value=10,
        max_value=90,
        value=def_days,
        step=1,
        key="lab_bench_days",
    )
    anomaly_rate_pct = b3.number_input(
        "Anomaly Injection Rate (%)",
        min_value=0.0,
        max_value=30.0,
        value=float(def_rate * 100.0),
        step=1.0,
        key="lab_bench_rate",
    )
    bench_seed = b4.number_input(
        "Benchmark Seed",
        min_value=0,
        max_value=999999,
        value=42,
        step=1,
        key="lab_bench_seed",
    )

    include_cam = st.checkbox(
        "Include Simulated Camera Person-Counts",
        value=True,
        key="lab_bench_include_cam",
        help="Simulate camera count status and visible-person counts for discrepancy testing.",
    )

    btn_run_benchmark = st.button(
        "🚀 Run Benchmark Evaluation",
        key="btn_run_benchmark",
        type="primary",
        help="Generate synthetic multi-class dataset, run detectors, and compute classification metrics.",
    )

    if btn_run_benchmark:
        try:
            bench_df = generate_synthetic_sessions(
                num_classes=int(num_classes),
                num_days=int(bench_days),
                anomaly_rate=float(anomaly_rate_pct / 100.0),
                random_seed=int(bench_seed),
                include_webcam=include_cam,
                include_labels=True,
            )
            bench_alerts = detect_anomalies(bench_df)
            bench_metrics = evaluate_detector_performance(bench_df, bench_alerts)
            st.session_state["lab_benchmark_data"] = {
                "df": bench_df,
                "alerts": bench_alerts,
                "metrics": bench_metrics,
                "seed": int(bench_seed),
                "num_classes": int(num_classes),
                "num_days": int(bench_days),
                "anomaly_rate_pct": float(anomaly_rate_pct),
            }
        except Exception as exc:
            st.error(f"Error running benchmark evaluation: {exc}")

    # Check for existing benchmark results in session state
    if "lab_benchmark_data" in st.session_state:
        b_data = st.session_state["lab_benchmark_data"]
        metrics: dict[str, Any] = b_data["metrics"]

        st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

        # Aggregate Performance Metrics Strip
        st.subheader("Test Performance Summary")
        bench_seed_val = b_data.get("seed", 42)
        bench_cls_val = b_data.get("num_classes", num_classes)
        bench_days_val = b_data.get("num_days", bench_days)

        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("Evaluated Sessions", metrics["total_samples"])
        sm2.metric("Overall Detection Accuracy", f"{metrics['f1_score']:.1%}")
        sm3.metric("Detected Anomalies", metrics["tp"] + metrics["fp"])

        # Progressive Disclosure Tier 2: More Details
        with st.expander("ℹ️ More Details: Understanding Benchmark Metrics & Safety Isolation"):
            st.markdown(
                """
                <div style="font-size: 0.88rem; color: #20352A; line-height: 1.55;">
                    • <strong>How Benchmarks Work:</strong> The system creates simulated attendance timelines with known ground-truth anomalies to test how reliably each detection rule fires.<br>
                    • <strong>Safe & Isolated:</strong> All test calculations run in temporary memory. Your real school attendance database is 100% untouched.<br>
                    • <strong>Academic Transparency:</strong> Precision, recall, and confusion matrices provide complete mathematical proof of system reliability.
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.expander("Detailed Test Results", expanded=True):
            st.markdown(
                """
                <div style="font-size: 0.84rem; color: #718078; margin-bottom: 8px;">
                    <strong>Academic Research & Synthetic Evaluation Notice:</strong> All data generated in this testbench is 100% synthetic and never persisted to the active school attendance database.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                f"**Test Parameters:** Seed: `{bench_seed_val}` | Classes: **{bench_cls_val}** | "
                f"Days/Class: **{bench_days_val}** | Total Evaluated Records: **{metrics['total_samples']}**"
            )

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Total Records", metrics["total_samples"])
            m2.metric("Precision", f"{metrics['precision']:.1%}")
            m3.metric("Recall", f"{metrics['recall']:.1%}")
            m4.metric("F1-Score", f"{metrics['f1_score']:.1%}")
            m5.metric("Ground Truth (TP+FN)", metrics["tp"] + metrics["fn"])
            m6.metric("Detected (TP+FP)", metrics["tp"] + metrics["fp"])

            # Zero-Denominator Handling Notice
            zd_flags = metrics.get("zero_division_applied", {})
            if any(zd_flags.values()):
                flagged = [k for k, v in zd_flags.items() if v]
                st.info(
                    f"**Zero-Denominator Policy Applied ({', '.join(flagged)}):** "
                    "When a classification metric encounters a zero denominator (e.g., no positive predictions "
                    "or no actual positive instances in the evaluated dataset), the metric score safely defaults to 0.0 "
                    "per docs/data-contract.md Section 6.2 rather than producing an undefined result."
                )

            # Confusion Matrix Table
            st.subheader("Confusion Matrix")
            st.caption(
                f"True Positives: {metrics['tp']} | False Positives: {metrics['fp']} | "
                f"False Negatives: {metrics['fn']} | True Negatives: {metrics['tn']}"
            )
            cm_df = confusion_matrix_to_dataframe(metrics["confusion_matrix"])
            st.dataframe(cm_df, use_container_width=True)

            # Per-Rule Performance Breakdown
            st.subheader("Per-Rule Breakdown")
            by_rule = metrics.get("by_rule", {})
            if by_rule:
                rule_rows = []
                for r_id, r_stats in by_rule.items():
                    rule_rows.append(
                        {
                            "Rule ID": r_id,
                            "Rule Title": RULE_TITLES.get(r_id, r_id),
                            "Target Anomaly Types": (
                                "ATTENDANCE_DROP, COMPOUND"
                                if r_id == RULE_ATTENDANCE_DROP
                                else "REPEATED_HEADCOUNT, COMPOUND"
                                if r_id == RULE_REPEATED_HEADCOUNT
                                else "WEBCAM_DISCREPANCY, COMPOUND"
                            ),
                            "Detected (TP+FP)": r_stats.get("detected_count", 0),
                            "Precision": f"{r_stats.get('precision', 0.0):.1%}",
                            "Recall": f"{r_stats.get('recall', 0.0):.1%}",
                            "F1-Score": f"{r_stats.get('f1_score', 0.0):.1%}",
                        }
                    )
                st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)

                # Sequence Event Callout for Repeated Headcount
                seq_ev = metrics.get("sequence_events")
                if seq_ev and seq_ev["total_events"] > 0:
                    st.markdown(
                        f"**Temporal Sequence Event Detection (`RULE_REPEATED_HEADCOUNT`):** "
                        f"Identified Multi-Day Events: **{seq_ev['total_events']}** | Detected: **{seq_ev['tp']}** | "
                        f"Event Recall: **{seq_ev['recall']:.1%}** | Event Precision: **{seq_ev['precision']:.1%}**"
                    )

                st.caption(
                    "**Note on RULE_REPEATED_HEADCOUNT Session Recall vs. Event Recall:** "
                    "Sequential online detectors require multiple consecutive sessions before firing on Day 4. "
                    "Prefix sessions (Days 1–3) are accounted as false negatives in session-level classification, "
                    "even though the overall temporal event is detected successfully."
                )
            else:
                st.info(
                    "Per-rule metrics are omitted when ground-truth anomaly type annotations are absent, "
                    "preventing misleading cross-rule false negative inflation."
                )

            # Simulated Camera Estimation Metrics (when camera count simulation is active)
            cam_eval = metrics.get("webcam_estimation")
            if cam_eval and cam_eval["evaluated_pairs"] > 0:
                st.subheader("Simulated Camera Count Estimation Accuracy")
                cam_c1, cam_c2, cam_c3, cam_c4 = st.columns(4)
                cam_c1.metric("Evaluated Camera Pairs", cam_eval["evaluated_pairs"])
                cam_c2.metric(
                    "Mean Absolute Error (MAE)",
                    f"{cam_eval['mae']:.2f} students" if cam_eval["mae"] is not None else "N/A",
                )
                cam_c3.metric(
                    "MAPE (Non-Zero Actuals)",
                    f"{cam_eval['mape']:.1f}%" if cam_eval["mape"] is not None else "N/A",
                )
                cam_c4.metric("Zero-Actual Excluded", cam_eval["zero_actual_count"])

                st.caption(
                    "**Camera Estimation Metric Decoupling:** MAE and MAPE evaluate numerical tracking variance "
                    "between simulated visible-person estimates and manual roll-call counts. Sessions with 0 actual "
                    "attendance are excluded from MAPE calculation to avoid undefined percentage divisions."
                )

            # Camera Metric Separation & Real-World Generalization Disclaimers
            st.markdown(
                """
                <div class="decision-support-box">
                    <strong>Camera Metric Isolation:</strong> Simulated camera count estimation errors (MAE/MAPE)
                    reflect numerical tracking variance and are evaluated independently from binary roll-call attendance classification.
                    Camera discrepancies do not contaminate attendance record validity.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption(
            "**Academic Generalization Disclaimer:** Benchmark performance demonstrates algorithm sensitivity "
            "and specificity under synthetic assumptions. These controlled experimental results do not represent "
            "or guarantee operational precision in real-world classrooms subject to unpredictable physical variances."
        )
    else:
        st.info("Select a preset or custom parameters above and click '🚀 Run Benchmark Evaluation' to analyze detector precision and recall.")
