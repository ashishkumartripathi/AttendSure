# NFC / RFID Integration Scope & Feasibility Analysis
## Rural School Attendance Integrity and Intervention Decision System

**Document Version:** 1.0  
**Status:** Deferred Hardware Scope  
**Course Context:** CSE276 Artificial Intelligence Foundations Capstone  

---

## 1. Executive Summary

This document specifies the technical architecture, hardware requirements, deployment considerations, and architectural hooks for contactless Near-Field Communication (NFC) / Radio-Frequency Identification (RFID) attendance logging in the **Rural School Attendance Integrity and Intervention Decision System**.

Physical NFC/RFID reader hardware is **formally deferred** from the initial operational prototype. The software architecture, data models, repository interfaces, and anomaly detection pipelines have been engineered with forward-compatible schema hooks to accommodate contactless ingestion without structural modification.

---

## 2. Hardware Feasibility and Rural Deployment Constraints

### 2.1 Why Physical NFC/RFID Is Deferred

While contactless smart cards provide frictionless logging in well-funded urban institutions, field assessment of rural primary school environments highlights severe operational constraints:

| Evaluation Dimension | Operational Reality in Rural Primary Schools | Impact on System Viability |
| :--- | :--- | :--- |
| **Card Retention & Wear** | Primary students (ages 5–11) frequently lose, damage, swap, or forget passive smart cards. | High card replacement overhead exceeding annual school operational budgets. |
| **Hardware Procurement** | Dedicated USB or GPIO RFID readers require consistent driver support, protective enclosures, and local vendor sourcing. | Risk of single-point hardware failure rendering roll-call impossible. |
| **Power & Continuity** | Rural schools frequently experience brownouts or lack dedicated computer labs in every classroom. | Battery-backed mobile or offline tablet interfaces are significantly more resilient. |
| **Proxy Attendance** | A card can be tapped by a peer without physical presence ("buddy-punching"). | Contactless scanning alone does not guarantee physical classroom presence without visual verification. |

### 2.2 Decision

Manual roll-call by the class educator paired with **visual photo confirmation** (`st.camera_input`) provides high accountability, zero hardware consumable cost, and immediate explainability. NFC/RFID is treated as an optional high-throughput hardware accelerator for institutions with existing smart card infrastructure.

---

## 3. Recommended Hardware Specifications for Future Integration

When physical NFC/RFID infrastructure is deployed, the following specifications are required for compatibility:

### 3.1 Reader Hardware Specifications
- **Frequency Band:** 13.56 MHz High Frequency (HF).
- **Standards Compliance:** ISO/IEC 14443 Type A / MIFARE Classic 1K or NTAG213/215/216.
- **Recommended Interface Modules:**
  - **Embedded / Single-Board:** NXP PN532 (I2C / SPI / UART) or MFRC522 (SPI).
  - **Desktop / USB Station:** ACR122U USB Contactless Smart Card Reader (CCID compliant, PC/SC driverless on Linux/Windows).
- **Read Range:** 20 mm to 50 mm (prevents accidental collision from adjacent queues).
- **Operating Temperature:** -10°C to +55°C (rural non-climate-controlled classroom tolerance).

### 3.2 Transponder / Tag Specifications
- **Form Factor:** Heavy-duty ABS keyfobs or laminated PVC student ID cards with reinforced eyelets.
- **Memory Structure:** Read-only Unique Identifier (UID) (4-byte or 7-byte).
- **Durability:** IP67 water/dust resistance rating.

---

## 4. Software Architecture and Extensible Schema Hooks

The system's data contracts (`docs/data-contract.md`) and database schema are already designed to ingest NFC records without migration.

### 4.1 Schema Compatibility

In SQLite and the `SessionRecord` data model:
- `record_source`: An extensible string field. The system currently accepts:
  - `MANUAL_ENTRY`
  - `CSV_IMPORT`
  - `NFC_SCAN` *(forward-compatible identifier)*
  - `HYBRID_VERIFIED`

When an NFC reader station logs a batch of student taps:
1. The local station aggregates the card taps for a given `class_id` and `session_date`.
2. The count of unique valid card taps becomes the `present_count`.
3. The derived `absent_count` is computed as `expected_enrollment - present_count`.
4. The record is persisted with `record_source="NFC_SCAN"`.

```python
# Forward-compatible SessionRecord construction for NFC logging
nfc_session = SessionRecord(
    session_id=str(uuid.uuid4()),
    class_id="CLASS-03-A",
    session_date="2026-11-03",
    expected_enrollment=32,
    present_count=29,
    absent_count=3,
    webcam_status="NOT_ATTEMPTED",
    webcam_count=None,
    record_source="NFC_SCAN",
    created_at=datetime.now(timezone.utc).isoformat(),
)
```

### 4.2 Local UID-to-Cohort Mapping (Zero PII Guarantee)

To preserve the zero personally identifiable information (Zero-PII) guarantee:
- Individual student names, birthdates, and residential addresses are **never stored** in the database.
- The NFC service maps card UIDs to internal pseudonymous tokens:
  $$\text{Card UID} \xrightarrow{\text{SHA-256 + School Salt}} \text{Student Token} \in \text{Cohort ID}$$
- The operational database only receives aggregate counts per cohort session, ensuring full compliance with child data privacy guidelines.

### 4.3 Anomaly Detection Compatibility

NFC-generated records flow directly into the anomaly detection pipeline and the Machine Learning Decision Tree:
- **Rule Attendance Drop:** Flags sudden drops in card-tap attendance compared to historical rolling baselines.
- **Rule Repeated Headcount:** Flags identical card tap counts across consecutive days (potential automated replay or stagnant register).
- **ML Decision Tree:** Extracts feature vectors (`attendance_rate`, `absence_rate`, `baseline_deviation`, `recent_delta_1d`, `repeated_count_streak`, `relative_decline_pct`) identically regardless of whether `record_source` is `MANUAL_ENTRY` or `NFC_SCAN`.

---

## 5. Implementation Roadmap for NFC Hardware Integration

1. **Hardware Driver Integration (Phase Next.1):** Integrate `pyscard` (PC/SC interface) or `nfcpy` Python drivers.
2. **Offline Reader Daemon (Phase Next.2):** Background service that listens for card taps, sounds an audio buzzer, and buffers timestamps locally in an offline SQLite queue.
3. **Roll-Call Finalizer (Phase Next.3):** Teacher interface that displays scanned count and allows the teacher to review and commit the finalized headcount with a single tap.

