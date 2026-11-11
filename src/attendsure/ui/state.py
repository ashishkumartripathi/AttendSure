"""Repository lifecycle and session state management for AttendSure UI.

Provides safe, per-execution database repository management:
- Strictly avoids storing raw database connections or repository instances in
  st.session_state or global module variables (preventing cross-thread errors).
- Creates repository instances scoped to the current execution or context block.
- Explicitly closes connections via context management.
- Supports both managed Neon Cloud PostgreSQL (production) and local SQLite (development/tests).
- In production mode, strictly requires Neon PostgreSQL and prohibits silent SQLite fallback.
- Defaults to the canonical DEFAULT_DB_PATH ('data/attendsure.db') when running offline SQLite.
"""

from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import time
from typing import Any, Dict, Generator, Optional, Union

import pandas as pd
import sqlalchemy as sa
import streamlit as st

from attendsure.data.db_engine import (
    RelationalRepository,
    get_database_url,
    get_shared_engine,
    is_postgres_url,
    is_production_mode,
)
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository

# High-performance in-memory cache for repeated screen reads across navigation
_DATA_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_HEALTH_CHECK: Dict[str, Any] = {}


def invalidate_data_cache() -> None:
    """Explicitly clear all cached sessions and alerts data.

    Called immediately upon attendance submission, batch CSV import,
    or educator alert review determinations.
    """
    _DATA_CACHE.clear()


def _get_cache_key(repo: Any) -> str:
    """Generate a consistent cache partition key for the repository."""
    if hasattr(repo, "_db_path"):
        return str(repo._db_path)
    if hasattr(repo, "db_path"):
        return str(repo.db_path)
    if hasattr(repo, "db_url"):
        return str(repo.db_url)
    return "default"


def get_cached_sessions(repo: Any, ttl: float = 20.0) -> pd.DataFrame:
    """Retrieve sessions DataFrame with defensive copy and short TTL caching.

    Eliminates repeated database queries during navigation across all six screens
    while ensuring mutations and writes invalidate immediately.
    """
    key = _get_cache_key(repo) + "_sessions"
    now = time.time()

    if key in _DATA_CACHE:
        entry = _DATA_CACHE[key]
        if (now - entry["time"]) < ttl:
            return entry["data"].copy()

    df = repo.get_sessions(as_df=True)
    _DATA_CACHE[key] = {"data": df, "time": now}
    return df.copy()


def get_cached_alerts(repo: Any, ttl: float = 20.0) -> list:
    """Retrieve alert records with defensive copy and short TTL caching."""
    key = _get_cache_key(repo) + "_alerts"
    now = time.time()

    if key in _DATA_CACHE:
        entry = _DATA_CACHE[key]
        if (now - entry["time"]) < ttl:
            return list(entry["data"])

    alerts = repo.get_alerts()
    _DATA_CACHE[key] = {"data": alerts, "time": now}
    return list(alerts)


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


def get_active_database_metadata() -> Dict[str, Any]:
    """Retrieve active database backend metadata for user transparent display."""
    if "db_path" in st.session_state and st.session_state["db_path"] is not None:
        return {
            "backend": "Local SQLite Storage",
            "is_cloud": False,
            "region": "Local Filesystem",
            "db_path": str(st.session_state["db_path"]),
            "status": "Online & Ready",
        }

    pg_url = get_database_url(fallback_to_sqlite=False)
    if pg_url and is_postgres_url(pg_url):
        host = pg_url.split("@")[-1].split("/")[0] if "@" in pg_url else "cloud-managed"
        region = "aws-ap-southeast-1" if "ap-southeast-1" in host else "Cloud Managed"
        return {
            "backend": "Neon Cloud PostgreSQL",
            "is_cloud": True,
            "region": region,
            "host": host,
            "status": "Online & Connected",
        }

    if is_production_mode():
        return {
            "backend": "Neon Cloud PostgreSQL (Required)",
            "is_cloud": True,
            "region": "aws-ap-southeast-1",
            "status": "Configuration Required (Missing DATABASE_URL)",
        }

    return {
        "backend": "Local SQLite Storage",
        "is_cloud": False,
        "region": "Local Filesystem",
        "db_path": str(DEFAULT_DB_PATH),
        "status": "Online & Ready",
    }


@contextmanager
def get_repository(
    db_path: Optional[Union[str, Path]] = None,
) -> Generator[Any, None, None]:
    """Provide a thread-safe, auto-closing repository instance for a single operation.

    Usage:
        with get_repository() as repo:
            sessions_df = repo.get_sessions(as_df=True)

    Policy:
    1. If an explicit SQLite path is passed (e.g., in unit tests), uses AttendanceRepository.
    2. If st.session_state['db_path'] is set, uses AttendanceRepository on that path.
    3. In production mode (ATTENDSURE_ENVIRONMENT=production):
       - Requires Neon Cloud PostgreSQL (DATABASE_URL).
       - Never silently falls back to local SQLite.
    4. In local development / offline mode:
       - Uses PostgreSQL if DATABASE_URL is set, else falls back to local SQLite.

    Yields:
        Active repository instance (RelationalRepository or AttendanceRepository).
    """
    # 1. Explicit SQLite path provided (e.g. test isolation)
    if db_path is not None:
        repo = AttendanceRepository(db_path=db_path)
        try:
            yield repo
        finally:
            repo.close()
        return

    # 2. Session state override
    if "db_path" in st.session_state and st.session_state["db_path"] is not None:
        repo = AttendanceRepository(db_path=st.session_state["db_path"])
        try:
            yield repo
        finally:
            repo.close()
        return

    # 3. Check for PostgreSQL connection URL
    pg_url = get_database_url(fallback_to_sqlite=False)

    # 4. Enforce production policy: Neon PostgreSQL required, NO silent SQLite fallback
    if is_production_mode():
        if not pg_url or not is_postgres_url(pg_url):
            raise RuntimeError(
                "Production mode (ATTENDSURE_ENVIRONMENT=production) requires managed Neon PostgreSQL (DATABASE_URL). "
                "Silent fallback to local SQLite is strictly prohibited in production."
            )
        repo = RelationalRepository(pg_url)
        try:
            yield repo
        finally:
            repo.close()
        return

    # 5. Local development with PostgreSQL configured
    if pg_url and is_postgres_url(pg_url):
        repo = RelationalRepository(pg_url)
        try:
            yield repo
        finally:
            repo.close()
        return

    # 6. Local development default SQLite
    target = get_configured_db_path()
    repo = AttendanceRepository(db_path=target)
    try:
        yield repo
    finally:
        repo.close()


def test_db_connection(
    db_path: Optional[Union[str, Path]] = None,
    force: bool = False,
) -> tuple[bool, Optional[str]]:
    """Test whether the configured database can be accessed and queried safely.

    Optimized for high-responsiveness:
    - Uses lightweight 'SELECT 1;' query instead of heavy full-table scans.
    - Caches connection health for 30 seconds unless force=True, eliminating
      redundant round-trips to managed cloud databases on rapid user interactions.
    """
    now = time.time()
    if db_path is not None:
        cache_key = str(db_path)
    elif "db_path" in st.session_state and st.session_state["db_path"] is not None:
        cache_key = str(st.session_state["db_path"])
    else:
        cache_key = get_database_url(fallback_to_sqlite=False) or str(DEFAULT_DB_PATH)

    if not force and cache_key in _LAST_HEALTH_CHECK:
        entry = _LAST_HEALTH_CHECK[cache_key]
        if (now - entry["time"]) < 30.0:
            return entry["is_healthy"], entry["error"]

    try:
        # Explicit test path override
        if db_path is not None:
            conn = sqlite3.connect(str(db_path), timeout=5)
            try:
                conn.execute("SELECT 1;")
            finally:
                conn.close()
            _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": True, "error": None}
            return True, None

        # Session state override
        if "db_path" in st.session_state and st.session_state["db_path"] is not None:
            conn = sqlite3.connect(str(st.session_state["db_path"]), timeout=5)
            try:
                conn.execute("SELECT 1;")
            finally:
                conn.close()
            _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": True, "error": None}
            return True, None

        pg_url = get_database_url(fallback_to_sqlite=False)
        if is_production_mode():
            if not pg_url or not is_postgres_url(pg_url):
                err = "Production mode requires managed Neon PostgreSQL (DATABASE_URL)."
                _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": False, "error": err}
                return False, err
            engine = get_shared_engine(pg_url)
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1;"))
            _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": True, "error": None}
            return True, None

        if pg_url and is_postgres_url(pg_url):
            engine = get_shared_engine(pg_url)
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1;"))
            _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": True, "error": None}
            return True, None

        target = get_configured_db_path()
        conn = sqlite3.connect(str(target), timeout=5)
        try:
            conn.execute("SELECT 1;")
        finally:
            conn.close()
        _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": True, "error": None}
        return True, None

    except Exception as exc:
        _LAST_HEALTH_CHECK[cache_key] = {"time": now, "is_healthy": False, "error": str(exc)}
        return False, str(exc)
