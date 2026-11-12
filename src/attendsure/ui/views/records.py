"""Attendance Records view for Rural School Attendance Integrity and Intervention Decision System.

Provides dedicated searchable, filterable roll-call history with class, date,
and search filters, clean record detail inspection, and direct CSV export.
Designed for ordinary schoolteachers:
- Shows Date, Class, Total students, Present, Absent, Attendance %.
- Allows viewing record details in plain English.
- Hides internal database IDs, raw JSON, and model features.
"""

from datetime import datetime
import io
from typing import Optional

import pandas as pd
import streamlit as st

from attendsure.data.models import Alert
from attendsure.ui.dev_mode import is_developer_mode
from attendsure.ui.state import get_cached_alerts, get_cached_sessions, get_repository


def render_records() -> None:
    """Render the teacher-friendly Attendance Records screen."""
    st.header("Attendance Records")
    st.caption("Search, filter, and inspect past attendance records across all classes.")

    try:
        with get_repository() as repo:
            all_sessions = get_cached_sessions(repo)
            alerts = get_cached_alerts(repo)
    except Exception as exc:
        st.error(f"Unable to access the local attendance database: {exc}")
        return

    if all_sessions.empty:
        st.info(
            "No attendance records found in the database. "
            "Use 'Mark Attendance' to record daily sessions or import a CSV file in Reports."
        )
        return

    # Map alerted sessions for quick lookup
    alerted_session_ids = {a.session_id: a for a in alerts if a.review_status == "PENDING_REVIEW"}
    all_sessions["needs_review"] = all_sessions["session_id"].apply(lambda sid: sid in alerted_session_ids)

    # -------------------------------------------------------------------------
    # 1. Simple Search and Filter Controls
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 0.90rem; font-weight: 700; color: #0F172A; display: flex; align-items: center; gap: 8px;">
                <span style="color: #0D9488;">🔍</span> Search & Filter Records
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.5, 1.5, 1])

    available_classes = ["All Classes"] + sorted(all_sessions["class_id"].unique().tolist())
    selected_class = f_col1.selectbox(
        "Class",
        options=available_classes,
        index=0,
        key="rec_filter_class",
    )

    review_filter = f_col2.selectbox(
        "Status",
        options=["All Records", "Needs Review Only", "Normal Records Only"],
        index=0,
        key="rec_filter_status",
    )

    search_query = f_col3.text_input(
        "Search",
        value="",
        placeholder="Search class or date...",
        key="rec_search_query",
    )

    use_date_range = f_col4.checkbox(
        "Date Range",
        value=False,
        key="rec_filter_use_date",
    )

    start_date_str: Optional[str] = None
    end_date_str: Optional[str] = None

    if use_date_range:
        d_col1, d_col2 = st.columns(2)
        min_date = datetime.strptime(str(all_sessions["session_date"].min()), "%Y-%m-%d").date()
        max_date = datetime.strptime(str(all_sessions["session_date"].max()), "%Y-%m-%d").date()

        start_val = d_col1.date_input("From Date", value=min_date, key="rec_filter_start_date")
        end_val = d_col2.date_input("To Date", value=max_date, key="rec_filter_end_date")

        if start_val > end_val:
            st.warning("From Date cannot be later than To Date.")
            return
        start_date_str = str(start_val)
        end_date_str = str(end_val)

    # -------------------------------------------------------------------------
    # 2. Filter Application
    # -------------------------------------------------------------------------
    filtered_df = all_sessions.copy()

    if selected_class != "All Classes":
        filtered_df = filtered_df[filtered_df["class_id"] == selected_class]

    if use_date_range and start_date_str and end_date_str:
        filtered_df = filtered_df[
            (filtered_df["session_date"] >= start_date_str) & (filtered_df["session_date"] <= end_date_str)
        ]

    if review_filter == "Needs Review Only":
        filtered_df = filtered_df[filtered_df["needs_review"] == True]
    elif review_filter == "Normal Records Only":
        filtered_df = filtered_df[filtered_df["needs_review"] == False]

    if search_query.strip():
        q = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["class_id"].str.lower().str.contains(q)
            | filtered_df["session_date"].str.lower().str.contains(q)
        ]

    # Sort chronologically descending
    filtered_df = filtered_df.sort_values(by=["session_date", "class_id"], ascending=[False, True])

    # -------------------------------------------------------------------------
    # 3. Summary KPIs for Filtered View
    # -------------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    total_recs = len(filtered_df)
    total_pres = int(filtered_df["present_count"].sum()) if not filtered_df.empty else 0
    total_enr = int(filtered_df["expected_enrollment"].sum()) if not filtered_df.empty else 0
    avg_rate = (total_pres / total_enr * 100.0) if total_enr > 0 else 0.0
    flagged_recs = int(filtered_df["needs_review"].sum()) if not filtered_df.empty else 0

    k1.metric("Filtered Sessions", f"{total_recs}")
    k2.metric("Total Present", f"{total_pres}")
    k3.metric("Avg Attendance Rate", f"{avg_rate:.1f}%")
    k4.metric("Flagged for Review", f"{flagged_recs}")

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 16px 0;' />", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 4. Display Table
    # -------------------------------------------------------------------------
    if filtered_df.empty:
        st.info("No attendance records match the selected filters.")
        return

    # Prepare display columns
    display_df = filtered_df.copy()
    display_df["attendance_rate_pct"] = (
        display_df["present_count"] / display_df["expected_enrollment"] * 100.0
    ).round(1)
    display_df["status_display"] = display_df["needs_review"].apply(
        lambda n: "⚠️ Needs Review" if n else "✅ Normal"
    )

    clean_table = display_df[
        [
            "session_date",
            "class_id",
            "expected_enrollment",
            "present_count",
            "absent_count",
            "attendance_rate_pct",
            "status_display",
        ]
    ].rename(
        columns={
            "session_date": "Date",
            "class_id": "Class",
            "expected_enrollment": "Total Students",
            "present_count": "Present",
            "absent_count": "Absent",
            "attendance_rate_pct": "Attendance %",
            "status_display": "Integrity Status",
        }
    )

    st.dataframe(
        clean_table,
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------------
    # 5. Open & Inspect Record Details (Teacher-Friendly)
    # -------------------------------------------------------------------------
    with st.expander("🔍 View Record Details", expanded=False):
        record_options = [
            f"{r['session_date']} — {r['class_id']} ({r['present_count']}/{r['expected_enrollment']} present)"
            for _, r in filtered_df.iterrows()
        ]
        if record_options:
            selected_record_label = st.selectbox(
                "Select Record to Inspect",
                options=record_options,
                index=0,
                key="rec_inspect_selectbox",
            )
            selected_idx = record_options.index(selected_record_label)
            sel_row = filtered_df.iloc[selected_idx]

            det_enr = int(sel_row["expected_enrollment"])
            det_pres = int(sel_row["present_count"])
            det_abs = int(sel_row["absent_count"])
            det_rate = (det_pres / det_enr * 100.0) if det_enr > 0 else 0.0
            is_flagged = bool(sel_row["needs_review"])

            with st.container(border=True):
                col_r_title, col_r_stat = st.columns([3, 1])
                with col_r_title:
                    st.markdown(f"**Class {sel_row['class_id']} — {sel_row['session_date']}**")
                with col_r_stat:
                    if is_flagged:
                        st.warning("⚠️ Needs Review")
                    else:
                        st.success("✅ Normal")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Students", det_enr)
                m2.metric("Present", det_pres)
                m3.metric("Absent", det_abs)
                m4.metric("Attendance %", f"{det_rate:.1f}%")

            if is_flagged and sel_row["session_id"] in alerted_session_ids:
                matching_alert = alerted_session_ids[sel_row["session_id"]]
                st.warning(f"Reminder note: {matching_alert.explanation}")

            # Developer View: Session identifiers, internal source, webcam metadata
            if is_developer_mode():
                with st.expander("⚙️ Technical Details — Developer View", expanded=False):
                    st.markdown(f"• **Session UUID:** `{sel_row['session_id']}`")
                    st.markdown(f"• **Record Source:** `{sel_row.get('record_source', 'MANUAL_ENTRY')}`")
                    st.markdown(f"• **Webcam Status:** `{sel_row.get('webcam_status', 'NOT_ATTEMPTED')}`")
                    st.markdown(f"• **Webcam Count:** `{sel_row.get('webcam_count')}`")
                    st.markdown(f"• **Created At (UTC):** `{sel_row.get('created_at', 'N/A')}`")
                    st.json(dict(sel_row))

    # -------------------------------------------------------------------------
    # 6. Direct CSV Export
    # -------------------------------------------------------------------------
    col_exp_info, col_exp_btn = st.columns([3, 1])
    with col_exp_info:
        st.caption(f"Exporting {len(filtered_df)} filtered attendance records in standard CSV format.")
    with col_exp_btn:
        csv_buffer = io.StringIO()
        filtered_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_buffer.getvalue(),
            file_name=f"attendance_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="rec_download_csv_btn",
            type="primary",
        )
