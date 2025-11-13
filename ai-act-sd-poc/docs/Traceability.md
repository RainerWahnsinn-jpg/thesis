# Traceability (Kap. 5/6)

Zweck: Rückverfolgbarkeit zwischen Anforderungen/Zielen, Implementierungen und Evidenzen (Annex-IV). Fokus Sprint 1: Deterministic Credit API + Append-Only Logging. Artefakt-Benennungen gemäß Thesis (Abb. 5-1/5-2/6-1; System/Data/Policy/Logging/Oversight; Metrics Sheet).

## Traceability-Matrix

| ID | Requirement / Ziel | Quelle | Implementierung / Artefakt | Ort | Verifikation / Test | Evidenz | Status |
|----|---------------------|--------|-----------------------------|-----|---------------------|---------|--------|
| R1 | Deterministische Kreditentscheidung (/v1/credit/decision) inkl. thresholds | Kap. 5 (System/Policy) | FastAPI-Endpoint mit SHA-256 decision_id über kanonisches Request-JSON, thresholds {allow_max, review_range, block_min} | `backend/app.py` | Smoke-Tests (ALLOW/REVIEW/BLOCK), gleiche Anfrage → gleiche decision_id/score/decision | Abb. 5-1 (API-Antwort), OpenAPI `/openapi.json` | In Arbeit |
| R2 | Append-only Logging (UNIQUE decision_id, keine Updates/Deletes) | Kap. 6 (Logging) | SQLite `decision_logs` + UNIQUE-Index; Insert-only | `backend/db.py` | Wiederholte gleiche Anfrage erzeugt keine zweite Zeile; Row-Count steigt pro neuer decision_id | Abb. 6-1 (Audit-Log Ausschnitt); DB-Query | In Arbeit |
| R3 | Oversight-UI zeigt REVIEW-Fälle | Kap. 6 (Oversight) | Streamlit-UI (nur DB-Read) | `oversight_ui/app.py` | REVIEW-Request senden, UI-Reload, Toggle „Nur REVIEW“ | Abb. 5-2 (REVIEW-UI) | Bereit |
| R4 | Audit-Log Beispiel (JSONL) | Kap. 6 (Logging) | Beispiel-Log | `docs/examples/audit_log_example.jsonl` | Sichtprüfung, Tools lesen | Abb. 6-1 | Bereit |
| R5 | Metrik-Snapshot (u. a. near_threshold_ratio) | Kap. 6 (Metrics Sheet) | Batch-Tool erzeugt CSV | `tools/compute_metrics.py` → `data/metrics_snapshot.csv` | Tool-Run, CSV prüfen | Metrics Sheet | Bereit |
| R6 | p95-Latenz < 150 ms lokal | Kap. 6 (Non-Functional) | Messung via einfachem Client | n/a (Messskript optional) | 20–50 Requests messen, p95 ermitteln | Mess-Report | Offen |
| R7 | Override-Quote < 10 % (Testset) | Kap. 6 (Oversight) | Oversight-Prozess, Testdatensatz | `oversight_ui` + Testset | Zählung Overrides/Total | Report | Geplant |
| R8 | Single Source of Truth DB-Pfad | Kap. 5/6 (System/Logging) | DB_URL=sqlite:///.../backend/governance.db | README, Startkommandos | Test-Path + Row-Count | README Abschnitt 3/5 | Erfüllt |

## Artefaktverweise
- Abb. 5-1: API-Antwort – Beispiel aus `/v1/credit/decision` (HTTP 200) – Screenshot in Thesis einfügen
- Abb. 5-2: REVIEW-UI – Streamlit Ansicht mit Toggle „Nur REVIEW-Fälle“ – Screenshot in Thesis einfügen
- Abb. 6-1: Audit-Log – Auszug aus `docs/examples/audit_log_example.jsonl` – Screenshot in Thesis einfügen
- Metrics Sheet: Siehe `docs/MetricsSheet.md` und erzeugte `data/metrics_snapshot.csv`

## Verifikationshinweise (Sprint 1)
- Determinismus: Gleiche JSON-Body (sortierte Keys) → identische `decision_id`, `score`, `decision`
- Kohärenz: `decision` stimmt mit `thresholds` (59/60–79/≥80) überein
- Logging: Pro Entscheidung genau ein `INSERT` (UNIQUE `decision_id`), keine Updates/Deletes
- Timestamp/Versionen: `timestamp_utc` im ISO-Format mit `Z`; `rule_version`, `data_version='dv1.0'`, `service_version='svc1.0.0'`

---

## Evidenz-Artefakte (Screens & Tabellen)

> Benenne Dateien exakt so, lege sie unter `docs/screens/` ab, und referenziere sie hier.
> Nach dem Einfügen F9 → Verzeichnisse in der Thesis aktualisieren.

### Abb. 5-1: API-Antwort des Entscheidungsservices (Score, Schwellenbezug, Entscheidung, Versionen)
- Datei: `docs/screens/abb-5-1_api-antwort.png`
- Quelle: Swagger „Try it out“ ODER PowerShell-Response (ein REQUEST, sichtbar: `score`, `thresholds{allow_max,review_range,block_min}`, `decision`, `rule_version`, `data_version`, `service_version`, `timestamp_utc`).
- Ausschnitt: Nur Response-Panel/Textbox; keine Browser-UI; kein Scrollbalken.

### Abb. 5-2: Oversight-UI mit REVIEW-Fall, Begründungspflicht und Vier-Augen-Flag
- Datei: `docs/screens/abb-5-2_oversight-review-override.png`
- Quelle: Streamlit-UI, Tab „REVIEW Queue – Credit Decisions“.
- Ausschnitt: Titelzeile sichtbar, mindestens ein REVIEW-Eintrag ausgewählt; rechts/unten Panel mit Begründung (≥ 15 Zeichen) und second approval-Hinweis sichtbar.

### Abb. 6-1: Audit-Log-Auszug mit Pflicht- und Oversight-Feldern
- Datei: `docs/screens/abb-6-1_audit-log-auszug.png`
- Quelle: Log-Viewer (UI) oder ein formatiertes `SELECT` in der Konsole.
- Ausschnitt: 2–3 Zeilen, davon eine Override-Zeile (overridden=1, override_reason, second_approval). Zeitstempel im ISO-Format mit `Z`.

### Tab. 6-1: Kennzahlen-Snapshot (Decision-Mix, edge_band_pct, override_pct, log_completeness_pct)
- Datei: `docs/screens/tab-6-1_metrics-snapshot.png` oder CSV direkt angeben
- Quelle: `data/metrics_snapshot.csv` (aus Tools-Skript)
- Hinweis: Wenn als Bild: Nur die relevante Tabelle im Ausschnitt, Spaltenüberschriften sichtbar.

---

## Capture-Metadaten (ausfüllen nach Aufnahme)

| Artefakt | Datei | Quelle | Datum/Uhrzeit (UTC) | Regelversion | Datenversion | Serviceversion | Kommentar |
|---|---|---|---|---|---|---|---|
| Abb. 5-1 | docs/screens/abb-5-1_api-antwort.png | Swagger/PS |  | rules_v1.2 | dv1.0 | svc1.0.0 | ALLOW/REVIEW/BLOCK je nach Beispiel |
| Abb. 5-2 | docs/screens/abb-5-2_oversight-review-override.png | Streamlit |  | rules_v1.2 | dv1.0 | svc1.0.0 | Override-Dialog/Ergebnis sichtbar |
| Abb. 6-1 | docs/screens/abb-6-1_audit-log-auszug.png | UI/SQL |  | rules_v1.2 | dv1.0 | svc1.0.0 | Zeile mit Override enthalten |
| Tab. 6-1 | docs/screens/tab-6-1_metrics-snapshot.png | CSV/Tool |  | rules_v1.2 | dv1.0 | svc1.0.0 | edge_band_pct, override_pct, completeness |

---

## Capture-Checkliste (1 Minute vor Screenshot)

- [ ] Backend/DB_URL fix (Port 8000), UI aus `oversight_ui/` gestartet
- [ ] REVIEW-Fall erzeugt (Score 60–79) – UI Toggle „Nur REVIEW“ AN
- [ ] Override gesetzt (Begründung ≥ 15 Zeichen), second_approval greift bei ≥ 50k oder country_risk ≥ 4
- [ ] Log sichtbar: mindestens 1 normale + 1 Override-Zeile
- [ ] Ausschnitt ohne Browser-Chrome/Scrollleisten, lesbare Schrift, Titelzeile im Bild
- [ ] Versionen in der Ansicht (rule/data/service) erkennbar bzw. im Caption-Text ergänzt

---

## Benennungs-/Aufnahme-Konventionen

- Pfad: alle Bilder unter `docs/screens/`
- Namen: `abb-5-1_*.png`, `abb-5-2_*.png`, `abb-6-1_*.png`, `tab-6-1_*.png`
- Auflösung: ~1400–1600 px Breite, PNG, 1× Zoom (keine Retina-Verzerrung)
- Konsistenz: gleiche Zoomstufe für Abb. 5-2 und 6-1

---

## Nächster dev-Schritt (kurz)

Führe Sprint 1 zu Ende (Deterministische API + Append-only); mache 3 Smoke-Calls und speichere Abb. 5-1 direkt.
Danach Sprint 2 (UI read-only + DB-Caption) → sofort Abb. 5-2 vorbereitbar.
