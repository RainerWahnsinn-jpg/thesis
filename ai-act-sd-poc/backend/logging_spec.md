# Backend Logging Specification

## Purpose

Ensure traceability, auditability, and compliance with AI Act risk management & transparency obligations for the credit decision service.

## Log Levels

- DEBUG: Development details (rule deltas, scoring intermediates) – avoid in production unless troubleshooting.
- INFO: Lifecycle events (startup, shutdown), accepted requests, decision summaries.
- WARNING: Degraded health checks, slow queries, partial failures.
- ERROR: Unhandled exceptions, DB connectivity loss, rule evaluation failures.
- CRITICAL: Data corruption, repeated security violations.

## Log Event Schema (JSON-structured)

| Field          | Type           | Description                                |
| -------------- | -------------- | ------------------------------------------ |
| timestamp      | RFC3339 string | UTC timestamp                              |
| level          | string         | Log level                                  |
| event          | string         | Event name (e.g., `credit.decision`)       |
| application_id | string?        | Present for decision events                |
| customer_id    | string?        | Present for decision events                |
| score          | number?        | Final numeric score                        |
| risk_band      | string?        | Risk band classification                   |
| approved       | boolean?       | Final approval outcome                     |
| policy_flags   | array[string]? | Triggered policy constraints               |
| duration_ms    | number?        | Processing time                            |
| dti            | number?        | Debt-to-income ratio for traceability      |
| model_version  | string         | Service version                            |
| rules_version  | string         | Rules release tag                          |
| correlation_id | string?        | Incoming request correlation (if provided) |
| error          | string?        | Error message if any                       |

## PII Handling

- Avoid logging raw income or loan amount; only derived ratios (DTI) and score.
- Customer IDs treated as pseudonymous identifiers.

## Retention & Access

- Raw logs retained 180 days; aggregated metrics 3 years.
- Access restricted to compliance & engineering roles; yearly access review.

## Security & Integrity

- Append-only sink (e.g., blob storage or SIEM). Checksums / signing optional for high assurance.

## Sampling

- INFO decision events: 100% sampled.
- DEBUG internal scoring: disabled by default; enable temporary targeted sampling.

## Metrics Extraction

From logs produce: approval_rate, avg_score, dti_distribution, policy_flag_counts, latency_p99.

## Alerting Thresholds (Examples)

- ERROR rate > 2% over 5m window.
- Approval rate deviation > 15% from 30d baseline.
- Policy flag HIGH_DTI spikes > 3x median hourly.

## Change Management

- Any schema change increments `rules_version` or `model_version` and is documented in `docs/LoggingSpec.md`.
