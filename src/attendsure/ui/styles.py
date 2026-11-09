"""Shared styling and visual theme definitions for AttendSure Streamlit UI.

Accurately reproduces the visual specification of the supplied reference design:
- Outer background: #F0F3EA with soft sage gradient / curves
- Workspace background: #FAFBF8
- Sidebar background: #F0F3EA
- Surface/Card background: #FFFFFF
- Card border: #E5EAE1
- Primary forest green: #174A32
- Primary action green: #237A50
- Secondary green: #548D59
- Pastel green: #DCEBD8
- Soft green surface: #EAF2E6
- Primary text: #172F25
- Secondary text: #77837A
- Warning pastel: #FFF0D2 / Warning text: #946B20
- Critical pastel: #FBE9E6 / Critical text: #A64E46
"""

import streamlit as st

CUSTOM_CSS = """
<style>
/* -------------------------------------------------------------------------
   1. Typography & Base Shell
   ------------------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #F0F3EA !important;
    color: #172F25 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

/* Main workspace canvas with rounded top-left corner matching reference */
.main {
    background-color: #FAFBF8 !important;
    border-top-left-radius: 28px !important;
    border-top-right-radius: 28px !important;
    margin-top: 10px !important;
    margin-right: 14px !important;
    box-shadow: -2px 0 12px rgba(23, 74, 50, 0.03) !important;
}

.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 2.2rem !important;
    padding-right: 2.2rem !important;
    max-width: 1400px !important;
}

/* Header Vertical Bar matching reference */
h2 {
    border-left: 4.5px solid #79A982 !important;
    padding-left: 12px !important;
    line-height: 1.15 !important;
    color: #172F25 !important;
    font-size: 1.60rem !important;
    font-weight: 700 !important;
    margin-top: 0 !important;
    margin-bottom: 3px !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: #77837A !important;
    font-size: 0.85rem !important;
    line-height: 1.45 !important;
}

/* -------------------------------------------------------------------------
   2. Sidebar Shell & Navigation (Completely Hide Radio Circles)
   ------------------------------------------------------------------------- */
section[data-testid="stSidebar"] {
    background-color: #F0F3EA !important;
    border-right: 1px solid #E5EAE1 !important;
    width: 295px !important;
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 1.6rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
}

/* Target and completely remove the radio button circles, inputs, and SVG dots */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-child,
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-of-type,
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] input[type="radio"],
div[data-testid="stRadio"] [role="radiogroup"] label > div:first-child,
div[data-testid="stRadio"] [role="radiogroup"] label input {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Navigation items as refined pill links */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"],
div[data-testid="stRadio"] [role="radiogroup"] label {
    background-color: transparent !important;
    padding: 9px 14px !important;
    border-radius: 12px !important;
    margin-bottom: 5px !important;
    transition: all 0.16s ease-in-out !important;
    cursor: pointer !important;
    width: 100% !important;
    border: 1px solid transparent !important;
    display: flex !important;
    align-items: center !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label > div:last-child {
    color: #172F25 !important;
    font-size: 0.91rem !important;
    font-weight: 500 !important;
    width: 100% !important;
}

/* Hover navigation item */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover,
div[data-testid="stRadio"] [role="radiogroup"] label:hover {
    background-color: #EAF2E6 !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label:hover > div:last-child {
    color: #174A32 !important;
}

/* Selected navigation item matching reference pill */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked),
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background-color: #DCEBD8 !important;
    border-color: #C4DFC0 !important;
    box-shadow: 0 1px 3px rgba(23, 74, 50, 0.05) !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:last-child {
    color: #174A32 !important;
    font-weight: 600 !important;
}

/* -------------------------------------------------------------------------
   3. Five KPI Cards Row (Grid alignment matching reference)
   ------------------------------------------------------------------------- */
div[data-testid="stMetric"] {
    display: grid !important;
    grid-template-columns: auto 1fr !important;
    grid-template-rows: auto auto !important;
    column-gap: 12px !important;
    align-items: center !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E5EAE1 !important;
    border-radius: 18px !important;
    padding: 16px 18px !important;
    box-shadow: 0 2px 8px rgba(23, 74, 50, 0.03) !important;
    min-height: 96px !important;
    transition: all 0.16s ease-in-out !important;
}

div[data-testid="stMetric"]:hover {
    border-color: #79A982 !important;
    box-shadow: 0 4px 12px rgba(23, 74, 50, 0.06) !important;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    grid-row: 1;
    grid-column: 2;
    margin: 0 !important;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
div[data-testid="stMetric"] [data-testid="stMetricLabel"] span {
    color: #77837A !important;
    font-size: 0.81rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
    margin: 0 !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    grid-row: 2;
    grid-column: 2;
    margin-top: 2px !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    color: #172F25 !important;
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    line-height: 1.1 !important;
    margin: 0 !important;
}

/* Card 1 Icon: Calendar */
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stMetric"]::before {
    content: "📅";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background-color: #EAF2E6;
    border: 1px solid #DCEBD8;
    border-radius: 12px;
    font-size: 1.25rem;
}

/* Card 2 Icon: Cohorts */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stMetric"]::before {
    content: "👥";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background-color: #EAF2E6;
    border: 1px solid #DCEBD8;
    border-radius: 12px;
    font-size: 1.25rem;
}

/* Card 3 (Highlight Card): Overall Attendance */
div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #EAF2E6 0%, #DCEBD8 100%) !important;
    border-color: #C4DFC0 !important;
}
div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"]::before {
    content: "📊";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background-color: #C8E5C2;
    border: 1px solid #B2D8AB;
    border-radius: 12px;
    font-size: 1.25rem;
}

/* Card 4 Icon: Total Signals */
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"]::before {
    content: "🔔";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background-color: #FFF0D2;
    border: 1px solid #FBE6B3;
    border-radius: 12px;
    font-size: 1.25rem;
}

/* Card 5 Icon: Pending Review */
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"]::before {
    content: "🚩";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background-color: #FFF0D2;
    border: 1px solid #FBE6B3;
    border-radius: 12px;
    font-size: 1.25rem;
}

/* -------------------------------------------------------------------------
   4. Reference Dashboard Cards (Chart & Table Containers)
   ------------------------------------------------------------------------- */
.attendsure-card-chart, .attendsure-card-table {
    background-color: #FFFFFF;
    border: 1px solid #E5EAE1;
    border-radius: 20px;
    padding: 22px 26px;
    margin-top: 1.25rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 2px 8px rgba(23, 74, 50, 0.03);
}

.card-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}

.card-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.card-header-icon {
    width: 36px;
    height: 36px;
    background-color: #EAF2E6;
    border: 1px solid #DCEBD8;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
}

.card-header-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #172F25;
    margin: 0;
    line-height: 1.2;
}

.card-header-sub {
    font-size: 0.82rem;
    color: #77837A;
    margin: 2px 0 0 0;
}

/* -------------------------------------------------------------------------
   5. Styled Reference Table for Recent Sessions
   ------------------------------------------------------------------------- */
.reference-table-wrap {
    width: 100%;
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid #E5EAE1;
}

.reference-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    text-align: left;
}

.reference-table th {
    background-color: #EAF2E6;
    color: #174A32;
    font-weight: 600;
    padding: 12px 18px;
    border-bottom: 1px solid #E5EAE1;
    font-size: 0.82rem;
    letter-spacing: 0.02em;
}

.reference-table td {
    padding: 14px 18px;
    border-bottom: 1px solid #F0F3EA;
    color: #172F25;
}

.reference-table tr:last-child td {
    border-bottom: none;
}

.reference-table tr:hover td {
    background-color: #FAFBF8;
}

.cohort-pill {
    display: inline-block;
    padding: 3px 12px;
    background-color: #EAF2E6;
    border: 1px solid #79A982;
    border-radius: 16px;
    color: #174A32;
    font-weight: 600;
    font-size: 0.80rem;
}

.rate-badge-drop {
    display: inline-block;
    padding: 3px 12px;
    background-color: #FFF0D2;
    border: 1px solid #FBE6B3;
    border-radius: 16px;
    color: #946B20;
    font-weight: 600;
    font-size: 0.80rem;
}

.rate-badge-normal {
    display: inline-block;
    padding: 3px 12px;
    background-color: #DCEBD8;
    border: 1px solid #C4DFC0;
    border-radius: 16px;
    color: #174A32;
    font-weight: 600;
    font-size: 0.80rem;
}

.view-all-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    background-color: #FFFFFF;
    border: 1px solid #E5EAE1;
    border-radius: 20px;
    color: #172F25;
    font-size: 0.82rem;
    font-weight: 500;
    text-decoration: none;
    transition: all 0.15s ease-in-out;
}

.view-all-btn:hover {
    background-color: #EAF2E6;
    border-color: #79A982;
    color: #174A32;
}

/* Hide Streamlit duplicate dataframe on overview screen */
div.overview-hidden-df {
    display: none !important;
}

/* -------------------------------------------------------------------------
   6. General Elements: Badges, Buttons, Cards
   ------------------------------------------------------------------------- */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 18px;
    font-size: 0.77rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    vertical-align: middle;
}

.badge-review {
    background-color: #FFF0D2;
    color: #946B20;
    border: 1px solid #FBE6B3;
}

.badge-critical {
    background-color: #FBE9E6;
    color: #A64E46;
    border: 1px solid #F8D2CD;
}

.badge-success {
    background-color: #DCEBD8;
    color: #174A32;
    border: 1px solid #C4DFC0;
}

.badge-info {
    background-color: #EAF2E6;
    color: #174A32;
    border: 1px solid #DCEBD8;
}

.badge-pastel {
    background-color: #DCEBD8;
    color: #174A32;
    border: 1px solid #C4DFC0;
}

.badge-neutral {
    background-color: #FFFFFF;
    color: #77837A;
    border: 1px solid #E5EAE1;
}

.attendsure-card {
    background-color: #FFFFFF;
    border: 1px solid #E5EAE1;
    border-radius: 18px;
    padding: 20px 24px;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(23, 74, 50, 0.03);
}

.attendsure-card:empty {
    display: none !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
}

.decision-support-box {
    background-color: #EAF2E6;
    border-left: 4px solid #237A50;
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 1.5rem;
    margin-bottom: 1rem;
    color: #172F25;
    font-size: 0.86rem;
    line-height: 1.55;
    border-top: 1px solid #E5EAE1;
    border-right: 1px solid #E5EAE1;
    border-bottom: 1px solid #E5EAE1;
}

.decision-support-box strong {
    color: #174A32;
}

div[data-testid="stButton"] button {
    border-radius: 12px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    border: 1px solid #E5EAE1 !important;
    background-color: #FFFFFF !important;
    color: #172F25 !important;
}

div[data-testid="stButton"] button[kind="primary"] {
    background-color: #237A50 !important;
    border-color: #237A50 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

div[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #174A32 !important;
    border-color: #174A32 !important;
}

/* Tabs */
div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 500 !important;
    color: #77837A !important;
    font-size: 0.90rem !important;
    padding: 8px 16px !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #174A32 !important;
    font-weight: 600 !important;
    border-bottom: 2.5px solid #237A50 !important;
}
</style>
"""


def apply_theme() -> None:
    """Inject custom styles into the active Streamlit app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
