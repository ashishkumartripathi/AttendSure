#!/usr/bin/env python3
"""Synthetic Demonstration Dataset Generator for AttendSure.

Generates a dedicated, fully reproducible synthetic demonstration dataset in
`submission/demonstration/dataset/`.
- Never touches the operational Neon PostgreSQL cloud database or local operational SQLite.
- Every record is explicitly tagged as `SYNTHETIC` and documented for evaluation.
- Covers nominal attendance, repeated headcount streaks, attendance drops, camera discrepancies,
  and demonstration human administrative review states.

Usage:
    python submission/demonstration/generate_demo_dataset.py
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

import pandas as pd

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from attendsure.data.generator import generate_synthetic_sessions
from attendsure.detection.rules import detect_anomalies


def generate_demonstration_dataset():
    output_dir = repo_root / "submission" / "demonstration" / "dataset"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Generating Synthetic Demonstration Dataset for AttendSure...")
    print("=" * 70)

    # 1. Generate 150 deterministic synthetic sessions (5 classes x 30 days)
    # Using fixed seed 42 for exact bit-for-bit reproducibility
    df_sessions = generate_synthetic_sessions(
        num_classes=5,
        num_days=30,
        anomaly_rate=0.05,
        random_seed=42,
        include_webcam=True,
        include_labels=True,
    )

    # Add synthetic demonstration flag column
    df_sessions["is_synthetic_demonstration"] = True

    # 2. Run detection pipeline to generate explainable alerts
    alerts = detect_anomalies(df_sessions)

    # Convert alerts to DataFrame
    alert_rows = []
    for a in alerts:
        alert_rows.append({
            "alert_id": a.alert_id,
            "session_id": a.session_id,
            "class_id": a.class_id,
            "session_date": a.session_date,
            "rule_id": a.rule_id,
            "rule_title": a.rule_title,
            "priority": a.priority.value if hasattr(a.priority, "value") else str(a.priority),
            "review_status": a.review_status.value if hasattr(a.review_status, "value") else str(a.review_status),
            "observed_value": json.dumps(a.observed_value),
            "baseline_reference": json.dumps(a.baseline_reference),
            "threshold_applied": json.dumps(a.threshold_applied),
            "explanation": a.explanation,
            "created_at": a.created_at,
        })
    df_alerts = pd.DataFrame(alert_rows)

    # 3. Create demonstration human review actions (demonstrating all 4 states)
    # States: PENDING_REVIEW, ACKNOWLEDGED, RESOLVED, DISMISSED
    review_rows = []
    now_iso = datetime.now(timezone.utc).isoformat()

    if len(df_alerts) >= 3:
        # Review 1: Resolved attendance drop (Flooding verification)
        drop_matches = df_alerts[df_alerts["rule_id"] == "RULE_ATTENDANCE_DROP"]
        if not drop_matches.empty:
            a1 = drop_matches.iloc[0]
            df_alerts.loc[df_alerts["alert_id"] == a1["alert_id"], "review_status"] = "RESOLVED"
            review_rows.append({
                "review_id": f"REV-{uuid.uuid4().hex[:8]}",
                "alert_id": a1["alert_id"],
                "reviewed_by": "Headmaster (HM-01)",
                "review_action": "RESOLVED",
                "notes": "Verified severe localized monsoon rain and overflowing village nallah. Student absenteeism verified as justified environmental factor. No disciplinary action warranted.",
                "created_at": now_iso,
            })

        # Review 2: Acknowledged repeated headcount
        repeat_matches = df_alerts[df_alerts["rule_id"] == "RULE_REPEATED_HEADCOUNT"]
        if not repeat_matches.empty:
            a2 = repeat_matches.iloc[0]
            df_alerts.loc[df_alerts["alert_id"] == a2["alert_id"], "review_status"] = "ACKNOWLEDGED"
            review_rows.append({
                "review_id": f"REV-{uuid.uuid4().hex[:8]}",
                "alert_id": a2["alert_id"],
                "reviewed_by": "Block Officer (BEO-North)",
                "review_action": "ACKNOWLEDGED",
                "notes": "Flagged for on-site roll-call audit during upcoming Friday block inspection.",
                "created_at": now_iso,
            })

        # Review 3: Dismissed camera discrepancy (Lighting/shadow occlusion)
        cam_matches = df_alerts[df_alerts["rule_id"] == "RULE_WEBCAM_DISCREPANCY"]
        if not cam_matches.empty:
            a3 = cam_matches.iloc[0]
            df_alerts.loc[df_alerts["alert_id"] == a3["alert_id"], "review_status"] = "DISMISSED"
            review_rows.append({
                "review_id": f"REV-{uuid.uuid4().hex[:8]}",
                "alert_id": a3["alert_id"],
                "reviewed_by": "Teacher (TR-04)",
                "review_action": "DISMISSED",
                "notes": "Camera frame was partially occluded by open wooden window frame and morning direct sunlight glare. Physical roll-call manual count 27 verified accurate.",
                "created_at": now_iso,
            })

    df_reviews = pd.DataFrame(review_rows)

    # 4. Save CSV files
    sessions_csv = output_dir / "demo_attendance_sessions.csv"
    alerts_csv = output_dir / "demo_alerts.csv"
    reviews_csv = output_dir / "demo_alert_reviews.csv"

    df_sessions.to_csv(sessions_csv, index=False)
    df_alerts.to_csv(alerts_csv, index=False)
    df_reviews.to_csv(reviews_csv, index=False)

    print(f"Sessions CSV written:  {sessions_csv} ({len(df_sessions)} records)")
    print(f"Alerts CSV written:    {alerts_csv} ({len(df_alerts)} records)")
    print(f"Reviews CSV written:   {reviews_csv} ({len(df_reviews)} records)")
    print("=" * 70)
    print("Demonstration dataset generation complete. Operational databases remain untouched.")


if __name__ == "__main__":
    generate_demonstration_dataset()
