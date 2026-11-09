# Model Card: Attendance Decision Tree Classifier
## Rural School Attendance Integrity and Intervention Decision System

**Model Name:** Attendance Decision Tree Classifier  
**Framework:** scikit-learn (`DecisionTreeClassifier`)  
**Curriculum Alignment:** CSE276: Artificial Intelligence Foundations — Unit IV (Supervised Learning) & Practical 7  
**Artifact Location:** `src/attendsure/ml/artifacts/attendance_decision_tree.joblib`  
**Date:** November 2026  

---

## 1. Model Details & Objective

- **Model Type:** Supervised Binary Decision Tree Classifier.
- **Intended Purpose:** Classify a single classroom attendance session into:
  - `0`: **Normal** (Typical attendance fluctuation consistent with historical baseline).
  - `1`: **Needs Review** (Statistically unusual attendance pattern warranting educator verification).
- **Core Design Objective:** Transparent decision support to assist rural schoolteachers and administrators in identifying unusual attendance drops or reporting inertia without accusations or punitive penalties.

---

## 2. Feature Engineering (Strictly Non-Leaking & Causal)

Features are computed using only information from the current session and strictly preceding sessions for the same cohort:

| Feature Name | Type | Formula / Definition | Rationale & Predictive Role |
|---|---|---|---|
| `attendance_rate` | float | $(N_{\text{pres}} / N_{\text{exp}}) \times 100$ | Primary indicator of student turnout. |
| `absence_rate` | float | $(N_{\text{abs}} / N_{\text{exp}}) \times 100$ | Complementary attendance measure ($100 - \text{attendance\_rate}$). |
| `baseline_deviation` | float | $\text{median}(r_{t-5..t-1}) - \text{attendance\_rate}$ | Quantifies how far current turnout is below the cohort's usual baseline. Positive values denote drops. |
| `recent_delta_1d` | float | $r_t - r_{t-1}$ | Captures sudden single-day shifts between consecutive school days. |
| `repeated_count_streak` | int | Consecutive run length of identical $N_{\text{pres}}$ | Detects reporting inertia (copy-pasting roll calls). |
| `relative_decline_pct` | float | $\max(0, \frac{\text{median} - r_t}{\text{median}} \times 100)$ | Measures scale-normalized percentage drop relative to the cohort baseline. |

*Leakage Prevention:* Target labels, future attendance days, and downstream alert outcomes are never accessible during feature extraction.

---

## 3. Training & Evaluation Dataset

- **Data Generation:** Independently formulated synthetic attendance generator (`src/attendsure/ml/dataset.py`) simulating rural primary school scenarios:
  - Baseline nominal attendance (82–94%)
  - Mild weather variance (10–15% dip)
  - Severe disruptions (cloudbursts, viral fever: > 30% drop)
  - Reporting inertia (copy-pasting identical count $\ge 4$ days)
  - Gradual multi-day decline
- **Partitioning Strategy:** Group-aware split partitioning classroom cohorts (70% train cohorts / 30% test cohorts), ensuring no cross-cohort leakage.
- **Reproducibility:** Seed fixed at `random_seed = 42`.

---

## 4. Evaluated Performance Metrics (Test Set: 88 Sessions)

Evaluated independently on unseen test cohorts:

| Metric | Measured Score | Evaluation Meaning |
|---|:---:|---|
| **Precision** | **40.0%** (0.4000) | Proportion of ML-flagged sessions that represented genuine simulated anomalies. |
| **Recall (Sensitivity)** | **80.0%** (0.8000) | Proportion of true anomalous sessions successfully flagged by the tree. |
| **Specificity** | **92.8%** (0.9277) | Proportion of normal sessions correctly left unflagged (low false alarm rate). |
| **F1-Score** | **53.3%** (0.5333) | Harmonic mean of precision and recall. |
| **Confusion Matrix** | `TP = 4, FP = 6, TN = 77, FN = 1` | Correctly identified 4 of 5 anomalies while preserving high normal specificity. |

*Honest Reporting:* We do not claim 100% accuracy. The model prioritizes high recall (80%) so unusual patterns are surfaced for educator review, while the decision tree structure allows teachers to immediately inspect why a flag occurred.

---

## 5. Model Interpretability & Tree Rules

The trained decision tree is constrained to `max_depth = 4` and `min_samples_leaf = 4`, producing an interpretable rule structure:
```text
|--- attendance_rate <= 64.50
|   |--- class: 1 (Needs Review)
|--- attendance_rate >  64.50
|   |--- repeated_count_streak <= 1.50
|   |   |--- class: 0 (Normal)
|   |--- repeated_count_streak >  1.50
|   |   |--- attendance_rate <= 83.43
|   |   |   |--- absence_rate <= 18.75
|   |   |   |   |--- class: 1 (Needs Review)
|   |   |   |--- absence_rate >  18.75
|   |   |   |   |--- class: 0 (Normal)
|   |   |--- attendance_rate >  83.43
|   |   |   |--- class: 0 (Normal)
```

---

## 6. Limitations & Ethical Safeguards

1. **Synthetic Data Disclaimer:** The model was trained and evaluated on synthetic scenario distributions. Real-world rural school performance has not been established.
2. **Decision Support, Not Determination:** The model never penalizes or accuses educators. Predictions are framed as neutral pointers for human verification.
3. **Uncertainty Guard:** Predictions with confidence score $< 0.65$ or sessions with fewer than 3 historical days are flagged as `INSUFFICIENT_DATA` or uncertain, prompting teachers to rely on manual checks.

