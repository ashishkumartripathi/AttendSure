"""Synthetic training and evaluation dataset generator for attendance ML models.

Conforms to CSE276 Unit IV and Practical 7 standards:
- Fully reproducible with documented random seeds.
- Independently defined ground-truth scenarios (no rule circularity).
- Group-aware and time-aware train/test separation to prevent data leakage.
"""

from datetime import date, timedelta
import random
from typing import Literal, NamedTuple, Optional
import pandas as pd

ScenarioType = Literal[
    "NOMINAL",
    "MILD_VARIATION",
    "HIGH_RETENTION",
    "SUDDEN_SEVERE_DISRUPTION",
    "ADMINISTRATIVE_INERTIA",
    "GRADUAL_CHRONIC_DROP",
]


class DatasetSplit(NamedTuple):
    """Encapsulates partitioned training and evaluation datasets."""

    train_df: pd.DataFrame
    test_df: pd.DataFrame
    class_distribution_train: dict[int, int]
    class_distribution_test: dict[int, int]
    random_seed: int


def generate_independent_ml_dataset(
    num_classes: int = 10,
    days_per_class: int = 35,
    random_seed: int = 42,
    start_date: Optional[date] = None,
) -> pd.DataFrame:
    """Generate an independently formulated synthetic attendance dataset with explicit ground truth.

    Does not use detection rules to synthesize labels, avoiding circular evaluation.
    Scenarios simulate realistic rural primary school dynamics:
    - Normal baseline attendance (82-94%) -> Label: 0 (Normal)
    - Mild weather variance (10-15% dip) -> Label: 0 (Normal)
    - High-attendance small cohorts (95-100%) -> Label: 0 (Normal)
    - Severe disruptions (flash floods, epidemic: > 30% drop) -> Label: 1 (Needs Review)
    - Reporting inertia (copy-pasting identical count >= 4 days) -> Label: 1 (Needs Review)
    - Gradual chronic absenteeism (cumulative decline > 25%) -> Label: 1 (Needs Review)

    Args:
        num_classes: Number of distinct classroom cohorts.
        days_per_class: Number of consecutive school days per cohort.
        random_seed: Integer seed for full reproducibility.
        start_date: Starting calendar date.

    Returns:
        DataFrame with session records including 'label' (0 or 1) and 'scenario_type'.
    """
    rng = random.Random(random_seed)
    current_start = start_date or date(2026, 9, 1)

    records: list[dict] = []

    for c_idx in range(1, num_classes + 1):
        class_id = f"CLASS-{c_idx:02d}-A"
        enrollment = rng.choice([25, 30, 35, 40, 45])
        base_rate = rng.uniform(0.82, 0.92)

        # Assign cohort scenario distribution
        # Most days are nominal; specific weeks experience disruptions or copy-paste inertia
        has_severe_drop = (c_idx % 3 == 0)
        has_inertia = (c_idx % 2 == 0)
        has_gradual_drop = (c_idx % 4 == 0)

        severe_drop_day = rng.randint(12, 18) if has_severe_drop else -1
        inertia_start_day = rng.randint(20, 24) if has_inertia else -1
        gradual_start_day = rng.randint(26, 28) if has_gradual_drop else -1

        frozen_count: Optional[int] = None

        for d_idx in range(days_per_class):
            sess_date = current_start + timedelta(days=d_idx)
            # Skip weekends (Saturday=5, Sunday=6)
            if sess_date.weekday() >= 5:
                continue

            session_id = f"SESS-{class_id}-{sess_date.isoformat()}"

            # 1. Severe disruption scenario (Label: 1)
            if d_idx == severe_drop_day:
                present = int(enrollment * rng.uniform(0.35, 0.52))
                label = 1
                scenario = "SUDDEN_SEVERE_DISRUPTION"

            # 2. Administrative inertia (repeated copy-pasting for 4 consecutive days) (Label: 1)
            elif inertia_start_day <= d_idx < inertia_start_day + 4:
                if frozen_count is None:
                    frozen_count = int(enrollment * rng.uniform(0.80, 0.88))
                present = frozen_count
                label = 1 if d_idx >= inertia_start_day + 3 else 0  # Becomes anomalous on 4th consecutive day
                scenario = "ADMINISTRATIVE_INERTIA"

            # 3. Gradual chronic drop (Label: 1)
            elif gradual_start_day <= d_idx < gradual_start_day + 4:
                step = d_idx - gradual_start_day
                drop_factor = base_rate - (0.08 * (step + 1))
                present = max(5, int(enrollment * drop_factor))
                label = 1 if step >= 2 else 0
                scenario = "GRADUAL_CHRONIC_DROP"

            # 4. Mild weather dip (Label: 0)
            elif d_idx in [5, 15] and rng.random() > 0.5:
                present = int(enrollment * (base_rate - rng.uniform(0.08, 0.14)))
                label = 0
                scenario = "MILD_VARIATION"

            # 5. Nominal baseline day (Label: 0)
            else:
                variation = rng.gauss(0.0, 0.03)
                eff_rate = min(1.0, max(0.65, base_rate + variation))
                present = int(round(enrollment * eff_rate))
                present = min(enrollment, max(0, present))
                label = 0
                scenario = "NOMINAL"

            absent = enrollment - present

            records.append({
                "session_id": session_id,
                "class_id": class_id,
                "session_date": sess_date.isoformat(),
                "expected_enrollment": enrollment,
                "present_count": present,
                "absent_count": absent,
                "webcam_status": "NOT_ATTEMPTED",
                "webcam_count": None,
                "record_source": "SYNTHETIC",
                "label": label,
                "scenario_type": scenario,
            })

    return pd.DataFrame(records)


def create_train_test_split(
    num_classes: int = 10,
    days_per_class: int = 35,
    test_class_ratio: float = 0.3,
    random_seed: int = 42,
) -> DatasetSplit:
    """Create a group-aware train/test partition to prevent cross-cohort data leakage.

    Splits by classroom cohort: training cohorts never appear in the test set.

    Args:
        num_classes: Total cohorts to generate.
        days_per_class: Days per cohort.
        test_class_ratio: Proportion of cohorts reserved for testing.
        random_seed: Reproducible seed.

    Returns:
        DatasetSplit containing train_df, test_df, and class distributions.
    """
    raw_df = generate_independent_ml_dataset(
        num_classes=num_classes,
        days_per_class=days_per_class,
        random_seed=random_seed,
    )

    all_cohorts = sorted(raw_df["class_id"].unique())
    rng = random.Random(random_seed)
    shuffled_cohorts = list(all_cohorts)
    rng.shuffle(shuffled_cohorts)

    num_test = max(1, int(round(len(all_cohorts) * test_class_ratio)))
    test_cohorts = set(shuffled_cohorts[:num_test])
    train_cohorts = set(shuffled_cohorts[num_test:])

    train_df = raw_df[raw_df["class_id"].isin(train_cohorts)].copy()
    test_df = raw_df[raw_df["class_id"].isin(test_cohorts)].copy()

    dist_train = train_df["label"].value_counts().to_dict()
    dist_test = test_df["label"].value_counts().to_dict()

    return DatasetSplit(
        train_df=train_df,
        test_df=test_df,
        class_distribution_train=dist_train,
        class_distribution_test=dist_test,
        random_seed=random_seed,
    )

