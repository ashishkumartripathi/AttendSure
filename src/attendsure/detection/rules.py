"""Rule-based anomaly detection engines for AttendSure.

Implements explainable attendance integrity detection rules following
docs/data-contract.md.
"""

from datetime import datetime, timezone
import hashlib
import statistics
from typing import Optional
import uuid

import pandas as pd

from attendsure.data.models import Alert
from attendsure.data.validation import validate_session_dataframe

RULE_ATTENDANCE_DROP = "RULE_ATTENDANCE_DROP"
RULE_ATTENDANCE_DROP_TITLE = "Attendance Drop — Manual Verification Recommended"
DEFAULT_DROP_THRESHOLD_PCT = 30.0
DEFAULT_BASELINE_WINDOW = 5

RULE_REPEATED_HEADCOUNT = "RULE_REPEATED_HEADCOUNT"
RULE_REPEATED_HEADCOUNT_TITLE = "Repeated Identical Headcounts"
DEFAULT_REPEATED_THRESHOLD = 4
PERFECT_ATTENDANCE_REPEATED_THRESHOLD = 6

RULE_WEBCAM_DISCREPANCY = "RULE_WEBCAM_DISCREPANCY"
RULE_WEBCAM_DISCREPANCY_TITLE = "Visible-Person Discrepancy"
DEFAULT_WEBCAM_ABS_THRESHOLD = 5
DEFAULT_WEBCAM_REL_THRESHOLD_PCT = 20.0


def generate_alert_id(session_id: str, rule_id: str) -> str:
    """Generate a deterministic, collision-resistant UUIDv4 alert ID for a (session_id, rule_id) pair.

    Satisfies docs/data-contract.md Section 4.1 format:
    '^ALT-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'.
    Guarantees that:
    1. The same session and rule deterministically produce the same alert ID across runs.
    2. Different rules triggering on the same session produce distinct alert IDs, preventing
       primary key collisions in SQLite storage.
    3. Different sessions produce distinct alert IDs.
    """
    raw_hash = hashlib.sha256(f"{session_id}:{rule_id}".encode("utf-8")).digest()[:16]
    b = bytearray(raw_hash)
    # RFC 4122 Section 4.4: Set version to 4 (0100)
    b[6] = (b[6] & 0x0F) | 0x40
    # RFC 4122 Section 4.1.1: Set variant to 10xx (RFC 4122)
    b[8] = (b[8] & 0x3F) | 0x80
    u = uuid.UUID(bytes=bytes(b))
    return f"ALT-{u}"


def detect_attendance_drop(
    sessions_df: pd.DataFrame,
    *,
    relative_decline_threshold_pct: float = DEFAULT_DROP_THRESHOLD_PCT,
    window_sessions: int = DEFAULT_BASELINE_WINDOW,
    alert_created_at: Optional[str] = None,
) -> list[Alert]:
    """Detect unusual attendance drops using a rolling historical median baseline.

    Implements RULE_ATTENDANCE_DROP per docs/data-contract.md Section 5.1:
    - Excludes invalid records via contract validation.
    - Analyzes sessions chronologically, independently for each class_id.
    - Requires at least window_sessions (default 5) valid prior sessions.
    - Calculates baseline_rate = median(rates_{t-5} .. rates_{t-1}), strictly
      excluding the current session (self-exclusion).
    - If baseline_rate == 0.0, skips relative decline calculation to guard
      against division by zero; no alert is generated.
    - Calculates relative percentage decline:
        (baseline_rate - current_rate) / baseline_rate * 100
    - Triggers if and only if relative_decline >= relative_decline_threshold_pct
      (default 30.0%). Stable or improved attendance never triggers.
    - Produces contract-compliant, non-accusatory Alert objects.

    Args:
        sessions_df: DataFrame of attendance session records.
        relative_decline_threshold_pct: Relative decline percentage trigger threshold.
        window_sessions: Number of immediately preceding valid sessions for baseline.
        alert_created_at: Optional fixed ISO 8601 UTC timestamp for created_at.

    Returns:
        List of Alert objects sorted by session_date and class_id.
    """
    if not isinstance(sessions_df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(sessions_df).__name__}.")

    if sessions_df.empty:
        return []

    # Filter records through contract validation; invalid records must never be treated as valid history
    valid_df, _ = validate_session_dataframe(sessions_df)
    if valid_df.empty:
        return []

    alerts: list[Alert] = []

    # Process each class cohort independently to prevent historical cross-contamination
    for class_id, class_group in valid_df.groupby("class_id"):
        # Sort chronologically by session_date (YYYY-MM-DD string sort is strictly chronological)
        sorted_records = class_group.sort_values(by="session_date", ascending=True).to_dict(orient="records")

        # Rolling history of valid sessions for this cohort: list of (record_dict, attendance_rate_pct)
        cohort_history: list[tuple[dict, float]] = []

        for record in sorted_records:
            expected_enrollment = int(record["expected_enrollment"])
            present_count = int(record["present_count"])
            session_date = str(record["session_date"])
            session_id = str(record["session_id"])

            current_rate = (present_count / expected_enrollment) * 100.0

            # Only evaluate if at least window_sessions prior valid sessions are available
            if len(cohort_history) >= window_sessions:
                # 5 immediately preceding sessions strictly prior to the current session (self-excluded)
                recent_window = cohort_history[-window_sessions:]
                recent_rates = [rate for _, rate in recent_window]

                baseline_rate = float(statistics.median(recent_rates))

                # Division by zero guard: if baseline is 0.0, skip relative decline calculation
                if baseline_rate > 0.0:
                    relative_decline = ((baseline_rate - current_rate) / baseline_rate) * 100.0

                    # Trigger condition: relative decline >= threshold
                    # Rounding to 9 decimal places prevents floating-point imprecision on exact boundary
                    if round(relative_decline, 9) >= relative_decline_threshold_pct:
                        created_timestamp = (
                            alert_created_at
                            if alert_created_at is not None
                            else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        )

                        number_words = {
                            1: "one",
                            2: "two",
                            3: "three",
                            4: "four",
                            5: "five",
                            6: "six",
                            7: "seven",
                            8: "eight",
                            9: "nine",
                            10: "ten",
                        }
                        window_str = number_words.get(window_sessions, str(window_sessions))

                        explanation = (
                            f"Class {class_id} recorded {present_count} of {expected_enrollment} students present "
                            f"({current_rate:.1f}%) on {session_date}. This is a {relative_decline:.1f}% decline "
                            f"from the {window_str}-session rolling baseline of {baseline_rate:.1f}%. "
                            "Please verify the attendance register and check possible explanations, including "
                            "weather, transport disruption, local health conditions, or a data-entry error. "
                            "This signal does not establish misconduct."
                        )

                        alert = Alert(
                            alert_id=generate_alert_id(session_id, RULE_ATTENDANCE_DROP),
                            session_id=session_id,
                            class_id=str(class_id),
                            session_date=session_date,
                            rule_id=RULE_ATTENDANCE_DROP,
                            rule_title=RULE_ATTENDANCE_DROP_TITLE,
                            priority="REVIEW_REQUIRED",
                            observed_value={
                                "present_count": present_count,
                                "expected_enrollment": expected_enrollment,
                                "attendance_rate_pct": round(current_rate, 2),
                            },
                            baseline_reference={
                                "baseline_type": "rolling_median",
                                "window_sessions": window_sessions,
                                "baseline_rate_pct": round(baseline_rate, 2),
                            },
                            threshold_applied={
                                "relative_decline_threshold_pct": float(relative_decline_threshold_pct),
                                "observed_relative_decline_pct": round(relative_decline, 2),
                            },
                            explanation=explanation,
                            review_status="PENDING_REVIEW",
                            created_at=created_timestamp,
                        )
                        alerts.append(alert)

            # Append current valid session to history for subsequent sessions
            cohort_history.append((record, current_rate))

    # Sort alerts chronologically by session_date, then class_id
    alerts.sort(key=lambda a: (a.session_date, a.class_id))
    return alerts


def detect_repeated_headcount(
    sessions_df: pd.DataFrame,
    *,
    standard_threshold: int = DEFAULT_REPEATED_THRESHOLD,
    perfect_attendance_threshold: int = PERFECT_ATTENDANCE_REPEATED_THRESHOLD,
    alert_created_at: Optional[str] = None,
) -> list[Alert]:
    """Detect repeated identical headcounts across consecutive sessions.

    Implements RULE_REPEATED_HEADCOUNT per docs/data-contract.md Section 5.2 and Decision D11:
    - Excludes invalid records via contract validation.
    - Processes each class_id independently in ascending chronological order.
    - Tracks consecutive sessions with identical present_count.
    - Changes in expected_enrollment do NOT reset the sequence (Decision D11).
    - Standard threshold is K >= 4 consecutive sessions with identical present_count.
    - 100% attendance exception: if and only if EVERY session in the current
      sequence has present_count == expected_enrollment, requires K >= 6.
    - If any session in the sequence has present_count < expected_enrollment,
      the standard K >= 4 threshold applies.
    - Generates contract-compliant, non-accusatory Alert objects.

    Args:
        sessions_df: DataFrame of attendance session records.
        standard_threshold: Threshold for sequences with < 100% attendance (default 4).
        perfect_attendance_threshold: Threshold for sequences where every session
            has 100% attendance (default 6).
        alert_created_at: Optional fixed ISO 8601 UTC timestamp for created_at.

    Returns:
        List of Alert objects sorted by session_date and class_id.
    """
    if not isinstance(sessions_df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(sessions_df).__name__}.")

    if sessions_df.empty:
        return []

    valid_df, _ = validate_session_dataframe(sessions_df)
    if valid_df.empty:
        return []

    alerts: list[Alert] = []

    for class_id, class_group in valid_df.groupby("class_id"):
        sorted_records = class_group.sort_values(by="session_date", ascending=True).to_dict(orient="records")

        current_run: list[dict] = []

        for record in sorted_records:
            present_count = int(record["present_count"])
            session_id = str(record["session_id"])
            session_date = str(record["session_date"])

            if not current_run:
                current_run.append(record)
            else:
                prev_present = int(current_run[-1]["present_count"])
                if present_count == prev_present:
                    # Roster/enrollment shifts do NOT reset the sequence
                    current_run.append(record)
                else:
                    # Headcount changed -> reset sequence to start with this record
                    current_run = [record]

            # Current sequence run length up to and including this session
            K = len(current_run)

            # Check if every session in the sequence is 100% attendance
            is_100_pct_run = all(
                int(r["present_count"]) == int(r["expected_enrollment"])
                for r in current_run
            )

            # Applicable threshold per Decision D11
            threshold = perfect_attendance_threshold if is_100_pct_run else standard_threshold

            if K >= threshold:
                start_date = str(current_run[0]["session_date"])
                end_date = session_date

                created_timestamp = (
                    alert_created_at
                    if alert_created_at is not None
                    else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                )

                explanation = (
                    f"Class {class_id} recorded an identical headcount of {present_count} students "
                    f"across {K} consecutive sessions from {start_date} to {end_date}. "
                    "This pattern warrants human confirmation to ensure daily roll-call verification is active."
                )

                alert = Alert(
                    alert_id=generate_alert_id(session_id, RULE_REPEATED_HEADCOUNT),
                    session_id=session_id,
                    class_id=str(class_id),
                    session_date=session_date,
                    rule_id=RULE_REPEATED_HEADCOUNT,
                    rule_title=RULE_REPEATED_HEADCOUNT_TITLE,
                    priority="REVIEW_REQUIRED",
                    observed_value={
                        "repeated_headcount": present_count,
                        "consecutive_sessions": K,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    baseline_reference={
                        "baseline_type": "historical_variation",
                        "expected_behavior": "daily_headcount_variation",
                    },
                    threshold_applied={
                        "consecutive_sessions_threshold": threshold,
                        "observed_consecutive_sessions": K,
                        "is_100_pct_attendance_run": is_100_pct_run,
                    },
                    explanation=explanation,
                    review_status="PENDING_REVIEW",
                    created_at=created_timestamp,
                )
                alerts.append(alert)

    alerts.sort(key=lambda a: (a.session_date, a.class_id))
    return alerts


def detect_webcam_discrepancy(
    sessions_df: pd.DataFrame,
    *,
    absolute_threshold: int = DEFAULT_WEBCAM_ABS_THRESHOLD,
    relative_threshold_pct: float = DEFAULT_WEBCAM_REL_THRESHOLD_PCT,
    alert_created_at: Optional[str] = None,
) -> list[Alert]:
    """Detect discrepancies between manual attendance headcounts and visible-person camera counts.

    Implements RULE_WEBCAM_DISCREPANCY per docs/data-contract.md Section 5.3 and Decision D10:
    - Excludes invalid records via contract validation.
    - Evaluates only sessions where webcam_status == "SUCCESS" and webcam_count is not None.
    - If webcam capture was not attempted, unavailable, or failed, skips without alert.
    - For present_count > 0:
        absolute_difference = abs(webcam_count - present_count)
        relative_difference_pct = (absolute_difference / present_count) * 100
        Triggers if and only if BOTH absolute_difference >= absolute_threshold (default 5)
        AND relative_difference_pct >= relative_threshold_pct (default 20.0%).
    - For present_count == 0:
        Do not divide by zero; relative difference is undefined.
        Triggers if and only if absolute_difference >= absolute_threshold (default 5).
    - Produces contract-compliant, non-accusatory Alert objects.
    - Never alters manual attendance records or treats webcam counts as verified identity.

    Args:
        sessions_df: DataFrame of attendance session records.
        absolute_threshold: Minimum absolute difference to trigger alert (default 5).
        relative_threshold_pct: Minimum relative difference percentage for positive manual
            headcounts (default 20.0%).
        alert_created_at: Optional fixed ISO 8601 UTC timestamp for created_at.

    Returns:
        List of Alert objects sorted by session_date and class_id.
    """
    if not isinstance(sessions_df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(sessions_df).__name__}.")

    if sessions_df.empty:
        return []

    valid_df, _ = validate_session_dataframe(sessions_df)
    if valid_df.empty:
        return []

    alerts: list[Alert] = []

    for record in valid_df.to_dict(orient="records"):
        # Execution Guard: Evaluated only when webcam_status == "SUCCESS" and webcam_count is valid
        if record.get("webcam_status") != "SUCCESS":
            continue

        webcam_count_raw = record.get("webcam_count")
        if webcam_count_raw is None or pd.isna(webcam_count_raw):
            continue

        present_count = int(record["present_count"])
        webcam_count = int(webcam_count_raw)
        session_id = str(record["session_id"])
        class_id = str(record["class_id"])
        session_date = str(record["session_date"])

        abs_diff = abs(webcam_count - present_count)

        if present_count > 0:
            rel_diff = (abs_diff / present_count) * 100.0
            is_anomaly = (abs_diff >= absolute_threshold) and (rel_diff >= relative_threshold_pct)
            rel_diff_str = f"{rel_diff:.1f}% relative difference"
        else:
            rel_diff = None
            is_anomaly = (abs_diff >= absolute_threshold)
            rel_diff_str = "relative difference undefined"

        if is_anomaly:
            created_timestamp = (
                alert_created_at
                if alert_created_at is not None
                else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            explanation = (
                f"On {session_date}, manual roll call logged {present_count} students present, "
                f"while the camera module estimated {webcam_count} visible individuals "
                f"(difference of {abs_diff} people, {rel_diff_str}). "
                "Discrepancies may arise naturally from camera placement, physical occlusion, "
                "or students outside the camera's view."
            )

            alert = Alert(
                alert_id=generate_alert_id(session_id, RULE_WEBCAM_DISCREPANCY),
                session_id=session_id,
                class_id=class_id,
                session_date=session_date,
                rule_id=RULE_WEBCAM_DISCREPANCY,
                rule_title=RULE_WEBCAM_DISCREPANCY_TITLE,
                priority="REVIEW_REQUIRED",
                observed_value={
                    "present_count": present_count,
                    "webcam_count": webcam_count,
                    "absolute_difference": abs_diff,
                    "relative_difference_pct": round(rel_diff, 2) if rel_diff is not None else None,
                },
                baseline_reference={
                    "baseline_type": "manual_roll_call",
                    "reference_count": present_count,
                },
                threshold_applied={
                    "absolute_difference_threshold": absolute_threshold,
                    "relative_difference_threshold_pct": relative_threshold_pct,
                    "observed_absolute_difference": abs_diff,
                    "observed_relative_difference_pct": round(rel_diff, 2) if rel_diff is not None else None,
                    "zero_attendance_evaluation": (present_count == 0),
                },
                explanation=explanation,
                review_status="PENDING_REVIEW",
                created_at=created_timestamp,
            )
            alerts.append(alert)

    alerts.sort(key=lambda a: (a.session_date, a.class_id))
    return alerts


def detect_anomalies(
    sessions_df: pd.DataFrame,
    active_rules: Optional[list[str]] = None,
    *,
    alert_created_at: Optional[str] = None,
) -> list[Alert]:
    """Runs configured rule-based detectors across validated session records.

    Satisfies docs/data-contract.md Section 7 module interface.

    Args:
        sessions_df: DataFrame of session records to evaluate.
        active_rules: Optional list of rule IDs to execute. If None, all implemented
            rules are executed.
        alert_created_at: Optional fixed UTC timestamp for alert creation.

    Returns:
        List of explainable Alert objects sorted chronologically.
    """
    alerts: list[Alert] = []

    if active_rules is None or RULE_ATTENDANCE_DROP in active_rules:
        alerts.extend(detect_attendance_drop(sessions_df, alert_created_at=alert_created_at))

    if active_rules is None or RULE_REPEATED_HEADCOUNT in active_rules:
        alerts.extend(detect_repeated_headcount(sessions_df, alert_created_at=alert_created_at))

    if active_rules is None or RULE_WEBCAM_DISCREPANCY in active_rules:
        alerts.extend(detect_webcam_discrepancy(sessions_df, alert_created_at=alert_created_at))

    alerts.sort(key=lambda a: (a.session_date, a.class_id, a.rule_id))
    return alerts
