"""Centralized Design Tokens and Reusable Component Helpers for AttendSure UI.

Adheres strictly to the Modern SaaS design direction:
- Primary surfaces: Deep navy (#0F172A, #1E293B)
- Primary actions & positive states: Teal (#0D9488, #14B8A6, #0F766E, #CCFBF1, #115E59)
- Backgrounds: Neutral slate (#F8FAFC, #F1F5F9, #FFFFFF)
- Attention states: Amber (#F59E0B, #FEF3C7, #92400E)
- Critical states: Red (#EF4444, #FEE2E2, #991B1B)
- Typography: Slate (#0F172A primary, #475569 secondary, #64748B muted)
- Elevation: Clean 8px-12px radii, subtle shadows
"""

from typing import Optional


# Design Tokens
TOKENS = {
    # Surfaces & Backgrounds
    "bg_main": "#F8FAFC",
    "bg_canvas": "#F8FAFC",
    "bg_sidebar": "#F1F5F9",
    "surface_light": "#F1F5F9",
    "card_bg": "#FFFFFF",
    "navy_primary": "#0F172A",
    "navy_card": "#1E293B",
    "dark_forest": "#0F172A",  # Backward compatibility alias

    # Primary Actions & Accents (Teal)
    "primary": "#0D9488",
    "teal_primary": "#0D9488",
    "teal_hover": "#0F766E",
    "teal_light": "#CCFBF1",
    "teal_text": "#115E59",
    "secondary": "#64748B",
    "pastel": "#CCFBF1",

    # Typography
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "text_muted": "#64748B",

    # Borders & Dividers
    "border": "#E2E8F0",
    "border_subtle": "#E2E8F0",
    "border_strong": "#CBD5E1",

    # Status: Warning / Attention (Amber)
    "warning_bg": "#FEF3C7",
    "warning_text": "#92400E",
    "warning_border": "#FDE68A",

    # Status: Critical / Alert (Red)
    "error_bg": "#FEE2E2",
    "error_text": "#991B1B",
    "error_border": "#FECACA",

    # Status: Success / Normal (Teal)
    "success_bg": "#CCFBF1",
    "success_text": "#115E59",
    "success_border": "#99F6E4",

    # Layout & Elevation
    "radius_card": "10px",
    "radius_input": "8px",
    "radius_btn": "8px",
    "radius_badge": "9999px",
    "shadow_sm": "0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.08)",
}


def render_page_header(title: str, caption: str, badge: Optional[str] = None) -> str:
    """Generate HTML for a consistent Modern SaaS page header with optional status badge."""
    badge_html = f"<span class='badge badge-neutral'>{badge}</span>" if badge else ""
    return f"""
    <div class="saas-page-header" style="margin-bottom: 1.25rem;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
            <h1 style="margin: 0; font-size: 1.65rem; font-weight: 700; color: #0F172A; letter-spacing: -0.025em;">
                {title}
            </h1>
            {badge_html}
        </div>
        <p style="margin: 0; font-size: 0.88rem; color: #475569; font-weight: 400; line-height: 1.45;">
            {caption}
        </p>
    </div>
    """


def render_decision_support_box(
    text: str,
    title: str = "Decision Support Notice:",
) -> str:
    """Generate HTML for standard non-accusatory educational decision support notices."""
    return f"""
    <div class="decision-support-box">
        <strong>{title}</strong> {text}
    </div>
    """


def render_badge(text: str, variant: str = "neutral") -> str:
    """Generate HTML for a styled SaaS pill badge.

    Variants: 'neutral', 'success', 'review', 'critical', 'info', 'pastel', 'ml'
    """
    variant_class = {
        "neutral": "badge-neutral",
        "success": "badge-success",
        "review": "badge-review",
        "critical": "badge-critical",
        "info": "badge-info",
        "pastel": "badge-pastel",
        "ml": "badge-ml",
    }.get(variant, "badge-neutral")
    return f"<span class='badge {variant_class}'>{text}</span>"


def render_card_start(padding: str = "18px 22px", margin_bottom: str = "1rem") -> str:
    """Generate opening tag for a styled Modern SaaS surface card."""
    return f"<div class='attendsure-card' style='padding: {padding}; margin-bottom: {margin_bottom};'>"


def render_card_end() -> str:
    """Generate closing tag for a styled Modern SaaS surface card."""
    return "</div>"


def render_kpi_card(
    label: str,
    value: str,
    subtext: Optional[str] = None,
    badge: Optional[str] = None,
    status: str = "neutral",
    icon: Optional[str] = None,
) -> str:
    """Generate HTML for an elevated Modern SaaS KPI stat card."""
    icon_html = f"<div class='saas-kpi-icon'>{icon}</div>" if icon else ""
    badge_html = f"<span class='badge badge-{status}'>{badge}</span>" if badge else ""
    subtext_html = f"<div class='saas-kpi-subtext'>{subtext}</div>" if subtext else ""
    return f"""
    <div class="saas-kpi-card status-{status}">
        <div class="saas-kpi-header">
            <span class="saas-kpi-label">{label}</span>
            {badge_html}
        </div>
        <div class="saas-kpi-body">
            {icon_html}
            <div class="saas-kpi-value">{value}</div>
        </div>
        {subtext_html}
    </div>
    """


def render_summary_banner(
    title: str,
    text: str,
    variant: str = "info",
    icon: Optional[str] = None,
) -> str:
    """Generate HTML for a clean Modern SaaS summary or notification banner."""
    default_icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "critical": "🚨",
    }
    use_icon = icon or default_icons.get(variant, "ℹ️")
    return f"""
    <div class="saas-banner saas-banner-{variant}">
        <div class="saas-banner-icon">{use_icon}</div>
        <div class="saas-banner-content">
            <div class="saas-banner-title">{title}</div>
            <div class="saas-banner-text">{text}</div>
        </div>
    </div>
    """


def render_empty_state(title: str, message: str, icon: str = "📋") -> str:
    """Generate HTML for an empty-state illustration container."""
    return f"""
    <div class="saas-empty-state">
        <div class="saas-empty-icon">{icon}</div>
        <h4 class="saas-empty-title">{title}</h4>
        <p class="saas-empty-message">{message}</p>
    </div>
    """


def render_metric_highlight(
    label_1: str,
    val_1: str,
    label_2: str,
    val_2: str,
) -> str:
    """Generate HTML for two large numerical highlight pills comparing observed vs baseline."""
    return f"""
    <div class="saas-metric-compare-row">
        <div class="saas-metric-compare-card">
            <span class="compare-label">{label_1}</span>
            <span class="compare-value value-observed">{val_1}</span>
        </div>
        <div class="saas-metric-compare-card">
            <span class="compare-label">{label_2}</span>
            <span class="compare-value value-baseline">{val_2}</span>
        </div>
    </div>
    """
