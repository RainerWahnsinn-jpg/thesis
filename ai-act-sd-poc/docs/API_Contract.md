# API Contract (MVP) – O2C Credit Decision + Returns Triage (Stub)

This document specifies deterministic, auditable APIs. Implementation can follow later; this is the contract for thesis artifacts and tests.

## Common Principles

- Determinismus: Gleicher Input ⇒ gleiche Entscheidung (idempotent for decision_id based on request body).
- Versionierung: `rule_version`, `data_version`, `service_version` returned on every response.
- Oversight: Responses include thresholds and policy rationale; append-only audit logs record inputs/outputs.

---

## 1) Credit Decision API (primary)

- Method: POST
- Path: `/o2c/credit/decide`
- Request: `CreditRequest` (see schema)
- Response: `CreditResponse`

### Request Schema (CreditRequest)

Fields mirror your Datengrundlage. All required unless noted.

- order_id: string
- customer_id: string
- order_value_eur: number
- payment_terms_days: integer
- overdue_ratio: number [0..1]
- dso_proxy_days: integer
- risk_class: enum [A,B,C,D]
- country_risk: integer [1..5]
- incoterm: enum [EXW,DDP,DAP,FCA,CPT]
- is_new_customer: boolean
- credit_limit_eur: number
- past_limit_breach: boolean
- express_flag: boolean
- data_version: string (default "dv1.0")

### Response Schema (CreditResponse)

- decision_id: string (deterministic hash of request for idempotency)
- score: integer [0..100]
- thresholds: object { "allow_max": int, "review_range": [int,int], "block_min": int } – explicit ranges
- decision: enum [ALLOW, REVIEW, BLOCK]
- rule_version: string (e.g., "rv1.0")
- data_version: string (echo from request)
- policy_rationale: string (human-readable rule summary)
- timestamp_utc: RFC3339 datetime
- service_version: string (e.g., "svc1.0.0")

### Thresholds & Kohärenz

- Example default thresholds (configurable):
  ```json
  { "allow_max": 59, "review_range": [60, 79], "block_min": 80 }
  ```
- Decision policy: score ≤ allow_max → ALLOW; score ∈ review_range → REVIEW; score ≥ block_min → BLOCK.
- Monotonie: Höherer Score darf die Risikoklasse/Entscheidung nicht verschlechtern.
- Randzone: ±5 Punkte um die untere Grenze von review_range (z. B. um 60) wird als "near_threshold" erfasst (für Randzonen-Quote).

---

## 2) Returns Triage API (stub)

- Method: POST
- Path: `/o2c/returns/triage`
- Request: `ReturnsRequest`
- Response: `ReturnsResponse`

### Request Schema (ReturnsRequest)

- return_id: string
- reason: enum [Transport, Falschlieferung, Korrosion, Sonstiges]
- amount_eur: number
- warranty: boolean
- order_age_days: integer
- customer_tier: enum [NEW, ACTIVE, VIP]
- data_version: string (default "dv1.0")

### Response Schema (ReturnsResponse)

- decision_id: string
- route: enum [AUTO, REVIEW]
- rationale: string
- rule_version: string
- data_version: string
- timestamp_utc: RFC3339 datetime

### Stub Policy

- AUTO, außer: high amount (e.g., > 1000 EUR) oder reason ∈ {Korrosion, Falschlieferung} ⇒ REVIEW; warranty=true verstärkt REVIEW.
- Monotonie: Höherer Betrag senkt nie REVIEW-Wahrscheinlichkeit (0 Verstöße).

---

## 3) Audit Log Contract (append-only)

Every API call emits a JSON line with required fields:

- event: "credit.decision" | "returns.triage"
- decision_id: string
- request: full validated request (sans PII beyond customer_id)
- response: full response
- rule_version: string
- data_version: string
- service_version: string
- thresholds (credit only): { "allow_max": int, "review_range": [int,int], "block_min": int }
- score (credit only): number
- decision (credit only): "ALLOW" | "REVIEW" | "BLOCK"
- near_threshold (credit only): boolean
- actor_sys: string (e.g., "credit_decision_api")
- actor_ux: string? (optional user id for overrides)
- overridden: 0|1
- override_reason: string? (≥15 chars when overridden=1)
- duration_ms: number
- timestamp_utc: string (ISO-8601 with Z)
- correlation_id: string? (optional)
- prev_hash: string? (optional for chained integrity)

Missing mandatory fields ⇒ log completeness KPI fails.

---

## 4) Health & Metrics Endpoints (MVP)

- GET `/health` ⇒ { status, rule_version, data_version?, service_version, timestamp_utc }
- GET `/metrics/snapshot` ⇒ returns key counters (see MetricsPlan.md) computed from recent logs/db.

---

## 5) Determinism Contract

- `decision_id` = SHA-256 Base16 hash over the canonically serialized request: sorted JSON keys, excluding `decision_id`, including `rule_version` & `data_version`.
- Prefix with `dec-` (e.g., `dec-<hash>`).
- Same request body ⇒ same decision + same `decision_id` (Target KPI: determinism_consistency = 100%).
- Rule and data versions are explicit inputs to determinism.
