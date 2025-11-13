# Runbook (MVP tools)

Standardbibliothek, keine Anforderungen an requirements\*.txt. Ausführen im Projektstamm.

1. Synthetic Cases erzeugen (100 Credit, 40 Returns)

```powershell
python .\tools\generate_cases.py
```

2. Metriken aus Audit-Log rechnen (Default: docs/examples/audit_log_example.jsonl)

```powershell
python .\tools\compute_metrics.py --batch demo1
```

3. Outputs

- `data/synthetic_credit_cases.csv`
- `data/synthetic_returns_cases.csv`
- `data/metrics_snapshot.csv`

Hinweise

- `--force` bei generate_cases überschreibt vorhandene CSVs.
- compute_metrics akzeptiert `--log <pfad>` und `--out <pfad>`.
