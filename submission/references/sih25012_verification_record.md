# Smart India Hackathon (SIH 2025) Problem Statement Verification Record

**Document Identifier:** `REF-SIH25012-VERIFICATION`  
**Date of Verification:** 2026-11-11  
**Verification Method:** Authoritative portal search & government record lookup  

---

## 1. Verified Official Problem Statement Details

The problem statement utilized for the **Rural School Attendance Integrity and Intervention Decision System** has been verified against official Smart India Hackathon records:

| Dimension | Official Authority Record |
| :--- | :--- |
| **Problem Statement ID** | **SIH25012** |
| **Official Title** | **Automated Attendance System for Rural Schools** |
| **Theme** | **Smart Education** |
| **Category** | **Software** |
| **Sponsoring Department** | **Department of Higher Education, Government of Punjab** |
| **Target Operational Context** | Primary and secondary educational institutions in resource-constrained rural areas |
| **Core Problem Mandate** | Develop an automated, low-cost attendance monitoring system suited for rural schools where conventional biometric or internet-dependent methods fail. |

---

## 2. Institutional Alignment & Research Scope

### Problem Mandate vs. AttendSure Implementation

1. **Rural Constraints:**
   - *SIH Mandate:* Hardware and connectivity are severely limited; conventional systems fail.
   - *AttendSure Response:* 100% offline-first execution via local embedded SQLite with zero external API dependencies. Runs on standard laptops or school PCs without specialized servers.

2. **Attendance Verification:**
   - *SIH Mandate:* Automated attendance monitoring to improve administrative transparency.
   - *AttendSure Response:* Multi-signal statistical auditing:
     - Mathematical roll-call count invariant enforcement ($P + A = E$).
     - Rolling drop detection against historical baselines ($Z$-score / percentage drop $\ge 30\%$).
     - Repeated headcount streak detection ($\ge 4$ consecutive days) to capture ledger copying.
     - Ephemeral overhead silhouette contour estimation ($|P - W| \ge 5$) with mandatory teacher confirmation.

3. **Ethical & Child Safeguarding Standards:**
   - *Statutory Alignment:* Digital Personal Data Protection (DPDP) Act of 2023 (Act No. 22 of 2023).
   - *AttendSure Response:* Deliberate exclusion of facial recognition, facial landmark embeddings, and child biometric storage. The atomic unit of data is the **aggregated cohort session count**.

---

## 3. Verification Conclusion

Problem Statement ID **SIH25012** is officially verified as an authentic, recognized Smart India Hackathon challenge sponsored by the Government of Punjab. AttendSure addresses the core technological and operational requirements of this challenge while prioritizing privacy, offline resilience, and explainable decision support.
