# AttendSure — Deployment Guide & Infrastructure Strategy

This document details the public deployment options, architecture, persistent storage characteristics, and operational safety protocols for **AttendSure: An Explainable Attendance Integrity and Anomaly Detection System for Rural Schools**.

---

## 1. Hosting Platform Evaluation Matrix

| Criterion | Streamlit Community Cloud (Recommended) | Render (Web Service) | Railway (Service + Volume) |
|---|---|---|---|
| **Cost** | **$0 / Free** (Included with GitHub) | Free Tier ($0) / Paid with Disk ($7+/mo) | Usage-based ($5 credit, then ~$5–10/mo) |
| **Ease of Deployment** | **Zero-Config** (Connect GitHub repo, point to `src/attendsure/ui/app.py`) | Low (Requires `render.yaml` or build/start commands) | Low (Requires Railway CLI or web dashboard Docker/Nixpacks) |
| **Python & Streamlit Compatibility** | **Native** (Maintained directly by Streamlit / Snowflake) | High (Supports Python 3.11–3.13 via buildpack) | High (Auto-detects Python and runs virtualenv) |
| **Persistent Storage** | **Ephemeral** (Filesystem resets on container restart/idle sleep) | **Ephemeral on Free Tier** (Persistent disk requires paid plan) | **Persistent Volume** (Configurable volume mount at `/data`) |
| **SQLite Support** | Full local file support during active session | Full local file support during active session | Full file support across restarts with volume |
| **Sleep / Wake Behaviour** | Sleeps after inactivity; wakes automatically on web request (10–20s) | Spins down after 15 min inactivity; wakes on HTTP request (30–50s) | Always on until credits deplete |
| **Resource Limits** | 1 GB RAM, 1 CPU (sufficient for AttendSure) | 512 MB RAM, 0.1 CPU on Free tier | 512 MB – 8 GB scalable |
| **Access Control** | Public or restricted by GitHub account | Public URL (`*.onrender.com`) | Public URL (`*.up.railway.app`) |
| **Academic Demo Suitability** | **Highest** (Clean, fast, officially branded, zero maintenance) | Medium (Cold-start latency of 50s on free tier) | Medium (Trial credit expiration risk) |

---

## 2. Recommended Deployment Strategy

### Primary Recommendation: Streamlit Community Cloud (Free Tier)
For academic college evaluations, capstone showcases, and viva examinations:
- **Cost**: **$0.00**.
- **Rationale**: AttendSure is built with Streamlit. Streamlit Community Cloud natively provisions and monitors the app directly from the GitHub repository (`ashishkumartripathi/AttendSure.git`).
- **Data Strategy**: Ephemeral storage is completely acceptable for academic demonstrations because:
  1. The operational database (`data/attendsure.db`) contains sensitive baseline data and must **never** be deployed publicly.
  2. The application includes a self-contained demonstration seed (`scripts/prepare_demo_database.py`) and pre-packaged synthetic datasets in `src/attendsure/data/generator.py` for testing scenarios.
  3. Evaluators can create, test, and triage live records in real time without persisting synthetic student counts indefinitely.

> [!WARNING]
> **Storage Architecture Disclosure**:
> Streamlit Community Cloud runs within an ephemeral container filesystem. Local SQLite database writes do **NOT** persist across container rebuilds or idle sleep cycles. Any attendance records created during a demo session are temporary. This is safe and appropriate for capstone demonstrations, but examiners should be informed that production multi-month persistence requires a dedicated persistent volume.

### Alternative Option: Render with Persistent Disk (Paid Tier)
If the evaluating panel strictly requires that records saved today remain saved next month across server restarts:
- **Provider**: Render.com Web Service (`Starter` Plan + 1 GB Persistent Disk).
- **Cost**: ~$7/month (Base) + $0.25/GB/month (Persistent Disk).
- **Mount Path**: Mount persistent disk to `/var/data` and configure `ATTENDSURE_DB_PATH="/var/data/attendsure_prod.db"`.
- *Note*: Requires explicit user payment authorization before provisioning.

---

## 3. Data Safety & Privacy Isolation Protocols

1. **Zero Deployment of Operational Database**:
   - `data/attendsure.db` is strictly untracked by `.gitignore`.
   - The deployment workflow strictly forbids uploading, committing, or scp-transferring `data/attendsure.db`.
2. **Dedicated Demonstration Data**:
   - The public app runs against a dedicated demonstration database initialized from `scripts/prepare_demo_database.py` with `random_seed=42`.
   - Every record in the demo database is stamped with `record_source='SYNTHETIC'`.
3. **Zero Personally Identifiable Information (PII)**:
   - AttendSure stores only cohort-level counts (`class_id`, `expected_enrollment`, `present_count`, `absent_count`).
   - No student names, admission numbers, biometric facial scans, or photos are ever collected, processed, or persisted.
4. **No Secrets in Repository**:
   - AttendSure operates completely offline with zero external cloud API keys, LLM tokens, or third-party database credentials.
   - The repository requires no `.env` file for core anomaly detection.

---

## 4. Step-by-Step Deployment Instructions

### Option A: Deploying to Streamlit Community Cloud (Step-by-Step)

1. **Prerequisites**:
   - GitHub repository: `https://github.com/ashishkumartripathi/AttendSure.git`
   - Active branch: `feature/attendsure-m5.4-evaluation` (or merged release branch).
2. **Account Sign-In**:
   - Navigate to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
3. **New App Creation**:
   - Click **Create App** > **I already have an app**.
   - **Repository**: `ashishkumartripathi/AttendSure`
   - **Branch**: `feature/attendsure-m5.4-evaluation`
   - **Main file path**: `src/attendsure/ui/app.py`
   - **App URL**: Custom slug (e.g., `attendsure-rural-demo.streamlit.app`)
4. **Advanced Settings (Optional Environment Variables)**:
   - Click **Advanced settings**.
   - Under **Environment variables (Secrets)**, add:
     ```toml
     ATTENDSURE_DB_PATH = "data/demo_showcase.db"
     ```
5. **Deploy**:
   - Click **Deploy!**. Streamlit builds the environment using `requirements.txt` and launches the application within 2 minutes.

---

## 5. Linux Compatibility & Path Verification

AttendSure was developed with multi-platform POSIX and Windows compatibility:
- **Path Handling**: All filesystem paths use `pathlib.Path` with forward-slash / OS-agnostic separators.
- **SQLite Concurrency**: Connects via `sqlite3.connect(..., timeout=30.0)` with WAL mode support.
- **Terminal Execution**: Validated with standard POSIX commands:
  ```bash
  pip install -r requirements.txt
  pip install -e .
  python -m streamlit run src/attendsure/ui/app.py --server.port 8501 --server.headless true
  ```

---

## 6. Offline Demonstration Fallback Plan

If internet connectivity fails during the college presentation:
1. **Local Daemon Command**:
   ```powershell
   $env:ATTENDSURE_DB_PATH="data/demo_showcase.db"; python -m streamlit run src/attendsure/ui/app.py --server.port 8501 --server.headless true
   ```
2. **Browser Access**: Open `http://localhost:8501`.
3. **Fallback Assets**: Have `AttendSure_Final_Presentation.pptx` and the 6 high-resolution screen PNGs ready in `docs/evidence/` as offline visual backup.

