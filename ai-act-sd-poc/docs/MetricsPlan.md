# Metrics Plan

This plan enumerates metrics, formulas, and target corridors for the thesis prototype. It focuses on a deterministic credit decision service with optional classifier support.

## 1) Functional Decision Metrics

| Metric                         | Definition                                                               | Target                                   |
| ------------------------------ | ------------------------------------------------------------------------ | ---------------------------------------- |
| decision_distribution          | % ALLOW / REVIEW / BLOCK                                                 | ALLOW 50–70%, REVIEW 20–40%, BLOCK 5–15% |
| monotonicity_violations        | Count of cases where higher score ⇒ worse decision                       | 0                                        |
| near_threshold_ratio           | Cases with score within ±5 around lower boundary of review_range / total | 10–25%                                   |
| determinism_consistency        | Identical request repeated ⇒ identical decision (%)                      | 100%                                     |
| violations_threshold_coherence | Count of score-order violations vs. class ordering                       | 0                                        |

## 2) Governance & Oversight

| Metric                    | Definition                                          | Target                   |
| ------------------------- | --------------------------------------------------- | ------------------------ |
| override_rate_total       | Overrides / decisions                               | <10%                     |
| override_rate_by_original | Split by original decision (ALLOW/REVIEW/BLOCK)     | BLOCK overrides rare <2% |
| override_reason_quality   | Overrides with reason length ≥15 chars              | 100%                     |
| four_eyes_rate            | Overrides with second_approval flag                 | 100% (where required)    |
| log_completeness          | Logs with all mandatory fields / total              | 100%                     |
| version_coverage          | Responses with explicit rule_version & data_version | 100%                     |

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

## 5) Optional: Classifier Evaluation (Scores Tab)

If a lightweight classifier is used to support the deterministic rules (e.g. predicting REVIEW vs. non-REVIEW):

| Metric             | Definition                                      | Target / Expectation                  |
| ------------------ | ----------------------------------------------- | ------------------------------------- |
| samples_total      | Number of evaluated samples                     | ≥ O(100) (demo scale)                 |
| class_distribution | Share per class (e.g. REVIEW vs. OTHER)         | No extreme imbalance if avoidable     |
| precision_review   | TP / (TP + FP) for REVIEW                       | High enough to trust REVIEW alerts    |
| recall_review      | TP / (TP + FN) for REVIEW                       | REVIEW-Fälle möglichst vollständig    |
| f1_review          | Harmonic mean of Precision/Recall for REVIEW    | Single KPI for REVIEW quality         |
| macro_f1           | Mean F1 over all classes                        | Headline metric for overall behaviour |
| calibration_bins   | Binned predicted prob. vs. observed REVIEW rate | Roughly monotonic, no extreme misfit  |

Calibration and confusion matrix are computed from a model output file (JSON/CSV) and surfaced in the Scores tab.

### Scores Tab Layout & Computation Flow

1. **Input Channels**

   - Deterministic baseline: aggregated `decision_logs` provide reference Allow/Review/Block mix, overrides, and SLA durations.
   - Classifier experiments: streamed via CSV/JSON containing predicted class, optional probability, and ground-truth label derived from the rules.

2. **Core Panels**

   - **Sample Overview**: counts, class distribution, macro-F1 headline; toggles between 3-class vs. binary “Prüfpflichtig” views.
   - **Confusion Matrix**: rendered as table/heatmap with PRE/REC/F1 per class; Review row highlighted for Oversight focus.
   - **Calibration Strip (optional)**: probability bins (deciles) comparing predicted vs. observed Review rates to expose miscalibration.
   - **Governance KPIs**: Allow/Review/Block distribution, override quote, Review queue mean and p95 processing time, sourced from `decision_logs` for the same batch.

3. **Update Cycle**

   - Each model run writes a structured JSON/CSV; the Streamlit tab loads the latest artefact, recomputes metrics on the fly, and annotates the snapshot with rule_version / data_version so Annex IV traceability is preserved.
   - If no classifier data is present, the tab falls back to deterministic KPIs with explanatory copy (“Classifier optional”).

4. **Routing**
   - Breadcrumb (Oversight › Review Queue › Audit Logs › Scores & Metrics) guides users through the workflow, emphasizing that the classifier augments—not replaces—the deterministic engine.

### Feature Catalog (Classifier Input)

| Feature            | Type     | Description                                                               |
| ------------------ | -------- | ------------------------------------------------------------------------- |
| order_id           | string   | Unique order identifier, allows traceability to audit logs and metrics.   |
| customer_id        | string   | Debtor identifier, links to master data and historical risk context.      |
| order_value_eur    | float    | Exposure per order in EUR, typically several thousand up to few 100k.     |
| payment_terms_days | integer  | Contracted payment terms; interacts with DSO for liquidity risk.          |
| overdue_ratio      | float    | Share of overdue receivables (0..1); high values indicate elevated risk.  |
| dso_proxy_days     | integer  | Approximate Days Sales Outstanding for the customer.                      |
| risk_class         | category | Internal risk band (A–D) reflecting baseline creditworthiness.            |
| country_risk       | ordinal  | Country risk score (1–5) capturing political/economic environment.        |
| incoterm           | category | Delivery & risk split (EXW, FCA, CPT, DAP, DDP, etc.).                    |
| is_new_customer    | boolean  | Flags limited payment history; enables conservative thresholds.           |
| credit_limit_eur   | float    | Approved credit line in EUR for context vs. order size.                   |
| past_limit_breach  | boolean  | Indicates historical credit limit breaches.                               |
| express_flag       | boolean  | Marks urgent/critical orders requiring higher governance attention.       |
| data_version       | string   | Records data assumption version for reproducibility.                      |
| service_version    | string   | Running service version (semantic) for Annex IV traceability.             |
| rule_version       | string   | Active rule set identifier to align classifier with deterministic policy. |

All classifier experiments must consume the same schema as the operational API. No new PII or derived fields are introduced; feature engineering must be traceable to these base fields.

### Classifier Output CSV Format

| Column             | Type   | Notes                                                                 |
| ------------------ | ------ | --------------------------------------------------------------------- |
| decision_id        | string | Must match the deterministic log entry (e.g., `dec-…`).               |
| true_label         | string | Ground-truth class from the rule engine (`ALLOW`, `REVIEW`, `BLOCK`). |
| predicted_label    | string | Classifier prediction using the same vocabulary.                      |
| review_probability | float  | Optional probability (0–1) for REVIEW/prüfpflichtig.                  |
| model_run_id       | string | Identifier of the model/config snapshot.                              |
| run_timestamp_utc  | string | ISO-8601 timestamp of the model run.                                  |
| rule_version       | string | Rule version used to derive the labels for traceability.              |
| data_version       | string | Data assumption version used during the run.                          |

Additional metadata columns may be appended if needed, but the above headers are required for ingestion. The CSV must use UTF-8 and include a header row.

Das Repository enthält ein Demo-Artefakt unter `data/classifier_results_demo.csv`, das als Standardquelle für den Scores Tab dient, falls kein Upload erfolgt.

## 6) Computation Sources

- `decision_logs` aggregated per batch (governance & functional metrics).
- Overrides recorded as dedicated events or as fields in `decision_logs`.
- Optional classifier outputs loaded from CSV/JSON for Scores tab evaluation.

### Governance KPIs surfaced in Oversight UI

- **Decision Mix** – live Allow/Review/Block percentages drawn from the current filter selection.
- **Override Quote** – share of overridden base decisions plus split by original class, matching the `override_rate_*` definitions above.
- **Four-Eyes Compliance** – percentage of overrides with `second_approval=1`, signalled whenever the queue requires admin participation.
- **Review Queue SLA** – rolling mean and p95 duration computed from `ts_utc` deltas between base decision and override (or closure) to expose backlog risk.
- **Log Completeness Flag** – UI callouts whenever mandatory fields are missing in `decision_logs` / CSV snapshots.

These KPIs share the same wording across docs, Streamlit copy, and exported CSV captions so screenshots (e.g. Abb. 6-1) and annex tables stay consistent.

## 7) Output Artifacts

- `metrics_snapshot.csv` – single snapshot for thesis (e.g. Abb. 6-1).
- `metrics_history.csv` – optional timeline (not required for the prototype).

## 8) Method Notes

- `near_threshold_ratio` uses the lower boundary of `review_range` from `thresholds` (e.g. 60) and counts scores in `[boundary-5, boundary+5]`.
- Monotonicity and threshold coherence are checked by ordering by score and verifying non-regression of the decision class.
- Governance metrics (override_rate, four_eyes_rate, log_completeness) are computed directly from `decision_logs` and should be explainable from the Oversight UI and audit log samples.
- Classifier metrics are treated as supportive evidence only; deterministic policy and Annex IV artefacts remain the primary governance backbone.
