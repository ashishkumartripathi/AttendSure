#!/usr/bin/env python3
"""Convenience script to safely prepare an AttendSure demonstration database.

Usage:
    python scripts/prepare_demo_database.py --dest data/demo_showcase.db
    python scripts/prepare_demo_database.py --dest data/demo_showcase.db --seed 42
"""

import sys
from pathlib import Path

# Ensure src/ is on sys.path if not installed in editable mode
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from attendsure.data.demo_seed import main

if __name__ == "__main__":
    main()
