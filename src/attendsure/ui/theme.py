"""Centralized Design Tokens and Reusable Component Helpers for AttendSure UI.

Adheres strictly to the Pastel Green design direction:
- Main background: #F7F8F3
- Sidebar background: #F0F3EA
- Primary green: #477D50
- Dark forest green: #173F2D
- Secondary green: #79A982
- Pastel green: #DCEBD8
- Light green surface: #EAF2E6
- Card background: #FFFFFF
- Primary text: #20352A
- Secondary text: #718078
- Border: #E2E9DF
- Warning background: #FFF3D9 / Warning text: #936B1C
- Error background: #FCE9E7 / Error text: #A64E46
- Success background: #E2F0DF / Success text: #397345
"""

from typing import Optional


# Design Tokens
TOKENS = {
    "bg_main": "#F7F8F3",
    "bg_sidebar": "#F0F3EA",
    "primary": "#477D50",
    "dark_forest": "#173F2D",
    "secondary": "#79A982",
    "pastel": "#DCEBD8",
    "surface_light": "#EAF2E6",
    "card_bg": "#FFFFFF",
    "text_primary": "#20352A",
    "text_secondary": "#718078",
    "border": "#E2E9DF",
    "warning_bg": "#FFF3D9",
    "warning_text": "#936B1C",
    "error_bg": "#FCE9E7",
    "error_text": "#A64E46",
    "success_bg": "#E2F0DF",
    "success_text": "#397345",
    "radius_card": "16px",
    "radius_input": "10px",
    "radius_btn": "10px",
    "radius_badge": "20px",
}


def render_page_header(title: str, caption: str, badge: Optional[str] = None) -> str:
    """Generate HTML for a consistent page header with optional status badge."""
    badge_html = f"<span class='badge badge-neutral'>{badge}</span>" if badge else ""
    return f"""
    <div style="margin-bottom: 1.25rem;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
            <h1 style="margin: 0; font-size: 1.65rem; font-weight: 700; color: #173F2D; letter-spacing: -0.02em;">
                {title}
            </h1>
            {badge_html}
        </div>
        <p style="margin: 0; font-size: 0.88rem; color: #718078; font-weight: 400; line-height: 1.45;">
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
    """Generate HTML for a styled pill badge.

    Variants: 'neutral', 'success', 'review', 'critical', 'info', 'pastel'
    """
    variant_class = {
        "neutral": "badge-neutral",
        "success": "badge-success",
        "review": "badge-review",
        "critical": "badge-critical",
        "info": "badge-info",
        "pastel": "badge-pastel",
    }.get(variant, "badge-neutral")
    return f"<span class='badge {variant_class}'>{text}</span>"


def render_card_start(padding: str = "18px 22px", margin_bottom: str = "1rem") -> str:
    """Generate opening tag for a styled surface card."""
    return f"<div class='attendsure-card' style='padding: {padding}; margin-bottom: {margin_bottom};'>"


def render_card_end() -> str:
    """Generate closing tag for a styled surface card."""
    return "</div>"

