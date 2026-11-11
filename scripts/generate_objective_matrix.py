"""Generates the authoritative Objective Fulfilment Matrix in both CSV and XLSX formats.

Strictly adheres to the 6-column schema:
1. Original Objective
2. Implemented Functionality
3. Evidence (File / Module)
4. Validation Method & Result
5. Status (Fulfilled / Partially Fulfilled / Not Fulfilled)
6. Remaining Limitation
"""

from pathlib import Path
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_CSV = WORKSPACE_DIR / "submission" / "references" / "Objective_Fulfilment_Matrix.csv"
OUTPUT_XLSX = WORKSPACE_DIR / "submission" / "references" / "Objective_Fulfilment_Matrix.xlsx"

MATRIX_DATA = [
    {
        "Original Objective": "Objective 1: Low-Cost Camera Capture Pipeline Suited to Rural Infrastructure",
        "Implemented Functionality": "Browser-based camera photo capture via st.camera_input with in-memory non-biometric silhouette estimation (FO-VCE) and automated image quality pre-screening (Laplacian blur variance, luminance, resolution). No student photographs or biometric templates are stored on disk or database. When estimation is uncertain, educator manual roll call count is strictly retained as the authoritative default.",
        "Evidence (File / Module)": "src/attendsure/ui/views/register.py, src/attendsure/data/person_estimator.py, src/attendsure/data/camera_quality.py, src/attendsure/data/webcam_capture.py",
        "Validation Method & Result": "Automated unit and integration tests (tests/test_person_estimator.py, tests/test_camera_quality.py, tests/test_ui_register.py). 23 tests passed. Clean silhouette MAE=0.00; 7-case benchmark MAE=0.14; 6-case quality suite verified.",
        "Status": "Partially Fulfilled",
        "Remaining Limitation": "Automated counting is experimental and unvalidated for real-world classrooms; low lighting (<40 lux) or crowded benches cause optical occlusions. Educator manual roll call remains authoritative."
    },
    {
        "Original Objective": "Objective 1: Low-Cost RFID Capture Pipeline Suited to Rural Infrastructure",
        "Implemented Functionality": "Forward-compatible database schema columns (record_source='NFC_SCAN', device_id), IRFIDProvider interface abstraction, and documented hardware integration specification.",
        "Evidence (File / Module)": "src/attendsure/data/models.py, docs/nfc-rfid-integration-scope.md, src/attendsure/data/storage.py",
        "Validation Method & Result": "Schema serialization tests in tests/test_data_models.py and tests/test_db_persistence.py. All passed.",
        "Status": "Not Fulfilled (Formally Deferred)",
        "Remaining Limitation": "Physical RFID/NFC card reader hardware is formally deferred due to rural pupil card loss, maintenance overhead, cost constraints, and vulnerability to buddy-punching proxy fraud."
    },
    {
        "Original Objective": "Objective 2: Anomaly Detection to Flag Implausible Attendance Patterns (Deterministic Production Rules)",
        "Implemented Functionality": "Three deterministic expert production rules (RULE_ATTENDANCE_DROP, RULE_REPEATED_HEADCOUNT, RULE_WEBCAM_DISCREPANCY) producing structured human-interpretable explanations with observed values, baselines, and plain rationales.",
        "Evidence (File / Module)": "src/attendsure/detection/rules.py, src/attendsure/detection/rules_drop.py, src/attendsure/detection/rules_streak.py, src/attendsure/detection/rules_webcam.py",
        "Validation Method & Result": "Standard Preset benchmark (5 classes x 30 days = 150 sessions, seed=42): TP=6, FP=0, TN=139, FN=5 (streak prefix), Accuracy=96.67%, Precision=100.0% (synthetic preset), Event Recall=100.0% (2 of 2 multi-day episodes flagged); 56 unit/integration tests passed.",
        "Status": "Fulfilled",
        "Remaining Limitation": "Evaluated strictly on synthetic benchmark distributions; 100% precision on synthetic scenarios does not guarantee zero false alerts in live school operation with local festivals or weather."
    },
    {
        "Original Objective": "Objective 2: Anomaly Detection to Flag Implausible Attendance Patterns (Supervised Machine Learning)",
        "Implemented Functionality": "Supervised DecisionTreeClassifier (max_depth=4, min_samples_leaf=4, class_weight='balanced') trained on 6 causal features; dual-stream decision fusion with expert rules for nuanced pattern flagging.",
        "Evidence (File / Module)": "src/attendsure/ml/model.py, src/attendsure/ml/predictor.py, src/attendsure/ml/features.py",
        "Validation Method & Result": "88-session independent test cohort (4 unseen classes, 3-day history burn-in): Accuracy=92.05%, Recall=80.00%, Specificity=92.77%, Precision=40.00%, F1=53.33%; 9 tests in tests/test_ml_decision_tree.py passed.",
        "Status": "Fulfilled",
        "Remaining Limitation": "Validated on synthetic cohort data only; real-world attendance patterns with weather and local agricultural cycles require live school calibration."
    },
    {
        "Original Objective": "Objective 3: Compliance-Oriented Reporting Dashboard",
        "Implemented Functionality": "6-page Streamlit application with Progressive Disclosure (Simple View vs. Developer Diagnostic View), PBKDF2 authentication, Neon PostgreSQL cloud database with SQLite local fallback, RFC 4180 CSV export/import with atomic rollback, and structured review triage.",
        "Evidence (File / Module)": "src/attendsure/ui/app.py, src/attendsure/ui/views/, src/attendsure/ui/auth.py, src/attendsure/data/csv_io.py, src/attendsure/data/db_engine.py",
        "Validation Method & Result": "Headless Streamlit AppTest suites across all 6 screens (84 UI tests in tests/test_ui_*.py). All passed. Verified atomic rollback on constraint violation and sub-second query caching.",
        "Status": "Partially Fulfilled",
        "Remaining Limitation": "The reporting interface is complete, but it has been validated against multi-week synthetic cohorts rather than a live school pilot period; dashboard does not confer statutory legal compliance."
    },
    {
        "Original Objective": "Objective 3: Validation Against a Pilot Period",
        "Implemented Functionality": "Multi-week longitudinal synthetic cohort generator (generate_independent_ml_dataset, create_train_test_split) simulating nominal and disruption dynamics across 300 sessions in 12 cohorts.",
        "Evidence (File / Module)": "src/attendsure/data/generator.py, src/attendsure/ml/dataset.py",
        "Validation Method & Result": "Evaluated across 300 synthetic sessions in 12 cohorts (200 training sessions across 8 classes [176 valid features after 3-day history burn-in], 100 test sessions across 4 unseen classes [88 valid features]).",
        "Status": "Not Fulfilled",
        "Remaining Limitation": "Real-world school pilot trial was NOT conducted; field pilot validation remains future work."
    }
]


def generate_matrix():
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(MATRIX_DATA)

    # 1. Export CSV
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Objective Fulfilment Matrix CSV generated: {OUTPUT_CSV}")

    # 2. Export Styled Excel (.xlsx)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Objective Fulfilment Matrix"

    # Styling Palettes (Modern Forest Theme)
    fill_header = PatternFill(start_color="173F2D", end_color="173F2D", fill_type="solid")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_body = Font(name="Calibri", size=10, color="20352A")
    font_bold = Font(name="Calibri", size=10, bold=True, color="174A32")

    fill_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    fill_odd = PatternFill(start_color="F4F7F4", end_color="F4F7F4", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="DCE5DA"),
        right=Side(style="thin", color="DCE5DA"),
        top=Side(style="thin", color="DCE5DA"),
        bottom=Side(style="thin", color="DCE5DA")
    )

    headers = list(df.columns)
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    status_colors = {
        "Fulfilled": "E8F5E9",
        "Partially Fulfilled": "FFF9C4",
        "Not Fulfilled": "FFEBEE",
        "Not Fulfilled (Formally Deferred)": "F5F5F5"
    }

    for row_idx, row_data in enumerate(df.values, start=2):
        ws.append(list(row_data))
        row_fill = fill_odd if row_idx % 2 == 1 else fill_even
        status_val = str(row_data[4])

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = font_body
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

            if col_idx == 5:  # Status column
                cell.font = font_bold
                bg = status_colors.get(status_val, "FFFFFF")
                cell.fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            else:
                cell.fill = row_fill

        ws.row_dimensions[row_idx].height = 70

    col_widths = {1: 22, 2: 36, 3: 24, 4: 36, 5: 18, 6: 34}
    for col_idx, width in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    ws.freeze_panes = "A2"
    wb.save(OUTPUT_XLSX)
    print(f"Objective Fulfilment Matrix XLSX generated: {OUTPUT_XLSX}")


if __name__ == "__main__":
    generate_matrix()
