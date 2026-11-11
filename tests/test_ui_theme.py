"""Unit tests for the Modern SaaS visual theme definitions and UI component helpers.

Verifies:
- Design tokens adhere to the approved Modern SaaS palette (Navy, Teal, Slate, Amber).
- Token keys preserve full backward compatibility.
- HTML helper functions produce well-formed, accessible markup.
- All hex color tokens are valid 7-character hexadecimal strings.
"""

import re
from pathlib import Path
import pytest

from attendsure.ui.theme import (
    TOKENS,
    render_badge,
    render_card_end,
    render_card_start,
    render_decision_support_box,
    render_empty_state,
    render_kpi_card,
    render_metric_highlight,
    render_page_header,
    render_summary_banner,
)


HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TestModernSaaSTokens:
    """Tests verifying the design tokens specification."""

    def test_core_saas_color_palette(self):
        """Verify the primary SaaS palette tokens are established."""
        assert TOKENS["navy_primary"] == "#0F172A"
        assert TOKENS["navy_card"] == "#1E293B"
        assert TOKENS["teal_primary"] == "#0D9488"
        assert TOKENS["teal_hover"] == "#0F766E"
        assert TOKENS["bg_main"] == "#F8FAFC"
        assert TOKENS["bg_canvas"] == "#F8FAFC"
        assert TOKENS["bg_sidebar"] == "#F1F5F9"
        assert TOKENS["card_bg"] == "#FFFFFF"
        assert TOKENS["warning_bg"] == "#FEF3C7"
        assert TOKENS["warning_text"] == "#92400E"
        assert TOKENS["error_bg"] == "#FEE2E2"
        assert TOKENS["error_text"] == "#991B1B"

    def test_backward_compatibility_token_keys(self):
        """Verify that legacy token keys remain accessible for existing views."""
        legacy_keys = [
            "primary",
            "dark_forest",
            "bg_main",
            "bg_sidebar",
            "surface_light",
            "card_bg",
            "text_primary",
            "text_secondary",
            "border",
            "warning_bg",
            "warning_text",
            "error_bg",
            "error_text",
            "success_bg",
            "success_text",
            "radius_card",
            "radius_input",
            "radius_btn",
            "radius_badge",
        ]
        for key in legacy_keys:
            assert key in TOKENS, f"Missing required token key: '{key}'"

    def test_hex_token_format_validity(self):
        """Verify all color values in TOKENS are valid 7-character hex colors."""
        for key, value in TOKENS.items():
            if key.startswith("radius") or key.startswith("shadow"):
                continue
            assert HEX_COLOR_PATTERN.match(value), (
                f"Token '{key}' has invalid hex format: '{value}'"
            )


class TestComponentHelpers:
    """Tests verifying HTML component helper markup generation."""

    def test_render_page_header(self):
        """Verify page header generation with and without status badge."""
        html_no_badge = render_page_header("Overview", "Daily summary")
        assert "<h1" in html_no_badge
        assert "Overview" in html_no_badge
        assert "Daily summary" in html_no_badge

        html_with_badge = render_page_header("Needs Attention", "Triage queue", badge="Active")
        assert "badge" in html_with_badge
        assert "Active" in html_with_badge

    def test_render_decision_support_box(self):
        """Verify decision support notice formatting and non-accusatory title."""
        html = render_decision_support_box("All alerts are advisory.", title="Notice:")
        assert "decision-support-box" in html
        assert "Notice:" in html
        assert "All alerts are advisory." in html

    def test_render_badge_variants(self):
        """Verify pill badge generation across supported status variants."""
        variants = ["neutral", "success", "review", "critical", "info", "pastel", "ml"]
        for v in variants:
            html = render_badge("Label", variant=v)
            assert f"badge-{v}" in html
            assert "Label" in html

        # Unknown variant fallback
        fallback = render_badge("Test", variant="unknown_variant")
        assert "badge-neutral" in fallback

    def test_render_card_delimiters(self):
        """Verify start and end delimiters for surface cards."""
        start = render_card_start(padding="12px", margin_bottom="0.5rem")
        assert "attendsure-card" in start
        assert "padding: 12px" in start
        assert "margin-bottom: 0.5rem" in start

        end = render_card_end()
        assert end == "</div>"

    def test_render_kpi_card(self):
        """Verify modern SaaS KPI card markup."""
        html = render_kpi_card(
            label="Total Enrolled",
            value="350",
            subtext="Across 12 classes",
            badge="Active",
            status="success",
            icon="👥",
        )
        assert "saas-kpi-card" in html
        assert "Total Enrolled" in html
        assert "350" in html
        assert "Across 12 classes" in html
        assert "badge-success" in html
        assert "👥" in html

    def test_render_summary_banner(self):
        """Verify summary banner rendering across variants."""
        html = render_summary_banner("Attendance Alert", "Drop detected", variant="warning")
        assert "saas-banner-warning" in html
        assert "Attendance Alert" in html
        assert "Drop detected" in html

    def test_render_empty_state(self):
        """Verify empty state container markup."""
        html = render_empty_state("No Records", "No sessions recorded yet.", icon="📭")
        assert "saas-empty-state" in html
        assert "No Records" in html
        assert "No sessions recorded yet." in html
        assert "📭" in html

    def test_render_metric_highlight(self):
        """Verify dual metric comparison markup."""
        html = render_metric_highlight(
            "Present Count", "12",
            "Expected Baseline", "35",
        )
        assert "saas-metric-compare-row" in html
        assert "Present Count" in html
        assert "12" in html
        assert "Expected Baseline" in html
        assert "35" in html

