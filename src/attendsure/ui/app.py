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
    initial_sidebar_state="auto",
)

from attendsure.ui.auth import (
    has_permission,
    is_auth_required,
    is_authenticated,
    render_access_denied_card,
    render_login_screen,
    render_user_badge_sidebar,
)
from attendsure.ui.state import get_configured_db_path, get_active_database_metadata, test_db_connection
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
    # Authentication & Institutional Gate
    # -------------------------------------------------------------------------
    if is_auth_required() and not is_authenticated():
        login_container = st.empty()
        with login_container.container():
            render_login_screen()
        return
    # -------------------------------------------------------------------------
    # Sidebar Header & Brand Identity (Modern SaaS Direction)
    # -------------------------------------------------------------------------
    st.sidebar.markdown(
        """
        <div style="padding-bottom: 2px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <div style="
                    width: 36px;
                    height: 36px;
                    background-color: #0F172A;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.25rem;
                    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
                    flex-shrink: 0;
                ">
                    🎓
                </div>
                <div>
                    <div style="font-size: 0.94rem; font-weight: 700; color: #0F172A; letter-spacing: -0.02em; line-height: 1.2;">
                        Rural School Attendance
                    </div>
                    <div style="font-size: 0.74rem; font-weight: 600; color: #0D9488; letter-spacing: -0.01em;">
                        Integrity & Intervention Decision System
                    </div>
                </div>
            </div>
            <p style="margin: 4px 0 12px 0; font-size: 0.70rem; color: #64748B; font-weight: 500; line-height: 1.35;">
                SIH25012 • Automated Attendance System for Rural Schools
            </p>
            <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 0 0 14px 0;" />
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

    # Render authenticated user status badge in the sidebar if auth is active
    if is_auth_required() and is_authenticated():
        render_user_badge_sidebar()

    selected_page = st.sidebar.radio(
        "Application Navigation",
        options=navigation_options,
        format_func=lambda p: PAGE_ICONS.get(p, p),
        index=nav_index,
        key="main_nav_radio",
    )

    db_meta = get_active_database_metadata()
    backend_display = db_meta["backend"]
    storage_line = (
        f"• {backend_display} ({db_meta['region']})<br>• Persistent Managed Relational Database<br>• No Biometrics Collected or Stored"
        if db_meta.get("is_cloud")
        else "• Offline School Operation<br>• Local SQLite Storage<br>• No Biometrics Collected or Stored"
    )

    st.sidebar.markdown(
        f"""
        <div style="margin-top: 2rem; padding: 12px 14px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #0D9488;"></span>
                <span style="font-size: 0.80rem; font-weight: 700; color: #0F172A;">{db_meta['status']}</span>
            </div>
            <div style="font-size: 0.74rem; color: #475569; line-height: 1.45;">
                {storage_line}
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
            "Persistent database service is currently unavailable. "
            "Please check storage folder write permissions or restore from backup."
        )
        if st.button("🔄  Retry Connection", key="retry_db_conn_btn"):
            st.rerun()
        return

    # -------------------------------------------------------------------------
    # Page Routing (Supporting Mandated 6 Pages with Role Authorization)
    # -------------------------------------------------------------------------
    if selected_page in ("Home", "Dashboard", "Overview Dashboard"):
        render_overview()

    elif selected_page in ("Mark Attendance", "Attendance", "Attendance Register"):
        render_register()

    elif selected_page in ("Attendance Records", "Records"):
        render_records()

    elif selected_page in ("Needs Attention", "Alerts", "Intelligence Centre"):
        if not has_permission("view_intelligence"):
            render_access_denied_card("Headmaster / Administrator")
        else:
            render_intelligence()

    elif selected_page in ("Reports", "Reports & Export"):
        render_reports()

    elif selected_page in ("Settings", "Data & Settings"):
        if not has_permission("manage_settings"):
            render_access_denied_card("Headmaster / Administrator")
        else:
            render_settings()

    elif selected_page in ("Test & Learn", "Algorithm Laboratory"):
        if not has_permission("access_laboratory"):
            render_access_denied_card("Headmaster / Administrator")
        else:
            render_laboratory()


if __name__ == "__main__":
    main()
