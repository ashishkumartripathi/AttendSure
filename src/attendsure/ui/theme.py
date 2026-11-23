"""Centralized design tokens and reusable component helpers for AttendSure.

The dashboard uses a calm indigo and periwinkle palette with a coral attention
accent, inspired by the supplied visual reference while preserving accessibility.
"""

from typing import Optional


# Design Tokens
TOKENS = {
    # Surfaces & Backgrounds
    "bg_main": "#F6F7FF",
    "bg_canvas": "#F6F7FF",
    "bg_sidebar": "#FFFFFF",
    "surface_light": "#EEF1FF",
    "card_bg": "#FFFFFF",
    "navy_primary": "#25234A",
    "navy_card": "#4B49AC",
    "dark_forest": "#25234A",  # Backward compatibility alias

    # Primary Actions & Accents (Teal)
    "primary": "#4B49AC",
    "teal_primary": "#4B49AC",  # Legacy key retained for view compatibility.
    "teal_hover": "#393787",
    "teal_light": "#E8E9FF",
    "teal_text": "#393787",
    "secondary": "#62617C",
    "pastel": "#E8E9FF",

    # Typography
    "text_primary": "#25234A",
    "text_secondary": "#62617C",
    "text_muted": "#81809A",

    # Borders & Dividers
    "border": "#E2E5F5",
    "border_subtle": "#EEF0FA",
    "border_strong": "#D7D8EC",

    # Status: Warning / Attention (Amber)
    "warning_bg": "#FFF1F2",
    "warning_text": "#B04452",
    "warning_border": "#F6C4CB",

    # Status: Critical / Alert (Red)
    "error_bg": "#FFF0F1",
    "error_text": "#B04452",
    "error_border": "#F7C3C9",

    # Status: Success / Normal (Teal)
    "success_bg": "#E8E9FF",
    "success_text": "#4B49AC",
    "success_border": "#C9C9F4",

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
            <h1 style="margin: 0; font-size: 1.65rem; font-weight: 700; color: #25234A; letter-spacing: -0.025em;">
                {title}
            </h1>
            {badge_html}
        </div>
        <p style="margin: 0; font-size: 0.88rem; color: #62617C; font-weight: 400; line-height: 1.45;">
            {caption}
        </p>
    </div>
    """


def render_workspace_intro(eyebrow: str, summary: str, meta: str) -> str:
    """Render a compact, modular context bar for an operational workspace."""
    return f"""
    <section class="workspace-intro">
        <div>
            <p class="workspace-eyebrow">{eyebrow}</p>
            <p class="workspace-summary">{summary}</p>
        </div>
        <span class="workspace-meta">{meta}</span>
    </section>
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
