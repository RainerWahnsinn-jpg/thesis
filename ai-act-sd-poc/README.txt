AI Act SD POC – Quick Start (Windows PowerShell)
===============================================

This README shows how to start the prototype locally and generate artefacts. No changes to existing code are required.

Schnellstart – Backend & UI
---------------------------
1. Backend starten
  ```powershell
  cd C:\Projekte\thesis\ai-act-sd-poc
  .\.venv\Scripts\Activate.ps1
  $env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
  # Optional: Token-Rollen setzen, z. B. nur für Admin-Test
  # $env:TOKENS_JSON='{"reviewer@rittal":"reviewer","admin@rittal":"admin"}'
  python -m uvicorn --app-dir .\backend app:app --host 127.0.0.1 --port 8000
  ```

2. Oversight-UI starten (neues Fenster, gleiches venv)
  ```powershell
  cd C:\Projekte\thesis\ai-act-sd-poc
  .\.venv\Scripts\Activate.ps1
  $env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
  streamlit run .\oversight_ui\app.py
  ```

  Danach im Browser oben links mit einem gültigen Token anmelden (z. B. `admin@rittal` falls in TOKENS_JSON gesetzt).

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
# Auth-Secret setzen (Sprint 5; entweder JSON direkt oder Datei)
# Beispiel JSON direkt:
# $env:TOKENS_JSON='{"reviewer@rittal":"reviewer","admin@rittal":"admin"}'
# oder per Datei außerhalb des Repos:
# $env:TOKENS_FILE='C:\\Secrets\\thesis_tokens.json'
# Strenger Modus (ohne Secret fehlschlagen):
# $env:STRICT_AUTH='1'
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

frontend

C:\Projekte\thesis\.venv\Scripts\Activate.ps1
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
cd C:\Projekte\thesis\ai-act-sd-poc\oversight_ui
streamlit run app.py


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

5) Start the Oversight UI (Login erforderlich)
--------------------------------------------------
# Neues PowerShell-Fenster, venv aktiv
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
cd .\oversight_ui
streamlit run .\app.py

# Hinweis:
# - Nach dem Start oben rechts mit Token anmelden, sonst werden keine Daten angezeigt.
#   Tokens kommen aus $env:TOKENS_JSON oder $env:TOKENS_FILE (siehe Schritt 3).
# - UI liest die Daten direkt aus der SQLite-Datei (DB_URL). Für Login/Overrides
#   spricht sie das Backend unter http://127.0.0.1:8000 an. Läuft das Backend auf
#   einem anderen Port, setze z. B. $env:BACKEND_URL = "http://127.0.0.1:8010".

5a) REVIEW-Beispielfall erzeugen (Port 8000)
--------------------------------------------
$body = @{
  order_id="R-DEMO-75"; customer_id="C-REVIEW"; order_value_eur=60000;
  payment_terms_days=30; overdue_ratio=0.20; dso_proxy_days=40; risk_class="B";
  country_risk=3; incoterm="EXW"; is_new_customer=$true; credit_limit_eur=50000;
  past_limit_breach=$false; express_flag=$false; data_version="dv1.0"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/credit/decision" -Method Post -ContentType "application/json" -Body $body | Format-List

# Streamlit-Seite reloaden; oben rechts anmelden; Toggle „Nur REVIEW-Fälle zeigen“ einschalten.

5b) DB schnell verifizieren
---------------------------
Test-Path C:\Projekte\thesis\ai-act-sd-poc\backend\governance.db
& C:\Projekte\thesis\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect(r'C:\\Projekte\\thesis\\ai-act-sd-poc\\backend\\governance.db'); cur=con.cursor(); cur.execute('SELECT decision, COUNT(*) FROM decision_logs GROUP BY decision'); print(cur.fetchall()); con.close()"

6) Optional: Start auf Port 8010 (falls 8000 belegt)
----------------------------------------------------
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
python -m uvicorn --app-dir .\backend app:app --host 127.0.0.1 --port 8010
Invoke-RestMethod -Uri http://127.0.0.1:8010/health | Format-List

6a) Optional: HTTPS-Proxy via stunnel (lokal)
--------------------------------------------
# In tools\tls siehe README_TLS.txt. Beispiel mit OpenSSL-Zertifikat:
# 1) cd .\tools\tls
# 2) openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
# 3) stunnel stunnel.conf
# API dann unter https://localhost:8443 erreichbar
# UI auf HTTPS zeigen:
#   $env:BACKEND_URL = "https://localhost:8443"

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
- Rate-Limit: Standard 5 req/s (Burst 10). Anpassbar via RATE_LIMIT_RATE/RATE_LIMIT_BURST.
- Body-Limit: Standard 64KB. Anpassbar via MAX_BODY_BYTES.
- Audit-Trail: decision_logs ist append-only (UPDATE/DELETE blockiert). prev_hash/row_hash bilden eine Hash-Kette.
- Export: python .\tools\export_log.py --from <ISO>Z --to <ISO>Z --out data\export.csv
- The audit log in docs/examples is a sample for metrics; the prototype does not write real logs to disk.
- Stop servers with Ctrl+C; deactivate venv with `deactivate`.
