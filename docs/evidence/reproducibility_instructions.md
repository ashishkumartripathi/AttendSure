# AttendSure — Reproducibility & Application Startup Guide

**Project Title:** AttendSure: Explainable Attendance Integrity System  
**Document Reference:** `docs/evidence/reproducibility_instructions.md`  
**Milestone:** M5.8 — Final Project Evaluation  

---

## 1. Environment Requirements

- **Python:** Python >= 3.13 (Evaluated under Python 3.13.9)
- **Supported Operating Systems:** Windows 10/11, Linux (Ubuntu 22.04+), macOS (13+)
- **Core Dependencies:**
  ```bash
  pip install -e .
  # Or install individual packages:
  pip install pandas>=2.2.0 streamlit>=1.30.0 pytest>=8.0.0 python-pptx
  ```

---

## 2. Test Suite Verification

Run the full automated test suite:
```powershell
python -m pytest -v
```
**Expected Outcome:**
- Total tests: **328 passed**
- Exit code: **0**
- Duration: **~11 seconds**

---

## 3. Demonstration Database Seeding

To generate the isolated demonstration database without touching operational storage:

```powershell
python scripts/prepare_demo_database.py --dest data/demo_showcase.db --seed 42
```

**Output Verification:**
- Total Sessions: **60**
- Monitored Cohorts: **5** (`CLASS-01-A` to `CLASS-05-E`)
- Total Generated Alerts: **14**
- Operational DB Safety: `DEFAULT_DB_PATH` (`data/attendsure.db`) remains untouched.

---

## 4. Application Startup

### Option A: Launch with Dedicated Demonstration Database (Recommended for Evaluation)

**Windows PowerShell:**
```powershell
$env:ATTENDSURE_DB_PATH="data/demo_showcase.db"; python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

**Linux / macOS Bash:**
```bash
ATTENDSURE_DB_PATH="data/demo_showcase.db" python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

### Option B: Launch with Canonical Operational Database

**Windows PowerShell:**
```powershell
python -m streamlit run src/attendsure/ui/app.py --server.port 8501
```

---

## 5. Health & Browser Verification

1. **Streamlit Health Check:**
   Open a browser or run:
   ```powershell
   curl http://localhost:8501/_stcore/health
   # Expected Response: 200 OK
   ```

2. **Access Application:**
   Navigate to:
   ```
   http://localhost:8501
   ```

3. **Alternative Port Contingency:**
   If port 8501 is occupied, launch on port 8502:
   ```powershell
   $env:ATTENDSURE_DB_PATH="data/demo_showcase.db"; python -m streamlit run src/attendsure/ui/app.py --server.port 8502
   ```

4. **Browser Testing Transparency:**
   In headless automated CI environments where physical browser driver binaries may be restricted by network security policies, UI functionality is verified via Streamlit's official headless test framework (`streamlit.testing.v1.AppTest`), which exercises all 6 screens with zero UI regressions.
