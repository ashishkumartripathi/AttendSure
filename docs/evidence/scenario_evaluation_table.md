# AttendSure — Verified Scenario Evaluation & Benchmark Evidence

**Evaluation Date:** October 2026  
**Auditor:** AttendSure Evaluation Engine (`attendsure.evaluation.metrics`)  
**Random Seed:** 42 (Deterministic Reproducibility)  
**Evaluated Horizon:** 15 Days per Single Scenario; 60 Sessions for Compound Showcase  

---

## 1. Verified Benchmark Table

| Scenario | Ground-Truth Definition | Evaluated Observations | Actual Alerts | TP | FP | TN | FN | Precision | Recall | F1-Score | Specificity | Webcam MAE / MAPE | Evaluation Semantics & Limitations |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **NOMINAL** *(Resolved M5.8)* | Strict nominal attendance (no anomalies) | 15 | 0 | 0 | 0 | 15 | 0 | 0.0* | 0.0* | 0.0* | **1.00 (100%)** | N/A | *Zero-division policy: Precision, recall, and F1 default to 0.0 with `zero_division_applied=True` because no positive labels or predictions exist. **Specificity is 100.0% (15/15)**. Accidental 4-day streak resolved in M5.8. |
| **ATTENDANCE_DROP** | 1 sharp drop on day 6 (33% attendance) | 15 | 1 | 1 | 0 | 14 | 0 | **1.00 (100%)** | **1.00 (100%)** | **1.00 (100%)** | 1.00 (100%) | N/A | Alert fired on 2026-10-12 (`RULE_ATTENDANCE_DROP`). Present count: 10/30 (33.33%) vs 5-day rolling median baseline of 27/30 (90.0%). Relative decline: 63.0% >= 30.0%. |
| **REPEATED_HEADCOUNT** | 4-day repeated streak of 25 (days 5–8) | 15 | 1 | 1 | 0 | 11 | 3 | **1.00 (100%)** | **0.25 (25%)*** | **0.40 (40%)** | 1.00 (100%) | N/A | *Session-level recall is 25% because online detector triggers on day 4 ($K \ge 4$). **Event-Level Recall is 1.00 (100.0%)** (1 of 1 event detected on 2026-10-14, 0 false event alarms). |
| **WEBCAM_DISCREPANCY** | 1 discrepancy on day 6 (manual 28 vs cam 20) | 15 | 1 | 1 | 0 | 14 | 0 | **1.00 (100%)** | **1.00 (100%)** | **1.00 (100%)** | 1.00 (100%) | **MAE: 1.20 students**<br>**MAPE: 4.38%** | Discrepancy on 2026-10-12: gap of 8 students (28.6% >= 20.0%). All 15 sessions evaluated under SUCCESS status. Injected gap elevates MAE from 0.71 (tracking noise) to 1.20. |
| **MULTI-COHORT COMPOUND** | 5 cohorts, 12 days each, mixed anomalies | 60 | 14 | 14 | 0 | 46 | 0* | **1.00 (100%)** | **1.00 (100%)*** | **1.00 (100%)** | 1.00 (100%) | **MAE: 1.15 students**<br>**MAPE: 4.12%** | Seeded in `data/demo_showcase.db`. Generated 11 repeated-headcount alerts, 2 attendance drops, and 1 camera discrepancy across classes. |

---

## 2. Deep Dive: Nominal False Positive Audit & Resolution

### Initial Finding in M5.7
When `generate_scenario_sessions("NOMINAL", num_days=15, random_seed=42)` was evaluated, the detection pipeline produced 1 alert:
- Rule: `RULE_REPEATED_HEADCOUNT`
- Date: `2026-10-11`
- Observed: `{'repeated_headcount': 26, 'consecutive_sessions': 4}`

### Audit Investigation in M5.8
1. **Present-Count Sequence Inspection:**
   The exact sequence of present counts generated on seed 42 was:
   `[27, 26, 26, 26, 26, 28, 28, 26, 26, 26, 27, 28, 27, 28, 28]`.
2. **Rule Threshold Analysis:**
   `RULE_REPEATED_HEADCOUNT` threshold is $K \ge 4$ identical counts for sub-100% attendance.
   Days 1, 2, 3, and 4 each reported exactly 26 students out of 30.
   Therefore, the detector's condition ($K \ge 4$) was genuinely met on Day 4.
3. **Detector Correctness Determination:**
   The detector was operating with 100% mathematical fidelity. It was **not** a detector malfunction.
4. **Generator Defect Identification:**
   In `src/attendsure/data/generator.py`, attendance variation was drawn independently via `rng.choice([-1, 0, 1])`. In independent sampling from a 3-element set, the probability of drawing the same element 4 times in a 4-day window is $(1/3)^3 \approx 3.7\%$. Over a 15-day sequence, there is a $\approx 35\%$ chance of an accidental 4-day streak occurring by pure chance. The generator was inadvertently creating an unflagged streak anomaly in a scenario labeled as nominal baseline.
5. **Verified Resolution:**
   Introduced `_sample_nominal_present()` with streak-capping logic. If candidate present count would cause consecutive identical counts to reach $\ge 4$, an alternative delta is chosen to maintain natural variation while guaranteeing streak $< 4$.
6. **Post-Fix Verification:**
   Across 100 random seeds (seeds 0 through 99), `NOMINAL` produces **0 alerts**, yielding a verified **Specificity of 100.0%** and **False Positive Rate of 0.0%**.
