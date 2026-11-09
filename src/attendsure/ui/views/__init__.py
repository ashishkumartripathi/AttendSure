"""View components for AttendSure Streamlit UI."""

from attendsure.ui.views.intelligence import render_intelligence
from attendsure.ui.views.laboratory import render_laboratory
from attendsure.ui.views.overview import render_overview
from attendsure.ui.views.register import render_register
from attendsure.ui.views.reports import render_reports
from attendsure.ui.views.settings import render_settings

__all__ = [
    "render_overview",
    "render_register",
    "render_intelligence",
    "render_laboratory",
    "render_reports",
    "render_settings",
]
