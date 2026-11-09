"""Synthetic attendance data generator for AttendSure.

Implements deterministic synthetic session generation and scenario creation
conforming to docs/data-contract.md.
"""

from datetime import datetime, timedelta, timezone
import random
import re
from typing import Any, Literal, Optional
import uuid

import pandas as pd

from attendsure.data.models import RecordSource, WebcamStatus

# Allowed ground-truth anomaly type literals matching contract section 6.1
GroundTruthAnomalyType = Literal[
    "NONE",
    "ATTENDANCE_DROP",
    "REPEATED_HEADCOUNT",
    "WEBCAM_DISCREPANCY",
    "COMPOUND",
]

SESSION_COLUMNS = [
    "session_id",
    "class_id",
    "session_date",
    "expected_enrollment",
    "present_count",
    "absent_count",
    "webcam_status",
    "webcam_count",
    "record_source",
    "created_at",
]

GROUND_TRUTH_COLUMNS = [
    "ground_truth_is_anomaly",
    "ground_truth_anomaly_type",
    "ground_truth_notes",
]

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLASS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,32}$")


def _deterministic_uuid(rng: random.Random) -> str:
    """Generate a valid RFC 4122 UUIDv4 string deterministically using a local RNG."""
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _resolve_start_date(start_date: Optional[str], num_days: int) -> datetime.date:
    """Resolve and validate the start date to guarantee no generated date is in the future."""
    today = max(datetime.now(timezone.utc).date(), datetime.now().date())

    if start_date is None:
        # Default to a safe past window ending before today
        return today - timedelta(days=num_days + 5)

    if not isinstance(start_date, str) or not DATE_PATTERN.match(start_date):
        raise ValueError(f"Invalid start_date '{start_date}'. Must be YYYY-MM-DD format.")

    try:
        parsed = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date '{start_date}'.") from exc

    end_date = parsed + timedelta(days=max(0, num_days - 1))
    if end_date > today:
        raise ValueError(
            f"Generated sessions from start_date '{start_date}' for {num_days} days "
            f"would end on '{end_date}', which is in the future relative to system date '{today}'."
        )

    return parsed


def _sample_nominal_present(
    rng: random.Random,
    enrollment: int,
    nominal_base: int,
    prior_counts: list[int],
    max_identical_consecutive: int = 3,
) -> int:
    """Sample a nominal present count with natural slight variation (+/- 1 to 2 students).

    Guarantees that nominal baseline variation does not inadvertently produce
    a streak of >= 4 identical counts (which under the data contract constitutes
    an unflagged repeated-headcount anomaly).
    """
    delta = rng.choice([-1, 0, 1]) if enrollment > 3 else 0
    present = max(0, min(enrollment, nominal_base + delta))

    if len(prior_counts) >= max_identical_consecutive:
        if all(p == present for p in prior_counts[-max_identical_consecutive:]):
            # Candidate count would form an accidental streak of >= 4 identical values.
            # Select an alternative delta from nominal range to break the streak.
            alt_candidates = [-2, -1, 1, 2] if enrollment > 5 else ([-1, 1] if enrollment > 3 else [0])
            for alt_delta in alt_candidates:
                candidate = max(0, min(enrollment, nominal_base + alt_delta))
                if candidate != present:
                    return candidate
    return present


def generate_scenario_sessions(
    scenario_type: Literal["NOMINAL", "NORMAL", "ATTENDANCE_DROP", "REPEATED_HEADCOUNT", "WEBCAM_DISCREPANCY"],
    class_id: str = "CLASS-01-A",
    num_days: int = 15,
    expected_enrollment: int = 30,
    start_date: Optional[str] = None,
    random_seed: int = 42,
    include_labels: bool = True,
) -> pd.DataFrame:
    """Generates an exact, deterministic single-cohort scenario for testing and demonstration.

    Supported Scenarios:
    - NOMINAL / NORMAL: Natural, benign attendance variation (85%-95% present).
    - ATTENDANCE_DROP: 5 baseline sessions followed by a steep drop on day 6.
    - REPEATED_HEADCOUNT: Identical manual present count repeated across 4 consecutive days.
    - WEBCAM_DISCREPANCY: Normal attendance with camera count differing by >= 5 and >= 20%.

    Args:
        scenario_type: The specific benchmark scenario to synthesize.
        class_id: Synthetic cohort identifier (must match ^[A-Za-z0-9_-]{2,32}$).
        num_days: Number of consecutive days (minimum 8 for anomaly scenarios).
        expected_enrollment: Total registered class size (must be >= 1).
        start_date: Optional YYYY-MM-DD start date (default: safe historical window).
        random_seed: Deterministic RNG seed.
        include_labels: Whether to include ground-truth evaluation columns.

    Returns:
        pd.DataFrame containing valid session records (and optional scenario labels).
    """
    valid_scenarios = {"NOMINAL", "NORMAL", "ATTENDANCE_DROP", "REPEATED_HEADCOUNT", "WEBCAM_DISCREPANCY"}
    if scenario_type not in valid_scenarios:
        raise ValueError(f"Invalid scenario_type '{scenario_type}'. Allowed: {sorted(valid_scenarios)}.")

    normalized_scenario = "NOMINAL" if scenario_type in ("NOMINAL", "NORMAL") else scenario_type

    if not isinstance(class_id, str) or not CLASS_ID_PATTERN.match(class_id):
        raise ValueError(f"Invalid class_id '{class_id}'. Must match contract pattern ^[A-Za-z0-9_-]{{2,32}}.")

    if isinstance(num_days, bool) or not isinstance(num_days, int) or num_days < 1:
        raise ValueError(f"num_days must be an integer >= 1, got {num_days!r}.")

    if isinstance(expected_enrollment, bool) or not isinstance(expected_enrollment, int) or expected_enrollment < 1:
        raise ValueError(f"expected_enrollment must be an integer >= 1, got {expected_enrollment!r}.")

    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise ValueError(f"random_seed must be an integer, got {random_seed!r}.")

    if normalized_scenario in {"ATTENDANCE_DROP", "REPEATED_HEADCOUNT", "WEBCAM_DISCREPANCY"} and num_days < 8:
        raise ValueError(f"scenario_type '{scenario_type}' requires num_days >= 8 to establish baseline.")

    if normalized_scenario == "WEBCAM_DISCREPANCY" and expected_enrollment < 10:
        raise ValueError(
            f"scenario_type 'WEBCAM_DISCREPANCY' requires expected_enrollment >= 10 to satisfy abs_diff >= 5 threshold, got {expected_enrollment}."
        )

    rng = random.Random(random_seed)
    base_date = _resolve_start_date(start_date, num_days)

    records: list[dict[str, Any]] = []

    # Nominal attendance target (around 85%-95%)
    nominal_present_base = max(1, int(expected_enrollment * 0.90))

    # Pre-determine repeated headcount for REPEATED_HEADCOUNT scenario
    repeated_count = max(1, expected_enrollment - 5)  # non-100% to test K >= 4 rule

    for day_idx in range(num_days):
        session_date_str = (base_date + timedelta(days=day_idx)).isoformat()
        session_id = _deterministic_uuid(rng)
        created_at = f"{session_date_str}T09:00:00Z"

        is_anomaly = False
        anomaly_type: GroundTruthAnomalyType = "NONE"
        notes = "Nominal attendance session"

        webcam_status: WebcamStatus = "NOT_ATTEMPTED"
        webcam_count: Optional[int] = None

        prior_counts = [r["present_count"] for r in records]

        if normalized_scenario == "NOMINAL":
            # Natural small variation: +/- 1-2 students, streak < 4
            present = _sample_nominal_present(rng, expected_enrollment, nominal_present_base, prior_counts)

        elif normalized_scenario == "ATTENDANCE_DROP":
            if day_idx < 5:
                # 5 nominal baseline sessions (~90%)
                present = _sample_nominal_present(rng, expected_enrollment, nominal_present_base, prior_counts)
            elif day_idx == 5:
                # Injected sharp drop on day 6 (index 5): drops to ~35% of enrollment (relative drop > 50%)
                present = max(1, int(expected_enrollment * 0.35))
                is_anomaly = True
                anomaly_type = "ATTENDANCE_DROP"
                notes = f"Injected sharp attendance drop on day {day_idx + 1} ({present}/{expected_enrollment})"
            else:
                # Post-drop recovery or continuing nominal
                present = _sample_nominal_present(rng, expected_enrollment, nominal_present_base, prior_counts)

        elif normalized_scenario == "REPEATED_HEADCOUNT":
            if day_idx in (4, 5, 6, 7):
                # 4 consecutive days (days 5, 6, 7, 8) with exact same count
                present = repeated_count
                is_anomaly = True
                anomaly_type = "REPEATED_HEADCOUNT"
                notes = (
                    f"Injected repeated headcount run of {repeated_count} students "
                    f"across 4 consecutive sessions (day {day_idx + 1})"
                )
            else:
                delta = rng.choice([-2, -1, 1, 2]) if expected_enrollment > 5 else 0
                present = max(0, min(expected_enrollment, nominal_present_base + delta))
                # Prevent accidental collision with repeated_count
                if present == repeated_count:
                    present = max(0, min(expected_enrollment, present - 1))

        elif normalized_scenario == "WEBCAM_DISCREPANCY":
            present = _sample_nominal_present(rng, expected_enrollment, nominal_present_base, prior_counts)
            webcam_status = "SUCCESS"

            if day_idx == 5:
                # Discrepancy: camera detects significantly fewer people (gap >= 5 and >= 20%)
                webcam_count = max(0, present - 8)
                is_anomaly = True
                anomaly_type = "WEBCAM_DISCREPANCY"
                notes = (
                    f"Injected webcam discrepancy on day {day_idx + 1}: "
                    f"manual {present} vs camera {webcam_count}"
                )
            else:
                # Normal minor tracking noise (+/- 1)
                cam_delta = rng.choice([-1, 0, 1])
                webcam_count = max(0, min(expected_enrollment, present + cam_delta))

        absent = expected_enrollment - present

        record = {
            "session_id": session_id,
            "class_id": class_id,
            "session_date": session_date_str,
            "expected_enrollment": expected_enrollment,
            "present_count": present,
            "absent_count": absent,
            "webcam_status": webcam_status,
            "webcam_count": webcam_count,
            "record_source": "SYNTHETIC",
            "created_at": created_at,
        }

        if include_labels:
            record["ground_truth_is_anomaly"] = is_anomaly
            record["ground_truth_anomaly_type"] = anomaly_type
            record["ground_truth_notes"] = notes

        records.append(record)

    cols = SESSION_COLUMNS + (GROUND_TRUTH_COLUMNS if include_labels else [])
    df = pd.DataFrame(records, columns=cols)
    if "webcam_count" in df.columns:
        df["webcam_count"] = pd.Series(
            [int(r["webcam_count"]) if r["webcam_count"] is not None else None for r in records],
            dtype=object,
        )
    return df


def generate_synthetic_sessions(
    num_classes: int = 5,
    num_days: int = 30,
    anomaly_rate: float = 0.05,
    random_seed: int = 42,
    include_webcam: bool = False,
    start_date: Optional[str] = None,
    include_labels: bool = True,
    record_source: RecordSource = "SYNTHETIC",
) -> pd.DataFrame:
    """Generates synthetic session DataFrame containing labelled anomalies for evaluation.

    Satisfies the public interface defined in docs/data-contract.md Section 7.

    Args:
        num_classes: Number of distinct classroom cohorts to generate.
        num_days: Number of consecutive calendar dates per class.
        anomaly_rate: Targeted proportion of sessions containing injected anomalies (0.0 to 1.0).
        random_seed: Deterministic integer seed for reproducible data generation.
        include_webcam: Whether to simulate webcam person counting status and counts.
        start_date: Optional starting ISO date (YYYY-MM-DD). Defaults to safe historical window.
        include_labels: If True, includes evaluation ground-truth columns.
        record_source: Record source tag (default: 'SYNTHETIC').

    Returns:
        pd.DataFrame containing valid, chronologically ordered session records.
    """
    if isinstance(num_classes, bool) or not isinstance(num_classes, int) or num_classes < 0:
        raise ValueError(f"num_classes must be a non-negative integer, got {num_classes!r}.")
    if isinstance(num_days, bool) or not isinstance(num_days, int) or num_days < 0:
        raise ValueError(f"num_days must be a non-negative integer, got {num_days!r}.")
    if isinstance(anomaly_rate, bool) or not isinstance(anomaly_rate, (int, float)) or not (0.0 <= anomaly_rate <= 1.0):
        raise ValueError(f"anomaly_rate must be a float between 0.0 and 1.0, got {anomaly_rate!r}.")
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise ValueError(f"random_seed must be an integer, got {random_seed!r}.")
    if record_source not in ("SYNTHETIC", "MANUAL_ENTRY", "CSV_IMPORT"):
        raise ValueError(f"Invalid record_source '{record_source}'. Allowed: SYNTHETIC, MANUAL_ENTRY, CSV_IMPORT.")

    cols = SESSION_COLUMNS + (GROUND_TRUTH_COLUMNS if include_labels else [])
    if num_classes == 0 or num_days == 0:
        return pd.DataFrame(columns=cols)

    rng = random.Random(random_seed)
    base_date = _resolve_start_date(start_date, num_days)

    records: list[dict[str, Any]] = []

    # Generate synthetic classes with typical rural classroom sizes (25 to 40 students)
    class_configs = []
    for c_idx in range(1, num_classes + 1):
        class_id = f"CLASS-{c_idx:02d}-A"
        enrollment = 25 + rng.randint(0, 15)  # between 25 and 40 students
        class_configs.append((class_id, enrollment))

    for class_id, enrollment in class_configs:
        # State tracking for ongoing multi-day anomalies (e.g. repeated headcounts)
        repeated_headcount_remaining = 0
        repeated_headcount_value = 0
        nominal_base = max(1, int(enrollment * 0.90))
        class_prior_counts: list[int] = []

        for day_idx in range(num_days):
            session_date_str = (base_date + timedelta(days=day_idx)).isoformat()
            session_id = _deterministic_uuid(rng)
            created_at = f"{session_date_str}T09:00:00Z"

            is_anomaly = False
            anomaly_type: GroundTruthAnomalyType = "NONE"
            notes = "Nominal attendance session"

            webcam_status: WebcamStatus = "NOT_ATTEMPTED"
            webcam_count: Optional[int] = None

            # Handle ongoing multi-day repeated headcount
            if repeated_headcount_remaining > 0:
                present = repeated_headcount_value
                repeated_headcount_remaining -= 1
                is_anomaly = True
                anomaly_type = "REPEATED_HEADCOUNT"
                notes = f"Injected repeated headcount run of {repeated_headcount_value} students"
            else:
                # Determine whether to trigger a new anomaly (only allowed after day 5 for baseline)
                trigger_anomaly = (
                    day_idx >= 5
                    and anomaly_rate > 0.0
                    and rng.random() < anomaly_rate
                )

                if trigger_anomaly:
                    # Select anomaly type based on webcam inclusion
                    candidates = ["ATTENDANCE_DROP", "REPEATED_HEADCOUNT"]
                    if include_webcam:
                        candidates.append("WEBCAM_DISCREPANCY")
                    selected_type = rng.choice(candidates)

                    if selected_type == "ATTENDANCE_DROP":
                        # Sharp decline to 30%-40% attendance
                        present = max(1, int(enrollment * rng.uniform(0.30, 0.40)))
                        is_anomaly = True
                        anomaly_type = "ATTENDANCE_DROP"
                        notes = f"Injected attendance drop to {present}/{enrollment} on {session_date_str}"

                    elif selected_type == "REPEATED_HEADCOUNT":
                        # Begin 4 consecutive sessions of identical count (< 100%)
                        repeated_headcount_value = max(1, enrollment - rng.randint(3, 7))
                        present = repeated_headcount_value
                        repeated_headcount_remaining = 3  # 3 additional consecutive days
                        is_anomaly = True
                        anomaly_type = "REPEATED_HEADCOUNT"
                        notes = f"Injected repeated headcount run of {repeated_headcount_value} students"

                    elif selected_type == "WEBCAM_DISCREPANCY":
                        present = _sample_nominal_present(rng, enrollment, nominal_base, class_prior_counts)
                        webcam_status = "SUCCESS"
                        # Gap of at least 6 students and >= 20%
                        webcam_count = max(0, present - rng.randint(6, 10))
                        is_anomaly = True
                        anomaly_type = "WEBCAM_DISCREPANCY"
                        notes = f"Injected webcam discrepancy (manual {present} vs camera {webcam_count})"
                else:
                    # Nominal session: natural slight attendance variation (streak < 4)
                    present = _sample_nominal_present(rng, enrollment, nominal_base, class_prior_counts)

            # Populate webcam fields if requested and not already set by anomaly
            if include_webcam and webcam_status == "NOT_ATTEMPTED":
                # 95% of sessions camera works; 5% camera is offline
                if rng.random() < 0.95:
                    webcam_status = "SUCCESS"
                    noise = rng.choice([-1, 0, 1])
                    webcam_count = max(0, min(enrollment, present + noise))
                else:
                    webcam_status = "CAMERA_UNAVAILABLE"
                    webcam_count = None

            absent = enrollment - present

            record = {
                "session_id": session_id,
                "class_id": class_id,
                "session_date": session_date_str,
                "expected_enrollment": enrollment,
                "present_count": present,
                "absent_count": absent,
                "webcam_status": webcam_status,
                "webcam_count": webcam_count,
                "record_source": record_source,
                "created_at": created_at,
            }

            if include_labels:
                record["ground_truth_is_anomaly"] = is_anomaly
                record["ground_truth_anomaly_type"] = anomaly_type
                record["ground_truth_notes"] = notes

            records.append(record)
            class_prior_counts.append(present)

    df = pd.DataFrame(records, columns=cols)
    if "webcam_count" in df.columns:
        df["webcam_count"] = pd.Series(
            [int(r["webcam_count"]) if r["webcam_count"] is not None else None for r in records],
            dtype=object,
        )
    return df
