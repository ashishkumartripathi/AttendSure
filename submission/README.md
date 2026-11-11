# AttendSure: Final Academic Submission Package

**Official Project Title:** Rural School Attendance Integrity and Intervention Decision System  
**Repository:** https://github.com/ashishkumartripathi/AttendSure  
**Branch:** `feature/modern-saas-ui`  
**Project Mentor:** Mr. Hitesh Jangid  

### Student Investigators:
- **Ashish Kumar Tripathi** — Registration No. `12509400` — Roll No. `21`
- **Harsh Jakhar** — Registration No. `12517556` — Roll No. `8`

### Authoritative Problem Statement:
- **Smart India Hackathon 2025 (SIH25012):** *Automated Attendance System for Rural Schools*  
- **Sponsoring Department:** Department of Higher Education, Government of Punjab  
- **Theme:** Smart Education (Software Category)

---

## 1. Deliverable Package Inventory

```text
submission/
├── report/
│   ├── Rural_School_Attendance_System_Final_Report.docx   # 33-section comprehensive academic project report (DOCX)
│   └── Rural_School_Attendance_System_Final_Report.pdf    # High-fidelity native PDF conversion via Microsoft Word COM
├── presentation/
│   ├── Rural_School_Attendance_System_Presentation.pptx   # 16-slide academic presentation deck (16:9 widescreen)
│   └── AttendSure_Presentation_Script.md                 # 10–15 minute slide-by-slide speaker script with viva Q&A
├── demonstration/
│   ├── DEMONSTRATION_GUIDE.md                            # 5–7 minute live evaluation walkthrough with 3-tier fallback
│   ├── generate_demo_dataset.py                          # Independent reproducible dataset generator
│   └── dataset/
│       ├── demo_attendance_sessions.csv                  # 150 synthetic sessions across 5 cohorts over 30 days
│       ├── demo_alerts.csv                               # 6 explainable anomaly detection alerts
│       ├── demo_alert_reviews.csv                        # 3 administrative reviews (Acknowledged, Resolved, Dismissed)
│       └── README.md                                     # Dataset schema, columns, injection rationale, and checksums
├── screenshots/
│   ├── 01_desktop_overview.png                           # Overview Dashboard (Simple KPI cards & daily trend)
│   ├── 02_desktop_mark_attendance.png                    # Mark Attendance (Roll-call entry & invariant checking)
│   ├── 03_desktop_attendance_records.png                 # Attendance Records (Sub-second filtering & pagination)
│   ├── 04_desktop_needs_attention.png                    # Needs Attention Triage (5-field explainable alerts & reviews)
│   ├── 05_desktop_reports.png                            # Reports (Longitudinal cross-cohort aggregations & CSV export)
│   ├── 06_desktop_settings.png                           # Settings (Database health ping, storage stats, diagnostics)
│   ├── 07_public_login_gate.png                          # Institutional Login Gate (PBKDF2-HMAC-SHA256 authentication)
│   ├── 08_public_cloud_overview.png                      # Public Cloud Overview (Neon PostgreSQL live status)
│   ├── 09_teacher_access_restricted.png                  # Role-Based Access Control (Teacher restricted card)
│   ├── 10_mobile_public_portal.png                       # Responsive Mobile Public Portal
│   ├── 11_tablet_overview.png                            # Responsive Tablet Viewport
│   └── 12_mobile_overview.png                            # Responsive Mobile Overview
├── references/
│   ├── sih25012_verification_record.md                   # Authoritative SIH problem statement verification details
│   └── evidence_index.md                                 # Technical evaluation cross-reference index & check constraints
└── README.md                                             # Master package overview, checklist, and reproduction guide
```

---

## 2. Final Verification & Quality Control Checklist

| Verification Item | Requirement Specification | Verification Evidence | Status |
| :--- | :--- | :--- | :---: |
| **DOCX Report Readability** | Formatted with styles, tables, callouts, and embedded figures | 895 KB generated via `python-docx` | **PASS** |
| **PDF Report Fidelity** | Converted via Microsoft Word COM automation | 1.19 MB generated (100% native Word layout) | **PASS** |
| **Presentation Deck (PPTX)**| 16 slides conforming to 16:9 widescreen layout | 273 KB generated via `python-pptx` | **PASS** |
| **Presentation Script** | Slide-by-slide 10–15 min script with viva Q&A | `AttendSure_Presentation_Script.md` (20.9 KB) | **PASS** |
| **Automated Test Suite** | >= 400 unit, integration, and UI tests | **414 of 414 tests passing in 87.32s** | **PASS** |
| **Operational DB Unchanged**| SHA256 matches verified baseline | `46C22853EF5697DFE449FD0D61CFE5E719A84FF5C8260A2BA0F16935ED97F6AE` | **PASS** |
| **Git main Unchanged** | `origin/main` commit remains strictly unaltered | `7324e9e067b7b0d01084b486adc04d0cc0a38c66` | **PASS** |
| **Zero Credentials Committed**| No `.env.local`, API keys, or passwords committed | Checked via `.gitignore` and `git status` | **PASS** |
| **Synthetic Data Tagging** | Every demonstration record explicitly tagged | `record_source='SYNTHETIC'`, isolated from DB | **PASS** |
| **Scientific Disclosures** | Camera benchmark vs real-world classroom reality | Explicitly disclosed across report, slides, and docs | **PASS** |
| **Hardware Boundary** | Clear disclosure of absence of physical RFID | Explicitly documented as software abstraction only | **PASS** |

---

## 3. Key Empirical Findings Summary

```text
Deterministic Rules Benchmark (150 Sessions):
• Accuracy:           96.67% (145 / 150 sessions)
• Precision:          100.00% (6 / 6 alerts; zero false alarms)
• Specificity:        100.00% (139 / 139 nominal sessions)
• Session Recall:     54.55% (6 / 11 injected sessions; 5 FN are pre-threshold prefix sessions)
• Event Recall:       100.00% (2 of 2 multi-day episodes flagged; EVT-CLASS-02-A-1 & EVT-CLASS-05-A-2)

Camera Silhouette Benchmark (Synthetic):
• Clean Silhouettes:  0.00 MAE (Cases 1–5 & 7; 100% zero-error)
• Standard 7 Cases:   0.14 MAE (85.7% zero-error accuracy)
• 9 Numeric Cases:    0.44 MAE (77.8% zero-error accuracy; 0 overcounts, 2 undercounts)
• Degraded Frames:    100% flagged as uncertain (is_uncertain=True)

System Latencies (Live Neon Cloud in AWS Singapore):
• Overview Screen:    343 ms (p50) / 362 ms (p95)
• Records Screen:     158 ms (p50) / 509 ms (p95)
• Settings Screen:    1,017 ms (p50) / 1,265 ms (p95)
• Mark Attendance:    1,034 ms (p50) / 4,141 ms (p95)
• Needs Attention:    2,000 ms (p50) / 2,975 ms (p95) [Slower Screen: triage cards & review forms]
• Reports & Export:   3,684 ms (p50) / 6,901 ms (p95) [Slower Screen: longitudinal aggregations & CSV]
• Network Transit:    ~422 ms baseline physical round-trip to Singapore (ap-southeast-1)
```

---

## 4. Independent Reproduction Instructions

To independently verify every claim, document, and dataset in this package:

```bash
# 1. Clone repository and checkout working branch
git clone https://github.com/ashishkumartripathi/AttendSure.git
cd AttendSure
git checkout feature/modern-saas-ui

# 2. Install dependencies (Python >= 3.13)
pip install -r requirements.txt

# 3. Run complete automated test suite (414 tests)
pytest

# 4. Reproduce machine learning and deterministic rule benchmarks
python scripts/reproduce_benchmarks.py

# 5. Regenerate synthetic demonstration dataset
python submission/demonstration/generate_demo_dataset.py

# 6. Rebuild academic presentation (PPTX)
python scripts/generate_academic_presentation.py

# 7. Rebuild academic report (DOCX & PDF)
python scripts/generate_academic_report.py

# 8. Verify operational database integrity
Get-FileHash -Algorithm SHA256 "data/attendsure.db"
# Expected Hash: 46C22853EF5697DFE449FD0D61CFE5E719A84FF5C8260A2BA0F16935ED97F6AE
```
