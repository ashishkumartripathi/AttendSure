"""Verify application imports and startup modules in public release worktree."""
import sys
from pathlib import Path

# Add src to path
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

print("=" * 70)
print("VERIFYING APPLICATION STARTUP & MODULE IMPORT CHAIN")
print("=" * 70)

modules = [
    "attendsure",
    "attendsure.data.models",
    "attendsure.data.storage",
    "attendsure.data.csv_io",
    "attendsure.data.validation",
    "attendsure.data.generator",
    "attendsure.data.demo_seed",
    "attendsure.data.webcam",
    "attendsure.data.webcam_capture",
    "attendsure.detection.rules",
    "attendsure.evaluation.metrics",
    "attendsure.ml.features",
    "attendsure.ml.dataset",
    "attendsure.ml.model",
    "attendsure.ml.predictor",
    "attendsure.services.attendance_service",
    "attendsure.ui.state",
    "attendsure.ui.styles",
    "attendsure.ui.theme",
    "attendsure.ui.dev_mode",
    "attendsure.ui.views.overview",
    "attendsure.ui.views.register",
    "attendsure.ui.views.records",
    "attendsure.ui.views.intelligence",
    "attendsure.ui.views.reports",
    "attendsure.ui.views.settings",
    "attendsure.ui.views.laboratory",
    "attendsure.ui.app",
]

for m in modules:
    try:
        __import__(m)
        print(f"  [OK] {m}")
    except Exception as exc:
        print(f"  [FAILED] {m}: {exc}")
        sys.exit(1)

print("\nAll 28 core and UI presentation modules imported successfully with 0 errors!")
print("=" * 70)

