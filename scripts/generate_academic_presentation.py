#!/usr/bin/env python3
"""Academic Presentation Generator for Rural School Attendance Integrity and Intervention Decision System.

Generates a professional 16-slide widescreen (16:9) PowerPoint presentation conforming to:
- Official Project Title: Rural School Attendance Integrity and Intervention Decision System
- Mentor: Mr. Hitesh Jangid
- Authors: Ashish Kumar Tripathi (Reg No. 12509400, Roll No. 21) & Harsh Jakhar (Reg No. 12517556, Roll No. 8)
- Problem Statement: SIH 2025: SIH25012 (Smart Education, Govt of Punjab, Higher Education)
- Repository: https://github.com/ashishkumartripathi/AttendSure
- Metrics: Verified 100% against docs/technical_evaluation_report.md
"""

from pathlib import Path
import pptx
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = REPO_ROOT / "submission"
OUTPUT_PPTX = SUBMISSION_DIR / "presentation" / "Rural_School_Attendance_System_Presentation.pptx"
SCREENSHOTS_DIR = SUBMISSION_DIR / "screenshots"

# Palette: Academic Forest & Sage Green Theme
COLOR_BG = RGBColor(248, 250, 248)          # #F8FAF8 Off-white/mint
COLOR_CARD_BG = RGBColor(240, 245, 241)     # #F0F5F1 Soft sage card
COLOR_CARD_BORDER = RGBColor(218, 230, 220) # Subtle border
COLOR_DARK_GREEN = RGBColor(23, 74, 50)     # #174A32 Primary header
COLOR_FOREST = RGBColor(35, 122, 80)        # #237A50 Accent green
COLOR_SAGE = RGBColor(71, 125, 80)          # #477D50 Secondary accent
COLOR_TEXT_DARK = RGBColor(33, 37, 41)      # #212529 Dark charcoal body
COLOR_TEXT_MUTED = RGBColor(108, 117, 125)  # #6C757D Muted gray
COLOR_WHITE = RGBColor(255, 255, 255)
COLOR_WARN = RGBColor(180, 80, 50)          # Warm rust warning
COLOR_HIGHLIGHT = RGBColor(20, 110, 180)    # Soft slate blue


def create_deck():
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_slide_base(title_text: str, category_text: str = "AttendSure Academic Evaluation", slide_num: int = 1):
        slide = prs.slides.add_slide(blank_layout)

        # Background fill
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_BG
        bg.line.fill.background()

        # Top Accent Bar
        top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.1))
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = COLOR_FOREST
        top_bar.line.fill.background()

        # Header Category & Title
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.7), Inches(1.1))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p_cat = tf.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = COLOR_FOREST

        p_title = tf.add_paragraph()
        p_title.text = title_text
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = COLOR_DARK_GREEN

        # Footer
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(7.05), Inches(11.7), Inches(0.35))
        ftf = footer_box.text_frame
        ftf.margin_left = ftf.margin_top = ftf.margin_right = ftf.margin_bottom = 0
        p_foot = ftf.paragraphs[0]
        p_foot.text = "Rural School Attendance Integrity and Intervention Decision System  |  Mentor: Mr. Hitesh Jangid"
        p_foot.font.size = Pt(9)
        p_foot.font.color.rgb = COLOR_TEXT_MUTED

        p_num = ftf.add_paragraph()
        p_num.text = f"{slide_num} / 16"
        p_num.font.size = Pt(9)
        p_num.font.bold = True
        p_num.alignment = PP_ALIGN.RIGHT
        p_num.font.color.rgb = COLOR_TEXT_MUTED

        return slide

    def add_card(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1)
        else:
            card.line.fill.background()
        return card

    # =========================================================================
    # SLIDE 1: Title Slide
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    bg1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = COLOR_BG
    bg1.line.fill.background()

    # Left Accent Panel
    panel1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.4), Inches(7.5))
    panel1.fill.solid()
    panel1.fill.fore_color.rgb = COLOR_DARK_GREEN
    panel1.line.fill.background()

    # Title Box
    tbox = slide1.shapes.add_textbox(Inches(1.2), Inches(1.2), Inches(11.0), Inches(2.6))
    ttf = tbox.text_frame
    ttf.word_wrap = True

    p0 = ttf.paragraphs[0]
    p0.text = "CSE276 CAPSTONE MINI PROJECT EVALUATION"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_FOREST

    p1 = ttf.add_paragraph()
    p1.text = "Rural School Attendance Integrity and\nIntervention Decision System"
    p1.font.size = Pt(32)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_DARK_GREEN

    p2 = ttf.add_paragraph()
    p2.text = "An Explainable, Privacy-First, Multi-Signal Decision-Support Platform for Resource-Constrained Schools"
    p2.font.size = Pt(15)
    p2.font.color.rgb = COLOR_TEXT_MUTED

    # Meta Cards (Team & Mentor)
    # Mentor Card
    m_card = add_card(slide1, Inches(1.2), Inches(4.3), Inches(5.2), Inches(2.2))
    mtf = m_card.text_frame
    mtf.word_wrap = True
    mtf.margin_left = Inches(0.3)
    mtf.margin_top = Inches(0.25)
    mp0 = mtf.paragraphs[0]
    mp0.text = "PROJECT MENTOR"
    mp0.font.size = Pt(10)
    mp0.font.bold = True
    mp0.font.color.rgb = COLOR_FOREST

    mp1 = mtf.add_paragraph()
    mp1.text = "Mr. Hitesh Jangid"
    mp1.font.size = Pt(18)
    mp1.font.bold = True
    mp1.font.color.rgb = COLOR_DARK_GREEN

    mp2 = mtf.add_paragraph()
    mp2.text = "Problem Statement: SIH 2025 (SIH25012)\nDepartment of Higher Education, Govt of Punjab"
    mp2.font.size = Pt(11)
    mp2.font.color.rgb = COLOR_TEXT_DARK

    # Team Card
    t_card = add_card(slide1, Inches(6.8), Inches(4.3), Inches(5.4), Inches(2.2))
    tttf = t_card.text_frame
    tttf.word_wrap = True
    tttf.margin_left = Inches(0.3)
    tttf.margin_top = Inches(0.25)
    tp0 = tttf.paragraphs[0]
    tp0.text = "STUDENT INVESTIGATORS"
    tp0.font.size = Pt(10)
    tp0.font.bold = True
    tp0.font.color.rgb = COLOR_FOREST

    tp1 = tttf.add_paragraph()
    tp1.text = "• Ashish Kumar Tripathi"
    tp1.font.size = Pt(14)
    tp1.font.bold = True
    tp1.font.color.rgb = COLOR_DARK_GREEN
    tp1_sub = tttf.add_paragraph()
    tp1_sub.text = "   Reg. No: 12509400  |  Roll No: 21"
    tp1_sub.font.size = Pt(11)
    tp1_sub.font.color.rgb = COLOR_TEXT_MUTED

    tp2 = tttf.add_paragraph()
    tp2.text = "• Harsh Jakhar"
    tp2.font.size = Pt(14)
    tp2.font.bold = True
    tp2.font.color.rgb = COLOR_DARK_GREEN
    tp2_sub = tttf.add_paragraph()
    tp2_sub.text = "   Reg. No: 12517556  |  Roll No: 8"
    tp2_sub.font.size = Pt(11)
    tp2_sub.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 2: Problem Context & Rural Verification Dilemma
    # =========================================================================
    slide2 = add_slide_base("Problem Context: The Rural Attendance Verification Dilemma", "Context & Motivation", 2)
    
    c1 = add_card(slide2, Inches(0.8), Inches(1.6), Inches(3.6), Inches(5.0))
    tf1 = c1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = Inches(0.3)
    tf1.paragraphs[0].text = "1. Institutional Entitlements"
    tf1.paragraphs[0].font.size = Pt(14)
    tf1.paragraphs[0].font.bold = True
    tf1.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    p = tf1.add_paragraph()
    p.text = "\n• In rural primary & secondary education, daily attendance directly governs national entitlements:\n  - Mid-Day Meal (PM POSHAN) rations\n  - Welfare stipends & uniform subsidies\n  - Per-pupil funding allocations\n\n• Verified headcounts are vital for budgeting, resource allocation, and identifying chronic student dropouts."
    p.font.size = Pt(11)
    p.font.color.rgb = COLOR_TEXT_DARK

    c2 = add_card(slide2, Inches(4.8), Inches(1.6), Inches(3.6), Inches(5.0))
    tf2 = c2.text_frame
    tf2.word_wrap = True
    tf2.margin_left = tf2.margin_top = Inches(0.3)
    tf2.paragraphs[0].text = "2. Paper Ledger Failures"
    tf2.paragraphs[0].font.size = Pt(14)
    tf2.paragraphs[0].font.bold = True
    tf2.paragraphs[0].font.color.rgb = COLOR_WARN
    p = tf2.add_paragraph()
    p.text = "\n• Traditional pen-and-paper registers exhibit chronic operational vulnerabilities:\n  - Ledger Inertia: Rushed teachers copy previous day's attendance counts.\n  - Arithmetic Transcription Errors: Human error in monthly summaries.\n  - Roster Inflation: Ghost enrollments to prevent funding cutbacks.\n\n• Zero auditability or real-time visibility for block education officers."
    p.font.size = Pt(11)
    p.font.color.rgb = COLOR_TEXT_DARK

    c3 = add_card(slide2, Inches(8.8), Inches(1.6), Inches(3.7), Inches(5.0))
    tf3 = c3.text_frame
    tf3.word_wrap = True
    tf3.margin_left = tf3.margin_top = Inches(0.3)
    tf3.paragraphs[0].text = "3. Why Biometrics Fail"
    tf3.paragraphs[0].font.size = Pt(14)
    tf3.paragraphs[0].font.bold = True
    tf3.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    p = tf3.add_paragraph()
    p.text = "\n• Biometric scanners & facial recognition fail in rural schools:\n  - Infrastructure Fragility: Frequent blackouts, high dust, zero internet.\n  - High Sensor Error: Developing fingerprints of young children fail.\n  - Child Privacy & Legal Hazards: Centralized facial embeddings of minors violate DPDP & child protection norms.\n  - Adversarial Stigma: Treats educators as suspects."
    p.font.size = Pt(11)
    p.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 3: Problem Statement Verification (SIH25012)
    # =========================================================================
    slide3 = add_slide_base("Official Problem Statement & Institutional Authority", "Problem Definition", 3)

    c_sih = add_card(slide3, Inches(0.8), Inches(1.6), Inches(11.7), Inches(1.8), bg_color=RGBColor(240, 248, 242))
    stf = c_sih.text_frame
    stf.word_wrap = True
    stf.margin_left = stf.margin_top = Inches(0.3)
    stf.paragraphs[0].text = "SMART INDIA HACKATHON (SIH) 2025 — OFFICIAL PROBLEM STATEMENT"
    stf.paragraphs[0].font.size = Pt(11)
    stf.paragraphs[0].font.bold = True
    stf.paragraphs[0].font.color.rgb = COLOR_FOREST
    sp1 = stf.add_paragraph()
    sp1.text = "Problem Statement ID: SIH25012  |  Title: Automated Attendance System for Rural Schools"
    sp1.font.size = Pt(16)
    sp1.font.bold = True
    sp1.font.color.rgb = COLOR_DARK_GREEN
    sp2 = stf.add_paragraph()
    sp2.text = "Organization / Department: Government of Punjab — Department of Higher Education  |  Theme: Smart Education (Software)"
    sp2.font.size = Pt(12)
    sp2.font.color.rgb = COLOR_TEXT_DARK

    # Detail comparison grid
    c_left = add_card(slide3, Inches(0.8), Inches(3.6), Inches(5.7), Inches(3.1))
    ltf = c_left.text_frame
    ltf.word_wrap = True
    ltf.margin_left = ltf.margin_top = Inches(0.3)
    ltf.paragraphs[0].text = "Authoritative Mandate"
    ltf.paragraphs[0].font.size = Pt(14)
    ltf.paragraphs[0].font.bold = True
    ltf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    lp = ltf.add_paragraph()
    lp.text = "• The problem statement calls for an automated, low-cost attendance monitoring system suited for rural schools where conventional biometric or internet-dependent methods fail.\n• Must bridge the gap between classroom roll call and administrative accountability without creating operational bottlenecks for rural educators."
    lp.font.size = Pt(11)
    lp.font.color.rgb = COLOR_TEXT_DARK

    c_right = add_card(slide3, Inches(6.8), Inches(3.6), Inches(5.7), Inches(3.1))
    rtf = c_right.text_frame
    rtf.word_wrap = True
    rtf.margin_left = rtf.margin_top = Inches(0.3)
    rtf.paragraphs[0].text = "AttendSure's Focused Contribution"
    rtf.paragraphs[0].font.size = Pt(14)
    rtf.paragraphs[0].font.bold = True
    rtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    rp = rtf.add_paragraph()
    rp.text = "• Rather than adding intrusive surveillance, AttendSure introduces an offline-first, explainable decision-support system.\n• Replaces opaque biometric matching with multi-signal statistical auditing: roll-call invariants, rolling drop detection, repeated count streak tracking, and non-biometric silhouette estimation.\n• Strictly zero-PII: audits aggregated cohort counts, not children's faces."
    rp.font.size = Pt(11)
    rp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 4: Proposed Solution & Core Pillars
    # =========================================================================
    slide4 = add_slide_base("Proposed Solution: The AttendSure Paradigm", "System Overview", 4)

    pillars = [
        ("Offline-First by Design", "Operates seamlessly on commodity laptops or school PCs without cloud dependencies. Local embedded SQLite handles complete offline operations with sub-second queries.", COLOR_FOREST),
        ("Multi-Signal Detection", "Combines three complementary statistical signals: single-day drops against rolling medians, identical headcount streaks, and cross-modal silhouette verification.", COLOR_DARK_GREEN),
        ("Decision Support, Not Accusation", "Alerts strictly serve as signals for human review. School headmasters investigate contextual ground reality (e.g. floods, crop harvest, local festivals) before taking action.", COLOR_SAGE),
        ("Strict Child Privacy (Zero PII)", "No student names, roll numbers, photos, facial landmarks, or biometric templates are captured or stored. Aggregated class counts are the sole atomic data unit.", COLOR_FOREST),
    ]

    for idx, (head, desc, col) in enumerate(pillars):
        x = Inches(0.8 + (idx % 2) * 5.95)
        y = Inches(1.6 + (idx // 2) * 2.65)
        card = add_card(slide4, x, y, Inches(5.7), Inches(2.4))
        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = ctf.margin_top = Inches(0.3)
        ctf.paragraphs[0].text = f"PILLAR 0{idx+1}: {head}"
        ctf.paragraphs[0].font.size = Pt(13)
        ctf.paragraphs[0].font.bold = True
        ctf.paragraphs[0].font.color.rgb = col
        cp = ctf.add_paragraph()
        cp.text = f"\n{desc}"
        cp.font.size = Pt(11)
        cp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 5: Project Objectives & Scope Boundaries
    # =========================================================================
    slide5 = add_slide_base("System Objectives & Formal Boundaries", "Scope & Assumptions", 5)

    o_card = add_card(slide5, Inches(0.8), Inches(1.6), Inches(5.7), Inches(5.1))
    otf = o_card.text_frame
    otf.word_wrap = True
    otf.margin_left = otf.margin_top = Inches(0.3)
    otf.paragraphs[0].text = "Verified System Objectives"
    otf.paragraphs[0].font.size = Pt(14)
    otf.paragraphs[0].font.bold = True
    otf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    op = otf.add_paragraph()
    op.text = "\n1. Explainable Anomaly Detection:\n   Implement deterministic, auditable rules with 5-field plain-language rationale.\n\n2. Strict Count Invariant Enforcement:\n   Guarantee Present + Absent = Enrollment across all inputs.\n\n3. Human-in-the-Loop Review Lifecycle:\n   Provide a four-state audit workflow (Pending, Acknowledged, Resolved, Dismissed).\n\n4. Assistive Non-Biometric Silhouette Estimation:\n   Provide advisory headcount estimates via contour segmentation with mandatory teacher confirmation.\n\n5. Dual-Mode Persistence:\n   Unified engine supporting cloud Neon PostgreSQL and offline local SQLite."
    op.font.size = Pt(11)
    op.font.color.rgb = COLOR_TEXT_DARK

    b_card = add_card(slide5, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.1))
    btf = b_card.text_frame
    btf.word_wrap = True
    btf.margin_left = btf.margin_top = Inches(0.3)
    btf.paragraphs[0].text = "Formal Boundaries & Non-Goals"
    btf.paragraphs[0].font.size = Pt(14)
    btf.paragraphs[0].font.bold = True
    btf.paragraphs[0].font.color.rgb = COLOR_WARN
    bp = btf.add_paragraph()
    bp.text = "\n• NO Facial Recognition or Biometrics:\n   Face embeddings, landmarks, and facial databases are strictly prohibited by system architecture.\n\n• NO Physical RFID Hardware Claimed:\n   RFID interface is implemented as a clean software provider abstraction for future IoT deployment; no physical scanners were deployed.\n\n• NO PM POSHAN Direct Integration:\n   Meal ration tracking is a future scope item; attendance audits remain the core scope.\n\n• NO Real-World 30-Day Pilot Claimed:\n   Evaluation is grounded in synthetic benchmarks and software verification, not live school deployments."
    bp.font.size = Pt(11)
    bp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 6: System Architecture & Data Flow
    # =========================================================================
    slide6 = add_slide_base("System Architecture: 4-Tier Decoupled Framework", "Architecture & Engineering", 6)

    # 4 Tier Cards horizontally
    tiers = [
        ("1. Client Tier", "Streamlit Modern SaaS UI\n(Port 8501)\n\n• Responsive layout\n• Ephemeral HTML5 camera\n• Role-based view router\n• Zero transition ghosting", COLOR_DARK_GREEN),
        ("2. Application Tier", "Core Attendance Engine\n(Python 3.13)\n\n• Invariant validator\n• Session management\n• Short-TTL read cache\n• Audit logging service", COLOR_FOREST),
        ("3. Intelligence Tier", "Detection & ML Modules\n(Explainable AI)\n\n• 3 Deterministic rules\n• CART Decision Tree\n• Contour segmentation\n• Human review lifecycle", COLOR_SAGE),
        ("4. Persistence Tier", "SQLAlchemy Dual Engine\n(Unified Abstraction)\n\n• Neon PostgreSQL 18.6\n• Local SQLite fallback\n• 6 Relational check constraints\n• Connection pooling", COLOR_DARK_GREEN),
    ]

    for idx, (thead, tdesc, tcol) in enumerate(tiers):
        tcard = add_card(slide6, Inches(0.8 + idx * 2.95), Inches(1.6), Inches(2.8), Inches(3.6))
        tttf = tcard.text_frame
        tttf.word_wrap = True
        tttf.margin_left = tttf.margin_top = Inches(0.2)
        tttf.paragraphs[0].text = thead
        tttf.paragraphs[0].font.size = Pt(12)
        tttf.paragraphs[0].font.bold = True
        tttf.paragraphs[0].font.color.rgb = tcol
        tp = tttf.add_paragraph()
        tp.text = f"\n{tdesc}"
        tp.font.size = Pt(10)
        tp.font.color.rgb = COLOR_TEXT_DARK

    # Bottom summary card
    bsum = add_card(slide6, Inches(0.8), Inches(5.4), Inches(11.7), Inches(1.4))
    bstf = bsum.text_frame
    bstf.word_wrap = True
    bstf.margin_left = bstf.margin_top = Inches(0.25)
    bstf.paragraphs[0].text = "ENGINEERING HIGHLIGHT: STRICT PRODUCTION ISOLATION"
    bstf.paragraphs[0].font.size = Pt(11)
    bstf.paragraphs[0].font.bold = True
    bstf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    bp = bstf.add_paragraph()
    bp.text = "When ATTENDSURE_ENVIRONMENT=production is active, the database engine enforces managed Neon Cloud PostgreSQL via psycopg v3 and strictly forbids silent fallback to local SQLite. In offline development mode, it gracefully operates on embedded SQLite."
    bp.font.size = Pt(10.5)
    bp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 7: Technology Stack
    # =========================================================================
    slide7 = add_slide_base("Technology Stack & Engineering Standards", "Engineering Specifications", 7)

    stack_items = [
        ("Application Runtime", "Python 3.13.9", "Modern asynchronous runtime with robust typing and memory optimization."),
        ("User Interface", "Streamlit 1.40+", "Declarative web UI with responsive layout, custom CSS, and session state."),
        ("Cloud Database", "Neon PostgreSQL 18.6", "Serverless PostgreSQL hosted in AWS Singapore (aws-ap-southeast-1)."),
        ("Local Persistence", "SQLite 3", "Zero-configuration, serverless, offline-first embedded transactional database."),
        ("DB Abstraction", "SQLAlchemy 2.0+ & psycopg v3", "Connection pooling, relational schema reflection, and driver normalization."),
        ("Image Processing", "OpenCV (headless) & Pillow", "Laplacian blur variance, luminance analysis, and Otsu contour extraction."),
        ("Anomaly Modeling", "Scikit-Learn (CART Tree)", "Interpretable shallow decision tree (max_depth=4) with class weighting."),
        ("Quality Assurance", "pytest & pytest-asyncio", "417 automated unit, integration, and UI tests passing in 79.9s."),
    ]

    for idx, (cat, tech, note) in enumerate(stack_items):
        col_idx = idx % 2
        row_idx = idx // 2
        x = Inches(0.8 + col_idx * 5.95)
        y = Inches(1.6 + row_idx * 1.3)
        scard = add_card(slide7, x, y, Inches(5.7), Inches(1.15))
        stf = scard.text_frame
        stf.word_wrap = True
        stf.margin_left = Inches(0.25)
        stf.margin_top = Inches(0.15)
        stf.paragraphs[0].text = f"{cat}: {tech}"
        stf.paragraphs[0].font.size = Pt(11)
        stf.paragraphs[0].font.bold = True
        stf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
        sp = stf.add_paragraph()
        sp.text = note
        sp.font.size = Pt(9.5)
        sp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 8: Camera-Assisted Roll-Call Workflow
    # =========================================================================
    slide8 = add_slide_base("Non-Biometric Camera Silhouette Estimation", "Computer Vision Pipeline", 8)

    # 4 Pipeline steps
    csteps = [
        ("1. Quality Gate", "• Evaluates blur via discrete Laplacian operator variance (sigma^2 >= 100).\n• Evaluates lighting via mean luminance (40 <= mu <= 225).\n• Minimum resolution: 320 x 240."),
        ("2. Silhouette Segmentation", "• Adaptive Otsu thresholding separates bodies from wall/desk.\n• Morphological opening removes high-frequency speckle noise.\n• Ephemeral memory only."),
        ("3. Contour Filtering", "• Filters connected components by aspect ratio (1.2 <= H/W <= 3.5).\n• Filters by bounding area (0.8% <= Area <= 20.0%).\n• Bench cluster normalization."),
        ("4. Mandatory Review", "• Count is strictly advisory.\n• Teacher visually inspects estimate.\n• Adjusts count if needed.\n• Confirms before database commit."),
    ]

    for idx, (stitle, sdesc) in enumerate(csteps):
        sc = add_card(slide8, Inches(0.8 + idx * 2.95), Inches(1.6), Inches(2.8), Inches(3.6))
        stf = sc.text_frame
        stf.word_wrap = True
        stf.margin_left = stf.margin_top = Inches(0.2)
        stf.paragraphs[0].text = stitle
        stf.paragraphs[0].font.size = Pt(12)
        stf.paragraphs[0].font.bold = True
        stf.paragraphs[0].font.color.rgb = COLOR_FOREST
        sp = stf.add_paragraph()
        sp.text = f"\n{sdesc}"
        sp.font.size = Pt(10)
        sp.font.color.rgb = COLOR_TEXT_DARK

    # Privacy banner
    c_priban = add_card(slide8, Inches(0.8), Inches(5.4), Inches(11.7), Inches(1.4), bg_color=RGBColor(245, 248, 245))
    ptf = c_priban.text_frame
    ptf.word_wrap = True
    ptf.margin_left = ptf.margin_top = Inches(0.25)
    ptf.paragraphs[0].text = "CORE PRIVACY SAFEGUARD: ZERO BIOMETRICS & EPHEMERAL PROCESSING"
    ptf.paragraphs[0].font.size = Pt(11)
    ptf.paragraphs[0].font.bold = True
    ptf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    pp = ptf.add_paragraph()
    pp.text = "Captured image frames are processed entirely in ephemeral RAM (io.BytesIO) and permanently purged upon function completion. No image files (.jpg, .png) are saved to disk, and no facial embeddings or identity markers are extracted."
    pp.font.size = Pt(10.5)
    pp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 9: Explainable Anomaly Detection Methodology
    # =========================================================================
    slide9 = add_slide_base("Explainable Anomaly Detection: 3 Production Rules", "Detection Engine", 9)

    rules = [
        ("Rule 1: Attendance Drop", "RULE_ATTENDANCE_DROP", "Detects statistically significant single-day drops relative to historical baseline.", "Threshold: Present count drops >= 30% below cohort's 5-session rolling median.\nFlags: Legitimate seasonal disruptions (harvest, floods) or reporting anomalies.\nPriority: REVIEW_REQUIRED"),
        ("Rule 2: Repeated Headcount", "RULE_REPEATED_HEADCOUNT", "Detects unnatural streaks of identical attendance indicative of ledger copying.", "Threshold: Identical present count across >= 4 consecutive days (>= 6 for 100% attendance).\nFlags: Inertial register copying without physical headcount roll-call.\nPriority: REVIEW_REQUIRED"),
        ("Rule 3: Camera Discrepancy", "RULE_WEBCAM_DISCREPANCY", "Audits cross-modal consistency between manual entry and camera count.", "Threshold: |Present Count - Camera Count| >= 5 students when camera is SUCCESS.\nFlags: High count inflation or severe camera occlusion requiring verification.\nPriority: REVIEW_REQUIRED"),
    ]

    for idx, (rtitle, rid, rdesc, rdetail) in enumerate(rules):
        rcard = add_card(slide9, Inches(0.8 + idx * 3.95), Inches(1.6), Inches(3.8), Inches(5.1))
        rtf = rcard.text_frame
        rtf.word_wrap = True
        rtf.margin_left = rtf.margin_top = Inches(0.25)
        rtf.paragraphs[0].text = rtitle
        rtf.paragraphs[0].font.size = Pt(13)
        rtf.paragraphs[0].font.bold = True
        rtf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
        rp1 = rtf.add_paragraph()
        rp1.text = f"ID: {rid}\n"
        rp1.font.size = Pt(9.5)
        rp1.font.bold = True
        rp1.font.color.rgb = COLOR_FOREST
        rp2 = rtf.add_paragraph()
        rp2.text = f"{rdesc}\n\n{rdetail}"
        rp2.font.size = Pt(10.5)
        rp2.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 10: Human Intervention & Decision Support Workflow
    # =========================================================================
    slide10 = add_slide_base("Human-in-the-Loop Review: Decision Support, Never Accusation", "Review Lifecycle", 10)

    # 4 State lifecycle boxes
    states = [
        ("PENDING REVIEW", "Initial state upon rule trigger.\nAlert is highlighted in Overview and Needs Attention queue.", COLOR_WARN),
        ("ACKNOWLEDGED", "Headmaster has inspected signal.\nScheduled for on-site verification during upcoming inspection.", COLOR_HIGHLIGHT),
        ("RESOLVED", "Legitimate cause confirmed.\nField note attached (e.g. monsoon flood verified; no misconduct).", COLOR_FOREST),
        ("DISMISSED", "Technical false alarm.\nCamera glare or lighting shadow verified by manual recount.", COLOR_TEXT_MUTED),
    ]

    for idx, (sname, sdesc, scol) in enumerate(states):
        scard = add_card(slide10, Inches(0.8 + idx * 2.95), Inches(1.6), Inches(2.8), Inches(2.2))
        stf = scard.text_frame
        stf.word_wrap = True
        stf.margin_left = stf.margin_top = Inches(0.2)
        stf.paragraphs[0].text = sname
        stf.paragraphs[0].font.size = Pt(12)
        stf.paragraphs[0].font.bold = True
        stf.paragraphs[0].font.color.rgb = scol
        sp = stf.add_paragraph()
        sp.text = f"\n{sdesc}"
        sp.font.size = Pt(9.5)
        sp.font.color.rgb = COLOR_TEXT_DARK

    # Lower Explanation Box: 5 Fields
    ebox = add_card(slide10, Inches(0.8), Inches(4.0), Inches(11.7), Inches(2.8))
    etf = ebox.text_frame
    etf.word_wrap = True
    etf.margin_left = etf.margin_top = Inches(0.3)
    etf.paragraphs[0].text = "MANDATORY 5-FIELD EXPLAINABILITY CONTRACT"
    etf.paragraphs[0].font.size = Pt(12)
    etf.paragraphs[0].font.bold = True
    etf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    ep = etf.add_paragraph()
    ep.text = "Every alert generated by AttendSure must produce human-interpretable rationale for rural administrators:\n" \
              "1. Rule Identifier & Title: Explicitly states which rule triggered.\n" \
              "2. Observed Value: Displays detected roll-call count, streak duration, or camera discrepancy.\n" \
              "3. Baseline Reference: Displays rolling median or expected historical baseline.\n" \
              "4. Applied Threshold: States mathematical cutoff (e.g. >= 30% drop or >= 4 consecutive days).\n" \
              "5. Plain-Language Rationale: Explains the educational or environmental significance without jargon."
    ep.font.size = Pt(11)
    ep.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 11: Interface Showcase (Screenshots)
    # =========================================================================
    slide11 = add_slide_base("Application Interface: Progressive Disclosure in Action", "User Interface Showcase", 11)

    # Place two real screenshots side by side
    img1 = SCREENSHOTS_DIR / "01_desktop_overview.png"
    img2 = SCREENSHOTS_DIR / "04_desktop_needs_attention.png"

    if img1.exists():
        slide11.shapes.add_picture(str(img1), Inches(0.8), Inches(1.6), width=Inches(5.7))
        c1_desc = slide11.shapes.add_textbox(Inches(0.8), Inches(5.8), Inches(5.7), Inches(0.8))
        c1_desc.text_frame.word_wrap = True
        c1_desc.text_frame.paragraphs[0].text = "Overview Screen: Plain-English KPI cards for today's active session, active today indicators, and daily attendance time-series trend."
        c1_desc.text_frame.paragraphs[0].font.size = Pt(10)
        c1_desc.text_frame.paragraphs[0].font.color.rgb = COLOR_TEXT_DARK

    if img2.exists():
        slide11.shapes.add_picture(str(img2), Inches(6.8), Inches(1.6), width=Inches(5.7))
        c2_desc = slide11.shapes.add_textbox(Inches(6.8), Inches(5.8), Inches(5.7), Inches(0.8))
        c2_desc.text_frame.word_wrap = True
        c2_desc.text_frame.paragraphs[0].text = "Needs Attention Screen: Expandable alert triage cards displaying rule evidence, baseline comparison tables, and administrative review actions."
        c2_desc.text_frame.paragraphs[0].font.size = Pt(10)
        c2_desc.text_frame.paragraphs[0].font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 12: Empirical Verification & Test Suite
    # =========================================================================
    slide12 = add_slide_base("Automated Verification Suite: 417 Tests Passing", "Verification & Quality Assurance", 12)

    # Metric Cards Top Row
    m_tests = add_card(slide12, Inches(0.8), Inches(1.6), Inches(2.7), Inches(1.6))
    mtf = m_tests.text_frame
    mtf.margin_left = mtf.margin_top = Inches(0.2)
    mtf.paragraphs[0].text = "TEST SUITE PASS RATE"
    mtf.paragraphs[0].font.size = Pt(10)
    mtf.paragraphs[0].font.bold = True
    mtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    mp = mtf.add_paragraph()
    mp.text = "100.0%"
    mp.font.size = Pt(28)
    mp.font.bold = True
    mp.font.color.rgb = COLOR_DARK_GREEN
    mp_sub = mtf.add_paragraph()
    mp_sub.text = "417 of 417 tests passing"
    mp_sub.font.size = Pt(9.5)
    mp_sub.font.color.rgb = COLOR_TEXT_MUTED

    m_time = add_card(slide12, Inches(3.8), Inches(1.6), Inches(2.7), Inches(1.6))
    mtf = m_time.text_frame
    mtf.margin_left = mtf.margin_top = Inches(0.2)
    mtf.paragraphs[0].text = "EXECUTION TIME"
    mtf.paragraphs[0].font.size = Pt(10)
    mtf.paragraphs[0].font.bold = True
    mtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    mp = mtf.add_paragraph()
    mp.text = "79.90 s"
    mp.font.size = Pt(28)
    mp.font.bold = True
    mp.font.color.rgb = COLOR_DARK_GREEN
    mp_sub = mtf.add_paragraph()
    mp_sub.text = "Python 3.13 / pytest"
    mp_sub.font.size = Pt(9.5)
    mp_sub.font.color.rgb = COLOR_TEXT_MUTED

    m_reg = add_card(slide12, Inches(6.8), Inches(1.6), Inches(2.7), Inches(1.6))
    mtf = m_reg.text_frame
    mtf.margin_left = mtf.margin_top = Inches(0.2)
    mtf.paragraphs[0].text = "REGRESSIONS / ERRORS"
    mtf.paragraphs[0].font.size = Pt(10)
    mtf.paragraphs[0].font.bold = True
    mtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    mp = mtf.add_paragraph()
    mp.text = "0"
    mp.font.size = Pt(28)
    mp.font.bold = True
    mp.font.color.rgb = COLOR_DARK_GREEN
    mp_sub = mtf.add_paragraph()
    mp_sub.text = "0 failures, 0 warnings"
    mp_sub.font.size = Pt(9.5)
    mp_sub.font.color.rgb = COLOR_TEXT_MUTED

    m_db = add_card(slide12, Inches(9.8), Inches(1.6), Inches(2.7), Inches(1.6))
    mtf = m_db.text_frame
    mtf.margin_left = mtf.margin_top = Inches(0.2)
    mtf.paragraphs[0].text = "DB CONSTRAINTS"
    mtf.paragraphs[0].font.size = Pt(10)
    mtf.paragraphs[0].font.bold = True
    mtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    mp = mtf.add_paragraph()
    mp.text = "6 Check"
    mp.font.size = Pt(28)
    mp.font.bold = True
    mp.font.color.rgb = COLOR_DARK_GREEN
    mp_sub = mtf.add_paragraph()
    mp_sub.text = "Enforced in schema"
    mp_sub.font.size = Pt(9.5)
    mp_sub.font.color.rgb = COLOR_TEXT_MUTED

    # Test breakdown table card
    b_table = add_card(slide12, Inches(0.8), Inches(3.4), Inches(11.7), Inches(3.4))
    ttf = b_table.text_frame
    ttf.word_wrap = True
    ttf.margin_left = ttf.margin_top = Inches(0.25)
    ttf.paragraphs[0].text = "VERIFIED TEST MODULE COVERAGE ACROSS CODEBASE"
    ttf.paragraphs[0].font.size = Pt(11)
    ttf.paragraphs[0].font.bold = True
    ttf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    tp = ttf.add_paragraph()
    tp.text = "• Authentication & RBAC (test_auth.py): 7 tests verifying PBKDF2 hashing, random salt, role separation, and bad login rejection.\n" \
              "• Data Validation & Check Constraints (test_data_validation.py): 30 tests validating count invariants (P+A=E), negative values, and dates.\n" \
              "• Database Engine & Persistence (test_db_engine.py, test_data_storage.py): 34 tests ensuring transaction rollback and zero silent SQLite fallback.\n" \
              "• Anomaly Detection Rules (test_detection_*.py): 49 tests verifying attendance drops, repeated headcounts, and camera discrepancies.\n" \
              "• Decision Tree Classifier (test_ml_decision_tree.py): 9 tests verifying CART model training, feature extraction, and holdout evaluation.\n" \
              "• Headless Streamlit UI (test_ui_*.py): 70+ tests driving AppTest across Overview, Mark, Records, Needs Attention, Reports, and Settings."
    tp.font.size = Pt(10.5)
    tp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 13: Anomaly Detection Benchmark Results
    # =========================================================================
    slide13 = add_slide_base("Anomaly Detection Evaluation: Deterministic Rules & ML", "Empirical Evaluation", 13)

    # Left: Deterministic Rules Table
    rcard = add_card(slide13, Inches(0.8), Inches(1.6), Inches(5.7), Inches(5.1))
    rtf = rcard.text_frame
    rtf.word_wrap = True
    rtf.margin_left = rtf.margin_top = Inches(0.25)
    rtf.paragraphs[0].text = "Deterministic Rules Benchmark (150 Sessions)"
    rtf.paragraphs[0].font.size = Pt(13)
    rtf.paragraphs[0].font.bold = True
    rtf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    rp = rtf.add_paragraph()
    rp.text = "Evaluated on 5 classes x 30 days (5.0% injection rate, Seed=42):\n\n" \
              "• Overall Accuracy: 96.67% (145 / 150 sessions)\n" \
              "• Precision: 100.00% (6 / 6 alerts; 0 false alarms)\n" \
              "• Specificity: 100.00% (139 / 139 nominal sessions)\n" \
              "• Session-Level Recall: 54.55% (6 / 11 injected sessions)\n" \
              "• Event-Level Recall: 100.00% (2 of 2 multi-day episodes flagged)\n\n" \
              "Operational Note: Session-level recall is 54.55% due to chronological prefix delay on repeated runs (alerts trigger on Day 4 of 4). Every multi-day episode triggered review alerts successfully."
    rp.font.size = Pt(10.5)
    rp.font.color.rgb = COLOR_TEXT_DARK

    # Right: ML Decision Tree Table
    mcard = add_card(slide13, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.1))
    mtf = mcard.text_frame
    mtf.word_wrap = True
    mtf.margin_left = mtf.margin_top = Inches(0.25)
    mtf.paragraphs[0].text = "Machine Learning Benchmark (Decision Tree)"
    mtf.paragraphs[0].font.size = Pt(13)
    mtf.paragraphs[0].font.bold = True
    mtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    mp = mtf.add_paragraph()
    mp.text = "Evaluated on 88 holdout test sessions across 4 unseen classes:\n\n" \
              "• Holdout Accuracy: 92.05% (81 / 88 sessions)\n" \
              "• Recall (Sensitivity): 80.00% (4 / 5 anomalous sessions)\n" \
              "• Specificity: 92.77% (77 / 83 nominal sessions)\n" \
              "• Precision: 40.00% (4 / 10 flagged sessions)\n" \
              "• F1-Score: 53.33%\n\n" \
              "Scientific Trade-Off: Decision tree offers higher session-level sensitivity to subtle deviations, but deterministic rules provide superior zero-false-alarm precision (100%) and instant explainability for rural teachers."
    mp.font.size = Pt(10.5)
    mp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 14: System Performance & Latency Decomposition
    # =========================================================================
    slide14 = add_slide_base("System Performance & Latency Decomposition", "System Benchmarks", 14)

    # 6 Screen Latency Cards
    screens = [
        ("Overview Screen", "343 ms (p50)", "362 ms (p95)", "Meets SLA", COLOR_FOREST),
        ("Attendance Records", "158 ms (p50)", "509 ms (p95)", "Meets SLA", COLOR_FOREST),
        ("Mark Attendance", "1,034 ms (p50)", "4,141 ms (p95)", "Meets SLA", COLOR_FOREST),
        ("Settings Screen", "1,017 ms (p50)", "1,265 ms (p95)", "Meets SLA", COLOR_FOREST),
        ("Needs Attention", "2,000 ms (p50)", "2,975 ms (p95)", "Slower View", COLOR_WARN),
        ("Reports & Export", "3,684 ms (p50)", "6,901 ms (p95)", "Slower View", COLOR_WARN),
    ]

    for idx, (sname, sp50, sp95, sstatus, scol) in enumerate(screens):
        col_idx = idx % 3
        row_idx = idx // 3
        x = Inches(0.8 + col_idx * 3.95)
        y = Inches(1.6 + row_idx * 1.6)
        card = add_card(slide14, x, y, Inches(3.8), Inches(1.4))
        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = ctf.margin_top = Inches(0.2)
        ctf.paragraphs[0].text = f"{sname} ({sstatus})"
        ctf.paragraphs[0].font.size = Pt(11)
        ctf.paragraphs[0].font.bold = True
        ctf.paragraphs[0].font.color.rgb = scol
        cp = ctf.add_paragraph()
        cp.text = f"Warm p50: {sp50}  |  p95: {sp95}"
        cp.font.size = Pt(10.5)
        cp.font.color.rgb = COLOR_TEXT_DARK

    # Bottom Latency Decomposition Box
    dec_box = add_card(slide14, Inches(0.8), Inches(4.9), Inches(11.7), Inches(1.9))
    dtf = dec_box.text_frame
    dtf.word_wrap = True
    dtf.margin_left = dtf.margin_top = Inches(0.25)
    dtf.paragraphs[0].text = "TRANSPARENT MULTI-LAYER LATENCY DECOMPOSITION"
    dtf.paragraphs[0].font.size = Pt(11)
    dtf.paragraphs[0].font.bold = True
    dtf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    dp = dtf.add_paragraph()
    dp.text = "• Network Transit: ~422 ms baseline round-trip to Neon PostgreSQL in AWS Singapore (aws-ap-southeast-1).\n" \
              "• Database Query Time: 395 ms cold; < 0.25 ms when served from in-memory short-TTL read cache.\n" \
              "• Slower Screens Explanation: Needs Attention (~2.00s) constructs expandable triage cards & HTML evidence; Reports (~3.68s) calculates longitudinal trends & generates CSV download buffer.\n" \
              "• Honest SLA Assessment: 4 of 6 screens satisfy the <= 2.0s target; analytical and triage screens require 2 to 3.7 seconds."
    dp.font.size = Pt(10)
    dp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 15: Limitations, Risks & Ethical Safeguards
    # =========================================================================
    slide15 = add_slide_base("Operational Limitations & Scientific Boundaries", "Limitations & Ethics", 15)

    lims = [
        ("Camera Silhouette Real-World Boundary", "The camera estimator achieves 0.14 MAE on synthetic silhouettes. We explicitly disclose that synthetic benchmarks do not guarantee equivalent accuracy in real classrooms with natural sunlight glare, clothing shadows, and bench occlusions. Mandatory teacher confirmation is enforced."),
        ("Absence of Physical RFID Hardware", "AttendSure includes a modular RFID provider software abstraction for future IoT card readers. No physical RFID hardware or antennas were tested or claimed for this project."),
        ("No Student-Level Tracking (Privacy Trade-Off)", "AttendSure intentionally tracks cohort counts rather than individual student identities. It cannot identify specific truant children by name—a deliberate privacy safeguard protecting minors under the DPDP Act."),
        ("Cloud Database Geographic Transit Latency", "Hosting Neon PostgreSQL in AWS Singapore introduces ~420 ms of network transit latency for Indian clients, mitigated by short-TTL in-memory caching and connection pooling."),
    ]

    for idx, (lhead, ldesc) in enumerate(lims):
        col_idx = idx % 2
        row_idx = idx // 2
        x = Inches(0.8 + col_idx * 5.95)
        y = Inches(1.6 + row_idx * 2.65)
        lcard = add_card(slide15, x, y, Inches(5.7), Inches(2.45))
        ltf = lcard.text_frame
        ltf.word_wrap = True
        ltf.margin_left = ltf.margin_top = Inches(0.25)
        ltf.paragraphs[0].text = lhead
        ltf.paragraphs[0].font.size = Pt(12)
        ltf.paragraphs[0].font.bold = True
        ltf.paragraphs[0].font.color.rgb = COLOR_WARN if "Physical" in lhead or "Real-World" in lhead else COLOR_DARK_GREEN
        lp = ltf.add_paragraph()
        lp.text = f"\n{ldesc}"
        lp.font.size = Pt(10)
        lp.font.color.rgb = COLOR_TEXT_DARK

    # =========================================================================
    # SLIDE 16: Conclusion & Academic References
    # =========================================================================
    slide16 = add_slide_base("Conclusion, Team & Academic References", "Summary & Acknowledgements", 16)

    # Conclusion Card
    ccard = add_card(slide16, Inches(0.8), Inches(1.6), Inches(5.7), Inches(5.1))
    ctf = ccard.text_frame
    ctf.word_wrap = True
    ctf.margin_left = ctf.margin_top = Inches(0.3)
    ctf.paragraphs[0].text = "Project Summary & Impact"
    ctf.paragraphs[0].font.size = Pt(14)
    ctf.paragraphs[0].font.bold = True
    ctf.paragraphs[0].font.color.rgb = COLOR_DARK_GREEN
    cp = ctf.add_paragraph()
    cp.text = "• Solved the Rural Attendance Dilemma:\n  Delivered a robust, privacy-first decision-support system without biometric surveillance or costly hardware.\n\n" \
              "• Verified Software Quality:\n  417 passing tests, 96.67% rule accuracy, 100% precision, 100% event recall, sub-second queries, and live cloud deployment.\n\n" \
              "• Institutional Readiness:\n  Equipped with progressive disclosure UI, relational constraints, zero silent fallback, and complete audit logging.\n\n" \
              "GitHub Repository:\nhttps://github.com/ashishkumartripathi/AttendSure"
    cp.font.size = Pt(11)
    cp.font.color.rgb = COLOR_TEXT_DARK

    # Team & References Right Card
    rcard = add_card(slide16, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.1))
    rtf = rcard.text_frame
    rtf.word_wrap = True
    rtf.margin_left = rtf.margin_top = Inches(0.3)
    rtf.paragraphs[0].text = "Academic Acknowledgements & References"
    rtf.paragraphs[0].font.size = Pt(14)
    rtf.paragraphs[0].font.bold = True
    rtf.paragraphs[0].font.color.rgb = COLOR_FOREST
    rp = rtf.add_paragraph()
    rp.text = "Project Mentor: Mr. Hitesh Jangid\n" \
              "Student Investigators:\n" \
              "• Ashish Kumar Tripathi (Reg No. 12509400, Roll No. 21)\n" \
              "• Harsh Jakhar (Reg No. 12517556, Roll No. 8)\n\n" \
              "Key References:\n" \
              "1. Smart India Hackathon (SIH 2025): Problem Statement SIH25012, Govt of Punjab, Higher Education.\n" \
              "2. Digital Personal Data Protection (DPDP) Act, 2023: Special provisions on children's biometric data.\n" \
              "3. Ministry of Education, Govt of India: Unified District Information System for Education Plus (UDISE+).\n" \
              "4. Breiman, L. et al. (1984): Classification and Regression Trees (CART)."
    rp.font.size = Pt(10.5)
    rp.font.color.rgb = COLOR_TEXT_DARK

    prs.save(str(OUTPUT_PPTX))
    print(f"Presentation saved successfully: {OUTPUT_PPTX} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    create_deck()
