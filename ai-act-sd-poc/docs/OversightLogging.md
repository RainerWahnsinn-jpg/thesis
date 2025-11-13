# Oversight & Logging Design

## 1) Log Transport

- MVP: local newline-delimited JSON file `logs/decisions.log` (append-only).
- Future: ship to SIEM.

## 2) Mandatory Fields (Completeness KPI = 100%)

Each log line (JSON) MUST contain these keys for credit decisions; for returns triage omit score/thresholds/near_threshold or set null, still retaining structural integrity.

```
{
  "event": "credit.decision" | "returns.triage" | "override.apply",
  "decision_id": "dec-<sha256>",
  "request": { /* validated input, no direct PII beyond customer_id */ },
  "response": { /* output incl. decision_id, decision, versions */ },
  "rule_version": "rv1.0",
  "data_version": "dv1.0",
  "service_version": "svc1.0.0",
  "thresholds": { "allow_max":59, "review_range":[60,79], "block_min":80 },
  "score": 72,
  "decision": "ALLOW",
  "near_threshold": false,
  "actor_sys": "credit_decision_api",
  "actor_ux": null,
  "overridden": 0,
  "override_reason": null,
  "second_approval": null,
  "duration_ms": 12.4,
  "timestamp_utc": "2025-11-12T10:15:12.345Z",
  "correlation_id": "optional-guid",
  "prev_hash": "optional-previous-record-hash"
}
```

Override apply example differences:

```
{
  "event": "override.apply",
  "decision_id": "dec-77aa11",
  ...,
  "overridden": 1,
  "override_reason": "Hoher strategischer Wert beim Kunden (>=15 Zeichen)",
  "second_approval": true,
  "actor_ux": "user:analyst",
  "actor_sys": "oversight_console"
}
```

## 3) Override Flow

1. Initial decision logged (`credit.decision`).
2. Oversight user posts override (`/o2c/credit/override/{decision_id}`) with `override_reason` (≥15 chars) + `second_approval`.
3. New log entry `override.apply` with `overridden=1`, `actor_ux` recorded.

## 4) Quality Validation

- Completeness: missing any mandatory key ⇒ log_completeness violation.
- Monotonie check: sort decisions by score ascent; ensure decision ordering non-regressive.

## 5) Security & Integrity

- Append-only file permissions (no in-place edits).
- Optional checksum chain: each record stores previous hash.

## 6) Privacy

- Remove/avoid any direct personal identifiers beyond customer_id pseudonym.

## 7) File Rotation (Optional)

- Daily rotate to `decisions-YYYY-MM-DD.log`.

## 8) Returns Stub Logging

- Same structure minus thresholds/score when not relevant (keep keys with null or omit with schema note).

## 9) Future Enhancements

- Structured logging library integration.
- Streaming metrics extraction.
- Hash chain enforcement (prev_hash mandatory).
