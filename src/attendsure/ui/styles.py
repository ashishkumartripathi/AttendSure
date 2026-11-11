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
</style>
"""


def apply_theme() -> None:
    """Inject custom styles into the active Streamlit app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
