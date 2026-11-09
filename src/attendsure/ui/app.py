"""Rural School Attendance Integrity and Intervention Decision System Entrypoint.

Provides navigation shell, visual theming, and modular routing conforming to
the approved 6-page teacher-friendly flow and reference design specification.
"""

import sys
from pathlib import Path
import streamlit as st

# Ensure src directory is on sys.path if not installed in site-packages
_SRC_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Configure page settings first before any other Streamlit commands
st.set_page_config(
    page_title="Rural School Attendance Integrity and Intervention Decision System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

from attendsure.ui.state import get_configured_db_path, test_db_connection
from attendsure.ui.styles import apply_theme
from attendsure.ui.views.intelligence import render_intelligence
from attendsure.ui.views.laboratory import render_laboratory
from attendsure.ui.views.overview import render_overview
from attendsure.ui.views.records import render_records
from attendsure.ui.views.register import render_register
from attendsure.ui.views.reports import render_reports
from attendsure.ui.views.settings import render_settings

# Apply visual theme tokens and custom CSS
apply_theme()


def main() -> None:
    """Main application navigation router and shell layout."""
    # -------------------------------------------------------------------------
    # Sidebar Header & Brand Identity (Matching Reference)
    # -------------------------------------------------------------------------
    st.sidebar.markdown(
        """
        <div style="padding-bottom: 2px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                <div style="
                    width: 36px;
                    height: 36px;
                    background-color: #EAF2E6;
                    border: 1px solid #DCEBD8;
                    border-radius: 10px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.30rem;
                ">
                    🎓
                </div>
                <div>
                    <span style="font-size: 1.18rem; font-weight: 700; color: #174A32; letter-spacing: -0.02em; line-height: 1.15;">
                        Rural School
                    </span>
                    <br>
                    <span style="font-size: 0.88rem; font-weight: 600; color: #237A50; letter-spacing: -0.01em;">
                        Attendance System
                    </span>
                </div>
            </div>
            <p style="margin: 4px 0 12px 0; font-size: 0.73rem; color: #77837A; font-weight: 500; line-height: 1.3;">
                Attendance Integrity and Intervention Decision System
            </p>
            <hr style="border: none; border-top: 1px solid #E5EAE1; margin: 0 0 14px 0;" />
        </div>
        """,
        unsafe_allow_html=True,
    )

    navigation_options = [
        "Home",
        "Mark Attendance",
        "Attendance Records",
        "Needs Attention",
        "Reports",
        "Settings",
    ]

    PAGE_ICONS = {
        "Home": "🏠  Home",
        "Mark Attendance": "📝  Mark Attendance",
        "Attendance Records": "📋  Attendance Records",
        "Needs Attention": "🛡️  Needs Attention",
        "Reports": "📊  Reports",
        "Settings": "⚙️  Settings",
        # Backward compatibility aliases
        "Dashboard": "🏠  Home",
        "Attendance": "📝  Mark Attendance",
        "Alerts": "🛡️  Needs Attention",
        "Test & Learn": "🧪  Test & Learn",
    }

    # Handle programmatic navigation requests
    nav_index = 0
    if "nav_target" in st.session_state and st.session_state["nav_target"] in navigation_options:
        nav_index = navigation_options.index(st.session_state["nav_target"])
        st.session_state["main_nav_radio"] = st.session_state["nav_target"]
        del st.session_state["nav_target"]

    selected_page = st.sidebar.radio(
        "Application Navigation",
        options=navigation_options,
        format_func=lambda p: PAGE_ICONS.get(p, p),
        index=nav_index,
        key="main_nav_radio",
    )

    st.sidebar.markdown(
        """
        <div style="margin-top: 2.2rem; padding: 14px 14px; background: #FFFFFF; border: 1px solid #E5EAE1; border-radius: 12px; box-shadow: 0 1px 3px rgba(23, 74, 50, 0.02);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="font-size: 1rem;">🏫</span>
                <span style="font-size: 0.80rem; font-weight: 700; color: #174A32;">School System Ready</span>
            </div>
            <div style="font-size: 0.74rem; color: #556B5F; line-height: 1.45;">
                • Offline School Edition<br>
                • Saves data on this device<br>
                • Private student records
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # Pre-Flight Database Health Check
    # -------------------------------------------------------------------------
    db_healthy, db_error = test_db_connection()
    if not db_healthy:
        st.error(f"Database Connection Error: {db_error}")
        st.warning(
            f"Configured path: '{get_configured_db_path()}'. "
            "Please check folder write permissions or restore the SQLite file."
        )
        return

    # -------------------------------------------------------------------------
    # Page Routing (Supporting Mandated 6 Pages and Legacy Aliases)
    # -------------------------------------------------------------------------
    if selected_page in ("Home", "Dashboard", "Overview Dashboard"):
        render_overview()

    elif selected_page in ("Mark Attendance", "Attendance", "Attendance Register"):
        render_register()

    elif selected_page in ("Attendance Records", "Records"):
        render_records()

    elif selected_page in ("Needs Attention", "Alerts", "Intelligence Centre"):
        render_intelligence()

    elif selected_page in ("Reports", "Reports & Export"):
        render_reports()

    elif selected_page in ("Settings", "Data & Settings"):
        render_settings()

    elif selected_page in ("Test & Learn", "Algorithm Laboratory"):
        render_laboratory()


if __name__ == "__main__":
    main()
