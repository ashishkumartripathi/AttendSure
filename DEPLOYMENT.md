# Production Deployment & Infrastructure Guide

**Official Project Title:** Rural School Attendance Integrity and Intervention Decision System  
**Problem Statement ID:** SIH2025 — SIH25012 (*Automated Attendance System for Rural Schools*)  
**Project Mentor:** Mr. Hitesh Jangid  
**Repository:** `https://github.com/ashishkumartripathi/AttendSure`  
**Current Working Branch:** `feature/modern-saas-ui`  
**Live Public HTTPS URL:** `https://finding-flush-anime-payroll.trycloudflare.com`  

---

## 1. Hosting Architecture & Infrastructure Topology

AttendSure is engineered as an **offline-first, zero-biometrics, decision-support platform** optimized for resource-constrained rural government schools:

```
[ School Tablet / Mobile / Laptop ]
                 │  (TLS 1.3 / HTTPS Edge Routing)
                 ▼
    ┌───────────────────────────┐
    │  Cloudflare Edge Gateway  │ (Public Edge Tunnel via QUIC/HTTP2)
    └─────────────┬─────────────┘
                  │  (Encrypted Tunnel)
                  ▼
    ┌───────────────────────────┐
    │ Streamlit Web Application │ (Python 3.13 + Modern SaaS UI Engine)
    │  - PBKDF2 Authentication  │
    │  - Role Authorization     │
    │  - Decision Support Core  │
    └─────────────┬─────────────┘
                  │  (ACID WAL Mode)
                  ▼
    ┌───────────────────────────┐
    │ Persistent Storage Engine │ (WAL Enabled, Zero-Lock Snapshot Backups)
    │  - production_rumv.db     │
    │  - backups/*.db           │
    │  - dumps/*.sql            │
    └───────────────────────────┘
```

### Architectural Characteristics
1. **Edge SSL/TLS Termination**: Managed by Cloudflare Edge with automatic valid wildcard TLS certificates. Accessible from clean browser sessions, desktop browsers, tablets, and smartphones without port forwarding or VPN requirements.
2. **Offline-Capable Streamlit Core**: High-efficiency Python 3.13 Streamlit runtime operating without outbound external API dependencies or paid LLM tokens.
3. **Persistent Relational Storage**: Local SQLite database with Write-Ahead Logging (`WAL` mode) and busy timeout safeguards, decoupled from ephemeral runtime memory.
4. **Disaster Recovery**: Automated point-in-time snapshot backup (`Connection.backup`) and portable ANSI SQL dumps (`iterdump`).

---

## 2. Persistent Storage Strategy

To resolve cloud dependence on ephemeral storage containers:
- **Write-Ahead Logging (WAL)**: Initialized via `PRAGMA journal_mode = WAL;` and `PRAGMA synchronous = NORMAL;`. Guarantees immediate commit persistence and concurrent read operations without database lock contention.
- **Dedicated Volume Mount**: In cloud container deployments (Render, Fly.io, Railway, Docker), persistent storage is achieved by mounting a persistent block volume to `/app/data` and configuring `ATTENDSURE_DB_PATH=/app/data/production_rumv.db`.
- **Zero Accidental Overwrite**: The production database guard (`is_production_environment()`) strictly prevents demonstration seed scripts (`scripts/prepare_demo_database.py`) from executing against or resetting production records.
- **Verified Durability**: A newly created attendance session, generated anomaly, and educator review note survive complete application restarts and process crashes without data degradation.

---

## 3. Authentication & Authorization Model

AttendSure enforces cryptographic authentication appropriate for institutional school deployment:

### 3.1 Cryptographic Password Hashing
- **Algorithm**: PBKDF2-HMAC-SHA256 with 100,000 iterations and a cryptographically secure 16-byte random salt (`os.urandom(16)`).
- **Format**: `pbkdf2:sha256:100000:<salt_hex>:<hash_hex>`.
- **Timing Protection**: Password verification utilizes `secrets.compare_digest()` for constant-time comparison, neutralizing timing analysis attacks.

### 3.2 Role Separation
| Role | User Account | Authorized Operations | Restricted Operations |
|---|---|---|---|
| **Headmaster / School Administrator** | `headmaster` | Mark Attendance, View Records, Needs Attention (Alert Triage & Resolution), Reports, Settings, Algorithm Laboratory | None (Institutional Superuser) |
| **Classroom Teacher** | `teacher` | Mark Attendance, View Attendance Records, View Attendance Reports | Needs Attention Triage, Anomaly Resolution Notes, Settings Configuration |

### 3.3 Institutional Tenant Context
- Deployments are bound to an explicit rural school institution:
  - **School Name**: *Rajkiya Uchha Madhyamik Vidyalaya*
  - **School Code**: `RUMV-081204`
  - **Location**: Jaipur Rural, Rajasthan

---

## 4. Environment Variables Configuration

All operational secrets and paths are configured via environment variables, avoiding hardcoded secrets in Git:

| Environment Variable | Description | Production Default / Example |
|---|---|---|
| `ATTENDSURE_ENVIRONMENT` | Deployment environment identifier | `production` |
| `ATTENDSURE_IS_PRODUCTION` | Flag enforcing production safety guards | `1` |
| `ATTENDSURE_AUTH_REQUIRED` | Flag requiring login for all pages | `true` |
| `ATTENDSURE_DB_PATH` | Path to persistent SQLite database file | `/app/data/production_rumv.db` |
| `ATTENDSURE_SCHOOL_NAME` | Institutional name of the school | `Rajkiya Uchha Madhyamik Vidyalaya` |
| `ATTENDSURE_SCHOOL_ID` | Official institutional code (UDISE/State) | `RUMV-081204` |
| `ATTENDSURE_ADMIN_USERNAME` | Headmaster administrative username | `headmaster` |
| `ATTENDSURE_ADMIN_PASSWORD` | Headmaster password override | *(Configured securely in hosting secrets)* |
| `ATTENDSURE_TEACHER_USERNAME`| Classroom teacher username | `teacher` |
| `ATTENDSURE_TEACHER_PASSWORD`| Classroom teacher password override | *(Configured securely in hosting secrets)* |
| `ATTENDSURE_ADMIN_NAME` | Display name of Headmaster | `Sh. R. K. Sharma (Headmaster)` |
| `ATTENDSURE_TEACHER_NAME` | Display name of Classroom Teacher | `Smt. Sunita Verma (Teacher)` |

---

## 5. Deployment and Update Procedure

### Option A: Local Edge Cloudflare Tunnel (Active Free Deployment)
1. Launch the persistent Streamlit application:
   ```bash
   export ATTENDSURE_ENVIRONMENT="production"
   export ATTENDSURE_IS_PRODUCTION="1"
   export ATTENDSURE_AUTH_REQUIRED="true"
   export ATTENDSURE_DB_PATH="data/production_rumv.db"
   python -m streamlit run src/attendsure/ui/app.py --server.port 8501 --server.headless true
   ```
2. Launch Cloudflare Tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:8501
   ```
3. Copy the generated `https://*.trycloudflare.com` URL.

### Option B: Container / Render / Docker Deployment
1. Build container image using the included `Dockerfile` or `render.yaml`.
2. Attach a 1 GB persistent block volume at `/app/data`.
3. Set environment variables in the platform's Secret Manager.
4. Set container start command:
   ```bash
   streamlit run src/attendsure/ui/app.py --server.port $PORT --server.headless true
   ```

---

## 6. Database Migration, Backup & Restoration

AttendSure includes built-in persistent database management tools in `src/attendsure/data/db_persistence.py`:

### 6.1 Creating an Online Snapshot Backup
Executes a non-blocking point-in-time snapshot using the SQLite native backup engine:
```python
from attendsure.data.db_persistence import create_database_backup
backup_file = create_database_backup(db_path="data/production_rumv.db")
print("Snapshot saved:", backup_file)
```

### 6.2 Exporting ANSI SQL Dump
Generates portable SQL schema and data export for migration to PostgreSQL or MySQL:
```python
from attendsure.data.db_persistence import export_database_sql_dump
sql_file = export_database_sql_dump(db_path="data/production_rumv.db")
```

### 6.3 Safe Restoration from Backup
Restores database after executing pre-restoration integrity validation (`PRAGMA integrity_check`):
```python
from attendsure.data.db_persistence import restore_database_backup
ok, msg = restore_database_backup(
    backup_path="data/backups/attendsure_backup_20261111_083500.db",
    target_path="data/production_rumv.db"
)
```

---

## 7. Hosting Costs & Financial Disclosure

| Component | Provider / Architecture | Monthly Cost | Academic / Free Tier Details |
|---|---|---|---|
| **Web UI Application Hosting** | Streamlit Core / Cloudflare Tunnel | **$0.00** | Cloudflare Quick Tunnels provide unlimited free edge routing |
| **Edge SSL / TLS Certificate** | Cloudflare Edge Network | **$0.00** | Automatic TLS 1.3 wildcard certificate included |
| **Database Storage** | Persistent SQLite WAL Engine | **$0.00** | Stored locally on persistent disk volume |
| **Compute & Memory** | Standard Host Container (1 CPU, 1 GB RAM) | **$0.00** | Minimal footprint, offline-capable |
| **Total Incurred Cost** | — | **$0.00** | **100% Free / Academic Tier Compliant** |

---

## 8. Known Operational Limitations

1. **Single-School Tenancy**: The current release is architected for single-school institutional governance (`RUMV-081204`). Multi-school district federation will be introduced in future enterprise milestones.
2. **SQLite Single-Writer Concurrency**: While SQLite WAL mode permits thousands of simultaneous readers, write operations (marking attendance) are handled sequentially with a 5000ms busy timeout queue. This is optimal for a rural school with 5–15 classrooms.
3. **Transient Camera Frames**: Classroom webcam analysis processes video frames strictly in ephemeral volatile RAM; classroom images and facial templates are never written to disk, conforming to the zero-biometrics privacy contract.

