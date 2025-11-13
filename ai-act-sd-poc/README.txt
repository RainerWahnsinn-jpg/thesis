AI Act SD POC – Quick Start (Windows PowerShell)
===============================================

This README shows how to start the prototype locally and generate artefacts. No changes to existing code are required.

Prerequisites
- Windows with PowerShell
- Python 3.10+ available as `py` or `python`

1) Create and activate a virtual environment
-------------------------------------------
# In the project root: c:\Projekte\thesis\ai-act-sd-poc

# Create venv (choose one)
py -m venv .venv
# or
python -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1

2) Install dependencies
-----------------------
# Backend (API)
pip install -r .\backend\requirements.txt

# Oversight UI (optional, for Streamlit app)
pip install -r .\oversight_ui\requirements.txt

3) Start the backend API (standard: Port 8000, feste DB_URL)
-----------------------------------------------------------
# Neues PowerShell-Fenster (empfohlen)
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
cd C:\Projekte\thesis\ai-act-sd-poc\backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000

# Alternativ (aus Projekt-Root, robust für Importe)
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
python -m uvicorn --app-dir .\backend app:app --host 127.0.0.1 --port 8000

# Health check (in einem anderen PowerShell-Fenster)
Invoke-RestMethod -Uri http://127.0.0.1:8000/health | Format-List

# Implemented endpoints in this prototype:
#   POST /v1/credit/decision
#   GET  /health
# (Returns triage is documented but not implemented yet.)

4) Quick smoke test (PowerShell)
--------------------------------
# Sample decision request (matches backend/schemas.CreditRequest)
$body = @{
  order_id           = "ord-001"
  customer_id        = "C-1001"
  order_value_eur    = 52000
  payment_terms_days = 30
  overdue_ratio      = 0.10
  dso_proxy_days     = 32
  risk_class         = "B"        # one of A,B,C,D
  country_risk       = 3           # 1..5
  incoterm           = "DAP"      # EXW,DDP,DAP,FCA,CPT
  is_new_customer    = $true
  credit_limit_eur   = 80000
  past_limit_breach  = $false
  express_flag       = $false
  data_version       = "dv1.0"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/credit/decision `
  -ContentType application/json `
  -Body $body | Format-List

5) Start the Oversight UI (liest nur die DB-Datei)
--------------------------------------------------
# Neues PowerShell-Fenster, venv aktiv
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
cd .\oversight_ui
streamlit run .\app.py

# Hinweis: Der UI ist der API-Port egal – sie liest direkt aus der SQLite-Datei.

5a) REVIEW-Beispielfall erzeugen (Port 8000)
--------------------------------------------
$body = @{
  order_id="R-DEMO-75"; customer_id="C-REVIEW"; order_value_eur=60000;
  payment_terms_days=30; overdue_ratio=0.20; dso_proxy_days=40; risk_class="B";
  country_risk=3; incoterm="EXW"; is_new_customer=$true; credit_limit_eur=50000;
  past_limit_breach=$false; express_flag=$false; data_version="dv1.0"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/credit/decision" -Method Post -ContentType "application/json" -Body $body | Format-List

# Streamlit-Seite reloaden; Toggle „Nur REVIEW-Fälle zeigen“ einschalten.

5b) DB schnell verifizieren
---------------------------
Test-Path C:\Projekte\thesis\ai-act-sd-poc\backend\governance.db
& C:\Projekte\thesis\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect(r'C:\\Projekte\\thesis\\ai-act-sd-poc\\backend\\governance.db'); cur=con.cursor(); cur.execute('SELECT decision, COUNT(*) FROM decision_logs GROUP BY decision'); print(cur.fetchall()); con.close()"

6) Optional: Start auf Port 8010 (falls 8000 belegt)
----------------------------------------------------
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
python -m uvicorn --app-dir .\backend app:app --host 127.0.0.1 --port 8010
Invoke-RestMethod -Uri http://127.0.0.1:8010/health | Format-List

7) Root-DB aufräumen (Konflikte vermeiden)
------------------------------------------
# Prozesse stoppen, dann:
if (Test-Path C:\Projekte\thesis\governance.db) {
  Copy-Item C:\Projekte\thesis\governance.db C:\Projekte\thesis\ai-act-sd-poc\backend\governance.db -Force
  Remove-Item C:\Projekte\thesis\governance.db
}

6) Generate synthetic cases (CSV)
---------------------------------
# Stdlib-only generator (no extra installs)
python .\tools\generate_cases.py
# Outputs:
#   data\synthetic_credit_cases.csv  (>=100 rows)
#   data\synthetic_returns_cases.csv (>=40 rows)
# Use --force to overwrite existing files

7) Compute metrics snapshot (CSV)
---------------------------------
# Uses docs\examples\audit_log_example.jsonl by default
python .\tools\compute_metrics.py --batch demo1
# Output: data\metrics_snapshot.csv
# Optional: python .\tools\compute_metrics.py --log <path-to-jsonl> --out <out.csv>

Notes & Troubleshooting
- .env.example is provided; setting env vars is optional for the prototype.
- If Uvicorn reports "No module named 'backend'", use the robust form with `--app-dir .\backend` as shown above.
- If port 8000 is in use, change the port (e.g., `--port 8010`) and set `$env:BACKEND_URL = "http://127.0.0.1:8010"` for the UI.
- SQLite DB lives at `backend\governance.db`. If locked, close tools that keep it open and retry.
- If Streamlit cannot reach the API, check BACKEND_URL and that the API is listening on 127.0.0.1:8000.
- The audit log in docs/examples is a sample for metrics; the prototype does not write real logs to disk.
- Stop servers with Ctrl+C; deactivate venv with `deactivate`.
