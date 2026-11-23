"""Shared styling and visual theme definitions for AttendSure Streamlit UI.

Accurately implements the Modern SaaS design direction:
- Surfaces: Deep navy (#0F172A, #1E293B) and clean white (#FFFFFF)
- Primary Actions & Positive States: Teal (#0D9488, #14B8A6, #0F766E, #CCFBF1, #115E59)
- Backgrounds: Neutral slate (#F8FAFC, #F1F5F9)
- Attention States: Amber (#F59E0B, #FEF3C7, #92400E)
- Critical States: Red (#EF4444, #FEE2E2, #991B1B)
- Typography: Inter font hierarchy (#0F172A primary, #475569 secondary, #64748B muted)
- Spacing & Radii: 8px to 12px compact radii, subtle SaaS elevation
"""

import streamlit as st

CUSTOM_CSS = """
<style>
/* -------------------------------------------------------------------------
   1. Typography & Base Workspace Shell
   ------------------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

/* Main workspace canvas */
.main {
    background-color: #FFFFFF !important;
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    margin-top: 8px !important;
    margin-right: 12px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
}

.main .block-container {
    padding-top: 1.8rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1400px !important;
    animation: fadeInContainer 0.15s ease-in-out;
}

@keyframes fadeInContainer {
    from { opacity: 0.88; }
    to { opacity: 1; }
}

/* Snappy transitions: eliminate lingering stale elements or opacity ghosting */
[data-stale="true"] {
    opacity: 0 !important;
    transition: opacity 0.12s ease-out !important;
}

/* Headings with Modern SaaS Accent */
h1 {
    color: #0F172A !important;
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    margin-top: 0 !important;
    margin-bottom: 4px !important;
}

h2 {
    border-left: 3.5px solid #0D9488 !important;
    padding-left: 10px !important;
    line-height: 1.2 !important;
    color: #0F172A !important;
    font-size: 1.50rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    margin-top: 0 !important;
    margin-bottom: 4px !important;
}

h3 {
    color: #0F172A !important;
    font-size: 1.20rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.015em !important;
    margin-top: 0 !important;
    margin-bottom: 4px !important;
}

h4 {
    color: #1E293B !important;
    font-size: 1.00rem !important;
    font-weight: 600 !important;
    margin-top: 0 !important;
    margin-bottom: 4px !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: #64748B !important;
    font-size: 0.85rem !important;
    line-height: 1.45 !important;
}

/* -------------------------------------------------------------------------
   2. Sidebar Shell & Navigation
   ------------------------------------------------------------------------- */
section[data-testid="stSidebar"] {
    background-color: #F1F5F9 !important;
    border-right: 1px solid #E2E8F0 !important;
    width: 295px !important;
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
    padding-left: 1.1rem !important;
    padding-right: 1.1rem !important;
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

/* Navigation items as refined modern SaaS links */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"],
div[data-testid="stRadio"] [role="radiogroup"] label {
    background-color: transparent !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    margin-bottom: 4px !important;
    transition: all 0.15s ease-in-out !important;
    cursor: pointer !important;
    width: 100% !important;
    border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    display: flex !important;
    align-items: center !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label > div:last-child {
    color: #475569 !important;
    font-size: 0.90rem !important;
    font-weight: 500 !important;
    width: 100% !important;
}

/* Hover navigation item */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover,
div[data-testid="stRadio"] [role="radiogroup"] label:hover {
    background-color: #E2E8F0 !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label:hover > div:last-child {
    color: #0F172A !important;
}

/* Selected navigation item with Teal accent pill */
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked),
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background-color: #CCFBF1 !important;
    border-left: 3.5px solid #0D9488 !important;
    border-color: #99F6E4 !important;
    border-left-color: #0D9488 !important;
    box-shadow: 0 1px 2px rgba(13, 148, 136, 0.08) !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:last-child {
    color: #0F766E !important;
    font-weight: 600 !important;
}

/* -------------------------------------------------------------------------
   3. Five KPI Cards Row (Modern SaaS Stat Cards)
   ------------------------------------------------------------------------- */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 12px !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.8rem !important;
}

div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"] {
    flex: 1 1 calc(20% - 12px) !important;
    min-width: 160px !important;
}

@media (max-width: 1150px) {
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"] {
        flex: 1 1 calc(33.33% - 12px) !important;
        min-width: 140px !important;
    }
}

@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
}

@media (max-width: 900px) {
    div[data-testid="stHorizontalBlock"]:has(.saas-action-banner) {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.saas-action-banner) > div[data-testid="stColumn"] {
        width: 100% !important;
        min-width: 100% !important;
    }
}

/* -------------------------------------------------------------------------
   9. Indigo dashboard refresh
   ------------------------------------------------------------------------- */
html, body, [data-testid="stAppViewContainer"] {
    background: #F6F7FF !important;
    color: #25234A !important;
}

.main {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    margin: 0 !important;
}

.main .block-container {
    max-width: 1500px !important;
    padding-top: 2.2rem !important;
}

h1, h2, h3, h4 { color: #25234A !important; }
h2 { border-left-color: #4B49AC !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: #81809A !important; }

section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E2E5F5 !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"],
div[data-testid="stRadio"] [role="radiogroup"] label {
    border-radius: 9px !important;
    margin-bottom: 5px !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover,
div[data-testid="stRadio"] [role="radiogroup"] label:hover {
    background: #F2F3FF !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked),
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background: #4B49AC !important;
    border-color: #4B49AC !important;
    border-left-color: #4B49AC !important;
    box-shadow: 0 8px 18px rgba(75, 73, 172, 0.18) !important;
}

section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) > div:last-child,
div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:last-child {
    color: #FFFFFF !important;
}

div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E5F5 !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 20px rgba(70, 69, 156, 0.07) !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] div { color: #4B49AC !important; }
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stMetric"]::before,
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stMetric"]::before,
div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"]::before {
    background: #EEF1FF !important;
    border-color: #DDE0FB !important;
}
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] {
    background: #7978E9 !important;
    border-color: #7978E9 !important;
}
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"]::before { background: rgba(255,255,255,.18) !important; border-color: rgba(255,255,255,.24) !important; }
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] [data-testid="stMetricValue"] div { color: #FFFFFF !important; }
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"] {
    background: #FFF6F6 !important;
    border-color: #F5D5D8 !important;
}
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"] [data-testid="stMetricValue"] div { color: #D9616D !important; }

.saas-action-banner {
    background: linear-gradient(110deg, #4B49AC, #7978E9) !important;
    border: 0 !important;
    border-radius: 14px !important;
    padding: 15px 18px !important;
    box-shadow: 0 10px 24px rgba(75, 73, 172, 0.20) !important;
}
.saas-action-banner-title, .saas-action-banner-desc { color: #FFFFFF !important; }
.saas-action-banner-icon { filter: saturate(.85); }

.saas-header-pill {
    border-color: #E2E5F5 !important;
    color: #62617C !important;
    border-radius: 10px !important;
}

.attendsure-card, .attendsure-card-chart, .attendsure-card-table {
    border: 1px solid #E2E5F5 !important;
    border-radius: 14px !important;
    box-shadow: 0 9px 22px rgba(70, 69, 156, 0.06) !important;
}
.card-header-icon { background: #EEF1FF !important; border-color: #DDE0FB !important; }
.card-header-title, .reference-table td, .reference-table th { color: #25234A !important; }
.card-header-sub, .saas-kpi-subtext { color: #81809A !important; }
.reference-table th { background: #F7F8FF !important; }
.reference-table tr:hover td { background: #F8F8FF !important; }

.decision-support-box {
    background: #EEF1FF !important;
    border-color: #C9C9F4 !important;
    color: #393787 !important;
}

div.stButton > button[kind="primary"] {
    background: #4B49AC !important;
    border-color: #4B49AC !important;
    border-radius: 9px !important;
    box-shadow: 0 7px 14px rgba(75, 73, 172, .18) !important;
}
div.stButton > button[kind="primary"]:hover { background: #393787 !important; border-color: #393787 !important; }
div[data-baseweb="input"]:focus-within { border-color: #7978E9 !important; box-shadow: 0 0 0 1px #7978E9 !important; }

div[data-testid="stMetric"] {
    display: grid !important;
    grid-template-columns: auto 1fr !important;
    grid-template-rows: auto auto !important;
    column-gap: 12px !important;
    align-items: center !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
    min-height: 90px !important;
    transition: all 0.16s ease-in-out !important;
}

div[data-testid="stMetric"]:hover {
    border-color: #CBD5E1 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06) !important;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    grid-row: 1;
    grid-column: 2;
    margin: 0 !important;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
div[data-testid="stMetric"] [data-testid="stMetricLabel"] span {
    color: #64748B !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.025em !important;
    margin: 0 !important;
    white-space: nowrap !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    grid-row: 2;
    grid-column: 2;
    margin-top: 2px !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    color: #0F172A !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    line-height: 1.15 !important;
    margin: 0 !important;
}

/* Card 1 Icon: Total Students */
div[data-testid="stColumn"]:nth-child(1) div[data-testid="stMetric"]::before {
    content: "👥";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    font-size: 1.10rem;
}

/* Card 2 Icon: Present Today */
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stMetric"]::before {
    content: "🎒";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    font-size: 1.10rem;
}

/* Card 3 Icon: Absent Today */
div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"]::before {
    content: "🚪";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    font-size: 1.10rem;
}

/* Card 4 (Highlight Card): Attendance Rate (Teal Accent) */
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-color: #99F6E4 !important;
}
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"]::before {
    content: "📊";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background-color: #CCFBF1;
    border: 1px solid #99F6E4;
    border-radius: 8px;
    font-size: 1.10rem;
}
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    color: #0F766E !important;
}

/* Card 5 Icon: Pending Review / Needs Attention (Amber Accent) */
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"] {
    border-color: #FDE68A !important;
}
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"]::before {
    content: "⚠️";
    grid-row: 1 / span 2;
    grid-column: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background-color: #FEF3C7;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    font-size: 1.10rem;
}
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    color: #92400E !important;
}

/* Quick Action Banner (Roll-Call CTA) */
.saas-action-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    background-color: #F0FDFA;
    border: 1px solid #99F6E4;
    border-radius: 8px;
    padding: 10px 16px;
    height: 100%;
}

.saas-action-banner-icon {
    font-size: 1.30rem;
    flex-shrink: 0;
}

.saas-action-banner-title {
    font-weight: 600;
    font-size: 0.88rem;
    color: #115E59;
}

.saas-action-banner-desc {
    font-size: 0.80rem;
    color: #0F766E;
    line-height: 1.35;
}

/* Header Pills */
.saas-header-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 9999px;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
    font-size: 0.80rem;
    font-weight: 500;
    color: #0F172A;
}

/* -------------------------------------------------------------------------
   4. Modern SaaS Containers (Chart & Table Containers)
   ------------------------------------------------------------------------- */
.attendsure-card-chart, .attendsure-card-table {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 20px 24px;
    margin-top: 1.1rem;
    margin-bottom: 1.1rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
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
    width: 34px;
    height: 34px;
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.15rem;
}

.card-header-title {
    font-size: 1.10rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    line-height: 1.25;
}

.card-header-sub {
    font-size: 0.82rem;
    color: #64748B;
    margin: 2px 0 0 0;
}

/* -------------------------------------------------------------------------
   5. Styled Reference Table for Recent Sessions
   ------------------------------------------------------------------------- */
.reference-table-wrap {
    width: 100%;
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
}

.reference-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    text-align: left;
}

.reference-table th {
    background-color: #F8FAFC;
    color: #475569;
    font-weight: 600;
    padding: 11px 16px;
    border-bottom: 1px solid #E2E8F0;
    font-size: 0.80rem;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.reference-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #F1F5F9;
    color: #0F172A;
}

.reference-table tr:last-child td {
    border-bottom: none;
}

.reference-table tr:hover td {
    background-color: #F8FAFC;
}

.cohort-pill {
    display: inline-block;
    padding: 2px 10px;
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    color: #0F172A;
    font-weight: 600;
    font-size: 0.80rem;
}

.rate-badge-drop {
    display: inline-block;
    padding: 2px 10px;
    background-color: #FEF3C7;
    border: 1px solid #FDE68A;
    border-radius: 9999px;
    color: #92400E;
    font-weight: 600;
    font-size: 0.80rem;
}

.rate-badge-normal {
    display: inline-block;
    padding: 2px 10px;
    background-color: #CCFBF1;
    border: 1px solid #99F6E4;
    border-radius: 9999px;
    color: #115E59;
    font-weight: 600;
    font-size: 0.80rem;
}

.view-all-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #0F172A;
    font-size: 0.82rem;
    font-weight: 500;
    text-decoration: none;
    transition: all 0.15s ease-in-out;
}

.view-all-btn:hover {
    background-color: #F8FAFC;
    border-color: #94A3B8;
    color: #0F172A;
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
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.77rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    vertical-align: middle;
}

.badge-review {
    background-color: #FEF3C7;
    color: #92400E;
    border: 1px solid #FDE68A;
}

.badge-critical {
    background-color: #FEE2E2;
    color: #991B1B;
    border: 1px solid #FECACA;
}

.badge-success {
    background-color: #CCFBF1;
    color: #115E59;
    border: 1px solid #99F6E4;
}

.badge-info {
    background-color: #E0F2FE;
    color: #0369A1;
    border: 1px solid #BAE6FD;
}

.badge-pastel {
    background-color: #CCFBF1;
    color: #115E59;
    border: 1px solid #99F6E4;
}

.badge-neutral {
    background-color: #F1F5F9;
    color: #475569;
    border: 1px solid #CBD5E1;
}

.badge-ml {
    background-color: #F3E8FF;
    color: #6B21A8;
    border: 1px solid #E9D5FF;
}

.attendsure-card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
}

.attendsure-card:empty {
    display: none !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
}

.decision-support-box {
    background-color: #F8FAFC;
    border-left: 4px solid #0D9488;
    border-radius: 8px;
    padding: 13px 18px;
    margin-top: 1.25rem;
    margin-bottom: 1rem;
    color: #334155;
    font-size: 0.86rem;
    line-height: 1.55;
    border-top: 1px solid #E2E8F0;
    border-right: 1px solid #E2E8F0;
    border-bottom: 1px solid #E2E8F0;
}

.decision-support-box strong {
    color: #0F172A;
}

/* Streamlit Native Buttons */
div[data-testid="stButton"] button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    border: 1px solid #CBD5E1 !important;
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
    transition: all 0.15s ease-in-out !important;
}

div[data-testid="stButton"] button:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

div[data-testid="stButton"] button[kind="primary"] {
    background-color: #0D9488 !important;
    border-color: #0D9488 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 2px 0 rgba(13, 148, 136, 0.2) !important;
}

div[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #0F766E !important;
    border-color: #0F766E !important;
}

/* Form Controls & Inputs */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {
    border-radius: 8px !important;
    border: 1px solid #CBD5E1 !important;
    color: #0F172A !important;
}

div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stDateInput"] input:focus {
    border-color: #0D9488 !important;
    box-shadow: 0 0 0 1px #0D9488 !important;
}

/* Tabs */
div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 500 !important;
    color: #64748B !important;
    font-size: 0.90rem !important;
    padding: 8px 16px !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #0D9488 !important;
    font-weight: 600 !important;
    border-bottom: 2.5px solid #0D9488 !important;
}

/* -------------------------------------------------------------------------
   7. Reusable Modern SaaS UI Components
   ------------------------------------------------------------------------- */
.saas-banner {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 10px 0 14px 0;
    border: 1px solid #E2E8F0;
    background-color: #F8FAFC;
}

.saas-banner-info {
    border-color: #BAE6FD;
    background-color: #F0F9FF;
    color: #0369A1;
}

.saas-banner-success {
    border-color: #99F6E4;
    background-color: #F0FDFA;
    color: #115E59;
}

.saas-banner-warning {
    border-color: #FDE68A;
    background-color: #FFFBEB;
    color: #92400E;
}

.saas-banner-critical {
    border-color: #FECACA;
    background-color: #FEF2F2;
    color: #991B1B;
}

.saas-banner-title {
    font-weight: 600;
    font-size: 0.88rem;
    margin-bottom: 2px;
}

.saas-banner-text {
    font-size: 0.82rem;
    line-height: 1.45;
}

.saas-empty-state {
    text-align: center;
    padding: 3rem 2rem;
    background-color: #FFFFFF;
    border: 1px dashed #CBD5E1;
    border-radius: 10px;
    margin: 1.5rem 0;
}

.saas-empty-icon {
    font-size: 2.2rem;
    margin-bottom: 0.75rem;
}

.saas-empty-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #0F172A;
    margin-bottom: 0.25rem;
}

.saas-empty-message {
    font-size: 0.85rem;
    color: #64748B;
    max-width: 480px;
    margin: 0 auto;
    line-height: 1.45;
}

.saas-metric-compare-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 12px 0;
}

.saas-metric-compare-card {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
}

.saas-metric-compare-card .compare-label {
    font-size: 0.78rem;
    font-weight: 500;
    color: #64748B;
    margin-bottom: 4px;
}

.saas-metric-compare-card .compare-value {
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.value-observed {
    color: #0F172A;
}

.value-baseline {
    color: #0D9488;
}

/* -------------------------------------------------------------------------
   8. Responsive Media Queries
   ------------------------------------------------------------------------- */
@media (max-width: 900px) {
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    div[data-testid="stMetric"] {
        padding: 10px 12px !important;
        min-height: 80px !important;
    }
    .saas-metric-compare-row {
        grid-template-columns: 1fr;
    }
}
/* Operations Center visual system */
:root { --ink:#191735; --indigo:#5B57D8; --canvas:#F6F7FC; --line:#E5E7F1; --muted:#77758F; --success:#16A394; --coral:#E96B76; }
html, body, [data-testid="stAppViewContainer"] { background:var(--canvas) !important; color:var(--ink) !important; }
.main, .main .block-container { background:transparent !important; border:0 !important; box-shadow:none !important; }
.main .block-container { max-width:1500px !important; padding:3rem 3.25rem 4rem !important; }
h1,h2,h3,h4 { color:var(--ink) !important; } h2 { border-left:0 !important; font-size:2.15rem !important; letter-spacing:-.045em !important; }
.stCaption,[data-testid="stCaptionContainer"] { color:var(--muted) !important; }

section[data-testid="stSidebar"] { width:300px !important; background:#1E1C44 !important; border:0 !important; box-shadow:12px 0 34px rgba(25,23,53,.08) !important; }
section[data-testid="stSidebar"] .block-container { padding:2rem 1.15rem !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"],div[data-testid="stRadio"] [role="radiogroup"] label { min-height:46px !important; border:0 !important; border-radius:12px !important; margin:4px 0 !important; padding:10px 13px !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:last-child,div[data-testid="stRadio"] [role="radiogroup"] label > div:last-child,section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#C8C7E9 !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover,div[data-testid="stRadio"] [role="radiogroup"] label:hover { background:rgba(255,255,255,.08) !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked),div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) { background:linear-gradient(135deg,#625CE5,#4B46BE) !important; box-shadow:0 9px 20px rgba(7,6,41,.32) !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) > div:last-child,div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) > div:last-child { color:#FFF !important; }

.saas-header-pill { background:#FFF !important; border:1px solid var(--line) !important; border-radius:999px !important; box-shadow:0 5px 16px rgba(37,35,83,.05) !important; padding:8px 14px !important; }
.saas-action-banner { position:relative; overflow:hidden; min-height:96px; padding:22px 24px !important; background:linear-gradient(125deg,#272458,#4E49BD 58%,#7771E9) !important; border:0 !important; border-radius:18px !important; box-shadow:0 18px 35px rgba(61,56,162,.24) !important; }
.saas-action-banner::after { content:""; position:absolute; width:180px; height:180px; border:32px solid rgba(255,255,255,.08); border-radius:50%; right:-58px; top:-76px; }
.saas-action-banner-icon,.saas-action-banner-title,.saas-action-banner-desc { position:relative; z-index:1; color:#FFF !important; }
.saas-action-banner-icon { font-size:1.8rem !important; }.saas-action-banner-title { font-size:1.06rem !important; }.saas-action-banner-desc { color:#E4E3FF !important; font-size:.86rem !important; }
div[data-testid="stButton"] button { min-height:48px !important; border-radius:12px !important; font-weight:700 !important; border:1px solid var(--line) !important; color:var(--ink) !important; box-shadow:none !important; }
div[data-testid="stButton"] button[kind="primary"] { background:var(--indigo) !important; border-color:var(--indigo) !important; color:#FFF !important; box-shadow:0 10px 18px rgba(91,87,216,.22) !important; }

.today-empty-banner { background:#FFF !important; border:1px solid var(--line) !important; border-left:4px solid #857CF2 !important; border-radius:14px !important; padding:16px 18px !important; box-shadow:0 6px 15px rgba(37,35,83,.03) !important; }
.today-empty-banner span { background:#EEEDFF !important; color:#46419F !important; border-radius:999px !important; }
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) { gap:16px !important; margin:1.7rem 0 2.15rem !important; }
div[data-testid="stMetric"] { position:relative; overflow:hidden; min-height:118px !important; background:#FFF !important; border:1px solid var(--line) !important; border-radius:16px !important; padding:18px !important; box-shadow:0 10px 22px rgba(37,35,83,.055) !important; }
div[data-testid="stMetric"]::after { content:""; position:absolute; left:0; bottom:0; width:100%; height:4px; background:#D7D6FF; }
div[data-testid="stMetric"] [data-testid="stMetricLabel"] p { color:var(--muted) !important; font-size:.68rem !important; letter-spacing:.075em !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] div { color:var(--ink) !important; font-size:1.72rem !important; }
div[data-testid="stColumn"]:nth-child(2) div[data-testid="stMetric"]::after { background:#58C8BD; } div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"]::after { background:#F0A2A9; }
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] { background:#29265D !important; border-color:#29265D !important; } div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] [data-testid="stMetricValue"] div { color:#FFF !important; }
div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"] { background:#FFF8F8 !important; border-color:#F3D9DD !important; } div[data-testid="stColumn"]:nth-child(5) div[data-testid="stMetric"]::after { background:var(--coral); }
.attendsure-card,.attendsure-card-chart,.attendsure-card-table { border:1px solid var(--line) !important; border-radius:18px !important; box-shadow:0 12px 28px rgba(37,35,83,.055) !important; padding:24px 26px !important; background:#FFF !important; }
.card-header-icon { border-radius:12px !important; background:#EFEEFF !important; border-color:#DCD9FF !important; }.card-header-title { font-size:1.18rem !important; }.card-header-sub { color:var(--muted) !important; }
.reference-table-wrap { border-color:var(--line) !important; border-radius:12px !important; }.reference-table th { background:#F7F7FC !important; color:#696781 !important; }.reference-table td { color:#353250 !important; border-color:#F0F0F6 !important; }
div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stDateInput"] input { border-radius:11px !important; border-color:#D9DBE9 !important; }
@media (max-width:900px) { .main .block-container { padding:1.45rem 1rem 3rem !important; } .saas-action-banner { min-height:auto; } }
/* Modular content patterns used across all views */
.session-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.session-tile { background:#FAFAFE; border:1px solid #E7E8F2; border-radius:14px; padding:16px; transition:transform .18s ease,box-shadow .18s ease; }
.session-tile:hover { transform:translateY(-2px); box-shadow:0 12px 24px rgba(37,35,83,.09); }
.session-tile-top,.session-counts,.session-review-state { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.session-date { color:#77758F; font-size:.76rem; font-weight:700; }.session-class { color:#191735; font-size:1rem; font-weight:800; margin:15px 0 13px; letter-spacing:-.02em; }
.session-counts { border-top:1px solid #E9EAF2; padding-top:12px; color:#77758F; font-size:.73rem; }.session-counts b { color:#302D55; font-size:.86rem; }
.session-review-state { margin-top:15px; font-size:.74rem; font-weight:700; }.session-clear { color:#129987; }.session-signal { color:#C15763; }
.session-rate-healthy,.session-rate-review { padding:5px 9px; border-radius:999px; font-size:.72rem; font-weight:800; }.session-rate-healthy { color:#0A8175; background:#DDF8F3; }.session-rate-review { color:#B15142; background:#FFF0D8; }

/* Form routes become compact workspaces instead of default Streamlit panels. */
div[data-testid="stForm"],div[data-testid="stVerticalBlockBorderWrapper"],div[data-testid="stExpander"] { border:1px solid var(--line) !important; border-radius:16px !important; background:#FFF !important; box-shadow:0 8px 22px rgba(37,35,83,.04) !important; }
div[data-testid="stForm"] { padding:22px !important; }
div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:8px !important; border-bottom:0 !important; background:#ECECF7; border-radius:12px; padding:5px; }
div[data-testid="stTabs"] button[role="tab"] { border-radius:8px !important; padding:9px 14px !important; color:#66647E !important; }
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background:#FFF !important; color:#403B9D !important; border-bottom:0 !important; box-shadow:0 3px 8px rgba(37,35,83,.08); }
div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; box-shadow:0 8px 20px rgba(37,35,83,.035); }
div[data-testid="stAlert"] { border-radius:14px !important; border-width:1px !important; }
@media (max-width:1000px) { .session-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:640px) { .session-grid { grid-template-columns:1fr; } }
.workspace-intro { display:flex; align-items:center; justify-content:space-between; gap:20px; background:#FFFFFF; border:1px solid #E5E7F1; border-radius:16px; padding:16px 18px; margin:0 0 24px; box-shadow:0 8px 20px rgba(37,35,83,.04); }
.workspace-eyebrow { margin:0 0 5px; color:#5B57D8; font-weight:800; font-size:.7rem; letter-spacing:.13em; }.workspace-summary { margin:0; color:#65637D; font-size:.9rem; }.workspace-meta { flex-shrink:0; padding:7px 10px; border-radius:999px; background:#EEEDFF; color:#4842A6; font-weight:750; font-size:.72rem; }
/* Every data-dense page now uses the same modular sections, controls, and card rhythm. */
div[data-testid="stSelectbox"] > div > div, div[data-testid="stDateInput"] > div, div[data-testid="stTextInput"] > div > div, div[data-testid="stNumberInput"] > div > div { border-radius:11px !important; }
div[data-testid="stSubheader"] { margin-top:1.65rem !important; padding:0 0 10px; border-bottom:1px solid #E8E9F1; }
div[data-testid="stSubheader"] h3 { font-size:1.12rem !important; letter-spacing:-.02em !important; }
@media (max-width:700px) { .workspace-intro { align-items:flex-start; flex-direction:column; gap:10px; }.workspace-meta { align-self:flex-start; } }
</style>
"""


def apply_theme() -> None:
    """Inject custom styles into the active Streamlit app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
