#!/usr/bin/env python3
"""Public Benchmark Reproduction Script for AttendSure.

Reproduces both the Supervised Machine Learning Benchmark (88 independent test sessions)
and the Deterministic Production Rules Benchmark (150 synthetic sessions) exactly as
documented in the project technical architecture.

Usage:
    python scripts/reproduce_benchmarks.py
"""

import sys
from pathlib import Path

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from attendsure.data.generator import generate_synthetic_sessions
from attendsure.detection.rules import detect_anomalies
from attendsure.evaluation.metrics import evaluate_detector_performance
from attendsure.ml.dataset import create_train_test_split
from attendsure.ml.model import AttendanceDecisionTreeClassifier


def run_ml_benchmark():
    print("=" * 75)
    print("1. SUPERVISED MACHINE LEARNING BENCHMARK (Decision Tree Classifier)")
    print("=" * 75)
    print("Dataset: 12 cohorts over 35 calendar days (excluding weekends = 25 school days/class)")
    print("Split:   8 training classes (200 records), 4 holdout testing classes (100 records)")
    print("Burn-in: 3-day history window excludes first 3 sessions/cohort for causal rolling baseline")
    print("Samples: 176 valid training sessions, 88 independent test sessions (Random Seed = 42)")
    print("-" * 75)

    split = create_train_test_split(num_classes=12, days_per_class=35, test_class_ratio=0.3, random_seed=42)
    clf = AttendanceDecisionTreeClassifier(max_depth=4, min_samples_leaf=4, random_state=42)
    clf.fit(split.train_df)

    metrics = clf.evaluate(split.test_df)
    cm = metrics["confusion_matrix"]
    total = metrics["test_samples"]
    acc = (cm["tp"] + cm["tn"]) / total * 100.0

    print(f"Test Samples:      {total}")
    print(f"Confusion Matrix:  TP={cm['tp']}, FP={cm['fp']}, TN={cm['tn']}, FN={cm['fn']}")
    print(f"Accuracy:          {acc:.2f}% ({cm['tp'] + cm['tn']} / {total})")
    print(f"Precision:         {metrics['precision'] * 100.0:.2f}% ({cm['tp']} / {cm['tp'] + cm['fp']})")
    print(f"Recall (Sensitivity): {metrics['recall'] * 100.0:.2f}% ({cm['tp']} / {cm['tp'] + cm['fn']})")
    print(f"Specificity:       {metrics['specificity'] * 100.0:.2f}% ({cm['tn']} / {cm['tn'] + cm['fp']})")
    print(f"F1-Score:          {metrics['f1_score'] * 100.0:.2f}%")
    print("-" * 75)
    print("Trade-Off Note: Class weighting intentionally prioritizes high recall (80.0%) and high")
    print("specificity (92.8%) over precision (40.0%) due to low synthetic anomaly prevalence (~5.7%).")


def run_rule_benchmark():
    print("\n" + "=" * 75)
    print("2. DETERMINISTIC PRODUCTION RULES BENCHMARK (Standard Testbench Preset)")
    print("=" * 75)
    print("Parameters: 5 classes x 30 school days = 150 sessions total")
    print("Injection:  5.0% anomaly injection rate, Random Seed = 42")
    print("Detectors:  Attendance Drop (>=30%), Repeated Count (>=4 days), Camera Discrepancy")
    print("-" * 75)

    bench_df = generate_synthetic_sessions(
        num_classes=5,
        num_days=30,
        anomaly_rate=0.05,
        random_seed=42,
        include_webcam=True,
        include_labels=True,
    )
    bench_alerts = detect_anomalies(bench_df)
    rm = evaluate_detector_performance(bench_df, bench_alerts)
    cm = rm["confusion_matrix"]
    total = rm["total_samples"]
    acc = (cm["tp"] + cm["tn"]) / total * 100.0
    spec = (cm["tn"] / (cm["tn"] + cm["fp"])) * 100.0 if (cm["tn"] + cm["fp"]) > 0 else 100.0

    print(f"Evaluated Sessions: {total}")
    print(f"Confusion Matrix:   TP={cm['tp']}, FP={cm['fp']}, TN={cm['tn']}, FN={cm['fn']}")
    print(f"Accuracy:           {acc:.2f}% ({cm['tp'] + cm['tn']} / {total})")
    print(f"Precision:          {rm['precision'] * 100.0:.2f}% ({cm['tp']} / {cm['tp'] + cm['fp']})")
    print(f"Recall (Session):   {rm['recall'] * 100.0:.2f}% ({cm['tp']} / {cm['tp'] + cm['fn']})")
    print(f"Specificity:        {spec:.2f}% ({cm['tn']} / {cm['tn'] + cm['fp']})")
    print(f"F1-Score:           {rm['f1_score'] * 100.0:.2f}%")

    if rm.get("sequence_events"):
        ev = rm["sequence_events"]
        print(f"Recall (Event-Level): {ev['recall'] * 100.0:.2f}% ({ev['tp']} of {ev['total_events']} multi-day episodes flagged)")
    print("-" * 75)
    print("Operational Note: Session-level recall is 54.55% due to chronological prefix accumulation")
    print("delay on repeated runs (alerts trigger on Day 4 of 4). Event-level detection is 100.0%.")
    print("=" * 75)


if __name__ == "__main__":
    run_ml_benchmark()
    run_rule_benchmark()

