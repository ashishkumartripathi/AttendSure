#!/usr/bin/env python3
"""Comprehensive Academic Project Report Generator for AttendSure.

Generates the complete 33-chapter academic report in DOCX format:
`submission/report/Rural_School_Attendance_System_Final_Report.docx`
and automatically converts it to PDF using Microsoft Word COM automation:
`submission/report/Rural_School_Attendance_System_Final_Report.pdf`.

Conforms strictly to:
- Official Project Title: Rural School Attendance Integrity and Intervention Decision System
- Project Mentor: Mr. Hitesh Jangid
- Authors: Ashish Kumar Tripathi (Reg No. 12509400, Roll No. 21) & Harsh Jakhar (Reg No. 12517556, Roll No. 8)
- Problem Statement: Smart India Hackathon 2025: SIH25012 (Govt of Punjab, Higher Education)
- Repository: https://github.com/ashishkumartripathi/AttendSure
- Metrics: Verified 100% against docs/technical_evaluation_report.md
"""

from datetime import datetime
import os
from pathlib import Path
import sys

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = REPO_ROOT / "submission"
OUTPUT_DOCX = SUBMISSION_DIR / "report" / "Rural_School_Attendance_System_Final_Report.docx"
OUTPUT_PDF = SUBMISSION_DIR / "report" / "Rural_School_Attendance_System_Final_Report.pdf"
SCREENSHOTS_DIR = SUBMISSION_DIR / "screenshots"

# Palette: Academic Forest & Sage Green Theme
COLOR_DARK_GREEN = RGBColor(23, 74, 50)    # #174A32 Primary header
COLOR_FOREST = RGBColor(35, 122, 80)       # #237A50 Accent green
COLOR_SAGE = RGBColor(71, 125, 80)         # #477D50 Secondary accent
COLOR_DARK_TEXT = RGBColor(33, 37, 41)     # #212529 Dark charcoal body
COLOR_MUTED = RGBColor(108, 117, 125)      # #6C757D Muted gray
COLOR_LIGHT_BG = "F4F7F4"                  # Soft Mint table header
COLOR_BORDER = "DCE5DA"                    # Border gray
COLOR_CALLOUT_BG = "F0F5F1"                # Callout background


def set_cell_background(cell, hex_color: str):
    """Sets background shading of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{hex_color}"/>')
    tc_pr.append(shd)


def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    """Sets internal padding for a table cell in dxa (1/20 pt)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)


def add_custom_heading(doc, text: str, level: int):
    """Adds a styled heading conforming to the academic green palette."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    if level == 1:
        run.font.size = Pt(18)
        run.font.color.rgb = COLOR_DARK_GREEN
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True
    elif level == 2:
        run.font.size = Pt(13.5)
        run.font.color.rgb = COLOR_FOREST
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
    elif level == 3:
        run.font.size = Pt(11)
        run.font.color.rgb = COLOR_SAGE
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
    return p


def add_callout(doc, text: str, title: str = "CORE ARCHITECTURAL PRINCIPLE"):
    """Adds a highlighted callout box with a colored border and soft background."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, COLOR_CALLOUT_BG)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)

    # Set left thick border
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="237A50"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    run_t = p.add_run(f"[{title}]\n")
    run_t.bold = True
    run_t.font.size = Pt(9.5)
    run_t.font.color.rgb = COLOR_FOREST

    run_b = p.add_run(text)
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = COLOR_DARK_TEXT

    # Empty paragraph after table for spacing
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)


def format_table(tbl, col_widths, headers, data_rows):
    """Formats a table with pastel green headers, alternating rows, and proper padding."""
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    # Header Row
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = Inches(col_widths[i])
        set_cell_background(hdr_cells[i], COLOR_LIGHT_BG)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = COLOR_DARK_GREEN

    # Data Rows
    for r_idx, row_data in enumerate(data_rows):
        row_cells = tbl.add_row().cells
        bg_col = "FFFFFF" if r_idx % 2 == 0 else "FBFDFB"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].width = Inches(col_widths[c_idx])
            set_cell_background(row_cells[c_idx], bg_col)
            set_cell_margins(row_cells[c_idx], top=90, bottom=90, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            run = p.add_run(str(val))
            run.font.size = Pt(9)
            run.font.color.rgb = COLOR_DARK_TEXT


def add_image_figure(doc, img_path: Path, caption: str, width_in: float = 6.0):
    """Adds an image figure with centered alignment, subtle border, and descriptive caption."""
    if not img_path.exists():
        p_err = doc.add_paragraph(f"[Image not found: {img_path.name}]")
        p_err.runs[0].font.color.rgb = RGBColor(180, 50, 50)
        return

    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(10)
    p_img.paragraph_format.space_after = Pt(4)
    run_img = p_img.add_run()
    run_img.add_picture(str(img_path), width=Inches(width_in))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(12)
    run_cap = p_cap.add_run(f"Figure: {caption}")
    run_cap.italic = True
    run_cap.font.size = Pt(9)
    run_cap.font.color.rgb = COLOR_MUTED


def build_complete_academic_report():
    print("=" * 70)
    print("Building AttendSure Final Academic Project Report (DOCX)...")
    print("=" * 70)

    doc = Document()

    # Set Standard Page Margins (1 inch all around)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)

    # Base Normal Style
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = COLOR_DARK_TEXT
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 1: COVER PAGE
    # =========================================================================
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_before = Pt(36)
    p_top.paragraph_format.space_after = Pt(6)
    r_uni = p_top.add_run("CSE276: ARTIFICIAL INTELLIGENCE FOUNDATIONS\nCAPSTONE MINI PROJECT EVALUATION\n")
    r_uni.bold = True
    r_uni.font.size = Pt(12)
    r_uni.font.color.rgb = COLOR_FOREST

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(18)
    p_title.paragraph_format.space_after = Pt(12)
    r_title = p_title.add_run("Rural School Attendance Integrity and\nIntervention Decision System\n")
    r_title.bold = True
    r_title.font.size = Pt(24)
    r_title.font.color.rgb = COLOR_DARK_GREEN

    r_sub = p_title.add_run("An Explainable, Privacy-First, Multi-Signal Decision-Support Platform for Resource-Constrained Educational Environments")
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = COLOR_MUTED

    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_before = Pt(24)
    p_div.paragraph_format.space_after = Pt(24)
    r_div = p_div.add_run("──────────────────────────────────────────")
    r_div.font.color.rgb = COLOR_FOREST

    # Meta Table (Students & Mentor)
    meta_tbl = doc.add_table(rows=4, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    col_w = [3.2, 3.2]

    rows_meta = [
        ("PROJECT MENTOR", "STUDENT INVESTIGATORS"),
        ("Mr. Hitesh Jangid\nFaculty Evaluator & Project Guide",
         "Ashish Kumar Tripathi (Reg No. 12509400, Roll No. 21)\nHarsh Jakhar (Reg No. 12517556, Roll No. 8)"),
        ("PROBLEM STATEMENT REFERENCE", "CODEBASE REPOSITORY"),
        ("Smart India Hackathon 2025: SIH25012\nDepartment of Higher Education, Govt of Punjab",
         "https://github.com/ashishkumartripathi/AttendSure\nBranch: feature/modern-saas-ui")
    ]

    for r_i, (c1, c2) in enumerate(rows_meta):
        cell1 = meta_tbl.rows[r_i].cells[0]
        cell2 = meta_tbl.rows[r_i].cells[1]
        cell1.width = Inches(col_w[0])
        cell2.width = Inches(col_w[1])
        set_cell_margins(cell1, top=80, bottom=80, left=100, right=100)
        set_cell_margins(cell2, top=80, bottom=80, left=100, right=100)
        set_cell_background(cell1, COLOR_LIGHT_BG if r_i % 2 == 0 else "FFFFFF")
        set_cell_background(cell2, COLOR_LIGHT_BG if r_i % 2 == 0 else "FFFFFF")

        p1 = cell1.paragraphs[0]
        p1.paragraph_format.space_before = p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(c1)
        r1.font.size = Pt(9.5) if r_i % 2 != 0 else Pt(9)
        r1.bold = (r_i % 2 == 0)
        if r_i % 2 == 0:
            r1.font.color.rgb = COLOR_FOREST

        p2 = cell2.paragraphs[0]
        p2.paragraph_format.space_before = p2.paragraph_format.space_after = Pt(2)
        r2 = p2.add_run(c2)
        r2.font.size = Pt(9.5) if r_i % 2 != 0 else Pt(9)
        r2.bold = (r_i % 2 == 0)
        if r_i % 2 == 0:
            r2.font.color.rgb = COLOR_FOREST

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(48)
    p_date.paragraph_format.space_after = Pt(0)
    r_date = p_date.add_run("November 2026  |  Final Capstone Academic Submission")
    r_date.font.size = Pt(10)
    r_date.font.color.rgb = COLOR_MUTED

    doc.add_page_break()

    # =========================================================================
    # SECTION 2: DECLARATION & CERTIFICATE PLACEHOLDERS
    # =========================================================================
    add_custom_heading(doc, "Section 2: Declaration & Certificate Placeholders", level=1)

    add_custom_heading(doc, "2.1 Candidate's Declaration", level=2)
    p_dec = doc.add_paragraph(
        "We, Ashish Kumar Tripathi (Registration No. 12509400) and Harsh Jakhar (Registration No. 12517556), "
        "hereby declare that the work presented in this Capstone Mini Project Report entitled "
        "\"Rural School Attendance Integrity and Intervention Decision System\" is an authentic record of our own work "
        "carried out under the supervision and guidance of Mr. Hitesh Jangid. "
        "This project has been developed strictly adhering to academic integrity standards. All software implementations, "
        "automated test suites, and empirical benchmarks presented herein have been independently executed and verified. "
        "No part of this report has been plagiarized or submitted elsewhere for any other degree or diploma."
    )

    tbl_sig = doc.add_table(rows=2, cols=2)
    tbl_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_sig.rows[0].cells[0].paragraphs[0].text = "\n\n___________________________\nAshish Kumar Tripathi\nReg. No: 12509400 (Roll No. 21)"
    tbl_sig.rows[0].cells[1].paragraphs[0].text = "\n\n___________________________\nHarsh Jakhar\nReg. No: 12517556 (Roll No. 8)"
    tbl_sig.rows[1].cells[0].paragraphs[0].text = "Date: November 11, 2026"
    tbl_sig.rows[1].cells[1].paragraphs[0].text = "Place: Institutional Campus"
    for r in tbl_sig.rows:
        for c in r.cells:
            c.width = Inches(3.2)
            for p in c.paragraphs:
                p.runs[0].font.size = Pt(9.5)

    add_custom_heading(doc, "2.2 Mentor Certificate Placeholder", level=2)
    doc.add_paragraph(
        "This is to certify that the Capstone Mini Project Report entitled \"Rural School Attendance Integrity and "
        "Intervention Decision System\", submitted by Ashish Kumar Tripathi (12509400) and Harsh Jakhar (12517556) "
        "in partial fulfillment of the requirements for the course CSE276: Artificial Intelligence Foundations, "
        "is a bonafide record of the project work completed under my mentorship and guidance. "
        "The algorithms, empirical verification tests, and application modules described in this report have been "
        "duly reviewed."
    )

    tbl_cert = doc.add_table(rows=2, cols=1)
    tbl_cert.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_cert.rows[0].cells[0].paragraphs[0].text = "\n\n___________________________\nMr. Hitesh Jangid\nProject Mentor & Faculty Evaluator"
    tbl_cert.rows[1].cells[0].paragraphs[0].text = "Date: November 11, 2026\n[Institutional Signature & Seal Placeholder]"
    for r in tbl_cert.rows:
        r.cells[0].width = Inches(6.4)
        for p in r.cells[0].paragraphs:
            p.runs[0].font.size = Pt(9.5)

    doc.add_page_break()

    # =========================================================================
    # SECTION 3: ACKNOWLEDGEMENT
    # =========================================================================
    add_custom_heading(doc, "Section 3: Acknowledgement", level=1)
    doc.add_paragraph(
        "We express our deepest sense of gratitude and sincere thanks to our esteemed mentor, Mr. Hitesh Jangid, "
        "whose constructive criticism, rigorous standards, and continuous technical guidance shaped the trajectory of this project. "
        "His insistence on empirical evidence, explainable algorithms, and scientific integrity challenged us to develop "
        "a reliable and transparent system rather than an opaque black-box demonstration."
    )
    doc.add_paragraph(
        "We also extend our appreciation to our faculty coordinators and the Department of Computer Science & Engineering "
        "for providing the computing infrastructure, automated test harnesses, and academic environment necessary to realize this work. "
        "Finally, we acknowledge the Smart India Hackathon (SIH 2025) initiative and the Department of Higher Education, "
        "Government of Punjab, whose problem statement SIH25012 inspired this inquiry into rural educational technology."
    )

    # =========================================================================
    # SECTION 4: ABSTRACT
    # =========================================================================
    add_custom_heading(doc, "Section 4: Abstract", level=1)
    doc.add_paragraph(
        "In developing rural educational ecosystems, classroom attendance records serve as the fundamental administrative gateway "
        "governing national entitlements—including Mid-Day Meal (PM POSHAN) grain portions, per-pupil infrastructure funding, "
        "and seasonal dropout interventions. Traditional pen-and-paper registers are acutely vulnerable to ledger copying, "
        "arithmetic errors, and reporting inflation. Conversely, modern technological countermeasures—predominantly fingerprint biometric scanners "
        "and facial recognition cameras—frequently collapse in rural schools due to frequent electrical outages, high ambient dust, "
        "absent internet connectivity, high sensor error rates on children's developing fingers, and severe legal liabilities regarding the centralized "
        "storage of minors' facial embeddings under emerging data protection frameworks like India's Digital Personal Data Protection (DPDP) Act of 2023."
    )
    doc.add_paragraph(
        "To resolve this dilemma, this project introduces the Rural School Attendance Integrity and Intervention Decision System "
        "(engineered under the code name AttendSure). AttendSure is an offline-first, explainable decision-support platform "
        "designed for resource-constrained schools. Rather than deploying invasive surveillance, AttendSure combines lightweight cohort count capture "
        "with a deterministic, multi-signal anomaly detection engine monitoring three signals: (1) single-day attendance drops relative to a 5-session "
        "rolling median, (2) identical headcount streaks across consecutive school sessions indicating uninspected ledger copying, and (3) cross-modal "
        "discrepancies between manual roll call and an ephemeral, non-biometric silhouette contour estimator."
    )
    doc.add_paragraph(
        "AttendSure enforces a strict 'Decision Support, Never Accusation' philosophy: every alert provides a human-interpretable 5-field "
        "rationale (Rule ID, Observed Count, Baseline Reference, Applied Cutoff, and Plain-Language Explanation) routed through an administrative "
        "state machine (Pending, Acknowledged, Resolved, Dismissed). The system operates on a zero-PII data architecture (storing no student names, "
        "photos, or biometrics) and features dual persistence: managed cloud PostgreSQL 18.6 in production (via psycopg v3) and embedded SQLite "
        "for offline execution. In rigorous evaluation across 414 automated tests (87.32s runtime), the deterministic rules achieved 96.67% accuracy, "
        "100.0% precision, 54.55% session-level recall, and 100.0% event-level recall across multi-day anomaly episodes. The silhouette estimator achieved "
        "0.14 MAE across standard benchmark scenes, and warm screen navigation completes in 158 ms to 1.03 s for standard workflows. "
        "AttendSure proves that attendance integrity can be safeguarded affordably, reliably, and ethically without sacrificing child privacy."
    )

    doc.add_page_break()

    # =========================================================================
    # SECTION 5: TABLE OF CONTENTS
    # =========================================================================
    add_custom_heading(doc, "Section 5: Table of Contents", level=1)
    toc_data = [
        ("Section 1: Cover Page", "Page 1"),
        ("Section 2: Declaration & Certificate Placeholders", "Page 2"),
        ("Section 3: Acknowledgement", "Page 3"),
        ("Section 4: Abstract", "Page 3"),
        ("Section 5: Table of Contents", "Page 4"),
        ("Section 6: Introduction & Background", "Page 5"),
        ("Section 7: Problem Statement & Motivation (SIH25012)", "Page 6"),
        ("Section 8: Existing System & Limitations (Comparative Matrix)", "Page 7"),
        ("Section 9: Proposed Solution & Core Value Proposition", "Page 8"),
        ("Section 10: Project Objectives (Primary & Secondary)", "Page 9"),
        ("Section 11: Scope, Assumptions & Formal Boundaries", "Page 10"),
        ("Section 12: Design-Thinking Methodology & Stakeholder Needs", "Page 11"),
        ("Section 13: Functional & Non-Functional Requirements", "Page 12"),
        ("Section 14: System Architecture & Data Flow", "Page 13"),
        ("Section 15: Technology Stack & Architectural Rationale", "Page 14"),
        ("Section 16: Database Design, Relational Constraints & Data Flow", "Page 15"),
        ("Section 17: Camera-Assisted Attendance Workflow", "Page 17"),
        ("Section 18: Non-Biometric Silhouette Estimation Methodology", "Page 18"),
        ("Section 19: RFID Interface & Hardware Integration Boundary", "Page 20"),
        ("Section 20: Anomaly Detection Methodology & Formulations", "Page 21"),
        ("Section 21: Human-in-the-Loop Intervention & Review Lifecycle", "Page 23"),
        ("Section 22: Application Modules & Six-Screen Walkthrough", "Page 24"),
        ("Section 23: Deployment Architecture & Cloud Configuration", "Page 28"),
        ("Section 24: Privacy, Security & Role-Based Access Control", "Page 29"),
        ("Section 25: Testing Methodology & Verification Suite (414 Tests)", "Page 31"),
        ("Section 26: Camera Synthetic Benchmark Results & Error Analysis", "Page 33"),
        ("Section 27: Anomaly Detection Benchmark & Episode Evaluation", "Page 35"),
        ("Section 28: Performance Evaluation & Latency Decomposition", "Page 38"),
        ("Section 29: Operational Limitations & Scientific Risks", "Page 40"),
        ("Section 30: Future Enhancements & Technical Roadmap", "Page 41"),
        ("Section 31: Conclusion", "Page 42"),
        ("Section 32: References & Statutory Frameworks", "Page 43"),
        ("Section 33: Appendices & Empirical Verification Evidence", "Page 44"),
    ]
    tbl_toc = doc.add_table(rows=1, cols=2)
    format_table(tbl_toc, [5.2, 1.2], ["Document Section Title", "Location"], toc_data)

    doc.add_page_break()

    # =========================================================================
    # SECTION 6: INTRODUCTION & BACKGROUND
    # =========================================================================
    add_custom_heading(doc, "Section 6: Introduction & Background", level=1)
    doc.add_paragraph(
        "Primary and secondary education in rural India represents one of the largest public welfare delivery channels in the world. "
        "Across over one million government and government-aided schools, daily classroom attendance serves two distinct and critical functions: "
        "pedagogical engagement and fiscal welfare governance."
    )
    doc.add_paragraph(
        "From a pedagogical perspective, consistent attendance is the strongest early predictor of literacy, numeracy, and educational retention. "
        "Sudden or persistent absenteeism signals vulnerability to seasonal child labor, agricultural harvesting obligations, localized health epidemics, "
        "or domestic economic distress. Identifying attendance drops promptly allows educators and block officers to deploy timely counseling and welfare interventions."
    )
    doc.add_paragraph(
        "From a fiscal and logistical perspective, statutory educational entitlements are distributed on a per-attending-student basis. "
        "The national Mid-Day Meal scheme (re-christened PM POSHAN) provides cooked nutritional meals daily. Foodgrain allocations, cooking cost reimbursements, "
        "textbook distributions, uniform allowances, and direct benefit transfers (DBT) depend fundamentally upon attendance registers. "
        "When attendance counts are distorted—whether through accidental bookkeeping errors or deliberate inflation—public funds are misallocated, "
        "ration food is wasted or diverted, and genuine educational distress remains concealed."
    )
    add_callout(
        doc,
        "Daily attendance in rural schools is not merely an administrative ledger; it is the fiscal and operational lifeline governing child nutrition, welfare subsidies, and dropout prevention.",
        "THE DUAL ROLE OF ATTENDANCE"
    )

    # =========================================================================
    # SECTION 7: PROBLEM STATEMENT & MOTIVATION
    # =========================================================================
    add_custom_heading(doc, "Section 7: Problem Statement & Motivation (SIH25012)", level=1)
    doc.add_paragraph(
        "This project directly addresses Smart India Hackathon (SIH 2025) Problem Statement SIH25012, "
        "entitled \"Automated Attendance System for Rural Schools\", sponsored by the Department of Higher Education, Government of Punjab, "
        "under the Smart Education software theme. The official mandate calls for an automated, low-cost attendance monitoring system suited for rural schools "
        "where conventional biometric or internet-dependent methods fail."
    )
    doc.add_paragraph(
        "In rural schools, attendance bookkeeping faces severe systemic challenges. Traditional paper ledgers suffer from three well-documented structural flaws:"
    )
    doc.add_paragraph(
        "1. Ledger Inertia: Rural primary school educators often manage multi-grade classrooms simultaneously. During hectic morning roll calls, "
        "teachers frequently copy previous days' attendance counts directly into the ledger without physical headcount verification.\n"
        "2. Arithmetic and Transcription Errors: Compiling monthly cohort attendance summaries by hand leads to persistent arithmetic errors "
        "that propagate upward into block-level databases.\n"
        "3. Roster Inflation & Ghost Enrollments: In schools on the threshold of teacher-student ratio cutoffs or mid-day meal funding tiers, "
        "uninspected manual bookkeeping creates structural incentives to maintain inflated present counts to preserve school resources."
    )

    # =========================================================================
    # SECTION 8: EXISTING SYSTEM & LIMITATIONS
    # =========================================================================
    add_custom_heading(doc, "Section 8: Existing System & Limitations (Comparative Matrix)", level=1)
    doc.add_paragraph(
        "To mitigate attendance distortion, various state and municipal education bodies have piloted automated technologies. "
        "However, existing commercial paradigms fail to accommodate rural operating realities. Below is a comparative analysis across four paradigms:"
    )

    comp_headers = ["Evaluation Metric", "Paper Registers", "Biometric Scanners", "Facial Recognition CV", "AttendSure (Proposed)"]
    comp_rows = [
        ("Hardware Cost", "Zero (paper only)", "High (scanners, tablets)", "Very High (GPUs, HD cameras)", "Zero (runs on existing laptops/PCs)"),
        ("Connectivity Dependence", "None", "Frequent / Daily sync", "Continuous High-Speed", "100% Offline Capable (SQLite)"),
        ("Power Grid Resilience", "100% resilient", "Fails during blackouts", "Fails during blackouts", "High (battery-backed commodity laptop)"),
        ("Sensor Failure Rate", "N/A", "High on children (FRR)", "High (harsh sun/shadows)", "Low (contour aid + teacher review)"),
        ("Child Privacy & Legal Risk", "Low PII exposure", "Extreme (fingerprints)", "Severe (facial embeddings)", "Strict Zero PII (cohort counts only)"),
        ("Explainability", "Manual ledger scan", "Black-box biometric score", "Opaque embedding distance", "Transparent 5-field explainable rules"),
        ("Operational Stance", "Passive record", "Punitive surveillance", "Adversarial surveillance", "Supportive decision support"),
    ]
    tbl_comp = doc.add_table(rows=1, cols=5)
    format_table(tbl_comp, [1.4, 1.2, 1.3, 1.3, 1.3], comp_headers, comp_rows)

    add_callout(
        doc,
        "Biometric fingerprinting and facial recognition fail in rural schools not because of algorithmic flaws, but because of environmental mismatch: power outages, dust, developing fingers of young children, and legal liabilities under the DPDP Act 2023.",
        "ENVIRONMENTAL REALITY CHECK"
    )

    # =========================================================================
    # SECTION 9: PROPOSED SOLUTION & VALUE PROPOSITION
    # =========================================================================
    add_custom_heading(doc, "Section 9: Proposed Solution & Core Value Proposition", level=1)
    doc.add_paragraph(
        "AttendSure resolves the rural attendance verification dilemma by introducing an appropriate technology solution: "
        "an explainable, offline-first decision-support software platform tailored for resource-constrained primary and secondary schools. "
        "Rather than deploying invasive surveillance hardware, AttendSure audits attendance integrity via multi-signal statistical consistency."
    )
    doc.add_paragraph(
        "Core Value Propositions:\n"
        "• Offline-First Architecture: Complete daily roll call, invariant checking, contour counting, and anomaly detection execute locally on embedded SQLite.\n"
        "• Multi-Signal Anomaly Detection: Blends temporal drop detection, repeated count streak tracking, and cross-modal silhouette verification.\n"
        "• Decision Support, Never Accusation: Alerts are framed as signals for administrative review, recognizing that legitimate external events (floods, harvest) cause rural attendance anomalies.\n"
        "• Strict Zero-PII Child Privacy: Audits aggregated class cohort counts exclusively. No student names, roll numbers, or facial biometrics are stored."
    )

    # =========================================================================
    # SECTION 10: PROJECT OBJECTIVES
    # =========================================================================
    add_custom_heading(doc, "Section 10: Project Objectives (Primary & Secondary)", level=1)
    doc.add_paragraph(
        "The project was executed against five formal, verifiable engineering objectives:\n"
        "1. Objective 1 (Explainable Rule Engine): Implement deterministic, auditable rules detecting attendance drops (>= 30%), repeated headcounts (>= 4 days), and camera discrepancies (>= 5 students) with 5-field plain-language rationale.\n"
        "2. Objective 2 (Count Invariant Enforcement): Mathematically enforce Present + Absent = Enrollment across all input vectors before database insertion.\n"
        "3. Objective 3 (Human-in-the-Loop Review): Provide an institutional four-state review lifecycle (Pending, Acknowledged, Resolved, Dismissed) with immutable audit logging.\n"
        "4. Objective 4 (Assistive Non-Biometric Silhouette Estimation): Implement an ephemeral contour estimator providing advisory headcounts with mandatory teacher verification.\n"
        "5. Objective 5 (Dual-Mode Persistence & Testing Rigor): Provide a unified engine supporting managed cloud PostgreSQL (Neon) and local SQLite, validated by >= 400 automated tests passing with 100% success."
    )

    # =========================================================================
    # SECTION 11: SCOPE, ASSUMPTIONS & FORMAL BOUNDARIES
    # =========================================================================
    add_custom_heading(doc, "Section 11: Scope, Assumptions & Formal Boundaries", level=1)
    doc.add_paragraph(
        "To preserve scientific integrity during academic examination, the formal boundaries of this project are declared:\n"
        "• In Scope: Class-level roll call, invariant validation, deterministic rule engine, decision tree classifier, ephemeral camera contour estimation, human review state machine, dual-mode database persistence, CSV data contracts, and headless UI testing.\n"
        "• Explicitly Out of Scope:\n"
        "  1. NO Facial Recognition or Facial Embeddings: Biometric feature extraction is strictly excluded by architecture.\n"
        "  2. NO Physical RFID Scanner Hardware: RFID interface is implemented as a clean software provider abstraction for future IoT card readers; no physical RFID hardware was deployed.\n"
        "  3. NO PM POSHAN Direct Meal Grain Allocation: Direct meal tracking is a future scope item; attendance integrity auditing remains the core focus.\n"
        "  4. NO Real-World 30-Day Classroom Pilot: System validity is established through bit-for-bit reproducible synthetic benchmarks, not live classroom deployments."
    )

    # =========================================================================
    # SECTION 12: DESIGN-THINKING METHODOLOGY & USER NEEDS
    # =========================================================================
    add_custom_heading(doc, "Section 12: Design-Thinking Methodology & Stakeholder Needs", level=1)
    doc.add_paragraph(
        "AttendSure was developed using the 5-stage Design-Thinking framework (Empathize, Define, Ideate, Prototype, Test). "
        "Field interviews and rural educational literature informed three primary stakeholder personas:"
    )
    doc.add_paragraph(
        "• Persona 1: Primary School Teacher (Smt. Anita Sharma, Grade 3 Teacher, Multi-Grade School)\n"
        "  - Need: Fast, dependable roll call that does not crash during power outages; zero complex technology.\n"
        "  - Feature: Simple roll-call form, instant validation banner, non-judgmental advisory camera count.\n\n"
        "• Persona 2: School Headmaster (Shri Rajesh Verma, Rural Composite High School)\n"
        "  - Need: Morning overview of total attendance, immediate alerts on anomalous drops, auditable review log.\n"
        "  - Feature: Overview KPI cards, Needs Attention triage queue, administrative review note submission.\n\n"
        "• Persona 3: Block Education Officer (BEO, Rural District Administration)\n"
        "  - Need: Monthly attendance aggregations across schools, exportable audit trail for welfare audits.\n"
        "  - Feature: Reports view, cohort ranking tables, standards-compliant CSV export."
    )

    # =========================================================================
    # SECTION 13: FUNCTIONAL & NON-FUNCTIONAL REQUIREMENTS
    # =========================================================================
    add_custom_heading(doc, "Section 13: Functional & Non-Functional Requirements", level=1)
    req_headers = ["Identifier", "Category", "Requirement Specification", "Verification Status"]
    req_rows = [
        ("FR-01", "Functional", "Allow daily attendance recording with Class ID, Date, Enrollment, Present, Absent.", "VERIFIED"),
        ("FR-02", "Functional", "Enforce Present + Absent = Enrollment, with Present >= 0 and Enrollment >= 1.", "VERIFIED"),
        ("FR-03", "Functional", "Trigger alert when attendance drops >= 30% below 5-session rolling median.", "VERIFIED"),
        ("FR-04", "Functional", "Trigger alert when present count is identical for >= 4 consecutive sessions.", "VERIFIED"),
        ("FR-05", "Functional", "Trigger alert when |Present - Camera Count| >= 5 with camera SUCCESS.", "VERIFIED"),
        ("FR-06", "Functional", "Provide 5-field explainable rationale on all generated alerts.", "VERIFIED"),
        ("FR-07", "Functional", "Provide 4-state administrative review lifecycle (Pending, Acknowledged, Resolved, Dismissed).", "VERIFIED"),
        ("FR-08", "Functional", "Generate downloadable CSV exports of sessions, alerts, and audit logs.", "VERIFIED"),
        ("NFR-01", "Non-Functional", "Sub-second database query execution for cached warm workflows (< 25 ms).", "VERIFIED"),
        ("NFR-02", "Non-Functional", "100% offline capability on embedded SQLite without internet access.", "VERIFIED"),
        ("NFR-03", "Non-Functional", "Zero storage of student PII, names, photos, or facial biometric templates.", "VERIFIED"),
        ("NFR-04", "Non-Functional", "Cryptographic password hashing using PBKDF2-HMAC-SHA256 (100,000 iterations).", "VERIFIED"),
    ]
    tbl_req = doc.add_table(rows=1, cols=4)
    format_table(tbl_req, [1.0, 1.4, 3.2, 0.9], req_headers, req_rows)

    # =========================================================================
    # SECTION 14: SYSTEM ARCHITECTURE & DATA FLOW
    # =========================================================================
    add_custom_heading(doc, "Section 14: System Architecture & Data Flow", level=1)
    doc.add_paragraph(
        "AttendSure follows a decoupled 4-tier architectural design:\n"
        "1. Client Tier: Streamlit Modern SaaS web application delivering responsive layout across desktop, tablet, and mobile browsers with zero transition ghosting.\n"
        "2. Application Tier: Python 3.13 core engine executing invariant validation, session lifecycle, and in-memory short-TTL read caching.\n"
        "3. Intelligence Tier: Deterministic production rules engine, CART shallow decision tree, and ephemeral OpenCV silhouette contour extraction.\n"
        "4. Persistence Tier: SQLAlchemy abstraction supporting managed cloud Neon PostgreSQL 18.6 in production and embedded SQLite in offline development mode."
    )
    add_callout(
        doc,
        "Production Mode Safeguard: When ATTENDSURE_ENVIRONMENT=production is configured, the application requires managed Neon PostgreSQL (DATABASE_URL) and explicitly refuses to start on local SQLite, preventing silent fallback.",
        "DATABASE FAILSAFE"
    )

    # =========================================================================
    # SECTION 15: TECHNOLOGY STACK & ARCHITECTURAL RATIONALE
    # =========================================================================
    add_custom_heading(doc, "Section 15: Technology Stack & Architectural Rationale", level=1)
    doc.add_paragraph(
        "All software dependencies were selected to guarantee cross-platform compatibility, minimal footprint, and zero external API dependencies:\n"
        "• Python 3.13.9: Core runtime providing robust type annotations, modern asyncio primitives, and performance improvements.\n"
        "• Streamlit 1.40+: Web UI framework enabling reactive state management and responsive components without complex JavaScript frameworks.\n"
        "• SQLAlchemy 2.0+ & psycopg v3: Modern database abstraction and binary PostgreSQL driver providing connection pooling and dialect normalization.\n"
        "• Neon Managed PostgreSQL 18.6: Production serverless cloud database in AWS Singapore (`aws-ap-southeast-1`) providing ACID compliance.\n"
        "• SQLite 3: Zero-configuration embedded transactional database for 100% offline rural school operation.\n"
        "• OpenCV (Headless) & Pillow: Lightweight image processing for blur variance and silhouette contour segmentation without GUI overhead.\n"
        "• Scikit-Learn: Interpretable CART decision tree classifier (max_depth=4) for baseline machine learning comparison.\n"
        "• pytest 8.4+: Rigorous testing framework executing 414 automated unit, integration, and UI tests."
    )

    # =========================================================================
    # SECTION 16: DATABASE DESIGN & RELATIONAL CONSTRAINTS
    # =========================================================================
    add_custom_heading(doc, "Section 16: Database Design, Relational Constraints & Data Flow", level=1)
    doc.add_paragraph(
        "The relational schema enforces data integrity at the database engine level via 6 explicit SQL check constraints, "
        "primary keys, and cascading foreign keys across three core tables:"
    )
    db_headers = ["Table Name", "Constraint Name", "Constraint Type", "Specification"]
    db_rows = [
        ("attendance_sessions", "pk_attendance_sessions", "Primary Key", "session_id (UUIDv4)"),
        ("attendance_sessions", "uq_sessions_class_date", "Unique", "Unique (class_id, session_date)"),
        ("attendance_sessions", "chk_sessions_enrollment", "Check", "expected_enrollment >= 1"),
        ("attendance_sessions", "chk_sessions_present", "Check", "present_count >= 0 AND present_count <= expected_enrollment"),
        ("attendance_sessions", "chk_sessions_absent", "Check", "absent_count >= 0 AND absent_count <= expected_enrollment"),
        ("attendance_sessions", "chk_sessions_count_invariant", "Check", "present_count + absent_count = expected_enrollment"),
        ("attendance_sessions", "chk_sessions_webcam_status", "Check", "IN ('SUCCESS', 'NOT_ATTEMPTED', 'CAMERA_UNAVAILABLE', 'DETECTION_FAILED')"),
        ("attendance_sessions", "chk_sessions_record_source", "Check", "IN ('SYNTHETIC', 'MANUAL_ENTRY', 'CSV_IMPORT')"),
        ("alerts", "fk_alerts_session", "Foreign Key", "session_id -> attendance_sessions.session_id (CASCADE)"),
        ("alerts", "chk_alerts_priority", "Check", "IN ('INFO', 'REVIEW_REQUIRED')"),
        ("alerts", "chk_alerts_review_status", "Check", "IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')"),
        ("alert_reviews", "fk_reviews_alert", "Foreign Key", "alert_id -> alerts.alert_id (CASCADE)"),
    ]
    tbl_db = doc.add_table(rows=1, cols=4)
    format_table(tbl_db, [1.5, 1.8, 1.1, 2.1], db_headers, db_rows)

    # =========================================================================
    # SECTION 17: CAMERA-ASSISTED ATTENDANCE WORKFLOW
    # =========================================================================
    add_custom_heading(doc, "Section 17: Camera-Assisted Attendance Workflow", level=1)
    doc.add_paragraph(
        "The camera-assisted roll-call workflow follows an assistive 5-step operational protocol:\n"
        "1. Capture: Teacher activates camera in browser via `st.camera_input`. A wide-angle group photo of the seated classroom is captured.\n"
        "2. Ephemeral Ingestion: Image bytes are transferred in RAM (`io.BytesIO`) without writing any `.jpg` or `.png` file to disk.\n"
        "3. Quality Pre-Screening: Image is audited for sharpness (Laplacian variance >= 100) and illumination (mean luminance 40–225).\n"
        "4. Silhouette Estimation: Person contours are segmented and counted, returning an advisory estimate.\n"
        "5. Mandatory Confirmation: The advisory count is displayed. The teacher visually verifies the number against the physical classroom, "
        "adjusts if necessary via numeric stepper, and confirms. Only the confirmed attendance numbers are saved."
    )

    # =========================================================================
    # SECTION 18: NON-BIOMETRIC SILHOUETTE ESTIMATION METHODOLOGY
    # =========================================================================
    add_custom_heading(doc, "Section 18: Non-Biometric Silhouette Estimation Methodology", level=1)
    doc.add_paragraph(
        "The person estimator (`person_estimator.py`) operates via morphological silhouette analysis rather than facial recognition:\n\n"
        "1. Laplacian Sharpness Formulation:\n"
        "Sharpness is evaluated using the variance of the discrete 2D Laplacian operator over grayscale image $I$:\n"
        "$$\\sigma_{\\text{Laplacian}}^2 = \\frac{1}{N} \\sum_{x,y} \\left( \\nabla^2 I(x,y) - \\mu_{\\nabla^2 I} \\right)^2$$\n"
        "Frames with $\\sigma^2 < 100.0$ are flagged as BLURRED with confidence 50%.\n\n"
        "2. Luminance Illumination Formulation:\n"
        "Mean grayscale luminance $\\mu_I = \\frac{1}{N} \\sum I(x,y)$. Frames with $\\mu_I < 40$ are flagged POOR_LIGHTING (underexposed); "
        "frames with $\\mu_I > 225$ are flagged OVEREXPOSED.\n\n"
        "3. Silhouette Segmentation & Contour Filtering:\n"
        "Adaptive Otsu thresholding segments foreground student bodies from backgrounds. High-frequency speckle noise is removed via "
        "morphological opening ($3 \\times 3$ elliptical kernel). Connected component contours are filtered by anatomical aspect ratio "
        "($1.2 \\le \\frac{H}{W} \\le 3.5$) and bounding area ($0.8\\% \\le \\text{Area} \\le 20.0\\%$ of total frame).\n\n"
        "4. Bench Cluster Normalization:\n"
        "When students sit closely on wooden benches, connected contours merge. Clusters exceeding $1.8 \\times$ median contour area are "
        "divided by median area to estimate the number of clustered students."
    )

    # =========================================================================
    # SECTION 19: RFID INTERFACE & HARDWARE BOUNDARY
    # =========================================================================
    add_custom_heading(doc, "Section 19: RFID Interface & Future Hardware Boundary", level=1)
    doc.add_paragraph(
        "AttendSure includes a modular RFID integration layer (`rfid_provider.py`) structured around an abstract base class `IRFIDProvider`. "
        "This allows the software to ingest digital tap events from future physical RFID smart cards or NFC tags."
    )
    add_callout(
        doc,
        "Hardware Disclosure: No physical RFID card readers or antennas were deployed for this evaluation. The software provides a clean, unit-tested provider abstraction ready for physical IoT hardware integration in future pilots.",
        "HARDWARE BOUNDARY DISCLOSURE"
    )

    # =========================================================================
    # SECTION 20: ANOMALY DETECTION METHODOLOGY & FORMULATIONS
    # =========================================================================
    add_custom_heading(doc, "Section 20: Anomaly Detection Methodology & Formulations", level=1)
    doc.add_paragraph(
        "AttendSure's core intelligence module implements three explainable production rules conforming to CSE276 requirements:\n\n"
        "1. Rule 1: Statistically Significant Attendance Drop (`RULE_ATTENDANCE_DROP`)\n"
        "Evaluates whether present count $P_t$ drops by $\\ge 30\\%$ relative to the cohort's rolling median $M_t$ over the previous 5 sessions:\n"
        "$$\\Delta_{\\text{drop}} = \\frac{M_t - P_t}{M_t} \\ge 0.30$$\n"
        "Identifies legitimate environmental crises (floods, harvest) or sudden reporting dropouts.\n\n"
        "2. Rule 2: Unnatural Repeated Headcount Streak (`RULE_REPEATED_HEADCOUNT`)\n"
        "Tracks chronological streaks of identical attendance counts across consecutive sessions $K$:\n"
        "$$P_t = P_{t-1} = P_{t-2} = \\dots = P_{t-K+1}$$\n"
        "Threshold: $K \\ge 4$ consecutive days for counts $< 100\\%$ enrollment; $K \\ge 6$ days for perfect attendance (100%). "
        "Flags ledger copying without physical counting.\n\n"
        "3. Rule 3: Cross-Modal Camera Discrepancy (`RULE_WEBCAM_DISCREPANCY`)\n"
        "Evaluates the absolute difference between manual roll call $P_t$ and camera estimate $W_t$ when camera status is SUCCESS:\n"
        "$$|P_t - W_t| \\ge 5$$\n"
        "Audits consistency and flags potential roster inflation or severe camera field-of-view occlusion.\n\n"
        "Every alert adheres to a mandatory 5-Field Explainability Contract: (1) Rule Identifier, (2) Observed Count, "
        "(3) Rolling Baseline, (4) Applied Threshold, and (5) Plain-Language Educational Rationale."
    )

    # =========================================================================
    # SECTION 21: HUMAN-IN-THE-LOOP INTERVENTION & REVIEW LIFECYCLE
    # =========================================================================
    add_custom_heading(doc, "Section 21: Human-in-the-Loop Intervention & Review Lifecycle", level=1)
    doc.add_paragraph(
        "AttendSure operates under the firm doctrine: Decision Support, Never Accusation. "
        "An attendance anomaly in a rural school is an indicator for supportive inquiry, not proof of misconduct. "
        "Alerts transition through a formal 4-state lifecycle:\n"
        "• PENDING_REVIEW: Default initial state upon rule trigger.\n"
        "• ACKNOWLEDGED: Headmaster has reviewed the signal and scheduled on-site inspection.\n"
        "• RESOLVED: Ground reality verified (e.g. localized flash flooding verified with village sarpanch; absence accounted for).\n"
        "• DISMISSED: Technical false alarm verified (e.g. morning sun glare occluded camera; manual count verified accurate).\n\n"
        "Every transition records the reviewer's role, timestamp, and field notes in an immutable audit trail (`alert_reviews` table)."
    )

    # =========================================================================
    # SECTION 22: APPLICATION MODULES & SIX-SCREEN WALKTHROUGH
    # =========================================================================
    add_custom_heading(doc, "Section 22: Application Modules & Six-Screen Walkthrough", level=1)
    doc.add_paragraph(
        "AttendSure delivers six core application views organized under Progressive Disclosure: "
        "Simple plain-English view by default, evidence breakdowns on demand, and advanced technical diagnostics for administrators."
    )

    # Walkthrough with images
    screens_meta = [
        ("01_desktop_overview.png", "Overview Dashboard (Level 1 Simple View)",
         "The Overview screen displays five core KPI cards: Total Enrollment, Present Today, Absent Today, Today's Attendance Rate, "
         "and Needs Attention alerts. Active Today indicators confirm whether today's session has occurred. Below, the Daily Attendance Trend "
         "chart visualizes longitudinal attendance rates across cohorts."),
        ("02_desktop_mark_attendance.png", "Mark Attendance & Invariant Validation",
         "Enables manual roll-call entry with instant client-side invariant checking. If Present + Absent != Enrollment, a prominent error banner "
         "blocks submission before database access. Supports optional ephemeral camera silhouette estimation with mandatory teacher confirmation."),
        ("03_desktop_attendance_records.png", "Attendance Records & Historical Audit",
         "Provides historical tabular audit logs with cohort selectors, date filters, and sub-second pagination (~158 ms). Tracks provenance via the "
         "record_source column (MANUAL_ENTRY, CSV_IMPORT, SYNTHETIC)."),
        ("04_desktop_needs_attention.png", "Needs Attention Triage Queue (Level 2 Evidence View)",
         "Displays explainable alert cards with priority badges (REVIEW_REQUIRED, INFO). Each card expands to reveal the 5-field evidence breakdown, "
         "baseline comparison table, and interactive administrative review form."),
        ("05_desktop_reports.png", "Reports & Longitudinal Analytics",
         "Computes cross-cohort longitudinal aggregations, monthly attendance averages, cohort stability rankings, and generates downloadable "
         "standards-compliant CSV summaries for block educational officers."),
        ("06_desktop_settings.png", "Settings & System Diagnostics (Level 3 Advanced View)",
         "Provides database connection health pings, storage statistics, active tenant identity (School ID: RUMV-081204), and algorithm settings."),
        ("07_public_login_gate.png", "Institutional Login & Role-Based Authentication Gate",
         "Gated entry requiring valid institutional credentials. Enforces PBKDF2-HMAC-SHA256 password hashing with unique random salts and constant-time comparison."),
        ("09_teacher_access_restricted.png", "Role-Based Access Control (Teacher Restricted View)",
         "Demonstrates institutional role enforcement: Classroom Teachers are restricted to roll-call entry and record viewing. Navigating to Settings or "
         "resolving alerts renders an access-restricted card."),
        ("10_mobile_public_portal.png", "Responsive Mobile Public Portal",
         "Demonstrates responsive layout adaptability on mobile viewports, enabling rural headmasters to inspect attendance on standard mobile phones."),
    ]

    for img_name, title, desc in screens_meta:
        add_custom_heading(doc, f"22.{screens_meta.index((img_name, title, desc))+1} {title}", level=2)
        doc.add_paragraph(desc)
        img_path = SCREENSHOTS_DIR / img_name
        add_image_figure(doc, img_path, title, width_in=5.8)

    # =========================================================================
    # SECTION 23: DEPLOYMENT ARCHITECTURE
    # =========================================================================
    add_custom_heading(doc, "Section 23: Deployment Architecture & Cloud Configuration", level=1)
    doc.add_paragraph(
        "AttendSure supports two distinct deployment topologies:\n"
        "1. Public Cloud SaaS Deployment: Hosted on Streamlit Community Cloud, backed by serverless managed Neon PostgreSQL 18.6 "
        "in AWS Singapore (`aws-ap-southeast-1`). Managed via connection pooling (`QueuePool`), SSL mode `require`, and psycopg v3 driver normalization.\n"
        "2. Offline Rural School Deployment: Hosted locally on school laptops using standard Python 3.13 and embedded SQLite (`data/attendsure.db`), "
        "requiring zero network access."
    )

    # =========================================================================
    # SECTION 24: PRIVACY, SECURITY & ROLE-BASED ACCESS CONTROL
    # =========================================================================
    add_custom_heading(doc, "Section 24: Privacy, Security & Role-Based Access Control", level=1)
    doc.add_paragraph(
        "The security and privacy architecture adheres to strict child safeguarding principles:\n"
        "• Cryptographic Password Security: Passwords hashed using PBKDF2 with HMAC-SHA256, 100,000 iterations, and 16-byte cryptographically secure random salts. "
        "Timing attacks mitigated via `secrets.compare_digest`.\n"
        "• Secret Handling: Credentials and connection strings are strictly untracked (.env.local in .gitignore); injected via environment variables.\n"
        "• Transactional Atomicity: Batch operations execute within database transactions. Invariant violations trigger clean rollback to 0 records.\n"
        "• Role-Based Access Control Matrix (Verified vs. Unverified Properties):"
    )

    rbac_headers = ["Capability / Operation", "Unauthenticated", "Teacher (ROLE_TEACHER)", "Headmaster (ROLE_HEADMASTER)", "Verification Status"]
    rbac_rows = [
        ("Application Navigation", "Blocked (Login Gate)", "Allowed (Permitted views)", "Allowed (All 6 views)", "VERIFIED"),
        ("Mark Attendance", "Blocked", "Allowed", "Allowed", "VERIFIED"),
        ("View Records", "Blocked", "Allowed", "Allowed", "VERIFIED"),
        ("View Reports & Export CSV", "Blocked", "Allowed", "Allowed", "VERIFIED"),
        ("View Anomaly Intelligence", "Blocked", "Blocked (Restricted Card)", "Allowed", "VERIFIED"),
        ("Review & Resolve Alerts", "Blocked", "Blocked (Access Denied)", "Allowed", "VERIFIED"),
        ("Modify Settings", "Blocked", "Blocked (Access Denied)", "Allowed", "VERIFIED"),
        ("Hardware KMS Encryption at Rest", "N/A", "N/A", "N/A", "NOT IMPLEMENTED"),
        ("PostgreSQL Row-Level Security (RLS)", "N/A", "N/A", "N/A", "NOT IMPLEMENTED"),
        ("View-Level Component Gating", "N/A", "Partially Wired", "Allowed", "PARTIALLY VERIFIED"),
    ]
    tbl_rbac = doc.add_table(rows=1, cols=5)
    format_table(tbl_rbac, [1.5, 1.1, 1.3, 1.3, 1.2], rbac_headers, rbac_rows)

    add_callout(
        doc,
        "Security Disclosure: Hardware KMS encryption at rest and PostgreSQL Row-Level Security (RLS) are NOT implemented. Local SQLite is unencrypted; cloud PostgreSQL uses provider-level AWS EBS encryption. Tenant isolation is enforced at the application layer via school_id queries.",
        "SECURITY PROPERTY DISCLOSURE"
    )

    # =========================================================================
    # SECTION 25: TESTING METHODOLOGY & VERIFICATION SUITE
    # =========================================================================
    add_custom_heading(doc, "Section 25: Testing Methodology & Verification Suite (414 Tests)", level=1)
    doc.add_paragraph(
        "Software quality is verified through an automated test suite executed via pytest. "
        "All 414 automated tests pass with 100% success in 87.32 seconds with 0 regressions, 0 failures, and 0 warnings."
    )

    test_headers = ["Test Module", "Test Scope & Capabilities", "Tests Count", "Execution Status"]
    test_rows = [
        ("test_auth.py", "PBKDF2 hashing, random salts, role gating, bad login rejection", "7", "PASS (100%)"),
        ("test_camera_quality.py", "Laplacian blur variance, mean luminance, resolution pre-screen", "9", "PASS (100%)"),
        ("test_data_validation.py", "Count invariants (P+A=E), negative values, future date rejection", "30", "PASS (100%)"),
        ("test_db_engine.py", "Connection pooling, PostgreSQL dialect normalization, zero silent fallback", "3", "PASS (100%)"),
        ("test_db_persistence.py", "Transactional atomicity, batch rollback on constraint violation", "6", "PASS (100%)"),
        ("test_detection_drop.py", "Attendance drop rule, rolling median window, threshold cutoffs", "15", "PASS (100%)"),
        ("test_detection_repeated.py", "Repeated headcount streak accumulator, consecutive day tracking", "19", "PASS (100%)"),
        ("test_detection_webcam.py", "Manual vs. camera discrepancy detection, camera status gating", "15", "PASS (100%)"),
        ("test_person_estimator.py", "Otsu threshold, aspect ratio filtering, bench cluster normalization", "6", "PASS (100%)"),
        ("test_ml_decision_tree.py", "CART decision tree training, feature extraction, holdout evaluation", "9", "PASS (100%)"),
        ("test_ui_overview.py", "Overview screen rendering, empty-state banners, active today KPIs", "6", "PASS (100%)"),
        ("test_ui_register.py", "Roll-call form inputs, invariant rejection banners, submission", "12", "PASS (100%)"),
        ("test_ui_records.py", "Records table rendering, cohort filtering, date search, pagination", "4", "PASS (100%)"),
        ("test_ui_intelligence.py", "Needs Attention triage cards, evidence formatting, review lifecycle", "10", "PASS (100%)"),
        ("test_ui_reports.py", "Reports aggregations, daily trend plots, CSV download generation", "12", "PASS (100%)"),
        ("test_ui_settings.py", "Diagnostic checks, DB health ping, storage stats, metadata", "5", "PASS (100%)"),
        ("Other Modules", "Package exports, CSV contracts, RFID providers, demo seeds", "246", "PASS (100%)"),
        ("TOTAL VERIFIED SUITE", "Complete System Functional, Architectural & UI Coverage", "414", "414 PASSED (87.32s)"),
    ]
    tbl_tests = doc.add_table(rows=1, cols=4)
    format_table(tbl_tests, [1.6, 2.7, 0.9, 1.2], test_headers, test_rows)

    # =========================================================================
    # SECTION 26: CAMERA SYNTHETIC BENCHMARK RESULTS
    # =========================================================================
    add_custom_heading(doc, "Section 26: Camera Synthetic Benchmark Results & Error Analysis", level=1)
    doc.add_paragraph(
        "The camera silhouette estimator was evaluated across 10 standardized synthetic scenarios, presented in two separate cohorts:"
    )

    add_custom_heading(doc, "26.1 Standard Benchmark Scenarios (Cases 1–7)", level=2)
    cam_std_headers = ["Case ID", "Scenario Description", "Ground Truth", "Predicted", "Abs Error", "Confidence", "Quality Flag", "Status"]
    cam_std_rows = [
        ("Case 1", "Single Student (Isolated Seated)", "1", "1", "0", "85.0%", "GOOD", "PASS"),
        ("Case 2", "Two Students (Spaced Seated)", "2", "2", "0", "85.0%", "GOOD", "PASS"),
        ("Case 3", "Three Students (Nominal Seated)", "3", "3", "0", "85.0%", "GOOD", "PASS"),
        ("Case 4", "Four Students (Row Seated)", "4", "4", "0", "85.0%", "GOOD", "PASS"),
        ("Case 5", "Five Students (Dense Row)", "5", "5", "0", "85.0%", "GOOD", "PASS"),
        ("Case 6", "Double Bench Cluster + 1 Isolated", "3", "2", "1", "85.0%", "GOOD", "PASS"),
        ("Case 7", "1 Student + Desk & Wall Edge Noise", "1", "1", "0", "85.0%", "GOOD", "PASS"),
    ]
    tbl_cam_std = doc.add_table(rows=1, cols=8)
    format_table(tbl_cam_std, [0.7, 2.0, 0.7, 0.7, 0.6, 0.7, 0.6, 0.5], cam_std_headers, cam_std_rows)

    doc.add_paragraph(
        "Standard Cases 1–7 Summary (Synthetic Benchmark Performance):\n"
        "• Clean Silhouette MAE (Cases 1–5 & 7): 0.00 across isolated seated configurations.\n"
        "• Original 7-Case MAE: 1 / 7 ≈ 0.14.\n"
        "• Zero-Error Percentage: 6 / 7 = 85.7%."
    )

    add_custom_heading(doc, "26.2 Degraded & Edge Scenarios (Cases 8–10)", level=2)
    cam_deg_headers = ["Case ID", "Scenario Description", "Ground Truth", "Predicted", "Abs Error", "Confidence", "Quality Flag", "Status"]
    cam_deg_rows = [
        ("Case 8", "Blurred Scene (Heavy Blur)", "3", "3", "0", "50.0%", "BLURRED", "PASS"),
        ("Case 9", "Dark Scene (Severe Underexposure)", "3", "0", "3", "50.0%", "POOR_LIGHTING", "PASS"),
        ("Case 10", "Corrupted / Empty Bytes", "None", "None", "N/A", "N/A", "INVALID_FORMAT", "PASS"),
    ]
    tbl_cam_deg = doc.add_table(rows=1, cols=8)
    format_table(tbl_cam_deg, [0.7, 2.0, 0.7, 0.7, 0.6, 0.7, 0.6, 0.5], cam_deg_headers, cam_deg_rows)

    doc.add_paragraph(
        "Combined 9-Numeric-Case Performance:\n"
        "• Combined MAE: 4 / 9 ≈ 0.44 (Sum of errors = 1 in Case 6 + 3 in Case 9).\n"
        "• Zero-Error Percentage: 7 / 9 = 77.8%.\n"
        "• Undercounts: 2 cases (Case 6 by 1, Case 9 by 3). Overcounts: 0 cases (0.0%).\n"
        "• Degraded Frame Handling: 100% correctly flagged is_uncertain=True."
    )

    add_callout(
        doc,
        "Scientific Boundary Disclosure: All reported camera metrics represent synthetic benchmark performance on controlled high-contrast silhouettes. They MUST NOT be described as real-world classroom accuracy. In operational classrooms, clothing variability, direct sunlight, and bench occlusion reduce contour accuracy. Mandatory teacher review is strictly required.",
        "SYNTHETIC BENCHMARK DISCLAIMER"
    )

    # =========================================================================
    # SECTION 27: ANOMALY DETECTION EVALUATION
    # =========================================================================
    add_custom_heading(doc, "Section 27: Anomaly Detection Benchmark & Episode Evaluation", level=1)
    doc.add_paragraph(
        "AttendSure's deterministic rules were evaluated across the standard testbench preset "
        "(5 classes x 30 days = 150 sessions total; 5.0% anomaly injection rate; random seed = 42):\n\n"
        "Confusion Matrix:\n"
        "• True Positives (TP): 6 sessions\n"
        "• False Positives (FP): 0 sessions\n"
        "• True Negatives (TN): 139 sessions\n"
        "• False Negatives (FN): 5 sessions\n\n"
        "Metric Performance:\n"
        "• Overall Classification Accuracy: 96.67% (145 / 150 sessions)\n"
        "• Precision: 100.00% (6 / 6 alerts; zero false alarms)\n"
        "• Specificity: 100.00% (139 / 139 nominal sessions)\n"
        "• Session-Level Recall: 54.55% (6 / 11 injected sessions)\n"
        "• Event-Level Recall: 100.00% (2 of 2 multi-day episodes flagged)"
    )

    add_custom_heading(doc, "27.1 Detailed Breakdown of Injected Anomaly Sessions", level=2)
    anom_headers = ["Class ID", "Date", "Injected Anomaly Type", "Roll-Call", "Camera", "Triggered Rule", "Status", "Session ID"]
    anom_rows = [
        ("CLASS-04-A", "2026-10-16", "WEBCAM_DISCREPANCY", "P=27, E=32", "W=19", "RULE_WEBCAM_DISCREPANCY", "TP", "78660765-14f7-4e8d-95bc-b8d04094dded"),
        ("CLASS-02-A", "2026-10-17", "REPEATED_HEADCOUNT (Day 1)", "P=20, E=25", "W=20", "None (Prefix Day 1)", "FN", "610461e3-2a25-4888-8f02-bad0e7067ef4"),
        ("CLASS-02-A", "2026-10-18", "REPEATED_HEADCOUNT (Day 2)", "P=20, E=25", "W=21", "None (Prefix Day 2)", "FN", "f512c4c3-b253-4218-ac4a-37ea490617f2"),
        ("CLASS-02-A", "2026-10-19", "REPEATED_HEADCOUNT (Day 3)", "P=20, E=25", "W=19", "None (Prefix Day 3)", "FN", "27a0c3d7-7c96-4f79-b7e9-9acaa97065e1"),
        ("CLASS-02-A", "2026-10-20", "REPEATED_HEADCOUNT (Day 4)", "P=20, E=25", "W=21", "RULE_REPEATED_HEADCOUNT", "TP", "bc594585-9445-48c0-8ef8-c2d6f7fd5646"),
        ("CLASS-05-A", "2026-10-20", "REPEATED_HEADCOUNT (Day 1)", "P=27, E=32", "W=27", "None (Prefix Day 1)", "FN", "4a8ff810-784c-4f29-9804-02a2b07aa066"),
        ("CLASS-05-A", "2026-10-21", "REPEATED_HEADCOUNT (Day 2)", "P=27, E=32", "W=28", "None (Prefix Day 2)", "FN", "ec856f37-3bc1-4987-aff8-754d1238d630"),
        ("CLASS-05-A", "2026-10-22", "REPEATED_HEADCOUNT (Day 3)", "P=27, E=32", "W=26", "RULE_REPEATED_HEADCOUNT", "TP", "ef04e57d-cdcc-433a-a943-4aa096fc734d"),
        ("CLASS-05-A", "2026-10-23", "REPEATED_HEADCOUNT (Day 4)", "P=27, E=32", "W=26", "RULE_REPEATED_HEADCOUNT", "TP", "26242b40-a5cb-43a2-b98d-1ca68b6870b5"),
        ("CLASS-02-A", "2026-10-26", "WEBCAM_DISCREPANCY", "P=23, E=25", "W=17", "RULE_WEBCAM_DISCREPANCY", "TP", "12922f83-ef8c-485b-807a-30f2edd4253b"),
        ("CLASS-02-A", "2026-11-03", "ATTENDANCE_DROP", "P=9, E=25", "W=8", "RULE_ATTENDANCE_DROP", "TP", "8f9797b0-6d7c-43c9-b4a6-9f3c8d3aed99"),
    ]
    tbl_anom = doc.add_table(rows=1, cols=8)
    format_table(tbl_anom, [0.8, 0.7, 1.4, 0.7, 0.5, 1.3, 0.4, 0.6], anom_headers, anom_rows)

    doc.add_paragraph(
        "Mathematical Explanation of Session-Level (54.55%) vs. Event-Level (100.0%) Recall:\n"
        "• Episode 1 (EVT-CLASS-02-A-1): 4 consecutive days with P=20. Days 1, 2, and 3 are pre-threshold prefix accumulation days (3 FN). "
        "Alert ALT-3c834b35 fires on Day 4 (1 TP) -> Event Detected.\n"
        "• Episode 2 (EVT-CLASS-05-A-2): 4 consecutive days with P=27. Days 1 and 2 accumulate history (2 FN). "
        "Alert fires on Day 3 (TP) and Day 4 (TP) -> Event Detected.\n"
        "• Single-Day Anomalies: All 3 single-day anomalies were detected immediately on the day of occurrence (3 TP).\n"
        "• Accounting: TP = 1 + 2 + 3 = 6. FN = 3 + 2 = 5 (all prefix sessions). Session Recall = 6 / 11 = 54.55%.\n"
        "• Event-Level Success Criterion: If at least one alert fires during a multi-day episode, the episode is successfully detected. "
        "Event Recall = 2 of 2 = 100.00%."
    )

    add_custom_heading(doc, "27.2 Machine Learning Comparison (Decision Tree Holdout)", level=2)
    doc.add_paragraph(
        "The CART shallow decision tree (max_depth=4) was evaluated on 88 independent holdout test sessions across 4 unseen classes:\n"
        "• Accuracy: 92.05% (81 / 88 sessions)\n"
        "• Recall (Sensitivity): 80.00% (4 / 5 anomalous sessions)\n"
        "• Specificity: 92.77% (77 / 83 nominal sessions)\n"
        "• Precision: 40.00% (4 / 10 flagged sessions)\n"
        "• F1-Score: 53.33%\n\n"
        "Comparison: The decision tree offers higher session sensitivity to subtle multi-variate deviations, but deterministic rules provide "
        "superior precision (100% vs 40%) and instant explainability, preventing false alarms that demoralize rural teachers."
    )

    # =========================================================================
    # SECTION 28: PERFORMANCE EVALUATION & LATENCY DECOMPOSITION
    # =========================================================================
    add_custom_heading(doc, "Section 28: Performance Evaluation & Latency Decomposition", level=1)
    doc.add_paragraph(
        "Latency benchmarks were measured against the live cloud instance connected to Neon PostgreSQL in AWS Singapore across 5 repeated runs:"
    )

    lat_headers = ["Application View / Operation", "Cold Start", "Warm p50", "95th % (p95)", "Architectural Workload & Status"]
    lat_rows = [
        ("Overview Screen", "2,399.79 ms", "343.16 ms", "362.52 ms", "Reads cached summary, renders 5 KPI cards (PASS)"),
        ("Attendance Records", "2,336.50 ms", "158.65 ms", "509.88 ms", "Pagination, cohort filtering table (PASS)"),
        ("Mark Attendance Screen", "3,450.12 ms", "1,034.20 ms", "4,141.25 ms", "Mounts roll-call form, camera component (PASS)"),
        ("Settings Screen", "2,867.52 ms", "1,017.03 ms", "1,265.44 ms", "Cached DB health ping, storage stats (PASS)"),
        ("Needs Attention (Slower Screen)", "2,110.29 ms", "2,000.53 ms", "2,975.47 ms", "Renders expandable triage cards & review forms"),
        ("Reports & Export (Slower Screen)", "3,684.05 ms", "3,684.05 ms", "6,901.05 ms", "Computes longitudinal aggregations, CSV buffer"),
        ("Cold Application Launch", "6,554.75 ms", "N/A", "N/A", "Initial Streamlit runtime spin-up & bundle parsing"),
        ("Login Submission to Dashboard", "2,022.02 ms", "1,508.27 ms", "2,022.02 ms", "PBKDF2 verification & dashboard mounting"),
    ]
    tbl_lat = doc.add_table(rows=1, cols=5)
    format_table(tbl_lat, [1.8, 1.1, 1.0, 1.0, 1.6], lat_headers, lat_rows)

    doc.add_paragraph(
        "Multi-Layer Latency Decomposition & Slower Screen Analysis:\n"
        "1. Network Round-Trip Transit (Singapore to India): ~422 ms p50 (662 ms cold / p95) due to physical transit to AWS ap-southeast-1.\n"
        "2. Database Query Execution: Cold 395 ms; < 0.25 ms warm when served from in-memory cache / ~12–25 ms direct pool query.\n"
        "3. Streamlit Script Execution: Average ~1,372 ms across views during AST evaluation.\n"
        "4. Slower Screen Root Cause:\n"
        "   - Needs Attention (~2.00s warm p50): Constructs expandable triage cards, HTML evidence blocks, reviewer inputs, and audit entries.\n"
        "   - Reports & Export (~3.68s warm p50): Performs on-the-fly cross-cohort aggregations and generates downloadable CSV byte buffers.\n"
        "5. Browser DOM Rendering: Estimated at 50–150 ms; explicitly documented as an unmeasured limitation of headless test harnesses.\n"
        "SLA Conclusion: Not all six screens meet the 2-second target. 4 screens meet the <= 2.0s target, while Needs Attention and Reports require 2.0 to 3.7 seconds."
    )

    # =========================================================================
    # SECTION 29: OPERATIONAL LIMITATIONS & SCIENTIFIC RISKS
    # =========================================================================
    add_custom_heading(doc, "Section 29: Operational Limitations & Scientific Risks", level=1)
    doc.add_paragraph(
        "Academic rigor requires explicit disclosure of five operational limitations:\n"
        "1. Camera Silhouette Sensitivity: In real classrooms, low illumination (< 40 lux), direct window glare, and crowded wooden benches "
        "cause contour merging and undercounting. The camera must remain an assistive aid with mandatory teacher confirmation.\n"
        "2. Chronological Streak Delay: The repeated headcount detector requires 4 school days of identical attendance before firing. "
        "A short fraudulent streak (e.g. 2 days) will not trigger an alert.\n"
        "3. Absence of Student-Level Tracking: AttendSure tracks class numbers, not individual truant student names. This is an intentional "
        "architectural tradeoff protecting child privacy.\n"
        "4. Cloud Network Transit Latency: Hosting Neon PostgreSQL in Singapore adds ~420 ms of baseline transit latency for Indian clients, "
        "necessitating local in-memory caching.\n"
        "5. Serverless Cold Start: Cold application boots on serverless cloud hosts require ~6.5 seconds due to Python bundle spin-up."
    )

    # =========================================================================
    # SECTION 30: FUTURE ENHANCEMENTS & ROADMAP
    # =========================================================================
    add_custom_heading(doc, "Section 30: Future Enhancements & Technical Roadmap", level=1)
    doc.add_paragraph(
        "Future iterations of AttendSure could explore three engineering extensions:\n"
        "1. Physical IoT Hardware Pilot: Integrate physical low-cost NFC/RFID card readers via the verified `IRFIDProvider` abstraction.\n"
        "2. Edge Computer Vision: Deploy quantized edge models (e.g. MobileNet-SSD silhouette counting) directly on local Raspberry Pi hardware.\n"
        "3. Peer-to-Peer Mesh Sync: Implement local Wi-Fi mesh synchronization enabling adjacent classrooms to aggregate attendance "
        "and synchronize to cloud databases when a teacher's mobile device gains intermittent cellular connectivity."
    )

    # =========================================================================
    # SECTION 31: CONCLUSION
    # =========================================================================
    add_custom_heading(doc, "Section 31: Conclusion", level=1)
    doc.add_paragraph(
        "The Rural School Attendance Integrity and Intervention Decision System demonstrates that high-integrity attendance verification "
        "can be delivered reliably, affordably, and ethically without resorting to child biometric surveillance or costly hardware. "
        "By grounding the system in four foundational principles—offline-first resilience, multi-signal explainable detection, "
        "decision support rather than accusation, and strict zero-PII data privacy—AttendSure bridges the gap between classroom reality and "
        "administrative accountability."
    )
    doc.add_paragraph(
        "With 414 passing automated tests (100% pass rate in 87s), 96.67% rule accuracy, 100% precision, 100% event-level recall, "
        "sub-second query execution, and a live cloud deployment backed by serverless PostgreSQL, the system is technically verified, "
        "scientifically bounded, and ready for academic demonstration."
    )

    # =========================================================================
    # SECTION 32: REFERENCES & STATUTORY FRAMEWORKS
    # =========================================================================
    add_custom_heading(doc, "Section 32: References & Statutory Frameworks", level=1)
    refs = [
        "1. Smart India Hackathon (SIH 2025): Problem Statement SIH25012, 'Automated Attendance System for Rural Schools', Department of Higher Education, Government of Punjab. Theme: Smart Education.",
        "2. Government of India: Digital Personal Data Protection (DPDP) Act, 2023. Act No. 22 of 2023. Special provisions regarding children's data and biometric processing.",
        "3. Ministry of Education, Government of India: Unified District Information System for Education Plus (UDISE+) Data Standards and Guidelines (2023-24).",
        "4. Ministry of Education, Government of India: PM POSHAN (Pradhan Mantri Poshan Shakti Nirman) National Scheme Guidelines for Mid-Day Meal in Schools (2021).",
        "5. Breiman, L., Friedman, J., Stone, C. J., & Olshen, R. A. (1984). Classification and Regression Trees (CART). Chapman and Hall/CRC.",
        "6. Otsu, N. (1979). 'A threshold selection method from gray-level histograms.' IEEE Transactions on Systems, Man, and Cybernetics, 9(1), 62-66.",
        "7. Bradski, G. (2000). 'The OpenCV Library.' Dr. Dobb's Journal of Software Tools.",
        "8. Bayer, M. (2020). SQLAlchemy: Database Access Library for Python. Python Software Foundation.",
    ]
    for r in refs:
        p = doc.add_paragraph(r)
        p.paragraph_format.left_indent = Inches(0.4)
        p.paragraph_format.first_line_indent = Inches(-0.4)
        p.paragraph_format.space_after = Pt(4)

    # =========================================================================
    # SECTION 33: APPENDICES & EMPIRICAL EVIDENCE
    # =========================================================================
    add_custom_heading(doc, "Section 33: Appendices & Empirical Verification Evidence", level=1)
    doc.add_paragraph(
        "Appendix A: Repository & Database Integrity Checksums\n"
        "• Working Branch: feature/modern-saas-ui\n"
        "• Verified Head Commit: f65ff3f7025b9b97ae8b2068bdda08e313ff01d9\n"
        "• Target main Branch Commit: 7324e9e067b7b0d01084b486adc04d0cc0a38c66 (Verified Strictly Unaltered)\n"
        "• Operational Database File: data/attendsure.db\n"
        "• Operational Database SHA256: 46C22853EF5697DFE449FD0D61CFE5E719A84FF5C8260A2BA0F16935ED97F6AE (Verified Strictly Unaltered)\n\n"
        "Appendix B: Test Suite Execution Command & Log Summary\n"
        "Execution Command: pytest\n"
        "Result: 414 passed in 87.32s (Python 3.13.9, pytest-8.4.2, pluggy-1.5.0)\n"
        "Regressions: 0 failures, 0 errors, 0 warnings."
    )

    doc.save(str(OUTPUT_DOCX))
    print(f"DOCX Report saved successfully: {OUTPUT_DOCX}")


def convert_docx_to_pdf():
    """Converts the generated DOCX report to PDF using Microsoft Word COM automation."""
    print("=" * 70)
    print("Converting DOCX Report to PDF via Microsoft Word COM...")
    print("=" * 70)

    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False

        docx_abs = str(OUTPUT_DOCX.resolve())
        pdf_abs = str(OUTPUT_PDF.resolve())

        print(f"Opening: {docx_abs}")
        doc = word.Documents.Open(docx_abs)
        print(f"Exporting PDF (wdFormatPDF=17): {pdf_abs}")
        doc.SaveAs(pdf_abs, FileFormat=17)
        doc.Close()
        word.Quit()
        print(f"PDF generated successfully: {OUTPUT_PDF} ({OUTPUT_PDF.stat().st_size} bytes)")
    except Exception as exc:
        print(f"Word COM conversion encountered error: {exc}")
        print("Note: DOCX is available. Ensure Word COM permissions or use alternative converter if needed.")


if __name__ == "__main__":
    build_complete_academic_report()
    convert_docx_to_pdf()
