"""Evaluation metrics and benchmarking engine for AttendSure anomaly detectors.

Implements standard classification metrics (True Positives, False Positives,
True Negatives, False Negatives, Precision, Recall, F1-Score, and Confusion Matrix)
conforming to docs/data-contract.md Section 6.2.

Zero-Denominator Policy:
-----------------------
- Precision = TP / (TP + FP):
    If (TP + FP) == 0 (no positive predictions made), precision defaults to 0.0
    (or configured zero_division parameter) and zero_division_applied['precision'] is True.
- Recall = TP / (TP + FN):
    If (TP + FN) == 0 (no actual positive ground-truth cases exist), recall defaults to 0.0
    (or configured zero_division parameter) and zero_division_applied['recall'] is True.
- F1-Score = 2 * (Precision * Recall) / (Precision + Recall):
    If (Precision + Recall) == 0.0, F1 defaults to 0.0
    (or configured zero_division parameter) and zero_division_applied['f1_score'] is True.

Session-Level vs. Event-Level Evaluation Semantics:
---------------------------------------------------
AttendSure evaluates anomaly detection strictly at the SESSION LEVEL (per
docs/data-contract.md Section 6.2):
- Each session record (row) in labelled_sessions_df is evaluated as an individual
  binary classification sample.
- For multi-day temporal anomaly sequences (e.g., a repeated-headcount run of 4
  consecutive identical days), the synthetic generator labels all 4 sessions as
  anomalous (ground_truth_is_anomaly = True).
- The online detector (RULE_REPEATED_HEADCOUNT) processes records chronologically
  and fires an alert only when the sequence length meets or exceeds the trigger
  threshold (K >= 4). Consequently, the alert fires on Day 4 (the threshold-reaching
  session).
- In session-level classification accounting, this results in:
    * Days 1, 2, 3: Actual Positive, Pred Negative -> False Negatives (FN = 3)
    * Day 4:        Actual Positive, Pred Positive -> True Positive (TP = 1)
  yielding a session-level recall of 1/4 (25%) on that 4-day event.
- This does NOT indicate that the rule failed to detect the event: the repeated-headcount
  event was successfully flagged on Day 4. Rather, it reflects that online sequential
  detectors cannot alert on prefix sessions before sufficient historical evidence
  has accumulated.

Per-Rule Evaluation Semantics:
------------------------------
- To isolate individual detector performance, per-rule evaluation requires
  the 'ground_truth_anomaly_type' column in labelled_sessions_df.
- Each rule is evaluated strictly against its corresponding anomaly target types:
    * RULE_ATTENDANCE_DROP -> {"ATTENDANCE_DROP", "COMPOUND"}
    * RULE_REPEATED_HEADCOUNT -> {"REPEATED_HEADCOUNT", "COMPOUND"}
    * RULE_WEBCAM_DISCREPANCY -> {"WEBCAM_DISCREPANCY", "COMPOUND"}
- If 'ground_truth_anomaly_type' is absent:
    * Aggregate metrics continue to evaluate binary anomaly status across all sessions.
    * Per-rule breakdowns are omitted ('by_rule' returns empty dict {}) to prevent
      misleading cross-rule false negative inflation.
    * Explicit requests for per-rule evaluation (via evaluate_rule_performance() or
      passing evaluated_rules to evaluate_detector_performance()) raise a ValueError.

Session ID Uniqueness Precondition:
-----------------------------------
- In conformance with docs/data-contract.md Section 2.1, 'session_id' is the primary
  key of each session record.
- labelled_sessions_df must contain unique 'session_id' values. Duplicate session IDs
  are rejected with ValueError to prevent sample-count inflation and ambiguous
  ground-truth states.

How to Reproduce Evaluation:
---------------------------
>>> from attendsure.data.generator import generate_synthetic_sessions
>>> from attendsure.detection.rules import detect_anomalies
>>> from attendsure.evaluation import evaluate_detector_performance
>>>
>>> # 1. Generate synthetic sessions containing ground-truth annotations
>>> sessions_df = generate_synthetic_sessions(num_classes=5, num_days=30, random_seed=42)
>>>
>>> # 2. Run rule-based detection pipeline
>>> alerts = detect_anomalies(sessions_df)
>>>
>>> # 3. Compute evaluation metrics against ground-truth labels
>>> metrics = evaluate_detector_performance(sessions_df, alerts)
>>> print(f"Precision: {metrics['precision']:.4f}")
>>> print(f"Recall:    {metrics['recall']:.4f}")
>>> print(f"F1-Score:  {metrics['f1_score']:.4f}")
>>> print("Confusion Matrix:", metrics["confusion_matrix"])
"""

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Union

import pandas as pd

from attendsure.data.models import Alert
from attendsure.detection.rules import (
    RULE_ATTENDANCE_DROP,
    RULE_REPEATED_HEADCOUNT,
    RULE_WEBCAM_DISCREPANCY,
)

# Standard mapping between detector rule_id and synthetic ground-truth anomaly type literals
RULE_TO_ANOMALY_TYPES: dict[str, set[str]] = {
    RULE_ATTENDANCE_DROP: {"ATTENDANCE_DROP", "COMPOUND"},
    RULE_REPEATED_HEADCOUNT: {"REPEATED_HEADCOUNT", "COMPOUND"},
    RULE_WEBCAM_DISCREPANCY: {"WEBCAM_DISCREPANCY", "COMPOUND"},
}

REQUIRED_EVALUATION_COLUMNS = ("session_id", "ground_truth_is_anomaly")


@dataclass(frozen=True)
class ClassificationCounts:
    """Confusion matrix counts for binary classification."""

    tp: int
    fp: int
    tn: int
    fn: int
    total: int

    def to_dict(self) -> dict[str, int]:
        """Convert counts to standard dictionary."""
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "total": self.total,
        }


def compute_classification_scores(
    tp: int,
    fp: int,
    tn: int,
    fn: int,
    zero_division: float = 0.0,
) -> tuple[float, float, float, dict[str, bool]]:
    """Calculate precision, recall, and F1 score with explicit zero-denominator handling.

    Args:
        tp: True positives count.
        fp: False positives count.
        tn: True negatives count.
        fn: False negatives count.
        zero_division: Fallback float value when denominator is 0 (default 0.0).

    Returns:
        Tuple of (precision, recall, f1_score, zero_division_applied_dict).
    """
    zd_flags = {
        "precision": False,
        "recall": False,
        "f1_score": False,
    }

    # Precision = TP / (TP + FP)
    pred_positives = tp + fp
    if pred_positives > 0:
        precision = float(tp / pred_positives)
    else:
        precision = float(zero_division)
        zd_flags["precision"] = True

    # Recall = TP / (TP + FN)
    actual_positives = tp + fn
    if actual_positives > 0:
        recall = float(tp / actual_positives)
    else:
        recall = float(zero_division)
        zd_flags["recall"] = True

    # F1-Score = 2 * (P * R) / (P + R)
    prec_plus_rec = precision + recall
    if prec_plus_rec > 0.0:
        f1_score = float(2.0 * (precision * recall) / prec_plus_rec)
    else:
        f1_score = float(zero_division)
        zd_flags["f1_score"] = True

    return precision, recall, f1_score, zd_flags


def confusion_matrix_to_dataframe(confusion_matrix: dict[str, int]) -> pd.DataFrame:
    """Format confusion matrix counts as a standard 2x2 presentation DataFrame.

    Conforms to docs/data-contract.md Section 6.2 format:
                      Actual Positive    Actual Negative
      Pred Positive        TP                 FP
      Pred Negative        FN                 TN

    Args:
        confusion_matrix: Dictionary containing 'tp', 'fp', 'tn', 'fn'.

    Returns:
        pd.DataFrame formatted for Streamlit or reporting tables.
    """
    tp = confusion_matrix.get("tp", 0)
    fp = confusion_matrix.get("fp", 0)
    tn = confusion_matrix.get("tn", 0)
    fn = confusion_matrix.get("fn", 0)

    data = {
        "Actual Positive": [tp, fn],
        "Actual Negative": [fp, tn],
    }
    index = ["Pred Positive", "Pred Negative"]
    return pd.DataFrame(data, index=index)


def _extract_alert_tuples(
    alerts: Union[Sequence[Union[Alert, dict, tuple[str, str]]], pd.DataFrame],
) -> list[tuple[str, str]]:
    """Safely extract (session_id, rule_id) tuples from alerts sequence or DataFrame."""
    if isinstance(alerts, pd.DataFrame):
        if alerts.empty or "session_id" not in alerts.columns:
            return []
        has_rule = "rule_id" in alerts.columns
        extracted: list[tuple[str, str]] = []
        for _, row in alerts.iterrows():
            sid = str(row["session_id"])
            rid = str(row["rule_id"]) if has_rule else ""
            extracted.append((sid, rid))
        return extracted

    extracted = []
    for item in alerts:
        if isinstance(item, Alert):
            extracted.append((item.session_id, item.rule_id))
        elif isinstance(item, dict):
            extracted.append((str(item.get("session_id", "")), str(item.get("rule_id", ""))))
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            extracted.append((str(item[0]), str(item[1])))
        else:
            raise TypeError(
                f"Expected Alert, dict, or (session_id, rule_id) tuple, got {type(item).__name__}."
            )
    return extracted


def evaluate_rule_performance(
    rule_id: str,
    labelled_sessions_df: pd.DataFrame,
    generated_alerts: Union[Sequence[Union[Alert, dict, tuple[str, str]]], pd.DataFrame],
    zero_division: float = 0.0,
) -> dict[str, Any]:
    """Evaluate performance of a specific detector rule against ground-truth labels.

    Requires 'ground_truth_anomaly_type' in labelled_sessions_df to accurately identify
    sessions intended as targets for this specific rule (avoiding false negative inflation
    from unrelated anomaly types).

    Args:
        rule_id: The detector rule identifier (e.g., RULE_ATTENDANCE_DROP).
        labelled_sessions_df: DataFrame containing at least 'session_id',
            'ground_truth_is_anomaly', and 'ground_truth_anomaly_type'.
        generated_alerts: Sequence of Alert objects, dicts, tuples, or DataFrame of alerts.
        zero_division: Fallback float value when denominator is 0 (default 0.0).

    Returns:
        Dictionary with classification counts, scores, and confusion matrix for the rule.

    Raises:
        TypeError: If labelled_sessions_df is not a DataFrame.
        ValueError: If required columns ('session_id', 'ground_truth_is_anomaly',
            'ground_truth_anomaly_type') are missing.
        ValueError: If duplicate session_id values are present in labelled_sessions_df.
    """
    if not isinstance(labelled_sessions_df, pd.DataFrame):
        raise TypeError(
            f"Expected labelled_sessions_df to be pandas DataFrame, got {type(labelled_sessions_df).__name__}."
        )

    for req_col in REQUIRED_EVALUATION_COLUMNS:
        if req_col not in labelled_sessions_df.columns:
            raise ValueError(
                f"labelled_sessions_df is missing required evaluation column '{req_col}'."
            )

    if "ground_truth_anomaly_type" not in labelled_sessions_df.columns:
        raise ValueError(
            f"Per-rule evaluation for rule '{rule_id}' requires 'ground_truth_anomaly_type' "
            "column in labelled_sessions_df."
        )

    if labelled_sessions_df["session_id"].duplicated().any():
        raise ValueError(
            "labelled_sessions_df contains duplicate session_id values; "
            "each evaluated session must have a unique session_id."
        )

    total_samples = len(labelled_sessions_df)
    if total_samples == 0:
        prec, rec, f1, zd = compute_classification_scores(0, 0, 0, 0, zero_division=zero_division)
        return {
            "rule_id": rule_id,
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "total_samples": 0,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "confusion_matrix": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "zero_division_applied": zd,
        }

    alert_tuples = _extract_alert_tuples(generated_alerts)
    dataset_session_ids = set(labelled_sessions_df["session_id"].astype(str))
    rule_alerted_sids = {
        sid for sid, rid in alert_tuples if sid in dataset_session_ids and rid == rule_id
    }
    rule_target_types = RULE_TO_ANOMALY_TYPES.get(rule_id, {rule_id})

    rule_tp = 0
    rule_fp = 0
    rule_tn = 0
    rule_fn = 0

    for _, row in labelled_sessions_df.iterrows():
        sid = str(row["session_id"])
        is_anomaly = bool(row["ground_truth_is_anomaly"])
        atype = str(row["ground_truth_anomaly_type"])
        is_rule_actual_positive = is_anomaly and (atype in rule_target_types)
        is_rule_pred_positive = sid in rule_alerted_sids

        if is_rule_actual_positive and is_rule_pred_positive:
            rule_tp += 1
        elif not is_rule_actual_positive and is_rule_pred_positive:
            rule_fp += 1
        elif not is_rule_actual_positive and not is_rule_pred_positive:
            rule_tn += 1
        else:
            rule_fn += 1

    r_prec, r_rec, r_f1, r_zd = compute_classification_scores(
        rule_tp, rule_fp, rule_tn, rule_fn, zero_division=zero_division
    )

    res: dict[str, Any] = {
        "rule_id": rule_id,
        "tp": rule_tp,
        "fp": rule_fp,
        "tn": rule_tn,
        "fn": rule_fn,
        "total_samples": total_samples,
        "precision": r_prec,
        "recall": r_rec,
        "f1_score": r_f1,
        "confusion_matrix": {
            "tp": rule_tp,
            "fp": rule_fp,
            "tn": rule_tn,
            "fn": rule_fn,
        },
        "zero_division_applied": r_zd,
    }

    if rule_id == RULE_REPEATED_HEADCOUNT:
        res["sequence_events"] = evaluate_sequence_events(
            labelled_sessions_df=labelled_sessions_df,
            generated_alerts=generated_alerts,
            target_rule_id=RULE_REPEATED_HEADCOUNT,
            zero_division=zero_division,
        )

    return res


def evaluate_webcam_estimation(
    sessions_df: pd.DataFrame,
) -> dict[str, Any]:
    """Calculate Mean Absolute Error (MAE) and Mean Absolute Percentage Error (MAPE)
    between manual roll-call attendance counts and simulated camera visible-person estimates.

    Conforms to docs/data-contract.md Section 6.2 camera metric decoupling:
    - Camera estimation accuracy evaluates numerical tracking variance, decoupled from binary
      roll-call attendance classification.
    - Evaluates strictly sessions where webcam_status == 'SUCCESS' and webcam_count is not None.
    - Non-success sessions (CAMERA_OFFLINE, CAMERA_UNAVAILABLE, DETECTION_FAILED, NOT_ATTEMPTED)
      are excluded from estimation error calculations.

    Zero-Actual Policy:
    -------------------
    - When ground-truth present_count == 0, percentage error |0 - y_hat| / 0 is mathematically undefined.
      To prevent division-by-zero or reporting misleading infinite/meaningless percentage errors,
      sessions with present_count == 0 are excluded from MAPE calculation, and their count
      is explicitly tracked in 'zero_actual_count'.
    - If all evaluated pairs have present_count == 0 (or no positive actuals exist),
      mape defaults to None and zero_division_applied['mape'] is set to True.
    - If no valid pairs exist (evaluated_pairs == 0), both mae and mape default to None
      with zero_division_applied flags set to True.

    Args:
        sessions_df: DataFrame containing at least 'present_count', 'webcam_status',
            and 'webcam_count' columns.

    Returns:
        Dictionary containing:
            - total_sessions: Total rows in sessions_df.
            - evaluated_pairs: Count of valid (SUCCESS, non-null) comparison pairs.
            - mae: Mean Absolute Error (float rounded to 4 decimals, or None).
            - mape: Mean Absolute Percentage Error in percent (float rounded to 4 decimals, or None).
            - mean_absolute_error: Alias for mae.
            - mean_absolute_percentage_error: Alias for mape.
            - zero_actual_count: Count of evaluated pairs where present_count == 0.
            - zero_division_applied: Dict with 'mae' and 'mape' booleans.

    Raises:
        TypeError: If sessions_df is not a pandas DataFrame.
        ValueError: If required columns ('present_count', 'webcam_status', 'webcam_count') are missing.
    """
    if not isinstance(sessions_df, pd.DataFrame):
        raise TypeError(
            f"Expected sessions_df to be pandas DataFrame, got {type(sessions_df).__name__}."
        )

    required_cols = ("present_count", "webcam_status", "webcam_count")
    for col in required_cols:
        if col not in sessions_df.columns:
            raise ValueError(
                f"sessions_df is missing required column '{col}' for camera estimation evaluation."
            )

    total_sessions = len(sessions_df)
    if total_sessions == 0:
        return {
            "total_sessions": 0,
            "evaluated_pairs": 0,
            "mae": None,
            "mape": None,
            "mean_absolute_error": None,
            "mean_absolute_percentage_error": None,
            "zero_actual_count": 0,
            "zero_division_applied": {"mae": True, "mape": True},
        }

    # Filter to valid camera success records
    valid_mask = (
        (sessions_df["webcam_status"] == "SUCCESS")
        & sessions_df["webcam_count"].notna()
        & sessions_df["present_count"].notna()
    )
    valid_pairs_df = sessions_df[valid_mask]
    evaluated_pairs = len(valid_pairs_df)

    if evaluated_pairs == 0:
        return {
            "total_sessions": total_sessions,
            "evaluated_pairs": 0,
            "mae": None,
            "mape": None,
            "mean_absolute_error": None,
            "mean_absolute_percentage_error": None,
            "zero_actual_count": 0,
            "zero_division_applied": {"mae": True, "mape": True},
        }

    actual_series = valid_pairs_df["present_count"].astype(float)
    estimated_series = valid_pairs_df["webcam_count"].astype(float)

    abs_errors = (actual_series - estimated_series).abs()
    mae_val = float(abs_errors.mean())

    # MAPE calculation with zero-actual protection
    nonzero_mask = actual_series > 0.0
    zero_actual_count = int((~nonzero_mask).sum())
    nonzero_actual = actual_series[nonzero_mask]
    nonzero_abs_err = abs_errors[nonzero_mask]

    if len(nonzero_actual) > 0:
        mape_val = float((nonzero_abs_err / nonzero_actual).mean() * 100.0)
        mape_zd = False
    else:
        mape_val = None
        mape_zd = True

    return {
        "total_sessions": total_sessions,
        "evaluated_pairs": evaluated_pairs,
        "mae": round(mae_val, 4),
        "mape": round(mape_val, 4) if mape_val is not None else None,
        "mean_absolute_error": round(mae_val, 4),
        "mean_absolute_percentage_error": round(mape_val, 4) if mape_val is not None else None,
        "zero_actual_count": zero_actual_count,
        "zero_division_applied": {"mae": False, "mape": mape_zd},
    }


def evaluate_sequence_events(
    labelled_sessions_df: pd.DataFrame,
    generated_alerts: Union[Sequence[Union[Alert, dict, tuple[str, str]]], pd.DataFrame],
    target_rule_id: str = RULE_REPEATED_HEADCOUNT,
    zero_division: float = 0.0,
) -> dict[str, Any]:
    """Evaluate temporal event-level detection performance for sequential anomaly rules.

    Distinguishes sequence-level event detection from single-session binary classification:
    - Sequential anomaly rules (e.g., RULE_REPEATED_HEADCOUNT) require multiple consecutive
      sessions before emitting an alert on the threshold session (e.g., Day 4 of 4).
    - Session-level accounting treats prefix sessions (Days 1–3) as False Negatives (FN).
    - Event-level accounting determines whether the multi-session anomalous event as a whole
      was successfully detected (True Positive).

    Args:
        labelled_sessions_df: DataFrame containing at least 'session_id', 'ground_truth_is_anomaly',
            and 'ground_truth_anomaly_type'.
        generated_alerts: Sequence of Alert objects, dicts, tuples, or DataFrame of alerts.
        target_rule_id: The sequential rule identifier to evaluate (default: RULE_REPEATED_HEADCOUNT).
        zero_division: Fallback float value when denominator is 0 (default 0.0).

    Returns:
        Dictionary containing:
            - target_rule_id: Evaluated rule identifier.
            - total_events: Total contiguous ground-truth anomaly events.
            - tp: Detected ground-truth events (at least 1 alert fired during the event).
            - fp: Spurious alerts for target_rule_id outside any ground-truth event.
            - fn: Undetected ground-truth events (0 alerts fired during the event).
            - precision: Event-level precision.
            - recall: Event-level recall.
            - f1_score: Event-level F1 score.
            - zero_division_applied: Dict with zero-division booleans.
            - events: List of detailed event records (class, dates, length, detected status).

    Raises:
        TypeError: If labelled_sessions_df is not a DataFrame.
        ValueError: If required columns ('session_id', 'ground_truth_is_anomaly',
            'ground_truth_anomaly_type') are missing.
    """
    if not isinstance(labelled_sessions_df, pd.DataFrame):
        raise TypeError(
            f"Expected labelled_sessions_df to be pandas DataFrame, got {type(labelled_sessions_df).__name__}."
        )

    for req_col in ("session_id", "ground_truth_is_anomaly", "ground_truth_anomaly_type"):
        if req_col not in labelled_sessions_df.columns:
            raise ValueError(
                f"labelled_sessions_df is missing required column '{req_col}' for sequence event evaluation."
            )

    alert_tuples = _extract_alert_tuples(generated_alerts)
    dataset_sids = set(labelled_sessions_df["session_id"].astype(str))
    target_alert_sids = {
        sid for sid, rid in alert_tuples if sid in dataset_sids and rid == target_rule_id
    }
    target_anomaly_types = RULE_TO_ANOMALY_TYPES.get(target_rule_id, {target_rule_id})

    # Prepare DataFrame sorted chronologically by cohort if cohort/date columns exist
    df_sorted = labelled_sessions_df.copy()
    sort_cols = []
    if "class_id" in df_sorted.columns:
        sort_cols.append("class_id")
    if "session_date" in df_sorted.columns:
        sort_cols.append("session_date")
    if sort_cols:
        df_sorted = df_sorted.sort_values(sort_cols).reset_index(drop=True)

    # Group contiguous anomaly sessions into discrete events
    events: list[dict[str, Any]] = []
    cohort_groups = (
        df_sorted.groupby("class_id", sort=False)
        if "class_id" in df_sorted.columns
        else [("ALL", df_sorted)]
    )

    for cid, cohort_df in cohort_groups:
        current_event_sids: list[str] = []
        current_event_dates: list[str] = []

        for _, row in cohort_df.iterrows():
            sid = str(row["session_id"])
            is_anomaly = bool(row["ground_truth_is_anomaly"])
            atype = str(row["ground_truth_anomaly_type"])
            sdate = str(row["session_date"]) if "session_date" in row else ""

            if is_anomaly and atype in target_anomaly_types:
                current_event_sids.append(sid)
                if sdate:
                    current_event_dates.append(sdate)
            else:
                if current_event_sids:
                    events.append(
                        {
                            "event_id": f"EVT-{cid}-{len(events) + 1}",
                            "class_id": str(cid),
                            "session_ids": list(current_event_sids),
                            "dates": list(current_event_dates),
                            "length": len(current_event_sids),
                        }
                    )
                    current_event_sids = []
                    current_event_dates = []

        if current_event_sids:
            events.append(
                {
                    "event_id": f"EVT-{cid}-{len(events) + 1}",
                    "class_id": str(cid),
                    "session_ids": list(current_event_sids),
                    "dates": list(current_event_dates),
                    "length": len(current_event_sids),
                }
            )

    # Evaluate each event against target alerts
    event_tp = 0
    event_fn = 0
    all_event_sids: set[str] = set()

    for evt in events:
        evt_sids = set(evt["session_ids"])
        all_event_sids.update(evt_sids)
        firing_sids = evt_sids.intersection(target_alert_sids)
        is_detected = len(firing_sids) > 0
        evt["detected"] = is_detected
        evt["alert_session_ids"] = sorted(firing_sids)

        if is_detected:
            event_tp += 1
        else:
            event_fn += 1

    # False positives: alerts that fired on sessions outside any ground-truth event window
    event_fp = len(target_alert_sids - all_event_sids)
    total_events = len(events)

    prec, rec, f1, zd = compute_classification_scores(
        event_tp, event_fp, 0, event_fn, zero_division=zero_division
    )

    return {
        "target_rule_id": target_rule_id,
        "total_events": total_events,
        "tp": event_tp,
        "fp": event_fp,
        "fn": event_fn,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "zero_division_applied": zd,
        "events": events,
    }


def evaluate_detector_performance(
    labelled_sessions_df: pd.DataFrame,
    generated_alerts: Union[Sequence[Union[Alert, dict, tuple[str, str]]], pd.DataFrame],
    zero_division: float = 0.0,
    evaluated_rules: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Evaluate attendance anomaly detector performance against ground-truth labels.

    Evaluates predictions at the session level conforming to docs/data-contract.md Section 6.2:
    - Matches detector alerts against synthetic ground-truth annotations (ground_truth_is_anomaly).
    - Computes True Positives (TP), False Positives (FP), True Negatives (TN), and False Negatives (FN).
    - Calculates Precision, Recall, and F1-score with deterministic zero-division handling.
    - Computes both aggregate (overall binary) performance and per-rule breakdowns.
    - Supports empty datasets and datasets without positive labels gracefully.
    - Does not mutate input DataFrame or alert objects.
    - Decouples webcam count-estimation metrics (MAE/MAPE) into a dedicated 'webcam_estimation' result.

    Args:
        labelled_sessions_df: DataFrame containing attendance sessions with at least
            'session_id' and 'ground_truth_is_anomaly' columns.
        generated_alerts: List, Sequence of Alert objects, dicts, or DataFrame of alerts.
        zero_division: Fallback float value when precision, recall, or F1 denominator is zero (default 0.0).
        evaluated_rules: Optional sequence of rule IDs to evaluate in by_rule breakdown.
            If specified, labelled_sessions_df must contain 'ground_truth_anomaly_type'.

    Returns:
        Summary dictionary containing:
            - tp, fp, tn, fn: Aggregate confusion matrix counts.
            - total_samples: Number of sessions evaluated.
            - precision, recall, f1_score: Overall performance metrics.
            - confusion_matrix: Structured dict {'tp': ..., 'fp': ..., 'tn': ..., 'fn': ...}.
            - zero_division_applied: Dict indicating which metrics used zero_division.
            - by_rule: Per-rule metric breakdown for each evaluated rule.
            - webcam_estimation: Optional camera count estimation metrics (MAE/MAPE) if
              camera columns are present; None otherwise.
            - sequence_events: Optional event-level sequence detection metrics for
              RULE_REPEATED_HEADCOUNT if 'ground_truth_anomaly_type' is present; None otherwise.

    Raises:
        TypeError: If labelled_sessions_df is not a DataFrame.
        ValueError: If required columns ('session_id', 'ground_truth_is_anomaly') are missing.
        ValueError: If labelled_sessions_df contains duplicate session_id values.
        ValueError: If evaluated_rules is explicitly requested but 'ground_truth_anomaly_type'
            is missing from labelled_sessions_df.
    """
    if not isinstance(labelled_sessions_df, pd.DataFrame):
        raise TypeError(
            f"Expected labelled_sessions_df to be pandas DataFrame, got {type(labelled_sessions_df).__name__}."
        )

    for req_col in REQUIRED_EVALUATION_COLUMNS:
        if req_col not in labelled_sessions_df.columns:
            raise ValueError(
                f"labelled_sessions_df is missing required evaluation column '{req_col}'."
            )

    if labelled_sessions_df["session_id"].duplicated().any():
        raise ValueError(
            "labelled_sessions_df contains duplicate session_id values; "
            "each evaluated session must have a unique session_id."
        )

    has_anomaly_type = "ground_truth_anomaly_type" in labelled_sessions_df.columns
    if evaluated_rules is not None and not has_anomaly_type:
        raise ValueError(
            "Per-rule evaluation was requested via evaluated_rules, but labelled_sessions_df "
            "is missing required 'ground_truth_anomaly_type' column."
        )

    total_samples = len(labelled_sessions_df)

    has_webcam_cols = (
        "webcam_status" in labelled_sessions_df.columns
        and "webcam_count" in labelled_sessions_df.columns
        and "present_count" in labelled_sessions_df.columns
    )
    webcam_estimation = (
        evaluate_webcam_estimation(labelled_sessions_df) if has_webcam_cols else None
    )

    # Handle empty dataset edge case immediately
    if total_samples == 0:
        prec, rec, f1, zd = compute_classification_scores(0, 0, 0, 0, zero_division=zero_division)
        empty_matrix = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        return {
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "total_samples": 0,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "confusion_matrix": empty_matrix,
            "zero_division_applied": zd,
            "by_rule": {},
            "webcam_estimation": webcam_estimation,
            "sequence_events": None,
        }

    alert_tuples = _extract_alert_tuples(generated_alerts)

    # Map dataset session IDs to prevent out-of-scope alert pollution
    dataset_session_ids = set(labelled_sessions_df["session_id"].astype(str))

    # Relevant alerts for sessions present in this evaluated dataset
    valid_alerts = [(sid, rid) for sid, rid in alert_tuples if sid in dataset_session_ids]
    alerted_session_ids = {sid for sid, _ in valid_alerts}

    # -------------------------------------------------------------------------
    # 1. Aggregate Binary Anomaly Evaluation
    # -------------------------------------------------------------------------
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for _, row in labelled_sessions_df.iterrows():
        sid = str(row["session_id"])
        is_actual_anomaly = bool(row["ground_truth_is_anomaly"])
        is_pred_anomaly = sid in alerted_session_ids

        if is_actual_anomaly and is_pred_anomaly:
            tp += 1
        elif not is_actual_anomaly and is_pred_anomaly:
            fp += 1
        elif not is_actual_anomaly and not is_pred_anomaly:
            tn += 1
        else:
            fn += 1

    precision, recall, f1_score, zd_flags = compute_classification_scores(
        tp, fp, tn, fn, zero_division=zero_division
    )

    confusion_matrix = {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }

    # -------------------------------------------------------------------------
    # 2. Rule-Specific Breakdown (Section 6.2 Rule Independence)
    # -------------------------------------------------------------------------
    by_rule: dict[str, dict[str, Any]] = {}

    if has_anomaly_type:
        rules_to_evaluate = (
            list(evaluated_rules)
            if evaluated_rules is not None
            else [
                RULE_ATTENDANCE_DROP,
                RULE_REPEATED_HEADCOUNT,
                RULE_WEBCAM_DISCREPANCY,
            ]
        )
        for rule_id in rules_to_evaluate:
            by_rule[rule_id] = evaluate_rule_performance(
                rule_id=rule_id,
                labelled_sessions_df=labelled_sessions_df,
                generated_alerts=valid_alerts,
                zero_division=zero_division,
            )

    sequence_events = (
        evaluate_sequence_events(
            labelled_sessions_df=labelled_sessions_df,
            generated_alerts=valid_alerts,
            target_rule_id=RULE_REPEATED_HEADCOUNT,
            zero_division=zero_division,
        )
        if has_anomaly_type
        else None
    )

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total_samples": total_samples,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "confusion_matrix": confusion_matrix,
        "zero_division_applied": zd_flags,
        "by_rule": by_rule,
        "webcam_estimation": webcam_estimation,
        "sequence_events": sequence_events,
    }
