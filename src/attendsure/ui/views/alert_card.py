"""Teacher-Ready Alert Card Component for AttendSure.

Provides a simplified, non-technical alert card presentation for teachers
following the principle: 'Hide technical complexity. Show useful outcomes.'
Adheres todocs/data-contract.md and AGENTS.md.
"""

from datetime import datetime
from typing import Optional
import streamlit as st

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository
from attendsure.services.attendance_service import update_alert_status
from attendsure.ui.state import get_repository


def format_friendly_date(date_str: str) -> str:
    """Format an ISO YYYY-MM-DD date string into natural English."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%A, %d %B %Y")
    except Exception:
        return date_str


def get_teacher_alert_details(alert: Alert, ref_session: Optional[SessionRecord] = None) -> dict:
    """Translate raw detector signals into plain-English teacher guidance.

    Returns structured fields:
    - heading: 'Attendance needs checking'
    - status_display: 'Please review', 'Seen', 'Checked', 'Dismissed'
    - finding: Clear statement of the discrepancy
    - class_id: Cohort name
    - date_str: Natural language date
    - what_we_found: Plain sentence explanation with actual counts
    - metric_1_label, metric_1_val: First large numerical card
    - metric_2_label, metric_2_val: Second large numerical card
    - why_happen: Plausible benign reasons (camera angle, illness, weather)
    - what_to_do: Actionable instructions for the teacher
    - reassurance: Non-accusatory reminder statement
    """
    rule_id = alert.rule_id
    obs = alert.observed_value if isinstance(alert.observed_value, dict) else {}
    base = alert.baseline_reference if isinstance(alert.baseline_reference, dict) else {}
    thresh = alert.threshold_applied if isinstance(alert.threshold_applied, dict) else {}

    friendly_date = format_friendly_date(alert.session_date)

    if "WEBCAM" in rule_id:
        heading = "Attendance needs checking"
        finding = "Classroom count does not match the attendance register."

        marked_present = obs.get("present_count", ref_session.present_count if ref_session else 0)
        webcam_count = obs.get("webcam_count", "N/A")

        what_we_found = (
            f"The attendance register shows {marked_present} students present, "
            f"but the classroom photograph shows approximately {webcam_count} people."
        )

        metric_1_label = "Students marked present"
        metric_1_val = str(marked_present)
        metric_2_label = "People visible in photograph"
        metric_2_val = f"~{webcam_count}" if str(webcam_count).isdigit() else str(webcam_count)

        why_happen = (
            "Some students may be outside the camera's view or hidden behind other students. "
            "The photograph may not show the entire classroom."
        )
        what_to_do = "Please check the attendance register and confirm the correct number of students."
        reassurance = "This is a reminder to verify the count, not an accusation of incorrect attendance."

    elif "DROP" in rule_id:
        heading = "Attendance needs checking"
        finding = "Attendance was lower than usual today."

        present_count = obs.get("present_count", ref_session.present_count if ref_session else 0)
        enrollment = obs.get("expected_enrollment", ref_session.expected_enrollment if ref_session else 0)
        baseline_rate = base.get("baseline_rate_pct", 0.0)

        if enrollment > 0 and baseline_rate > 0:
            typical_present = round(enrollment * baseline_rate / 100.0)
        else:
            typical_present = enrollment if enrollment > 0 else 0

        what_we_found = (
            f"The attendance register shows {present_count} students present today, "
            f"which is noticeably lower than the typical attendance of around {typical_present} students."
        )

        metric_1_label = "Students present today"
        metric_1_val = str(present_count)
        metric_2_label = "Typical attendance"
        metric_2_val = f"~{typical_present}"

        why_happen = (
            "Students may be absent due to heavy rain, seasonal fever, local village events, "
            "or transport problems in the village."
        )
        what_to_do = "Please check the attendance register and confirm the correct number of students."
        reassurance = "This is a reminder to verify the count, not an accusation of incorrect attendance."

    elif "REPEATED" in rule_id:
        heading = "Attendance needs checking"
        finding = "Several recent sessions recorded the exact same number of students."

        repeated_count = obs.get("repeated_headcount", ref_session.present_count if ref_session else 0)
        consecutive = obs.get("consecutive_sessions", thresh.get("observed_consecutive_sessions", 4))

        what_we_found = (
            f"The attendance register has recorded exactly {repeated_count} students present for "
            f"{consecutive} days in a row without normal daily variation."
        )

        metric_1_label = "Daily student count"
        metric_1_val = str(repeated_count)
        metric_2_label = "Days in a row"
        metric_2_val = f"{consecutive} days"

        why_happen = (
            "Student attendance naturally varies from day to day. Repeating the exact same count "
            "across multiple days may indicate a repeated roll call or an unverified headcount."
        )
        what_to_do = "Please verify the physical attendance register to confirm daily roll calls are recorded individually each day."
        reassurance = "This is a reminder to verify the count, not an accusation of incorrect attendance."

    else:
        heading = "Attendance needs checking"
        finding = alert.rule_title

        enr = ref_session.expected_enrollment if ref_session else obs.get("expected_enrollment", 0)
        pres = ref_session.present_count if ref_session else obs.get("present_count", 0)

        what_we_found = alert.explanation
        metric_1_label = "Students marked present"
        metric_1_val = str(pres)
        metric_2_label = "Total enrolled"
        metric_2_val = str(enr)

        why_happen = "This attendance record differs from normal attendance patterns for this class."
        what_to_do = "Please check the attendance register and confirm the correct number of students."
        reassurance = "This is a reminder to verify the count, not an accusation of incorrect attendance."

    status_map = {
        "PENDING_REVIEW": "Please review",
        "ACKNOWLEDGED": "Seen",
        "RESOLVED": "Checked",
        "DISMISSED": "Dismissed",
    }
    status_display = status_map.get(alert.review_status, alert.review_status)

    return {
        "heading": heading,
        "status_display": status_display,
        "finding": finding,
        "class_id": alert.class_id,
        "date_str": friendly_date,
        "what_we_found": what_we_found,
        "metric_1_label": metric_1_label,
        "metric_1_val": metric_1_val,
        "metric_2_label": metric_2_label,
        "metric_2_val": metric_2_val,
        "why_happen": why_happen,
        "what_to_do": what_to_do,
        "reassurance": reassurance,
    }


def render_teacher_alert_card(
    alert: Alert,
    ref_session: Optional[SessionRecord] = None,
    allow_status_update: bool = True,
    key_prefix: str = "",
) -> None:
    """Render the simplified teacher-facing alert card with two large numerical highlights using native Streamlit."""
    data = get_teacher_alert_details(alert, ref_session)

    with st.container(border=True):
        # 1. Heading & Status row
        head_col, status_col = st.columns([3, 1])
        with head_col:
            st.subheader(data["heading"])
            st.caption(f"Class {data['class_id']} • {data['date_str']}")
        with status_col:
            if alert.review_status == "PENDING_REVIEW":
                st.warning("⚠️ Please review")
            elif alert.review_status == "RESOLVED":
                st.success("✅ Checked")
            elif alert.review_status == "ACKNOWLEDGED":
                st.info("👀 Seen")
            else:
                st.caption(f"Status: {data['status_display']}")

        # 2. Finding Banner
        st.warning(f"**Finding:** {data['finding']}")

        # 3. What we found
        st.markdown("**What we found:**")
        st.write(data["what_we_found"])

        # 4. Two Large Numerical Highlight Cards
        m1, m2 = st.columns(2)
        with m1:
            st.metric(label=data["metric_1_label"], value=data["metric_1_val"])
        with m2:
            st.metric(label=data["metric_2_label"], value=data["metric_2_val"])

        # 5. Why might this happen?
        st.markdown(f"**Why might this happen?**\n\n{data['why_happen']}")

        # 6. What should you do?
        st.info(f"**What should you do?**\n\n{data['what_to_do']}")

        # 7. Brief Reassurance
        st.caption(f"ℹ️ {data['reassurance']}")

    # 8. Action Buttons
    if allow_status_update:
        col_rev, col_chk = st.columns([1, 1])
        with col_rev:
            if st.button("🔍 Review Attendance", key=f"{key_prefix}btn_rev_att_{alert.alert_id}", use_container_width=True):
                st.session_state[f"{key_prefix}show_guide_{alert.alert_id}"] = not st.session_state.get(
                    f"{key_prefix}show_guide_{alert.alert_id}", False
                )
        with col_chk:
            if st.button("✅ Mark as Checked", type="primary", key=f"{key_prefix}btn_mark_chk_{alert.alert_id}", use_container_width=True):
                try:
                    with get_repository() as repo:
                        update_alert_status(repo, alert.alert_id, "RESOLVED", raise_if_missing=True)
                    st.success(f"Class {alert.class_id} attendance verified and marked as checked.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error updating status: {exc}")

        if st.session_state.get(f"{key_prefix}show_guide_{alert.alert_id}", False):
            st.info(
                f"**Attendance Verification Checklist for Class {alert.class_id}:**\n"
                "1. Open the physical paper attendance register for this date.\n"
                "2. Count the roll-call entries to confirm the exact number of present students.\n"
                "3. Check for students participating in school activities, field trips, or late arrivals.\n"
                "4. When verified, click 'Mark as Checked' above to resolve this record."
            )

