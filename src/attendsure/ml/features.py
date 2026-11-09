"""Feature engineering for the Attendance Decision Tree Classifier.

Extracts non-leaking, causal time-series features from historical attendance records
to identify unusual attendance patterns and intervention signals.
"""

import statistics
from typing import Any, Optional
import pandas as pd

FEATURE_COLUMNS = [
    "attendance_rate",
    "absence_rate",
    "baseline_deviation",
    "recent_delta_1d",
    "repeated_count_streak",
    "relative_decline_pct",
]


def extract_session_features(
    sessions_df: pd.DataFrame,
    min_history: int = 3,
    baseline_window: int = 5,
) -> pd.DataFrame:
    """Extract causal, non-leaking ML features for all attendance sessions.

    For each session, features are computed using only information from that session
    and strictly preceding sessions for the same class_id (preventing data leakage).

    Features computed:
    1. attendance_rate: (present / expected) * 100
    2. absence_rate: (absent / expected) * 100
    3. baseline_deviation: baseline_median - attendance_rate (positive indicates below usual)
    4. recent_delta_1d: attendance_rate - previous_day_rate
    5. repeated_count_streak: run length of identical consecutive present counts
    6. relative_decline_pct: ((baseline - rate) / baseline) * 100 if baseline > 0 else 0

    Metadata columns preserved:
    - session_id, class_id, session_date, expected_enrollment, present_count, absent_count,
      is_insufficient_history (True if prior history < min_history)

    Args:
        sessions_df: DataFrame conforming to SessionRecord schema.
        min_history: Minimum number of prior sessions required for full baseline features.
        baseline_window: Number of immediately preceding valid sessions for baseline median.

    Returns:
        DataFrame containing FEATURE_COLUMNS and session metadata.
    """
    if sessions_df.empty:
        cols = ["session_id", "class_id", "session_date", "is_insufficient_history"] + FEATURE_COLUMNS
        return pd.DataFrame(columns=cols)

    records_out: list[dict[str, Any]] = []

    # Process each cohort independently in strict chronological order
    for class_id, class_group in sessions_df.groupby("class_id"):
        sorted_group = class_group.sort_values(by="session_date", ascending=True)

        history_rates: list[float] = []
        history_counts: list[int] = []

        for _, row in sorted_group.iterrows():
            enrollment = int(row["expected_enrollment"])
            present = int(row["present_count"])
            absent = int(row.get("absent_count", enrollment - present))
            rate = (present / enrollment) * 100.0 if enrollment > 0 else 0.0
            abs_rate = (absent / enrollment) * 100.0 if enrollment > 0 else 0.0

            history_len = len(history_rates)
            is_insufficient = history_len < min_history

            # 1. Baseline median of preceding window (self-excluded)
            if history_len > 0:
                window_slice = history_rates[-min(history_len, baseline_window):]
                baseline_median = float(statistics.median(window_slice))
                prev_rate = history_rates[-1]
                recent_delta = rate - prev_rate
            else:
                baseline_median = rate
                recent_delta = 0.0

            baseline_deviation = baseline_median - rate

            if baseline_median > 0.0 and rate < baseline_median:
                relative_decline = ((baseline_median - rate) / baseline_median) * 100.0
            else:
                relative_decline = 0.0

            # 2. Repeated present count streak
            streak = 1
            for past_count in reversed(history_counts):
                if past_count == present:
                    streak += 1
                else:
                    break

            feat_record = {
                "session_id": str(row["session_id"]),
                "class_id": str(class_id),
                "session_date": str(row["session_date"]),
                "expected_enrollment": enrollment,
                "present_count": present,
                "absent_count": absent,
                "is_insufficient_history": is_insufficient,
                "attendance_rate": round(rate, 2),
                "absence_rate": round(abs_rate, 2),
                "baseline_deviation": round(baseline_deviation, 2),
                "recent_delta_1d": round(recent_delta, 2),
                "repeated_count_streak": streak,
                "relative_decline_pct": round(relative_decline, 2),
            }

            # Preserve ground truth label if present in training data
            if "label" in row:
                feat_record["label"] = int(row["label"])
            elif "ground_truth_is_anomaly" in row:
                feat_record["label"] = int(bool(row["ground_truth_is_anomaly"]))

            records_out.append(feat_record)

            # Update rolling history
            history_rates.append(rate)
            history_counts.append(present)

    return pd.DataFrame(records_out)


def extract_features_for_session(
    class_id: str,
    enrollment: int,
    present: int,
    historical_sessions_df: pd.DataFrame,
    baseline_window: int = 5,
    min_history: int = 3,
) -> dict[str, Any]:
    """Extract feature dictionary for an individual candidate session before saving.

    Used by the interactive UI to evaluate ML predictions in real time.

    Args:
        class_id: Cohort identifier.
        enrollment: Expected total students.
        present: Present student count.
        historical_sessions_df: All existing saved sessions for this class_id.
        baseline_window: Window size for rolling median.
        min_history: Threshold for sufficient historical context.

    Returns:
        Dictionary containing FEATURE_COLUMNS, 'is_insufficient_history', and metadata.
    """
    if enrollment <= 0:
        return {
            "attendance_rate": 0.0,
            "absence_rate": 0.0,
            "baseline_deviation": 0.0,
            "recent_delta_1d": 0.0,
            "repeated_count_streak": 1,
            "relative_decline_pct": 0.0,
            "is_insufficient_history": True,
        }

    rate = (present / enrollment) * 100.0
    absent = enrollment - present
    abs_rate = (absent / enrollment) * 100.0

    cohort_history = historical_sessions_df[
        historical_sessions_df["class_id"] == class_id
    ].sort_values(by="session_date", ascending=True)

    history_len = len(cohort_history)
    is_insufficient = history_len < min_history

    if history_len > 0:
        recent_records = cohort_history.tail(min(history_len, baseline_window))
        recent_rates = [
            (int(r["present_count"]) / int(r["expected_enrollment"])) * 100.0
            for _, r in recent_records.iterrows()
            if int(r["expected_enrollment"]) > 0
        ]
        baseline_median = float(statistics.median(recent_rates)) if recent_rates else rate
        last_row = cohort_history.iloc[-1]
        last_rate = (
            (int(last_row["present_count"]) / int(last_row["expected_enrollment"])) * 100.0
            if int(last_row["expected_enrollment"]) > 0
            else rate
        )
        recent_delta = rate - last_rate

        # Streak calculation
        streak = 1
        for _, past_row in cohort_history.iloc[::-1].iterrows():
            if int(past_row["present_count"]) == present:
                streak += 1
            else:
                break
    else:
        baseline_median = rate
        recent_delta = 0.0
        streak = 1

    baseline_deviation = baseline_median - rate
    if baseline_median > 0.0 and rate < baseline_median:
        relative_decline = ((baseline_median - rate) / baseline_median) * 100.0
    else:
        relative_decline = 0.0

    return {
        "attendance_rate": round(rate, 2),
        "absence_rate": round(abs_rate, 2),
        "baseline_deviation": round(baseline_deviation, 2),
        "recent_delta_1d": round(recent_delta, 2),
        "repeated_count_streak": streak,
        "relative_decline_pct": round(relative_decline, 2),
        "is_insufficient_history": is_insufficient,
    }

