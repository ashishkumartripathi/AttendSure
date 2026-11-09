"""Tests for AttendSure package discovery, structure, and importability."""

import importlib
import sys
from pathlib import Path


def test_attendsure_package_import():
    """Verify that the attendsure package is properly discovered and importable."""
    pkg = importlib.import_module("attendsure")
    assert pkg is not None
    assert hasattr(pkg, "__file__")
    assert Path(pkg.__file__).name == "__init__.py"


def test_attendsure_subpackages_import():
    """Verify that all core subpackages are importable."""
    subpackages = [
        "attendsure.data",
        "attendsure.detection",
        "attendsure.evaluation",
        "attendsure.services",
        "attendsure.ui",
        "attendsure.ui.views",
    ]
    for subpkg in subpackages:
        mod = importlib.import_module(subpkg)
        assert mod is not None


def test_app_entrypoint_imports_cleanly():
    """Verify that app entrypoint imports without ModuleNotFoundError."""
    # Importing attendsure.ui.app checks all top-level state and view imports
    app_module = importlib.import_module("attendsure.ui.app")
    assert app_module is not None
    assert hasattr(app_module, "main")
