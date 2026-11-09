"""Demonstration Database Generator and Safe Seeding Strategy for AttendSure.

Provides an explicit, safe, reproducible workflow to synthesize isolated demonstration
databases for academic and evaluation showcases without ever touching or modifying the
user's active operational database.

Safety Guarantees:
1. Rejects any attempt to target the canonical operational database (DEFAULT_DB_PATH).
2. Refuses to overwrite existing database files (prevents accidental data loss).
3. Requires an explicit, non-empty destination path.
4. Marks 100% of generated records with record_source="SYNTHETIC".
5. Employs deterministic random seeds for bit-for-bit reproducible outcomes.
6. Conforms strictly to docs/data-contract.md schema constraints and invariants.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
from typing import Any, Optional, Union
import uuid

from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository
from attendsure.data.validation import validate_session_dict



def _deterministic_uuid(rng: random.Random) -> str:
    """Generate a valid RFC 4122 UUIDv4 deterministically from a local RNG."""
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def prepare_demo_database(
    dest_path: Union[str, Path],
    random_seed: int = 42,
    run_detection: bool = True,
) -> dict[str, Any]:
    """Prepare a dedicated SQLite demonstration database with pre-packaged scenarios.

    Args:
        dest_path: Explicit file path for the demonstration database.
                   Must not be empty, must not point to DEFAULT_DB_PATH,
                   and must not point to an already existing file.
        random_seed: Integer seed guaranteeing reproducible session numbers and dates.
        run_detection: If True, executes the detection pipeline across all seeded
                       sessions so the database contains reviewable anomaly signals.

    Returns:
        Summary dictionary with session counts, cohort IDs, and alert metrics.

    Raises:
        ValueError: If dest_path is empty or points to the operational database.
        FileExistsError: If dest_path already exists.
    """
    if dest_path is None or not str(dest_path).strip():
        raise ValueError("Safety Guard: Destination database path must be explicitly provided.")

    target = Path(dest_path).resolve()
    operational = DEFAULT_DB_PATH.resolve()

    # Safety Guard 1: Prevent overwriting or touching operational database
    if target == operational:
        raise ValueError(
            f"Safety Guard Violation: Refusing to seed demonstration data into the active operational "
            f"database ('{dest_path}'). Please specify a separate destination path "
            f"(e.g., 'data/demo_showcase.db')."
        )

    # Safety Guard 2: Prevent overwriting any pre-existing database file
    if target.exists():
        raise FileExistsError(
            f"Safety Guard Violation: Destination database '{dest_path}' already exists. "
            f"To prevent accidental data loss, AttendSure will not overwrite an existing file. "
            f"Please choose a different destination path or delete the old file manually."
        )

    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(random_seed)

    # Base date: 15 days in the past so all dates are valid past dates
    today = max(datetime.now(timezone.utc).date(), datetime.now().date())
    base_date = today - timedelta(days=20)

    all_sessions: list[SessionRecord] = []
    num_days = 12

    # -------------------------------------------------------------------------
    # Scenario 1: CLASS-01-A — Nominal Baseline Attendance (No Anomalies)
    # -------------------------------------------------------------------------
    enrollment_1 = 30
    for day_idx in range(num_days):
        sdate = (base_date + timedelta(days=day_idx)).isoformat()
        present = 26 + rng.randint(0, 3)  # 26-29 students (86.7% - 96.7%)
        absent = enrollment_1 - present
        sid = _deterministic_uuid(rng)
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-01-A",
            session_date=sdate,
            expected_enrollment=enrollment_1,
            present_count=present,
            absent_count=absent,
            webcam_status="SUCCESS",
            webcam_count=present,
            record_source="SYNTHETIC",
            created_at=f"{sdate}T09:00:00Z",
        )
        all_sessions.append(rec)

    # -------------------------------------------------------------------------
    # Scenario 2: CLASS-02-B — Unusual Attendance Drop (RULE_ATTENDANCE_DROP)
    # -------------------------------------------------------------------------
    enrollment_2 = 32
    for day_idx in range(num_days):
        sdate = (base_date + timedelta(days=day_idx)).isoformat()
        if day_idx == 5:
            # Day 6: Sharp drop to 11 students (~34.4% present)
            present = 11
        else:
            present = 28 + rng.randint(0, 2)  # 28-30 students (~90%)
        absent = enrollment_2 - present
        sid = _deterministic_uuid(rng)
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-02-B",
            session_date=sdate,
            expected_enrollment=enrollment_2,
            present_count=present,
            absent_count=absent,
            webcam_status="SUCCESS",
            webcam_count=present,
            record_source="SYNTHETIC",
            created_at=f"{sdate}T09:00:00Z",
        )
        all_sessions.append(rec)

    # -------------------------------------------------------------------------
    # Scenario 3: CLASS-03-C — Repeated Headcount (RULE_REPEATED_HEADCOUNT)
    # -------------------------------------------------------------------------
    enrollment_3 = 28
    repeated_val = 22
    for day_idx in range(num_days):
        sdate = (base_date + timedelta(days=day_idx)).isoformat()
        if 4 <= day_idx <= 7:
            # Days 5-8: Exactly 22 students present for 4 consecutive sessions
            present = repeated_val
        else:
            present = 24 + rng.randint(0, 3)  # 24-27 students
        absent = enrollment_3 - present
        sid = _deterministic_uuid(rng)
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-03-C",
            session_date=sdate,
            expected_enrollment=enrollment_3,
            present_count=present,
            absent_count=absent,
            webcam_status="NOT_ATTEMPTED",
            webcam_count=None,
            record_source="SYNTHETIC",
            created_at=f"{sdate}T09:00:00Z",
        )
        all_sessions.append(rec)

    # -------------------------------------------------------------------------
    # Scenario 4: CLASS-04-D — Camera Headcount Discrepancy (RULE_WEBCAM_DISCREPANCY)
    # -------------------------------------------------------------------------
    enrollment_4 = 30
    for day_idx in range(num_days):
        sdate = (base_date + timedelta(days=day_idx)).isoformat()
        present = 28
        absent = enrollment_4 - present
        sid = _deterministic_uuid(rng)
        if day_idx == 6:
            # Day 7: Camera estimates 19 students (diff = 9 >= 5, 32.1% >= 20%)
            cam_status = "SUCCESS"
            cam_count = 19
        elif day_idx == 10:
            cam_status = "CAMERA_UNAVAILABLE"
            cam_count = None
        else:
            cam_status = "SUCCESS"
            cam_count = present
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-04-D",
            session_date=sdate,
            expected_enrollment=enrollment_4,
            present_count=present,
            absent_count=absent,
            webcam_status=cam_status,
            webcam_count=cam_count,
            record_source="SYNTHETIC",
            created_at=f"{sdate}T09:00:00Z",
        )
        all_sessions.append(rec)

    # -------------------------------------------------------------------------
    # Scenario 5: CLASS-05-E — Multi-Cohort Compound Mixture
    # -------------------------------------------------------------------------
    enrollment_5 = 35
    for day_idx in range(num_days):
        sdate = (base_date + timedelta(days=day_idx)).isoformat()
        if day_idx == 5:
            present = 14  # Attendance drop
        elif 8 <= day_idx <= 11:
            present = 26  # Repeated run
        else:
            present = 30 + rng.randint(0, 3)
        absent = enrollment_5 - present
        sid = _deterministic_uuid(rng)
        rec = SessionRecord(
            session_id=sid,
            class_id="CLASS-05-E",
            session_date=sdate,
            expected_enrollment=enrollment_5,
            present_count=present,
            absent_count=absent,
            webcam_status="SUCCESS",
            webcam_count=present,
            record_source="SYNTHETIC",
            created_at=f"{sdate}T09:00:00Z",
        )
        all_sessions.append(rec)

    # Validate all sessions before database operations
    for s in all_sessions:
        v_res = validate_session_dict(asdict(s))
        if not v_res.is_valid:
            raise ValueError(f"Internal Demo Generator Error on session {s.session_id}: {v_res.errors}")

    # Persist sessions into the dedicated demonstration repository
    repo = AttendanceRepository(db_path=target)
    alerts: list[Alert] = []
    try:
        repo.save_sessions(all_sessions)

        if run_detection:
            from attendsure.services.attendance_service import run_full_detection_pipeline
            alerts = run_full_detection_pipeline(repo)
    finally:
        repo.close()

    alerts_by_rule: dict[str, int] = {}
    alerts_by_status: dict[str, int] = {}
    for a in alerts:
        alerts_by_rule[a.rule_id] = alerts_by_rule.get(a.rule_id, 0) + 1
        alerts_by_status[a.review_status] = alerts_by_status.get(a.review_status, 0) + 1

    return {
        "status": "success",
        "database_path": str(target),
        "random_seed": random_seed,
        "total_sessions": len(all_sessions),
        "cohorts": ["CLASS-01-A", "CLASS-02-B", "CLASS-03-C", "CLASS-04-D", "CLASS-05-E"],
        "total_alerts": len(alerts),
        "alerts_by_rule": alerts_by_rule,
        "alerts_by_status": alerts_by_status,
        "scenarios": [
            "CLASS-01-A: Nominal Baseline Attendance (12 sessions, natural variance, 0 alerts)",
            "CLASS-02-B: Unusual Attendance Drop (12 sessions, steep drop on Day 6, triggers RULE_ATTENDANCE_DROP)",
            "CLASS-03-C: Repeated Headcount (12 sessions, 4 identical sessions on Days 5-8, triggers RULE_REPEATED_HEADCOUNT)",
            "CLASS-04-D: Camera Headcount Discrepancy (12 sessions, simulated delta=9 on Day 7, triggers RULE_WEBCAM_DISCREPANCY)",
            "CLASS-05-E: Multi-Cohort Compound Mixture (12 sessions, compound drops and repeated patterns)",
        ],
    }


def main() -> None:
    """CLI entrypoint for safely preparing an AttendSure demonstration database."""
    parser = argparse.ArgumentParser(
        description="Safely generate an isolated AttendSure SQLite demonstration database with pre-packaged scenarios."
    )
    parser.add_argument(
        "--dest",
        type=str,
        required=True,
        help="Destination path for demonstration database (e.g., 'data/demo_showcase.db'). Must not be operational DB.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic integer random seed for reproducible scenario generation (default: 42).",
    )
    parser.add_argument(
        "--no-detection",
        action="store_true",
        help="Skip automatic detection scan after seeding (sessions will be persisted without alerts).",
    )

    args = parser.parse_args()

    try:
        summary = prepare_demo_database(
            dest_path=args.dest,
            random_seed=args.seed,
            run_detection=not args.no_detection,
        )
        print("=" * 68)
        print(" AttendSure Demonstration Database Ready")
        print("=" * 68)
        print(f" Database Path  : {summary['database_path']}")
        print(f" Random Seed    : {summary['random_seed']}")
        print(f" Total Sessions : {summary['total_sessions']}")
        print(f" Cohorts Seeded : {', '.join(summary['cohorts'])}")
        print(f" Generated Alerts: {summary['total_alerts']}")
        for rule, count in summary["alerts_by_rule"].items():
            print(f"   • {rule}: {count} signal(s)")
        print("\nScenarios Included:")
        for sc in summary["scenarios"]:
            print(f"   • {sc}")
        print("=" * 68)
        print(" To launch AttendSure with this demonstration database, run:")
        print(f"   Windows PowerShell : $env:ATTENDSURE_DB_PATH=\"{summary['database_path']}\"; python -m streamlit run src/attendsure/ui/app.py")
        print(f"   Bash / macOS / Linux: ATTENDSURE_DB_PATH=\"{summary['database_path']}\" python -m streamlit run src/attendsure/ui/app.py")
        print("=" * 68)
    except Exception as exc:
        print(f"Error preparing demonstration database: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
