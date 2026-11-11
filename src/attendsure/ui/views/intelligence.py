"""Intelligence Centre view for AttendSure.

Provides explainable anomaly review, structured evidence inspection,
review triage status transitions, and on-demand detection scanning adhering
to docs/data-contract.md and AGENTS.md.
Refined with the Pastel Green modern dashboard design language.
"""

from dataclasses import asdict
from datetime import date, datetime
import json
from typing import Any, Optional

import pandas as pd
import streamlit as st

from attendsure.data.models import Alert, AlertPriority, ReviewStatus, SessionRecord
from attendsure.data.storage import VALID_ALERT_PRIORITIES, VALID_REVIEW_STATUSES
from attendsure.detection.rules import (
    RULE_ATTENDANCE_DROP,
    RULE_ATTENDANCE_DROP_TITLE,
    RULE_REPEATED_HEADCOUNT,
    RULE_REPEATED_HEADCOUNT_TITLE,
    RULE_WEBCAM_DISCREPANCY,
    RULE_WEBCAM_DISCREPANCY_TITLE,
)
from attendsure.ml.predictor import (
    evaluate_session_ml,
    synthesize_intervention_decision,
)
from attendsure.services.attendance_service import (
    run_full_detection_pipeline,
    update_alert_status,
)
from attendsure.ui.state import get_repository
from attendsure.ui.dev_mode import is_developer_mode
from attendsure.ui.views.alert_card import render_teacher_alert_card


def render_intelligence() -> None:
    """Render the primary Needs Attention screen."""
    st.header("Needs Attention")
    st.caption("Review attendance records requiring inspection with explainable rules and AI decision support.")

    try:
        with get_repository() as repo:
            all_alerts: list[Alert] = repo.get_alerts()
    except Exception as exc:
        st.error(f"Unable to access the local attendance database: {exc}")
        st.info("Please verify database file permissions and path configuration.")
        return

    # -------------------------------------------------------------------------
    # 1. On-Demand Anomaly Detection Scan
    # -------------------------------------------------------------------------
    scan_col1, scan_col2 = st.columns([1, 2])
    scan_clicked = scan_col1.button(
        "🔍 Check for Unusual Attendance",
        key="btn_run_detection_scan",
        help="Check all recorded classes for unusual patterns.",
    )

    if scan_clicked:
        try:
            with get_repository() as repo:
                generated = run_full_detection_pipeline(repo)
            st.session_state["scan_outcome"] = {
                "status": "success",
                "count": len(generated),
            }
            # Re-fetch alerts to reflect any newly generated signals
            with get_repository() as repo:
                all_alerts = repo.get_alerts()
        except Exception as exc:
            st.session_state["scan_outcome"] = {
                "status": "error",
                "error": str(exc),
            }

    if "scan_outcome" in st.session_state:
        outcome = st.session_state["scan_outcome"]
        if outcome.get("status") == "success":
            count = outcome.get("count", 0)
            if count > 0:
                scan_col2.success(
                    f"Detection scan complete: Evaluated {count} anomaly signal(s) across stored cohort timelines. "
                    "Existing review determinations were preserved."
                )
            else:
                scan_col2.info(
                    "Detection scan complete: All historical attendance sessions evaluated within nominal bounds (0 new signals)."
                )
        elif outcome.get("status") == "error":
            scan_col2.error(f"Check error: {outcome.get('error')}")

    # -------------------------------------------------------------------------
    # 2. Overall KPI Summary Strip
    # -------------------------------------------------------------------------
    total_signals = len(all_alerts)
    pending_count = len([a for a in all_alerts if a.review_status == "PENDING_REVIEW"])
    acknowledged_count = len([a for a in all_alerts if a.review_status == "ACKNOWLEDGED"])
    resolved_count = len([a for a in all_alerts if a.review_status == "RESOLVED"])
    dismissed_count = len([a for a in all_alerts if a.review_status == "DISMISSED"])

    st.markdown("<div style='margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Alerts", total_signals)
    m2.metric("Needs Attention", pending_count)
    m3.metric("Seen", acknowledged_count)
    m4.metric("Checked", resolved_count)
    m5.metric("Dismissed", dismissed_count)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 3. Empty Database Guidance
    # -------------------------------------------------------------------------
    if not all_alerts:
        st.info(
            "No anomaly signals recorded in the database. "
            "As attendance roll calls are recorded or imported, detected signals will appear here for review."
        )
        _render_decision_support_box()
        return

    # -------------------------------------------------------------------------
    # 4. Filters Bar
    # -------------------------------------------------------------------------
    st.subheader("Filter Alerts")
    c1, c2, c3, c4 = st.columns(4)

    status_options = ["ALL", "PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
    status_display = {
        "ALL": "All Statuses",
        "PENDING_REVIEW": "Needs Attention",
        "ACKNOWLEDGED": "Seen",
        "RESOLVED": "Checked",
        "DISMISSED": "Dismissed",
    }
    selected_status = c1.selectbox(
        "Review Status",
        options=status_options,
        format_func=lambda s: status_display.get(s, s),
        index=0,
        key="filter_review_status",
    )

    unique_cohorts = ["All Classes"] + sorted(list({a.class_id for a in all_alerts}))
    selected_cohort = c2.selectbox("Class", options=unique_cohorts, index=0, key="filter_cohort")

    rule_map = {
        "All Rules": None,
        RULE_ATTENDANCE_DROP_TITLE: RULE_ATTENDANCE_DROP,
        RULE_REPEATED_HEADCOUNT_TITLE: RULE_REPEATED_HEADCOUNT,
        RULE_WEBCAM_DISCREPANCY_TITLE: RULE_WEBCAM_DISCREPANCY,
    }
    selected_rule_label = c3.selectbox("Alert Type", options=list(rule_map.keys()), index=0, key="filter_rule")
    selected_rule = rule_map[selected_rule_label]

    priority_options = ["ALL", "REVIEW_REQUIRED", "INFO"]
    priority_display = {
        "ALL": "All Priorities",
        "REVIEW_REQUIRED": "Needs Attention",
        "INFO": "Info",
    }
    selected_priority = c4.selectbox(
        "Priority",
        options=priority_options,
        format_func=lambda p: priority_display.get(p, p),
        index=0,
        key="filter_priority",
    )

    use_date_filter = st.checkbox("Filter by Date Range", value=False, key="filter_use_date")
    start_date_str: Optional[str] = None
    end_date_str: Optional[str] = None
    invalid_date_range = False

    if use_date_filter:
        cd1, cd2 = st.columns(2)
        all_dates = [datetime.strptime(a.session_date, "%Y-%m-%d").date() for a in all_alerts]
        min_d = min(all_dates) if all_dates else datetime.now().date()
        max_d = max(all_dates) if all_dates else datetime.now().date()
        start_d = cd1.date_input("Start Date", value=min_d, key="filter_start_date")
        end_d = cd2.date_input("End Date", value=max_d, key="filter_end_date")

        if start_d > end_d:
            st.warning("Start Date cannot be after End Date. Please adjust the date filter.")
            invalid_date_range = True
        else:
            start_date_str = str(start_d)
            end_date_str = str(end_d)

    # -------------------------------------------------------------------------
    # 5. Query Filtered Signals
    # -------------------------------------------------------------------------
    if invalid_date_range:
        filtered_alerts: list[Alert] = []
    else:
        status_arg = None if selected_status == "ALL" else selected_status
        cohort_arg = None if selected_cohort in ("All Classes", "All Cohorts") else selected_cohort

        try:
            with get_repository() as repo:
                filtered_alerts = repo.get_alerts(
                    review_status=status_arg,
                    class_id=cohort_arg,
                    rule_id=selected_rule,
                    start_date=start_date_str,
                    end_date=end_date_str,
                )
        except Exception as exc:
            st.error(f"Error querying signals from database: {exc}")
            return

        if selected_priority != "ALL":
            filtered_alerts = [a for a in filtered_alerts if a.priority == selected_priority]

    if not filtered_alerts:
        st.info("No anomaly signals match the selected filters. Try broadening your filter criteria.")
        _render_decision_support_box()
        return

    # Sort recent sessions first
    filtered_alerts = sorted(
        filtered_alerts,
        key=lambda a: (a.session_date, a.class_id, a.alert_id),
        reverse=True,
    )

    if not filtered_alerts:
        if not invalid_date_range:
            st.info("No anomaly signals match the selected filters. Try broadening your filter criteria.")
        _render_decision_support_box()
        return

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 6. Signals Registry Table
    # -------------------------------------------------------------------------
    st.subheader(f"Matching Signals Registry ({len(filtered_alerts)} signals)")

    table_data = []
    for a in filtered_alerts:
        table_data.append(
            {
                "Date": a.session_date,
                "Cohort": a.class_id,
                "Rule": a.rule_title,
                "Priority": a.priority,
                "Review Status": a.review_status,
                "Explanation": a.explanation,
            }
        )
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 7. Signal Detail & Natural Language Explanation (Teacher-Friendly)
    # -------------------------------------------------------------------------
    st.subheader("Alert Details & Recommended Action")
    st.caption("Understand what happened, why it was flagged, and what to do next.")

    alert_options = {
        f"{a.session_date} — {a.class_id}: {a.rule_title} [{a.review_status}]": a
        for a in filtered_alerts
    }

    selected_label = st.selectbox(
        "Select Record to Inspect:",
        options=list(alert_options.keys()),
        index=0,
    )
    active_alert: Alert = alert_options[selected_label]

    # Query associated session record if available
    with get_repository() as repo:
        ref_session: Optional[SessionRecord] = repo.get_session_by_id(active_alert.session_id)

    # -------------------------------------------------------------------------
    # Simplified Teacher-Facing Alert Card (Simple by Default)
    # -------------------------------------------------------------------------
    render_teacher_alert_card(active_alert, ref_session, allow_status_update=True)

    # -------------------------------------------------------------------------
    # Administrative Status Update Controls
    # -------------------------------------------------------------------------
    with st.expander("📝 Update Status & Audit Log", expanded=False):
        st.caption("Change the record's review determination or record administrative verification notes.")
        act_col1, act_col2 = st.columns([1, 2])
        valid_statuses = ["PENDING_REVIEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
        status_label_map = {
            "PENDING_REVIEW": "Needs Attention",
            "ACKNOWLEDGED": "Mark as Seen",
            "RESOLVED": "Mark as Reviewed",
            "DISMISSED": "Dismiss Alert",
        }
        current_idx = (
            valid_statuses.index(active_alert.review_status)
            if active_alert.review_status in valid_statuses
            else 0
        )

        new_target_status = act_col1.selectbox(
            "Select Status",
            options=valid_statuses,
            format_func=lambda s: status_label_map.get(s, s),
            index=current_idx,
            key=f"target_status_{active_alert.alert_id}",
        )
        apply_btn = act_col1.button(
            "Update Status",
            type="primary",
            key=f"btn_apply_{active_alert.alert_id}",
        )

        if apply_btn:
            if new_target_status == active_alert.review_status:
                act_col2.info(f"Signal is already in '{new_target_status}' status. No write was needed.")
            else:
                try:
                    with get_repository() as repo:
                        updated = update_alert_status(
                            repo,
                            active_alert.alert_id,
                            new_target_status,
                            raise_if_missing=True,
                        )
                    if updated:
                        friendly_name = status_label_map.get(new_target_status, new_target_status)
                        act_col2.success(
                            f"Review determination updated to '{new_target_status}' ({friendly_name}) for signal on cohort '{active_alert.class_id}'."
                        )
                except Exception as exc:
                    act_col2.error(f"Failed to update review determination: {exc}")

    # -------------------------------------------------------------------------
    # Advanced Tier: Technical Evidence (Developer View)
    # -------------------------------------------------------------------------
    if is_developer_mode():
        with st.expander("⚙️ Technical Details — Developer View", expanded=False):
            st.markdown("#### Technical Metadata & Contract Specifications")
            st.markdown(f"• **Rule Identifier:** `{active_alert.rule_id}` ({active_alert.rule_title})")
            st.markdown(f"• **Priority:** `{active_alert.priority}`")
            st.markdown(f"• **Alert ID:** `{active_alert.alert_id}`")
            st.markdown(f"• **Session ID:** `{active_alert.session_id}`")
            st.markdown(f"• **Created At (UTC):** `{active_alert.created_at}`")

            st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 10px 0;' />", unsafe_allow_html=True)

            ev1, ev2, ev3 = st.columns(3)
            with ev1:
                st.markdown("**Observed Values:**")
                if isinstance(active_alert.observed_value, dict):
                    for k, v in active_alert.observed_value.items():
                        st.markdown(f"• `{k}`: **{v}**")
                else:
                    st.write(active_alert.observed_value)

            with ev2:
                st.markdown("**Baseline Reference:**")
                if isinstance(active_alert.baseline_reference, dict):
                    for k, v in active_alert.baseline_reference.items():
                        st.markdown(f"• `{k}`: **{v}**")
                else:
                    st.write(active_alert.baseline_reference)

            with ev3:
                st.markdown("**Threshold Applied:**")
                if isinstance(active_alert.threshold_applied, dict):
                    for k, v in active_alert.threshold_applied.items():
                        st.markdown(f"• `{k}`: **{v}**")
                else:
                    st.write(active_alert.threshold_applied)

            st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 10px 0;' />", unsafe_allow_html=True)
            st.markdown("#### Associated Database Session Context")
            if ref_session is not None:
                sc1, sc2, sc3, sc4 = st.columns(4)
                rate_str = (
                    f"{(ref_session.present_count / ref_session.expected_enrollment * 100.0):.1f}%"
                    if ref_session.expected_enrollment > 0
                    else "N/A"
                )
                sc1.metric("Enrollment", ref_session.expected_enrollment)
                sc2.metric("Present", ref_session.present_count)
                sc3.metric("Absent", ref_session.absent_count)
                sc4.metric("Attendance Rate", rate_str)
            else:
                st.warning(
                    f"Associated session record '{active_alert.session_id}' was not found in storage. "
                    "Details reflect alert metadata preserved at time of detection."
                )

            st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 10px 0;' />", unsafe_allow_html=True)
            st.markdown("#### Dual Stream Decision Support: Rule Finding vs. Machine Learning")

            # Compute ML Decision Support for this session
            ml_pred_label = "INSUFFICIENT_DATA"
            ml_confidence = 0.5
            ml_expl = "Historical cohort timeline is insufficient for causal ML feature extraction."
            combined_status = "NEEDS_VERIFICATION"
            combined_rec = "Review session records against teacher roll-call notes."
            actionable_step = "Check physical roll-call register."

            if ref_session is not None:
                try:
                    with get_repository() as repo:
                        all_cohort_sessions = repo.get_sessions(class_id=ref_session.class_id, as_df=True)
                    ml_res = evaluate_session_ml(
                        class_id=ref_session.class_id,
                        enrollment=ref_session.expected_enrollment,
                        present=ref_session.present_count,
                        history_df=all_cohort_sessions,
                    )
                    decision = synthesize_intervention_decision([active_alert], ml_res)
                    ml_pred_label = decision.ml_prediction
                    ml_confidence = decision.ml_confidence
                    ml_expl = decision.ml_explanation
                    combined_status = decision.overall_status
                    combined_rec = decision.combined_recommendation
                    actionable_step = decision.actionable_next_step
                except Exception:
                    pass

            ml1, ml2 = st.columns(2)
            with ml1:
                st.markdown(f"**ML Predicted Status:** `{ml_pred_label}` (Confidence: {ml_confidence:.1%})")
                st.caption(ml_expl)
            with ml2:
                st.markdown(f"**Combined Synthesis:** `{combined_status}`")
                st.caption(combined_rec)

            st.markdown("#### Raw Audit JSON Payload")
            st.json(asdict(active_alert))

    _render_decision_support_box()


def _render_decision_support_box() -> None:
    """Render the standard non-accusatory decision support notice."""
    st.markdown(
        "💡 **Decision Support Notice:** This system highlights unusual attendance patterns so "
        "teachers and administrators can check them. Alerts are not proof of wrongdoing — they are simply "
        "reminders to double-check the numbers."
    )
