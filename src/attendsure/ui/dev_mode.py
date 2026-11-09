"""Central Global Developer Mode Service for AttendSure.

Provides a unified single source of truth for Developer Mode across all 6 application screens:
- Teacher View (Developer Mode OFF): Simple, clean, jargon-free interface showing only outcomes.
- Developer View (Developer Mode ON): Exposes technical models, diagnostics, evidence, and internal identifiers.
Adheres to docs/data-contract.md and AGENTS.md.
"""

from contextlib import contextmanager
import json
from pathlib import Path
from typing import Generator, Optional
import streamlit as st

CONFIG_FILE_PATH = Path("data") / ".attendsure_config.json"


def _read_persisted_preference() -> bool:
    """Read persisted developer mode preference from local config file."""
    try:
        if CONFIG_FILE_PATH.exists():
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("developer_mode", False))
    except Exception:
        pass
    return False


def _write_persisted_preference(enabled: bool) -> None:
    """Save developer mode preference to local config file."""
    try:
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["developer_mode"] = bool(enabled)
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_developer_mode() -> bool:
    """Return True if Developer Mode is globally active, False otherwise (default)."""
    # 1. Check Streamlit session_state
    if "developer_mode" in st.session_state and st.session_state["developer_mode"] is not None:
        return bool(st.session_state["developer_mode"])
    # 2. Check legacy alias for backward compatibility
    if "dev_mode_enabled" in st.session_state and st.session_state["dev_mode_enabled"] is not None:
        st.session_state["developer_mode"] = bool(st.session_state["dev_mode_enabled"])
        return st.session_state["developer_mode"]
    # 3. Check persistent config file on disk
    persisted = _read_persisted_preference()
    st.session_state["developer_mode"] = persisted
    st.session_state["dev_mode_enabled"] = persisted
    return persisted


def set_developer_mode(enabled: bool) -> None:
    """Set global developer mode and persist to session state and disk."""
    val = bool(enabled)
    st.session_state["developer_mode"] = val
    st.session_state["dev_mode_enabled"] = val
    _write_persisted_preference(val)


@contextmanager
def developer_section(
    title: str = "Technical Details — Developer View",
    expanded: bool = False,
) -> Generator[bool, None, None]:
    """Context manager that renders an expander ONLY if Developer Mode is enabled."""
    if is_developer_mode():
        with st.expander(f"⚙️ {title}", expanded=expanded):
            yield True
    else:
        yield False

