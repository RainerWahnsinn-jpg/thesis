# Metrics Plan

This plan enumerates metrics, formulas, and target corridors for the thesis.

## 1) Functional Decision Metrics

| Metric                  | Definition                                                               | Target                                   |
| ----------------------- | ------------------------------------------------------------------------ | ---------------------------------------- |
| decision_distribution   | % ALLOW / REVIEW / BLOCK                                                 | ALLOW 50–70%, REVIEW 20–40%, BLOCK 5–15% |
| monotonicity_violations | Count of cases where higher score ⇒ worse decision                       | 0                                        |
| near_threshold_ratio    | Cases with score within ±5 around lower boundary of review_range / total | 10–25%                                   |
| determinism_consistency | Identical request repeated ⇒ identical decision (%)                      | 100%                                     |

## 2) Governance & Oversight

| Metric                    | Definition                                          | Target                   |
| ------------------------- | --------------------------------------------------- | ------------------------ |
| override_rate_total       | Overrides / decisions                               | <10%                     |
| override_rate_by_original | Split by original decision                          | BLOCK overrides rare <2% |
| override_reason_quality   | Overrides with reason length ≥15 chars              | 100%                     |
| four_eyes_rate            | Overrides with second_approval flag                 | 100%                     |
| log_completeness          | Logs with all mandatory fields / total              | 100%                     |
| version_coverage          | Responses with explicit rule_version & data_version | 100%                     |

| violations_threshold_coherence | Count of score-order violations vs. class ordering | 0 |

## 3) Data Quality

| Metric           | Definition                                      | Target           |
| ---------------- | ----------------------------------------------- | ---------------- |
| schema_validity  | Valid requests / total                          | 100%             |
| missing_rate     | Missing required fields / total fields          | 0%               |
| range_violations | Values outside allowed ranges                   | 0                |
| drift_signal     | Stat diff of decision_distribution vs. baseline | Qualitative flag |

## 4) Operational

| Metric           | Definition                          | Target         |
| ---------------- | ----------------------------------- | -------------- |
| latency_p50_ms   | Median response time                | <80 ms (local) |
| latency_p95_ms   | 95th percentile                     | <150 ms        |
| error_rate_5xx   | 5xx responses / total               | ≈0%            |
| uptime_indicator | Successful health checks / attempts | ≈100%          |

## 5) Returns Triage Stub

| Metric                  | Definition                                           | Target               |
| ----------------------- | ---------------------------------------------------- | -------------------- |
| route_distribution      | % AUTO / REVIEW                                      | AUTO 60–80%          |
| coherence_reason_review | REVIEW share among high-risk reasons                 | Positive correlation |
| monotonicity_amount     | Violations where higher amount ⇒ lower review chance | 0                    |

## 6) Computation Sources

- Decision logs aggregated per batch.
- Overrides recorded in separate `override` events.

## 7) Output Artifacts

- `metrics_snapshot.csv` – computed single snapshot.
- `metrics_history.csv` – optional timeline.

## 8) Method Notes

- near_threshold_ratio uses review_threshold from thresholds object.
- monotonicity checked by ordering decisions by score & verifying non-regression.

## 8) Method Notes

- near_threshold_ratio uses the lower boundary of `review_range` from `thresholds` (e.g., 60) and counts scores in [boundary-5, boundary+5].
- monotonicity and threshold coherence are checked by ordering by score and verifying non-regression of decision class.
