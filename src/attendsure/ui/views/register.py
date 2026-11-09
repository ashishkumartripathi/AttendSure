"""Attendance Register view for AttendSure.

Provides manual roll-call entry, simulated camera headcount verification,
historical session inspection, and batch CSV ingestion adhering to
docs/data-contract.md.
Refined with the Pastel Green modern dashboard design language.
"""

from datetime import date, datetime
import io
import sqlite3
from typing import Optional

import pandas as pd
import streamlit as st

from attendsure.data.csv_io import CsvImportResult, import_sessions_from_csv
from attendsure.data.models import WebcamCounterResult
from attendsure.data.webcam import get_simulated_webcam_count
from attendsure.data.webcam_capture import create_webcam_capture_event
from attendsure.ml.predictor import evaluate_session_ml
from attendsure.services.attendance_service import (
    record_session_with_detection,
    validate_manual_session,
)
from attendsure.ui.dev_mode import is_developer_mode
from attendsure.ui.state import get_repository


def render_register() -> None:
    """Render the primary Attendance screen."""
    st.header("Mark Attendance")
    st.caption("Record how many students attended class today with optional visual confirmation.")

    tab_entry, tab_history, tab_csv = st.tabs(
        [
            "📝 Record Attendance",
            "📋 Recent Attendance",
            "📁 Upload Attendance File",
        ]
    )

    with tab_entry:
        _render_roll_call_entry()

    with tab_history:
        _render_historical_register()

    with tab_csv:
        _render_csv_import()


# -----------------------------------------------------------------------------
# Tab 1: Daily Roll Call Entry & Simulated Camera Verification
# -----------------------------------------------------------------------------


def _render_roll_call_entry() -> None:
    """Render the teacher-friendly daily roll-call entry form with optional classroom photo."""
    st.subheader("Record Attendance")
    st.caption("Record attendance for your class in a few simple steps.")

    # -------------------------------------------------------------------------
    # Steps 1 & 2: Select Class & Date
    # -------------------------------------------------------------------------
    col1, col2 = st.columns(2)
    class_id = col1.text_input(
        "Class",
        value="CLASS-01-A",
        help="Class name or code (e.g. CLASS-01-A, Grade 5B).",
        key="manual_class_id",
    )
    session_date = col2.date_input(
        "Date",
        value=datetime.now().date(),
        help="Date of the class.",
        key="manual_session_date",
    )

    # -------------------------------------------------------------------------
    # Steps 3 & 4: Total Students & Interactive Roster Check
    # -------------------------------------------------------------------------
    col3, col4, col5 = st.columns(3)
    expected_enrollment = col3.number_input(
        "Total Students",
        min_value=1,
        max_value=500,
        value=30,
        step=1,
        help="Total number of students enrolled in this class.",
        key="manual_expected_enrollment",
    )

    present_count = col4.number_input(
        "Present Today",
        min_value=0,
        max_value=500,
        value=25,
        step=1,
        help="Number of students present in class today.",
        key="manual_present_count",
    )

    # Calculate absent count automatically: enrollment - present
    calc_absent = max(0, int(expected_enrollment) - int(present_count))
    st.session_state["manual_absent_count_display"] = calc_absent
    col5.number_input(
        "Absent Today (Automatic)",
        value=calc_absent,
        disabled=True,
        help="Calculated automatically: Total Students minus Present Today.",
        key="manual_absent_count_display",
    )

    if int(present_count) > int(expected_enrollment):
        st.warning(
            f"Present count ({present_count}) cannot be greater than total students ({expected_enrollment}). "
            "Please check the numbers before saving."
        )

    # Quick Roster Helper
    with st.expander("📋 Student Roll Call Helper (Optional Quick Check)", expanded=False):
        st.caption("Quickly mark students present or absent from the class roster.")
        r_col1, r_col2 = st.columns(2)
        if r_col1.button("✅ Mark All Present", key="btn_quick_all_present", use_container_width=True):
            st.session_state["manual_present_count"] = int(expected_enrollment)
            st.rerun()
        if r_col2.button("❌ Mark All Absent", key="btn_quick_all_absent", use_container_width=True):
            st.session_state["manual_present_count"] = 0
            st.rerun()

    # -------------------------------------------------------------------------
    # Step 5: Simple Attendance Summary
    # -------------------------------------------------------------------------
    enr_val = int(expected_enrollment)
    pres_val = int(present_count)
    rate_val = (pres_val / enr_val * 100.0) if enr_val > 0 else 0.0

    st.markdown(
        f"""
        <div style="background: #F4F8F3; border: 1px solid #DCEBD8; border-radius: 12px; padding: 12px 18px; margin: 12px 0 16px 0;">
            <div style="font-size: 0.90rem; font-weight: 700; color: #174A32; margin-bottom: 4px;">
                📊 Attendance Summary for Class {class_id}
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 20px; font-size: 0.85rem; color: #20352A;">
                <span>Total Enrolled: <strong>{enr_val}</strong></span>
                <span>Present: <strong style="color: #237A50;">{pres_val}</strong></span>
                <span>Absent: <strong style="color: #A51D24;">{calc_absent}</strong></span>
                <span>Attendance Rate: <strong>{rate_val:.1f}%</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # Step 6: Classroom Verification Photo (Optional)
    # -------------------------------------------------------------------------
    st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 1.25rem 0 1rem 0;' />", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
            <h3 style="margin: 0; font-size: 1.05rem; color: #173F2D; font-weight: 600;">📷 Classroom Verification Photo (Optional)</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Take a classroom photo if you want to keep a visual record. Confirm the student count yourself.")

    camera_photo = st.camera_input("Take classroom verification photo", key="camera_input_photo")
    if camera_photo is not None:
        st.image(camera_photo, width=280, caption="Classroom verification photo (in-memory only, no student photos saved)")
        try:
            create_webcam_capture_event(
                class_id=str(class_id),
                session_date=str(session_date),
                status="SUCCESS",
                confirmed_headcount=int(present_count),
                image_bytes=camera_photo.getvalue(),
                expected_enrollment=int(expected_enrollment),
            )
            st.info(f"Visual Confirmation: Headcount confirmed by teacher ({present_count} students present).")
        except Exception as exc:
            st.caption(f"Photo note: {exc}")

    # Background decision tree inference (executed cleanly without cluttering teacher UI)
    ml_eval_result = None
    try:
        with get_repository() as repo:
            cohort_history_df = repo.get_sessions(class_id=class_id.strip() if isinstance(class_id, str) else str(class_id), as_df=True)
        ml_eval_result = evaluate_session_ml(
            class_id=str(class_id),
            enrollment=int(expected_enrollment),
            present=int(present_count),
            history_df=cohort_history_df,
        )
    except Exception:
        pass

    # Developer View: ML pre-save features, model prediction, and camera simulation test controls
    webcam_result: Optional[WebcamCounterResult] = None
    enable_camera: bool = False
    if is_developer_mode():
        with st.expander("⚙️ Technical Details — Developer View: ML Pre-Check & Camera Simulation", expanded=False):
            st.markdown("#### Machine Learning Feature Extraction & Pre-Save Prediction")
            if ml_eval_result is not None:
                p1, p2, p3 = st.columns(3)
                p1.metric("Predicted Status", ml_eval_result.prediction)
                p2.metric("ML Confidence", f"{ml_eval_result.confidence_score:.1%}")
                p3.metric("Extracted Features", len(ml_eval_result.feature_values))
                st.caption(f"Reasoning: {ml_eval_result.explanation}")
                st.json(ml_eval_result.feature_values)
            else:
                st.caption("ML inference not available for current inputs.")

            st.markdown("<hr style='border: none; border-top: 1px solid #E2E9DF; margin: 10px 0;' />", unsafe_allow_html=True)
            st.markdown("#### Secondary Camera Simulation Check")
            enable_camera = st.checkbox(
                "Include Sample Headcount Check (Camera Simulation)",
                value=False,
                key="manual_enable_camera",
                help="Simulate a secondary headcount comparison for testing.",
            )
            if enable_camera:
                c_mode, c_info = st.columns([1, 2])
                sim_labels = {
                    "NORMAL": "Normal (Counts Match)",
                    "DISCREPANCY": "Difference (Counts Don't Match)",
                    "CAMERA_OFFLINE": "Camera Offline",
                    "CAMERA_UNAVAILABLE": "Camera Unavailable",
                    "DETECTION_FAILED": "Check Failed",
                }
                sim_mode = c_mode.selectbox(
                    "Sample Situation",
                    options=["NORMAL", "DISCREPANCY", "CAMERA_OFFLINE", "CAMERA_UNAVAILABLE", "DETECTION_FAILED"],
                    format_func=lambda m: sim_labels.get(m, m),
                    index=0,
                    help="Choose a test scenario to see how the system compares counts.",
                    key="manual_sim_mode",
                )
                ref_present = max(0, int(present_count))
                webcam_result = get_simulated_webcam_count(
                    mode=sim_mode,
                    reference_present=ref_present,
                )
                with c_info:
                    st.caption(f"Headcount Status: {webcam_result.status}")

    # -------------------------------------------------------------------------
    # Save Attendance
    # -------------------------------------------------------------------------
    save_clicked = st.button(
        "Save Attendance",
        type="primary",
        key="btn_save_roll_call",
    )

    if save_clicked:
        enr = int(expected_enrollment)
        pres = int(present_count)
        recalculated_absent = enr - pres

        if enr < 1:
            st.error("Validation Error: Expected enrollment must be greater than zero.")
            return

        if pres < 0:
            st.error("Validation Error: Present count cannot be negative.")
            return

        if pres > enr:
            st.error(
                f"Validation Error: Present count ({pres}) cannot exceed expected enrollment ({enr}). "
                "Present count must be between zero and expected enrollment."
            )
            return

        if pres + recalculated_absent != enr:
            st.error(
                f"Validation Error: Count invariant violation: present ({pres}) + absent ({recalculated_absent}) != enrollment ({enr})."
            )
            return

        # Determine webcam status: simulation takes precedence if enabled, else real photo confirmation
        if enable_camera and webcam_result:
            wb_status = webcam_result.status
            wb_count = webcam_result.estimated_count
        elif camera_photo is not None:
            wb_status = "SUCCESS"
            wb_count = pres
        else:
            wb_status = "NOT_ATTEMPTED"
            wb_count = None

        candidate_data = {
            "class_id": class_id.strip() if isinstance(class_id, str) else str(class_id),
            "session_date": str(session_date),
            "expected_enrollment": enr,
            "present_count": pres,
            "absent_count": recalculated_absent,
            "webcam_status": wb_status,
            "webcam_count": wb_count,
            "record_source": "MANUAL_ENTRY",
        }

        val_result = validate_manual_session(candidate_data)
        if not val_result.is_valid:
            for err in val_result.errors:
                st.error(f"Validation Error: {err}")
            return

        try:
            with get_repository() as repo:
                session, alerts = record_session_with_detection(
                    repo=repo,
                    data=candidate_data,
                    run_detection=True,
                )

            st.success(
                f"Attendance session recorded successfully for cohort '{session.class_id}' on {session.session_date}."
            )
            if alerts:
                st.warning(
                    f"Notice: Generated {len(alerts)} review signal(s) requiring verification. "
                    f"You can review this record in 'Needs Attention'."
                )
                for alert in alerts:
                    st.info(f"Signal: {alert.rule_title} — {alert.explanation}")
            else:
                st.caption("Attendance counts are within normal patterns.")

        except sqlite3.IntegrityError:
            st.error(
                f"Database Collision: A session record for cohort '{candidate_data['class_id']}' on date '{candidate_data['session_date']}' "
                "already exists in the database. Existing records are never overwritten."
            )
        except ValueError as exc:
            st.error(f"Validation Error: {exc}")
        except Exception as exc:
            st.error(f"An unexpected error occurred while persisting the record: {exc}")

    # -------------------------------------------------------------------------
    # Guidance Section
    # -------------------------------------------------------------------------
    with st.expander("ℹ️ Attendance Guidelines"):
        st.markdown(
            """
            <div style="font-size: 0.88rem; color: #20352A; line-height: 1.55;">
                • <strong>Total Students:</strong> <code>Present + Absent = Total Students</code>. Absent count is calculated automatically.<br>
                • <strong>One Record Per Day:</strong> Each class has one attendance record per day. Saved records are protected against accidental overwriting.<br>
                • <strong>Helpful Reminders:</strong> If a class has an unusual attendance drop, the system flags it for review in 'Needs Attention' so teachers can double-check.
            </div>
            """,
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# Tab 2: Recent Attendance
# -----------------------------------------------------------------------------


def _render_historical_register() -> None:
    """Render historical session logs with class and date range filtering."""
    st.subheader("Recent Attendance")
    st.caption("Review and filter attendance records across classes.")

    try:
        with get_repository() as repo:
            all_sessions = repo.get_sessions(as_df=True)
    except Exception as exc:
        st.error(f"Unable to access the local attendance database: {exc}")
        return

    if all_sessions.empty:
        st.info(
            "No attendance records found in the database. "
            "Use 'Record Attendance' or 'Upload Attendance File' to add records."
        )
        return

    # Extract available classes for filter dropdown
    available_classes = ["All Classes"] + sorted(all_sessions["class_id"].unique().tolist())

    col_filter1, col_filter2 = st.columns([1, 1])
    selected_class = col_filter1.selectbox(
        "Filter by Class",
        options=available_classes,
        index=0,
        key="hist_cohort_filter",
    )

    use_date_filter = col_filter2.checkbox(
        "Filter by Date Range",
        value=False,
        key="hist_enable_date_filter",
    )

    start_date_filter: Optional[str] = None
    end_date_filter: Optional[str] = None
    invalid_date_range = False

    if use_date_filter:
        col_d1, col_d2 = st.columns(2)
        min_date_str = str(all_sessions["session_date"].min())
        max_date_str = str(all_sessions["session_date"].max())
        min_date_obj = datetime.strptime(min_date_str, "%Y-%m-%d").date()
        max_date_obj = datetime.strptime(max_date_str, "%Y-%m-%d").date()

        start_val = col_d1.date_input(
            "Start Date",
            value=min_date_obj,
            key="hist_start_date_val",
        )
        end_val = col_d2.date_input(
            "End Date",
            value=max_date_obj,
            key="hist_end_date_val",
        )
        if start_val > end_val:
            st.warning("Start Date cannot be after End Date. Please adjust the date filter.")
            invalid_date_range = True
        else:
            start_date_filter = str(start_val)
            end_date_filter = str(end_val)

    if invalid_date_range:
        st.info("No attendance sessions displayed due to an invalid date range.")
        return

    # Query filtered sessions via repository API
    class_id_param = None if selected_class in ("All Classes", "All Cohorts") else selected_class
    try:
        with get_repository() as repo:
            filtered_sessions = repo.get_sessions(
                class_id=class_id_param,
                start_date=start_date_filter,
                end_date=end_date_filter,
                as_df=True,
            )
    except Exception as exc:
        st.error(f"Error querying filtered attendance records: {exc}")
        return

    if filtered_sessions.empty:
        st.info("No attendance sessions match the selected filters.")
        return

    # Sort recent sessions first
    filtered_sessions = filtered_sessions.sort_values(
        by=["session_date", "class_id"], ascending=[False, True]
    ).copy()

    # Calculate attendance rate safely
    def _calc_rate(row) -> str:
        enrollment = row.get("expected_enrollment", 0)
        present = row.get("present_count", 0)
        if isinstance(enrollment, int) and enrollment > 0:
            return f"{(present / enrollment * 100.0):.1f}%"
        return "N/A"

    filtered_sessions["Rate"] = filtered_sessions.apply(_calc_rate, axis=1)

    # Summary metrics for the active filter selection
    total_matching = len(filtered_sessions)
    sum_present = int(filtered_sessions["present_count"].sum())
    sum_enrollment = int(filtered_sessions["expected_enrollment"].sum())
    overall_rate_str = (
        f"{(sum_present / sum_enrollment * 100.0):.1f}%" if sum_enrollment > 0 else "N/A"
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Matching Sessions", total_matching)
    m2.metric("Total Present", sum_present)
    m3.metric("Attendance Rate", overall_rate_str)

    # Format table for display
    display_cols = [
        "class_id",
        "session_date",
        "expected_enrollment",
        "present_count",
        "absent_count",
        "Rate",
        "webcam_status",
        "webcam_count",
        "record_source",
    ]
    display_df = filtered_sessions[display_cols].rename(
        columns={
            "class_id": "Class",
            "session_date": "Date",
            "expected_enrollment": "Total Students",
            "present_count": "Present",
            "absent_count": "Absent",
            "Rate": "Attendance Rate",
            "webcam_status": "Headcount Check",
            "webcam_count": "Headcount Count",
            "record_source": "Source",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# Tab 3: Upload Attendance File
# -----------------------------------------------------------------------------


def _render_csv_import() -> None:
    """Render batch CSV file upload and ingestion interface."""
    st.subheader("Upload Attendance File")
    st.caption("Upload attendance records from a CSV file.")

    st.markdown(
        """
        <div style="background-color: #EAF2E6; border: 1px solid #DCEBD8; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;">
            <strong style="color: #173F2D; font-size: 0.92rem;">CSV File Format:</strong>
            <ul style="margin: 6px 0 0 18px; padding: 0; font-size: 0.88rem; color: #20352A; line-height: 1.55;">
                <li><strong>Required columns:</strong> <code>class_id</code>, <code>session_date</code>, <code>expected_enrollment</code>, <code>present_count</code>, <code>absent_count</code>.</li>
                <li><strong>Calculation check:</strong> <code>present_count + absent_count</code> must equal <code>expected_enrollment</code>.</li>
                <li><strong>Safe import:</strong> Existing attendance records will never be overwritten or deleted.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Support testing override via st.session_state["test_uploaded_file"] or standard uploader
    test_upload = st.session_state.get("test_uploaded_file", None)
    uploaded_file = test_upload or st.file_uploader(
        "Select Attendance CSV File to Upload",
        type=["csv"],
        key="csv_file_uploader",
        help="Upload standard RFC 4180 CSV file with attendance session records.",
    )

    allow_partial = st.checkbox(
        "Allow partial import (import valid records and skip invalid rows)",
        value=False,
        key="chk_allow_partial",
        help="When unchecked (default), uses an all-or-nothing transaction. If checked, imports all valid non-colliding rows.",
    )

    import_button = st.button(
        "Process CSV Import",
        type="primary",
        key="btn_process_csv",
        disabled=(uploaded_file is None),
    )

    if import_button and uploaded_file is not None:
        try:
            # Ensure file pointer is reset to beginning
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)

            with get_repository() as repo:
                result = import_sessions_from_csv(
                    repo=repo,
                    csv_source=uploaded_file,
                    allow_partial=allow_partial,
                )

            st.session_state["csv_import_result"] = result
            st.session_state.pop("csv_import_error", None)

        except ValueError as val_err:
            st.session_state["csv_import_error"] = str(val_err)
            st.session_state.pop("csv_import_result", None)
        except Exception as exc:
            st.session_state["csv_import_error"] = f"Unexpected CSV processing error: {exc}"
            st.session_state.pop("csv_import_result", None)

    # Display results from the most recent import execution
    if "csv_import_error" in st.session_state:
        st.error(st.session_state["csv_import_error"])

    elif "csv_import_result" in st.session_state:
        res: CsvImportResult = st.session_state["csv_import_result"]

        if res.total_rows == 0:
            st.info("The uploaded CSV file contains no data rows.")
        else:
            # Outcome banner
            if res.failed_count == 0:
                st.success(
                    f"Import completed successfully! All {res.imported_count} record(s) imported into database."
                )
            elif res.imported_count == 0:
                st.error(
                    f"Import failed: 0 of {res.total_rows} record(s) imported. "
                    f"All {res.failed_count} row(s) failed validation or collided with existing records."
                )
            else:
                st.warning(
                    f"Partial import completed: {res.imported_count} record(s) imported, "
                    f"{res.failed_count} record(s) rejected."
                )

            # Concise summary metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Rows Processed", res.total_rows)
            m2.metric("Successfully Imported", res.imported_count)
            m3.metric("Rejected / Collisions", res.failed_count)

            # Expandable row-level errors
            if res.errors:
                with st.expander(
                    f"View Rejected Rows & Detailed Errors ({len(res.errors)})",
                    expanded=True,
                ):
                    error_rows = []
                    for e in res.errors:
                        error_rows.append(
                            {
                                "Line #": e.line_number,
                                "Row Index": e.row_index + 1,
                                "Cohort": e.class_id or "(Missing)",
                                "Date": e.session_date or "(Missing)",
                                "Validation Errors / Collisions": "; ".join(e.errors),
                            }
                        )
                    st.dataframe(pd.DataFrame(error_rows), use_container_width=True, hide_index=True)

            if res.warnings:
                for w in res.warnings:
                    st.warning(w)

    # -------------------------------------------------------------------------
    # Progressive Disclosure Tier 3: Advanced View (CSV Specifications)
    # -------------------------------------------------------------------------
    with st.expander("⚙️ Advanced View: CSV Schema & Collision Handling Specifications"):
        st.markdown(
            """
            <div style="font-size: 0.85rem; color: #20352A; line-height: 1.55;">
                • <strong>RFC 4180 Compliance:</strong> Standard CSV format with UTF-8 encoding.<br>
                • <strong>Required Columns:</strong> <code>class_id</code>, <code>session_date</code> (YYYY-MM-DD), <code>expected_enrollment</code>, <code>present_count</code>, <code>absent_count</code>.<br>
                • <strong>Collision Policy:</strong> Non-destructive: if a class already has a record for that date, it is rejected and not overwritten.
            </div>
            """,
            unsafe_allow_html=True,
        )
