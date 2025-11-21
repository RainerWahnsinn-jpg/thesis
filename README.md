AI Act SD POC – Quick Start (Windows PowerShell)
================================================

Prototype for credit-decision oversight (FastAPI backend + Streamlit UI). This guide explains how to run the stack, exercise demo flows, and export artefacts on Windows PowerShell.

1. Overview
-----------
- **Backend (FastAPI)**: deterministic `/v1/credit/decision`, `/v1/credit/override`, `/v1/auth/login`, `/health`; data persisted in `backend/governance.db` (SQLite).
- **Oversight UI (Streamlit)**: tabs for Review Queue, Audit Logs, Scores & Metrics, API Input; supports login via token, override workflow incl. Vier-Augen-Check, classifier CSV upload, audit snapshot view.
- **Tooling**: CLI helpers for audit export/verify, classifier metrics, synthetic case generation, metrics snapshots.

2. Requirements
---------------
- Windows PowerShell 5.1+ (oder Windows Terminal mit PowerShell-Profil).
- Python 3.10+ erreichbar als `py` oder `python`.
- Repo liegt unter `C:\Projekte\thesis\ai-act-sd-poc`.

Optional: `stunnel`, `openssl` (nur für HTTPS-Proxy nötig).

3. Environment Setup
--------------------
```powershell
cd C:\Projekte\thesis\ai-act-sd-poc
py -m venv .venv   # oder: python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Install dependencies (first run only):
```powershell
pip install -r .\backend\requirements.txt
pip install -r .\oversight_ui\requirements.txt
```

4. Shared Environment Variables
--------------------------------
```powershell
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
# Optional Tokens (Fallback Demo: reviewer@rittal / admin@rittal)
# $env:TOKENS_JSON='{"reviewer@rittal":"reviewer","admin@rittal":"admin"}'
# oder Datei:
# $env:TOKENS_FILE='C:\Secrets\thesis_tokens.json'
# Strenger Modus (ohne Token kein Start):
# $env:STRICT_AUTH='1'
```
Falls Backend auf anderem Port läuft, UI darauf zeigen:
```powershell
$env:BACKEND_URL = "http://127.0.0.1:8010"
```

5. Start Backend API
--------------------
```powershell
# neues PowerShell-Fenster, venv aktiv
cd C:\Projekte\thesis\ai-act-sd-poc
.\.venv\Scripts\Activate.ps1
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
python -m uvicorn --app-dir .\backend app:app --host 127.0.0.1 --port 8000
```
Health check:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health | Format-List
```
Exposed endpoints:
- `POST /v1/credit/decision`
- `POST /v1/credit/override`
- `POST /v1/auth/login`
- `GET /health`

6. Start Oversight UI
---------------------
```powershell
# separates Fenster, gleiches venv
cd C:\Projekte\thesis\ai-act-sd-poc
.\.venv\Scripts\Activate.ps1
$env:DB_URL = "sqlite:///C:/Projekte/thesis/ai-act-sd-poc/backend/governance.db"
# optional $env:BACKEND_URL setzen (siehe oben)
streamlit run .\oversight_ui\app.py
```
Nach dem Start rechts oben mit Token anmelden. UI liest direkt aus der SQLite-DB; Login & Overrides nutzen das Backend.

Tabs im UI:
1. **Review Queue** – Filter, Zeitachse, Tabelle, Detailpanel mit Override-Workflow.
2. **Audit Logs** – Inline-Ansicht der CSV `data/abb_6_1_decision_logs.csv` inkl. Ja/Nein-Spalten.
3. **Scores & Metrics** – Klassifikator-Upload (CSV), Confusion Matrix, Calibration, Governance-KPIs.
4. **API Input** – Request-Body + Thresholds für den aktiven Fall (Baukasten für API-Handover).

7. Demo Actions
---------------
### 7.1 Decision request (smoke)
```powershell
$body = @{
  order_id="ord-001"; customer_id="C-1001"; order_value_eur=52000;
  payment_terms_days=30; overdue_ratio=0.10; dso_proxy_days=32; risk_class="B";
  country_risk=3; incoterm="DAP"; is_new_customer=$true; credit_limit_eur=80000;
  past_limit_breach=$false; express_flag=$false; data_version="dv1.0"
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/credit/decision -Method Post -ContentType "application/json" -Body $body | Format-List
```

### 7.2 REVIEW-Demo erzeugen
```powershell
$body = @{
  order_id="R-DEMO-75"; customer_id="C-REVIEW"; order_value_eur=60000;
  payment_terms_days=30; overdue_ratio=0.24; dso_proxy_days=45; risk_class="B";
  country_risk=3; incoterm="EXW"; is_new_customer=$true; credit_limit_eur=50000;
  past_limit_breach=$false; express_flag=$false; data_version="dv1.0"
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/credit/decision -Method Post -ContentType "application/json" -Body $body | Format-List
```
UI neu laden, einloggen, Toggle „Nur REVIEW-Fälle“ aktivieren.

### 7.3 Override & Vier-Augen
- Override-Button erscheint nur für offene Review-Basisfälle.
- Vier-Augen-Grenzen: `order_value_eur >= 50000` **oder** `country_risk >= 4` ⇒ Admin-Token erforderlich.
- POST `/v1/credit/override` wird mit `X-Auth-Token` aus dem Login ausgeführt.

### 7.4 Audit exportieren
```powershell
cd C:\Projekte\thesis\ai-act-sd-poc
python .\tools\export_log.py --out .\data\abb_6_1_decision_logs.csv
```
UI-Sidebar zeigt danach „CSV geladen“ und bietet Download.

8. Tooling Reference
--------------------
| Zweck | Command |
| --- | --- |
| Export Audit CSV | `python .\tools\export_log.py --from 2025-01-01T00:00:00Z --to 2099-12-31T23:59:59Z --out .\docs\exports\audit_export.csv` |
| Audit verifizieren (DB) | `${workspaceFolder}\.venv\Scripts\python.exe ${workspaceFolder}\ai-act-sd-poc\tools\verify_audit.py --source db --db backend\governance.db` |
| Audit verifizieren (CSV) | `${workspaceFolder}\.venv\Scripts\python.exe ${workspaceFolder}\ai-act-sd-poc\tools\verify_audit.py --source csv --csv docs\exports\audit_export.csv` |
| Letzte DB-Einträge ansehen | VS Code Task `DB: last 5 rows (id, decision, overridden, second_approval)` |
| Smoke Decision (ALLOW) | Task `Smoke: POST ALLOW` |
| Smoke Decision (REVIEW) | Task `Smoke: POST REVIEW` |
| Override (ALLOW) | Task `Smoke: POST OVERRIDE (ALLOW)` |
| Generate synthetic cases | `python .\tools\generate_cases.py [--force]` |
| Compute metrics snapshot | `python .\tools\compute_metrics.py --batch demo1` |
| Classifier metrics helper | `python .\tools\classifier_metrics.py --help` |

9. Troubleshooting
-------------------
- **ImportError backend**: nutze `python -m uvicorn --app-dir .\backend ...`.
- **Port 8000 belegt**: `--port 8010` + `$env:BACKEND_URL` auf denselben Host/Port setzen.
- **SQLite gelockt**: prüfe offene Tools (Explorer, Excel). Entferne ggf. `C:\Projekte\thesis\governance.db` nach Kopie.
- **Login schlägt fehl**: Stelle sicher, dass `$env:TOKENS_JSON`/`TOKENS_FILE` gesetzt ist oder Demo-Tokens aktiv sind.
- **Vier-Augen Cases**: Reviewer-Token blockiert – mit Admin-Token erneut anmelden oder zweiten Benutzer nutzen.
- **Streamlit zeigt keine Daten**: `$env:DB_URL` korrekt? Backend muss laufen (für Auth & Overrides).
- **HTTPS Bedarf**: siehe `tools/tls/README_TLS.txt`; starte `stunnel`, setze `$env:BACKEND_URL = "https://localhost:8443"`.
- **Rate/Body Limits**: Defaults 5 req/s (Burst 10) & 64 KB; konfigurierbar via `RATE_LIMIT_RATE`, `RATE_LIMIT_BURST`, `MAX_BODY_BYTES`.
- **Audit Trail**: `decision_logs` ist append-only; Hash-Kette (`prev_hash`/`row_hash`).

10. Maintenance Notes
---------------------
- `.env.example` listet alle Variablen.
- UI fällt bei leeren Filtern auf den Gesamtbestand zurück (Arbeitsüberblick bleibt gefüllt).
- API Input Tab spiegelt den zuletzt gewählten Fall (Request + Thresholds).
- Nach UI-Code-Änderungen: `python -m py_compile .\oversight_ui\app.py` für schnellen Syntax-Check.
- Stoppe Server mit `Ctrl+C`, verlasse venv mit `deactivate`.
