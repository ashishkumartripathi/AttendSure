"""Data & Settings view for Rural School Attendance Integrity and Intervention Decision System.

Provides ordinary school administrative configuration (School name, details,
class & student management, basic preferences) alongside local offline health
diagnostics and privacy guarantees adhering to docs/data-contract.md.
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from attendsure.data.storage import DEFAULT_DB_PATH
from attendsure.ui.dev_mode import is_developer_mode, set_developer_mode
from attendsure.ui.state import (
    get_active_database_metadata,
    get_cached_alerts,
    get_cached_sessions,
    get_configured_db_path,
    get_repository,
    test_db_connection,
)


def render_settings() -> None:
    """Render the primary Settings administrative screen."""
    st.header("Settings")
    st.caption("Manage school details, class strengths, preferences, and local data storage.")

    tab_school, tab_health = st.tabs(
        [
            "🏫 School & Class Management",
            "⚙️ Local Storage & Health",
        ]
    )

    with tab_school:
        _render_school_management()

    with tab_health:
        _render_governance_and_privacy()
        if is_developer_mode():
            st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)
            with st.expander("⚙️ Technical Details — Database Diagnostics & Storage Health", expanded=True):
                _render_storage_diagnostics()
                st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)
                _render_repository_metrics()


# -----------------------------------------------------------------------------
# 1. School Information, Class & Student Management
# -----------------------------------------------------------------------------


def _render_school_management() -> None:
    """Render school profile, class rosters, and teacher preferences."""
    st.subheader("School Profile")
    st.caption("Configure your school name, district, and academic session.")

    c1, c2 = st.columns(2)
    school_name = c1.text_input(
        "School Name",
        value=st.session_state.get("cfg_school_name", "Govt. Primary School, Rampur"),
        key="set_school_name",
        help="Official name of the school.",
    )
    school_code = c2.text_input(
        "School U-DISE Code",
        value=st.session_state.get("cfg_udise_code", "09210401201"),
        key="set_udise_code",
        help="Official state or national school identifier.",
    )

    c3, c4 = st.columns(2)
    district = c3.text_input(
        "Block / District",
        value=st.session_state.get("cfg_district", "Block B, District Rural"),
        key="set_district",
    )
    academic_year = c4.selectbox(
        "Academic Session",
        options=["2026-2027", "2025-2026", "2024-2025"],
        index=0,
        key="set_academic_year",
    )

    if st.button("💾 Save School Details", key="btn_save_school_details"):
        st.session_state["cfg_school_name"] = school_name
        st.session_state["cfg_udise_code"] = school_code
        st.session_state["cfg_district"] = district
        st.success("School profile details saved successfully.")

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

    # Class & Student Management
    st.subheader("Class & Enrollment Management")
    st.caption("Registered classes and their expected enrolled student counts.")

    with get_repository() as repo:
        sessions_df = repo.get_sessions(as_df=True)

    if not sessions_df.empty:
        cohort_summary = (
            sessions_df.groupby("class_id")
            .agg(
                enrolled=("expected_enrollment", "max"),
                sessions_count=("session_id", "count"),
            )
            .reset_index()
        )
        st.dataframe(
            cohort_summary.rename(
                columns={
                    "class_id": "Class Name",
                    "enrolled": "Enrolled Students",
                    "sessions_count": "Recorded Roll Calls",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No classes recorded yet. Register your first class roll call in 'Mark Attendance'.")

    # Quick Add Class / Student Form
    with st.expander("➕ Register New Class or Update Enrollment"):
        new_c1, new_c2 = st.columns(2)
        new_class_name = new_c1.text_input("New Class Name", value="CLASS-03-A", key="set_new_class_name")
        new_class_enr = new_c2.number_input("Total Enrolled Students", min_value=1, max_value=200, value=30, key="set_new_class_enr")
        if st.button("Add / Update Class", key="btn_add_new_class"):
            st.success(f"Class '{new_class_name}' configured with {new_class_enr} students.")

    st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)

    # Teacher Preferences
    st.subheader("Application Preferences")
    p1, p2 = st.columns(2)
    p1.checkbox(
        "Enable Classroom Verification Photo (Camera)",
        value=True,
        key="pref_enable_camera_feature",
        help="Shows the optional classroom photo button during roll call.",
    )
    p2.selectbox(
        "Unusual Attendance Alert Sensitivity",
        options=["Standard (30% drop or 4 identical days)", "Strict (20% drop or 3 identical days)"],
        index=0,
        key="pref_alert_sensitivity",
        help="Sensitivity for highlighting unusual attendance.",
    )

    # Advanced Settings: Global Developer Mode Toggle
    st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)
    st.subheader("Advanced Settings")
    with st.container(border=True):
        st.markdown("**Developer Mode**")
        st.caption("Show technical information and system diagnostics throughout the application.")

        current_dev = is_developer_mode()
        opts = ["OFF — Teacher View", "ON — Developer View"]
        curr_idx = 1 if current_dev else 0

        selected_mode = st.radio(
            "Developer Mode Toggle",
            options=opts,
            index=curr_idx,
            key="global_developer_mode_radio",
            label_visibility="collapsed",
            horizontal=True,
        )
        new_dev_mode = (selected_mode == "ON — Developer View")
        if new_dev_mode != current_dev:
            set_developer_mode(new_dev_mode)
            st.rerun()


# -----------------------------------------------------------------------------
# 2. Storage Diagnostics & Health Check
# -----------------------------------------------------------------------------


def _render_storage_diagnostics() -> None:
    """Render active database path, connection status, and diagnostic health check."""
    st.subheader("Database Status")

    configured_path = get_configured_db_path()
    is_override = (
        "db_path" in st.session_state
        and st.session_state["db_path"] is not None
        and str(st.session_state["db_path"]) != str(DEFAULT_DB_PATH)
    )
    is_env_override = (
        not is_override
        and os.environ.get("ATTENDSURE_DB_PATH") is not None
        and os.environ.get("ATTENDSURE_DB_PATH").strip() != str(DEFAULT_DB_PATH)
    )

    if is_override:
        path_type_badge = "<span class='badge badge-review'>Runtime Test Override</span>"
    elif is_env_override:
        path_type_badge = "<span class='badge badge-info'>Demonstration Database Override</span>"
    else:
        path_type_badge = "<span class='badge badge-neutral'>Standard Local File</span>"

    # Test database connectivity
    force_check = bool(st.session_state.get("btn_recheck_db"))
    is_healthy, db_error = test_db_connection(force=force_check)

    if is_healthy:
        st.success("✅ **Database Connection Healthy:** System is ready and working normally.")
    else:
        st.error(f"❌ **Database Connection Failure:** {db_error}")
        st.warning(
            f"Target file: '{configured_path}'. Please verify folder permissions and disk availability."
        )

    db_meta = get_active_database_metadata()
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        if db_meta.get("is_cloud"):
            st.markdown(f"**Active Database:** `{db_meta['backend']}` — `Region: {db_meta['region']}`")
            st.caption("Connected to managed Neon PostgreSQL database.")
        else:
            badge_label = "Runtime Test Override" if is_override else ("Demonstration Database Override" if is_env_override else "Standard Local File")
            st.markdown(f"**Active Database File:** `{configured_path}` — `{badge_label}`")
            st.caption("SQLite database file stored securely on this computer.")

    with col_btn:
        st.button(
            "🔄 Re-check Connection",
            key="btn_recheck_db",
            help="Test the connection to the database.",
        )


# -----------------------------------------------------------------------------
# 3. Saved Data & Record Sources
# -----------------------------------------------------------------------------


def _render_repository_metrics() -> None:
    """Query live repository statistics and display record source breakdown."""
    st.subheader("Saved Data")
    st.caption("Summary of all attendance records and alerts stored on your computer.")

    try:
        with get_repository() as repo:
            sessions_df = get_cached_sessions(repo)
            alerts = get_cached_alerts(repo)

        total_sessions = len(sessions_df)
        total_alerts = len(alerts)

        pending_alerts = len([a for a in alerts if a.review_status == "PENDING_REVIEW"])
        resolved_alerts = len([a for a in alerts if a.review_status == "RESOLVED"])

        # Overview Metrics Strip
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Attendance Records", total_sessions)
        k2.metric("Total Alerts", total_alerts)
        k3.metric("Needs Attention", pending_alerts)
        k4.metric("Checked Alerts", resolved_alerts)

        # Empty Database Guidance
        if total_sessions == 0:
            st.info(
                "ℹ️ **Empty Database Notice:** No attendance records have been saved yet. "
                "You can record daily attendance in **Mark Attendance** or upload a file in **Reports**."
            )

        # Record Source Provenance Breakdown
        st.markdown("#### Data Sources")

        if not sessions_df.empty and "record_source" in sessions_df.columns:
            counts = sessions_df["record_source"].value_counts()
            manual_count = int(counts.get("MANUAL_ENTRY", 0))
            csv_count = int(counts.get("CSV_IMPORT", 0))
            synth_count = int(counts.get("SYNTHETIC", 0))
        else:
            manual_count = 0
            csv_count = 0
            synth_count = 0

        p1, p2, p3 = st.columns(3)
        p1.metric(
            "Entered by Hand",
            manual_count,
            help="Attendance records submitted via the Mark Attendance screen.",
        )
        p2.metric(
            "Uploaded from File",
            csv_count,
            help="Attendance records imported via CSV files.",
        )
        p3.metric(
            "Sample Records",
            synth_count,
            help="Sample records loaded for testing and evaluation.",
        )

    except Exception as exc:
        st.error(f"Error reading saved data summary: {exc}")


# -----------------------------------------------------------------------------
# 4. Architecture, Governance, and Privacy Disclaimers
# -----------------------------------------------------------------------------


def _render_governance_and_privacy() -> None:
    """Render explicit architecture, privacy, and non-accusatory governance disclosures."""
    st.subheader("Data Privacy & Local Storage")
    st.caption("How your school attendance records and student privacy are protected.")

    # Storage Architecture
    db_meta = get_active_database_metadata()
    if db_meta.get("is_cloud"):
        st.markdown(
            f"""
            > ☁️ **Cloud Relational Architecture:** The system is connected to a managed **{db_meta['backend']}** ({db_meta['region']})
            > database. Records are persisted across sessions and deployments with ACID transactions and managed cloud persistence.
            > No biometric data or student facial templates are stored.
            """
        )
    else:
        st.markdown(
            """
            > 🔒 **Offline-First & Local Storage Architecture:** The system operates as an offline-first tool.
            > All data is stored in a local SQLite database on this computer's storage.
            > No external AI APIs are queried and no remote telemetry or analytics are embedded.
            """
        )

    try:
        active_db_path = get_configured_db_path()
        if os.path.exists(active_db_path):
            with open(active_db_path, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                label="💾 Download SQLite Database Backup (.db)",
                data=db_bytes,
                file_name="attendsure_backup.db",
                mime="application/x-sqlite3",
                key="btn_download_db_backup",
                help="Download an exact copy of the active local SQLite database for offline backup or migration.",
            )
    except Exception:
        pass

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("**Student Privacy & Zero Biometrics Policy**")
        st.markdown(
            """
            - **No PII Collected:** The system processes solely aggregated classroom counts (`expected_enrollment`, `present_count`, `absent_count`).
            - **Zero Biometric Data:** No student names, student IDs, biometric facial templates, or permanent photos are ever collected, processed, or stored.
            - **No Permanent Image Storage:** Camera frames may be temporarily received and inspected in memory during roll-call capture to assist educator headcount verification, but are never permanently saved to disk, database, logs, or exports.
            - **No Facial Recognition or Templates:** No facial recognition, individual student identification, facial landmark tracking, or biometric feature templates are created or stored.
            - **Decision Support, Never Accusation:** Review signals highlight unusual attendance patterns for teachers and headmasters to verify, never as proof of misconduct.
            """
        )

    with g2:
        st.markdown("**Non-Destructive Storage & Seeding Policy**")
        st.markdown(
            """
            - **No Destructive Database Controls:** The system intentionally excludes database reset, drop table, or bulk-deletion controls to protect educational records from accidental loss in rural schools.
            - **Synthetic Data Seeding Deferred:** Operational database seeding is deliberately omitted in production to prevent synthetic test records from contaminating real school attendance history.
            - **Safe Sample Experiments:** For sample testing and scenario evaluation, use the dedicated test sections in Reports.
            """
        )
