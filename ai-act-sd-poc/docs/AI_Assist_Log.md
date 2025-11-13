# KI-Assistenz & Nachvollziehbarkeit

Ziel: Transparente Dokumentation des Einsatzes von KI-Assistenz (Copilot) zur Unterstützung der Entwicklung. Erfasst werden Kontext, Empfehlungen, getroffene Entscheidungen, betroffene Artefakte sowie Governance-relevante Checks (Determinismus, Logging-Compliance, Nachvollziehbarkeit).

Hinweis: Dieser Baustein unterstützt Annex-IV-Evidenzen (Nachvollziehbarkeit) und ist kein Ersatz für Code-Reviews oder Vier-Augen-Freigaben.

## Prozessrahmen

- Quelle: Entwickler-Prompt / Kontextbeschreibung (Tickets, Sprintziele)
- Empfehlung: Vorschlag/Änderung der Assistenz (kurz)
- Entscheidung: Übernahme/Abweichung inkl. Begründung
- Artefakte: Dateien/Endpunkte, die verändert bzw. angelegt wurden
- Checks: Determinismus, Logging-Vollständigkeit, Threshold-Kohärenz (falls relevant)
- Freigabe: Reviewer/Second Approval (falls benötigt)
- Evidenz: Link auf Commit/PR oder Änderungsdiff

## Template (Eintrag)

- Datum/Zeit (UTC): <YYYY-MM-DDTHH:MM:SSZ>
- Quelle (Ticket/Prompt): <Kurzbeschreibung>
- Empfehlung (Assistenz): <Kurzfassung>
- Entscheidung (Team): <Übernommen/Teilweise/Verworfen – Begründung>
- Artefakte: <Pfad(e)>
- Checks: <z. B. deterministische decision_id, append-only-Insert, Schwellen-Kohärenz>
- Freigabe: <Name/Initialen oder N/A>
- Evidenz: <Commit/PR/Run-Log>

## Initiale Einträge (Sprint 1, Setup)

1. Datum/Zeit (UTC): 2025-11-13T00:00:00Z

   - Quelle: Sprint 1 – Deterministic Credit API + Append-Only Logging
   - Empfehlung: Entscheidung deterministisch (SHA-256 über kanonisches Request-JSON), Logging append-only mit UNIQUE decision_id, thresholds wie spezifiziert
   - Entscheidung: Übernommen (konform zu Kap. 5/6 und Annex-IV)
   - Artefakte: backend/app.py, backend/db.py, backend/schemas.py, README.txt (Startvarianten)
   - Checks: deterministische decision_id; timestamp_utc mit Z; thresholds-Kohärenz; UNIQUE decision_id; no UPDATE/DELETE
   - Freigabe: N/A (POC)
   - Evidenz: OpenAPI /v1/credit/decision; DB-Row-Counts; Smoke-Tests (ALLOW/REVIEW/BLOCK)

2. Datum/Zeit (UTC): 2025-11-13T00:00:00Z
   - Quelle: Dokumentationsbausteine (Annex-IV)
   - Empfehlung: KI-Assistenz-Log und Traceability-Tabelle anlegen
   - Entscheidung: Übernommen
   - Artefakte: docs/AI_Assist_Log.md, docs/Traceability.md
   - Checks: Vollständigkeit der Verlinkung auf Artefakte/Nachweise
   - Freigabe: N/A (POC)
   - Evidenz: Diese Datei, Traceability-Matrix

---

# KI-Assistenz – Kurzprotokoll

> Ziel: Transparenz ohne Ballast. Jede Zeile = 1 Nutzung. Fokus auf WAS übernommen wurde und WIE es verifiziert ist.

## Template

- Datum/Zeit: YYYY-MM-DD HH:MM (lokal)
- Tool: Copilot (Inline) | GPT-5 (Chat)
- Zweck: z. B. „API-Vertrag glätten“, „Override-Validierung formulieren“
- Ergebnis (kurz): Was konkret übernommen? (1–2 Sätze)
- Verifikation: Wie geprüft? (Smoke-Tests, Kohärenz, Log-Vollständigkeit)
- Referenz: Commit/PR/Datei, optional Screenshot

## Einträge (Initial)

- Datum/Zeit: 2025-11-12 21:05  
   Tool: GPT-5 (Chat)  
   Zweck: README-Startpfad + DB_URL vereinheitlichen  
   Ergebnis: Einheitlicher Start (Port 8000), feste DB_URL und UI-Caption; Root-DB aufgeräumt  
   Verifikation: Health OK, REVIEW-Fall sichtbar, rowcount > 0 in `backend/governance.db`  
   Referenz: `README.txt`, `oversight_ui/app.py` (DB-Caption)

- Datum/Zeit: 2025-11-12 21:30  
   Tool: Copilot (Inline)  
   Zweck: Deterministische `decision_id` (SHA-256) + Append-only-Logging  
   Ergebnis: `decision_id` stabil, UNIQUE, Duplikate werden ignoriert (Insert-only)  
   Verifikation: 3 Smoke-Calls (ALLOW/REVIEW/BLOCK), Kohärenzverletzungen = 0, Log-Vollständigkeit = 100%  
   Referenz: `backend/app.py`, `backend/db.py`
