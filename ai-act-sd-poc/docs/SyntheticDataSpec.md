# Synthetic Data Specification

Goal: 50–100 deterministic, diverse O2C credit and returns cases covering decision space & edge conditions.

## 1) Credit Cases Coverage Matrix

Dimensions & representative values:
| Dimension | Values / Ranges | Notes |
|----------|-----------------|-------|
| order_value_eur | 500, 5k, 20k | small / mid / large |
| overdue_ratio | 0.0, 0.15, 0.35, 0.6 | triggers risk escalation |
| risk_class | A,B,C,D | baseline risk band |
| country_risk | 1,3,5 | geopolitical factor |
| incoterm | EXW, DDP, DAP | subset sufficient |
| is_new_customer | true/false | new vs. existing |
| past_limit_breach | true/false | penalty flag |
| express_flag | true/false | expedite surcharge effect |

Derived features considered for scoring: overdue_ratio bucket, country_risk weight, new customer penalty, past breach penalty.

## 2) Returns Cases Coverage

| Dimension     | Values                                           |
| ------------- | ------------------------------------------------ |
| reason        | Transport, Falschlieferung, Korrosion, Sonstiges |
| amount_eur    | 50, 400, 1200, 3000                              |
| warranty      | true/false                                       |
| customer_tier | NEW, ACTIVE, VIP                                 |

## 3) Dataset Construction Approach

- Cartesian sampling of critical combinations without full explosion.
- Ensure near-threshold credit scores (±5 around review boundary) ~20% of cases.
- Guarantee some BLOCK, some REVIEW, majority ALLOW.

## 4) File Formats

- `data/credit_cases.csv` – tabular credit requests (no responses).
- `data/returns_cases.csv` – returns triage requests.
- `data/expected_credit_decisions.csv` – pre-computed expected decisions (for determinism checks).

## 5) Versioning

- data_version field set to `dv1.0` in all rows; update if structure changes.

## 6) Quality Controls

- No missing required fields.
- Range validation done pre-generation.

## 7) Future Extensions

- Add fairness slices (e.g., country_risk stratification).
- Introduce seasonal drift batch for drift metric demonstration.
