# AttendSure Final Academic Presentation Script (10–15 Minutes)

**Official Project Title:** Rural School Attendance Integrity and Intervention Decision System  
**Repository:** https://github.com/ashishkumartripathi/AttendSure  
**Project Mentor:** Mr. Hitesh Jangid  
**Student Presenters:**  
- Ashish Kumar Tripathi (Registration No. 12509400 — Roll No. 21)  
- Harsh Jakhar (Registration No. 12517556 — Roll No. 8)  
**Problem Statement Reference:** SIH 2025: SIH25012 (*Automated Attendance System for Rural Schools*, Department of Higher Education, Government of Punjab)  

---

## 1. Presentation Structure & Timing Overview

| Slide # | Slide Title | Recommended Timing | Presenter |
| :---: | :--- | :---: | :---: |
| **01** | Title & Project Metadata | 0:00 – 0:45 | Ashish |
| **02** | Problem Context: Rural Attendance Verification Dilemma | 0:45 – 1:30 | Ashish |
| **03** | Official Problem Statement Verification (SIH25012) | 1:30 – 2:15 | Ashish |
| **04** | Proposed Solution: The AttendSure Paradigm | 2:15 – 3:00 | Harsh |
| **05** | System Objectives & Formal Scope Boundaries | 3:00 – 3:45 | Harsh |
| **06** | System Architecture: 4-Tier Decoupled Framework | 3:45 – 4:45 | Harsh |
| **07** | Technology Stack & Engineering Standards | 4:45 – 5:30 | Ashish |
| **08** | Non-Biometric Camera Silhouette Estimation | 5:30 – 6:30 | Ashish |
| **09** | Explainable Anomaly Detection: 3 Production Rules | 6:30 – 7:45 | Harsh |
| **10** | Human-in-the-Loop Review: Decision Support, Never Accusation | 7:45 – 8:45 | Harsh |
| **11** | Application Interface Showcase (Progressive Disclosure) | 8:45 – 9:45 | Ashish |
| **12** | Automated Verification Suite: 414 Tests Passing | 9:45 – 10:45 | Ashish |
| **13** | Anomaly Detection Benchmark Results | 10:45 – 11:45 | Harsh |
| **14** | System Performance & Latency Decomposition | 11:45 – 12:45 | Ashish |
| **15** | Operational Limitations & Scientific Boundaries | 12:45 – 13:45 | Harsh |
| **16** | Conclusion, Team & Academic References | 13:45 – 15:00 | Ashish & Harsh |

---

## 2. Slide-by-Slide Presenter Script & Commentary

### Slide 01: Title & Project Metadata (0:00 – 0:45)
**Presenter: Ashish**
> "Respected faculty evaluator Mr. Hitesh Jangid and examiners, good morning. We are pleased to present our final capstone project: the **Rural School Attendance Integrity and Intervention Decision System**, engineered under the code name **AttendSure**.
> My name is Ashish Kumar Tripathi, alongside my co-investigator Harsh Jakhar.
> Our project addresses Smart India Hackathon problem statement **SIH25012**, sponsored by the Department of Higher Education, Government of Punjab. Our codebase is publicly maintained at `github.com/ashishkumartripathi/AttendSure` on branch `feature/modern-saas-ui`.
> Over the next 14 minutes, we will demonstrate how AttendSure replaces opaque biometric surveillance with an explainable, privacy-preserving, offline-first decision-support platform designed specifically for rural primary and secondary schools."

---

### Slide 02: Problem Context: The Rural Attendance Verification Dilemma (0:45 – 1:30)
**Presenter: Ashish**
> "In developing rural education ecosystems, daily attendance verification is far more than an administrative routine. It directly governs state entitlements: Mid-Day Meal rations under PM POSHAN, per-pupil funding, uniform subsidies, and early dropout interventions.
> However, rural schools face a severe dilemma:
> On one side, paper registers suffer from 'ledger inertia'—busy teachers copying the previous day's attendance—along with manual summation errors and ghost enrollments.
> On the other side, modern technological countermeasures—predominantly fingerprint biometric scanners and facial recognition cameras—have repeatedly collapsed in rural deployments. They suffer from frequent power grid blackouts, high ambient dust, absent internet connectivity, high sensor error rates on children's developing fingerprints, and severe legal risks under the Digital Personal Data Protection Act of 2023 regarding the centralized storage of children's facial templates."

---

### Slide 03: Official Problem Statement Verification (SIH25012) (1:30 – 2:15)
**Presenter: Ashish**
> "To ground our work in verified national priorities, we inspected the official Smart India Hackathon 2025 portal. Problem Statement **SIH25012**, categorized under the Smart Education software theme by the Government of Punjab, calls for an automated, low-cost attendance monitoring system suited for rural schools where conventional biometric or internet-dependent methods fail.
> AttendSure answers this mandate through an appropriate technology approach:
> Rather than forcing high-maintenance biometric hardware into rural classrooms, AttendSure introduces an offline-first statistical decision-support system. It audits daily roll call for consistency, detects temporal anomalies, and performs privacy-safe contour counting—operating strictly on aggregated class counts with zero student personally identifiable information."

---

### Slide 04: Proposed Solution: The AttendSure Paradigm (2:15 – 3:00)
**Presenter: Harsh**
> "The AttendSure paradigm rests on four foundational pillars:
> First, **Offline-First Resilience**: The software requires zero cloud dependencies. It runs directly on a standard school laptop using an embedded SQLite database, delivering sub-second queries even during total network blackouts.
> Second, **Multi-Signal Detection**: We monitor three distinct signals: statistically significant single-day attendance drops relative to historical medians, consecutive identical headcount streaks, and cross-modal discrepancies with overhead silhouette counts.
> Third, **Decision Support, Never Accusation**: Alerts never accuse educators of fraud. An attendance drop often reflects monsoon flooding or crop harvesting. Every alert is framed as a signal for supportive administrative inquiry.
> Fourth, **Strict Child Privacy**: No student names, photos, or facial embeddings exist anywhere in our data model. The atomic unit of data is the anonymous class session count."

---

### Slide 05: System Objectives & Formal Scope Boundaries (3:00 – 3:45)
**Presenter: Harsh**
> "To maintain scientific honesty during academic evaluation, we explicitly distinguish our verified implementation from non-goals:
> In Scope, we have built and verified: explainable rule-based anomaly detection, mathematical count invariant enforcement ($P + A = E$), a four-state human review lifecycle, non-biometric silhouette estimation, and dual-mode database persistence.
> Explicitly Out of Scope:
> - We do **not** implement facial recognition or facial biometric matching.
> - We do **not** claim physical RFID scanner hardware; we provide a clean modular software provider abstraction for future IoT integration.
> - We do **not** claim direct PM POSHAN grain ration tracking.
> - And we do **not** claim a real-world 30-day classroom pilot; our findings are grounded in reproducible synthetic benchmarks and empirical software verification."

---

### Slide 06: System Architecture: 4-Tier Decoupled Framework (3:45 – 4:45)
**Presenter: Harsh**
> "AttendSure follows a decoupled 4-tier architecture:
> At the **Client Tier**, a Streamlit Modern SaaS web application delivers responsive interaction across desktop, tablet, and mobile browsers with zero transition ghosting.
> At the **Application Tier**, our Python 3.13 core validates mathematical invariants, manages user sessions, and operates an in-memory short-TTL read cache.
> At the **Intelligence Tier**, deterministic rule engines and an interpretable CART decision tree evaluate incoming sessions alongside ephemeral contour image processing.
> At the **Persistence Tier**, SQLAlchemy provides a unified abstraction across managed cloud Neon PostgreSQL in production and local embedded SQLite for offline operations.
> Crucially, our database engine strictly enforces production mode: when running in production, it requires managed PostgreSQL and refuses to silently fall back to local SQLite."

---

### Slide 07: Technology Stack & Engineering Standards (4:45 – 5:30)
**Presenter: Ashish**
> "Our engineering choices reflect a commitment to modern, minimal, and dependable dependencies:
> The application runs on Python 3.13.9. The user interface utilizes Streamlit with custom CSS.
> In production, we connect to Neon Managed PostgreSQL 18.6 in AWS Singapore using the modern `psycopg` v3 binary driver and connection pooling.
> Image processing relies on headless OpenCV and Pillow, while machine learning utilizes Scikit-Learn's CART tree.
> Our security layer uses PBKDF2 with HMAC-SHA256, 100,000 iterations, and 16-byte random salts.
> Finally, our quality assurance is powered by `pytest`, achieving 100% pass rates across 414 automated tests in 87 seconds."

---

### Slide 08: Non-Biometric Camera Silhouette Estimation (5:30 – 6:30)
**Presenter: Ashish**
> "Let us examine our camera-assisted roll-call module.
> Rather than capturing facial biometrics, our pipeline processes group silhouette contours:
> In Stage 1, an automated quality gate measures sharpness via discrete Laplacian operator variance, rejecting blurred frames below 100, and evaluates lighting luminance, rejecting frames outside the 40 to 225 range.
> In Stage 2, adaptive Otsu thresholding segments student bodies from background walls and wooden desks in ephemeral memory.
> In Stage 3, connected component contours are filtered by anatomical aspect ratio between 1.2 and 3.5, and bench clusters are normalized using median single-student area.
> In Stage 4, mandatory educator verification is enforced. The estimated count is advisory only. The teacher inspects the count, adjusts it if necessary, and confirms submission.
> Images are processed entirely in RAM (`io.BytesIO`) and purged immediately upon return. No photo files are stored on disk."

---

### Slide 09: Explainable Anomaly Detection Methodology (6:30 – 7:45)
**Presenter: Harsh**
> "At the heart of AttendSure is our deterministic, explainable rule engine comprising three production rules:
> **Rule 1 (Attendance Drop):** Compares today's present count against the cohort's rolling median over the previous 5 sessions. If attendance drops by 30% or more, an alert triggers. This captures acute disruptions like localized flash floods or crop harvesting.
> **Rule 2 (Repeated Headcount):** Detects unnatural streaks where a class reports the exact same present count for 4 or more consecutive school days (extended to 6 days for 100% attendance). This identifies inertial register copying without physical counting.
> **Rule 3 (Camera Discrepancy):** Audits cross-modal consistency. If the manual roll-call differs from the camera silhouette count by 5 or more students, an advisory alert is flagged to verify whether students were outside the classroom or if camera occlusion occurred."

---

### Slide 10: Human-in-the-Loop Review: Decision Support, Never Accusation (7:45 – 8:45)
**Presenter: Harsh**
> "Every alert generated by AttendSure adheres to a mandatory 5-field explainability contract:
> It displays the Rule Identifier, Observed Value, Rolling Baseline Reference, Applied Threshold, and a Plain-Language Rationale.
> The alert then enters a formal administrative state machine:
> It begins as `PENDING_REVIEW`. The Headmaster can transition it to `ACKNOWLEDGED` for on-site inspection, `RESOLVED` when an environmental cause like monsoon rain is confirmed, or `DISMISSED` if a technical false alarm such as window shadow glare occurred.
> Every transition appends the reviewer's identity, timestamp, and qualitative notes to an immutable audit trail. This turns attendance monitoring into an evidence-based intervention tool rather than a punitive weapon."

---

### Slide 11: Application Interface Showcase (8:45 – 9:45)
**Presenter: Ashish**
> "Here we showcase our live application interface, adhering to the principle of Progressive Disclosure across six core screens:
> On the left, the **Overview Screen** presents plain-English KPI cards: Total Enrollment, Present Today, Absent Today, Today's Attendance Rate, and active alerts. If no session has occurred today, it displays an informative banner rather than misleading zeroes or historical aggregates. Below, the Daily Attendance Trend chart visualizes longitudinal patterns.
> On the right, the **Needs Attention Screen** provides an actionable triage queue. Each card expands to reveal the full evidence breakdown, baseline comparison table, and interactive administrative review form.
> The interface is fully responsive, validated across desktop, tablet, and mobile viewports."

---

### Slide 12: Automated Verification Suite: 414 Tests Passing (9:45 – 10:45)
**Presenter: Ashish**
> "Engineering rigor is verified through our automated test suite:
> All **414 automated tests pass in 87.32 seconds** with zero regressions, zero failures, and zero warnings.
> Our tests cover:
> - Cryptographic password hashing and role-based permissions in `test_auth.py`.
> - Mathematical count invariants and check constraints in `test_data_validation.py`.
> - Connection pooling, transaction rollback, and production mode enforcement in `test_db_engine.py`.
> - Rule detection accuracy, rolling baselines, and cross-modal checks across 49 detection tests.
> - And over 70 headless UI integration tests using Streamlit's `AppTest` harness."

---

### Slide 13: Anomaly Detection Benchmark Results (10:45 – 11:45)
**Presenter: Harsh**
> "Let us examine our empirical benchmark results:
> In the deterministic rules evaluation over 150 synthetic sessions with a 5.0% anomaly injection rate:
> - Overall classification accuracy is **96.67%** (145 of 150 sessions).
> - Precision is a perfect **100.00%** (6 of 6 alerts triggered; zero false alarms).
> - Specificity is **100.00%** (139 of 139 nominal sessions unflagged).
> - Session-level recall is **54.55%** (6 of 11 positive sessions).
> - Event-level recall is **100.00%** (2 of 2 multi-day episodes flagged).
> Crucially, the 54.55% session recall is an intentional mathematical characteristic of the repeated headcount detector: on a 4-day repeated streak, Days 1, 2, and 3 accumulate history. On Day 4, the alert fires. Thus, at the session level recall is 25% for that episode, but at the event level, the episode is detected with 100% reliability before it concludes."

---

### Slide 14: System Performance & Latency Decomposition (11:45 – 12:45)
**Presenter: Ashish**
> "We conducted rigorous latency measurements against our live cloud deployment connected to Neon PostgreSQL in AWS Singapore:
> - Overview renders in **343 ms** (p50).
> - Attendance Records renders in **158 ms** (p50).
> - Settings renders in **1,017 ms** (p50).
> - Mark Attendance renders in **1,034 ms** (p50).
> In the interest of scientific honesty, we explicitly identify our two slower screens that exceed the 2-second target:
> - **Needs Attention** takes **2,000 ms** (p50) / 2,975 ms (p95) due to rendering expandable triage cards, HTML evidence blocks, and audit review forms.
> - **Reports & Export** takes **3,684 ms** (p50) / 6,901 ms (p95) due to on-the-fly cross-cohort aggregations and pre-generating the downloadable CSV buffer.
> Physical network round-trip transit from India to Singapore accounts for ~422 ms baseline latency, mitigated by our short-TTL in-memory read cache."

---

### Slide 15: Operational Limitations & Scientific Boundaries (12:45 – 13:45)
**Presenter: Harsh**
> "During academic evaluation, we must honestly disclose system limitations:
> 1. **Camera Silhouette Real-World Boundary:** While our contour estimator achieves 0.14 MAE on synthetic silhouettes, real rural classrooms have harsh sunlight glare, clothing shadows, and crowded benches. Synthetic testing does not equal field accuracy; teacher confirmation is mandatory.
> 2. **Absence of Physical RFID Hardware:** We have built a clean modular software provider interface, but no physical RFID scanners were deployed.
> 3. **No Student-Level Tracking:** AttendSure tracks cohort numbers, not individual student names. This is an intentional ethical trade-off to protect child privacy.
> 4. **Cloud Network Latency:** Hosting the database in Singapore introduces ~420 ms of physical network transit, requiring local caching."

---

### Slide 16: Conclusion, Team & Academic References (13:45 – 15:00)
**Presenter: Ashish & Harsh**
> "In conclusion, AttendSure proves that school attendance integrity can be safeguarded ethically, affordably, and dependably without resorting to child biometric surveillance or costly hardware.
> With 414 passing tests, 96.67% rule accuracy, 100% precision, sub-second queries, and a live cloud deployment backed by serverless PostgreSQL, the system is technically verified and demonstration-ready.
> We express our sincere gratitude to our project mentor, **Mr. Hitesh Jangid**, for his guidance throughout this project.
> We now invite questions from the examiners. Thank you."

---

## 3. Anticipated Viva Questions & Examiner Objections

### Q1: Why did you not implement facial recognition? Isn't that the standard AI approach today?
**Answer (Ashish):**
> "Facial recognition was deliberately excluded due to three critical factors:
> 1. **Legal & Ethical Compliance:** Under India's Digital Personal Data Protection (DPDP) Act of 2023, collecting and centrally storing biometric data of minors requires strict parental consent and carries severe liabilities during data breaches.
> 2. **Infrastructure Failure:** Rural schools lack the high-resolution cameras, GPUs, stable electricity, and continuous high-speed internet needed for real-time facial recognition.
> 3. **Adversarial Teacher Demoralization:** Facial surveillance frames teachers and young students as adversaries. AttendSure audits attendance integrity via cohort statistical consistency and non-biometric silhouette counting, protecting child privacy while achieving administrative accountability."

### Q2: Why is your session-level recall 54.55% for the deterministic rules? Isn't that low?
**Answer (Harsh):**
> "Session-level recall of 54.55% is a mathematical artifact of chronological streak detection.
> In our benchmark, 7 of the 11 injected anomaly sessions belong to two 4-day repeated headcount episodes (`EVT-CLASS-02-A-1` and `EVT-CLASS-05-A-2`).
> The detector requires 4 consecutive identical days before triggering. Days 1, 2, and 3 are pre-threshold prefix sessions. Firing an alert on Day 1 or Day 2 would cause massive false alarms on normal stable attendance.
> When the streak reaches Day 4, the alert fires. Thus, at the individual session level, recall is 25% for that episode, but at the **event level**, **100% of multi-day episodes (2 of 2) are successfully flagged for administrative intervention**."

### Q3: What happens if the school has no internet for 3 weeks?
**Answer (Ashish):**
> "AttendSure is architected offline-first. When offline, the application runs entirely on the local machine using an embedded SQLite database (`data/attendsure.db`).
> Roll-call entry, count invariant validation, local camera silhouette estimation, and anomaly detection rules execute with zero external network calls.
> When internet connectivity is restored, records can be synced to cloud PostgreSQL or exported as sanitized CSV files for block educational officers."

### Q4: What is your camera module's Mean Absolute Error, and what are its limits?
**Answer (Harsh):**
> "On clean synthetic silhouettes (1 to 5 students), our contour estimator achieves an MAE of **0.00**. Across all 7 standard benchmark cases, MAE is **0.14** with **85.7%** zero-error accuracy. Across all 9 numeric cases including degraded frames, MAE is **0.44**.
> However, we explicitly disclose that this is a **synthetic benchmark**. Real classrooms have overlapping students, uneven sunlight, and textured backgrounds. Therefore, our system enforces a mandatory human-in-the-loop gate: the camera count is strictly advisory, and the teacher must visually verify and confirm the count before commitment."

### Q5: How do you prevent SQL injection and transaction corruption?
**Answer (Ashish):**
> "We utilize SQLAlchemy Core and ORM with parameterized queries across both PostgreSQL and SQLite, eliminating raw SQL string concatenation.
> Furthermore, the database schema enforces 6 relational check constraints: enrollments must be $\ge 1$, present and absent counts must be non-negative, and the sum invariant $P + A = E$ is verified at the database engine level.
> In our automated tests (`test_db_engine.py`), we verified transactional atomicity: when an invalid session is inserted in a batch, the entire transaction rolls back cleanly, leaving zero corrupted records."
