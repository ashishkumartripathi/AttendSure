"""Repository lifecycle and session state management for AttendSure UI.

Provides safe, per-execution database repository management:
- Strictly avoids storing raw SQLite connections or repository instances in
  st.session_state or global module variables (preventing cross-thread SQLite errors).
- Creates repository instances scoped to the current execution or context block.
- Explicitly closes connections via AttendanceRepository context management.
- Does not modify check_same_thread or bypass standard sqlite3 safety.
- Defaults to the canonical DEFAULT_DB_PATH ('data/attendsure.db') established in Milestone M2.
- Does not automatically seed synthetic data on reruns.
"""

from contextlib import contextmanager
from pathlib import Path
import os
from typing import Generator, Optional, Union

import streamlit as st

from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository


def get_configured_db_path() -> Union[str, Path]:
    """Retrieve the configured database path.

    Checks:
    1. st.session_state['db_path'] for runtime overrides (e.g., isolated test databases);
    2. ATTENDSURE_DB_PATH environment variable (for dedicated demonstration runs);
    3. Defaults to the project's canonical DEFAULT_DB_PATH ('data/attendsure.db').
    """
    if "db_path" in st.session_state and st.session_state["db_path"] is not None:
        raw_path = st.session_state["db_path"]
        if str(raw_path) == ":memory:":
            return ":memory:"
        return Path(raw_path)

    env_path = os.environ.get("ATTENDSURE_DB_PATH")
    if env_path and env_path.strip():
        trimmed = env_path.strip()
        if trimmed == ":memory:":
            return ":memory:"
        return Path(trimmed)

    return DEFAULT_DB_PATH


@contextmanager
def get_repository(
    db_path: Optional[Union[str, Path]] = None,
) -> Generator[AttendanceRepository, None, None]:
    """Provide a thread-safe, auto-closing AttendanceRepository instance for a single operation.

    Usage:
        with get_repository() as repo:
            sessions_df = repo.get_sessions(as_df=True)

    Ensures that:
    1. A fresh repository instance is created on the current thread.
    2. Connection is closed immediately when the with-block terminates.
    3. No persistent connection leaks across Streamlit thread executions.

    Yields:
        Active AttendanceRepository instance.

    Raises:
        Exception: If database initialization or file access fails.
    """
    target = db_path if db_path is not None else get_configured_db_path()
    repo = AttendanceRepository(db_path=target)
    try:
        yield repo
    finally:
        repo.close()


def test_db_connection(db_path: Optional[Union[str, Path]] = None) -> tuple[bool, Optional[str]]:
    """Test whether the configured SQLite database can be accessed and queried safely.

    Returns:
        Tuple of (is_healthy: bool, error_message: Optional[str]).
    """
    try:
        with get_repository(db_path=db_path) as repo:
            # Simple query to verify table schema existence and read readiness
            repo.get_sessions(as_df=True)
        return True, None
    except Exception as exc:
        return False, str(exc)
