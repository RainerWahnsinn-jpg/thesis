# System Card - Credit Decision Service

## 1. Overview

A proof-of-concept credit decision API implementing simple rule-based risk scoring for educational purposes (AI Act SD POC).

## 2. Intended Use

- Educational / thesis demonstration of transparency & oversight patterns.
- Not for production lending decisions.

## 3. Out-of-Scope / Misuse

- High-stakes financial determinations.
- Deployment without bias & fairness evaluation.

## 4. Users & Stakeholders

| Role                 | Interaction             | Responsibilities              |
| -------------------- | ----------------------- | ----------------------------- |
| Developer            | Builds & maintains      | Ensure code quality & logging |
| Compliance/Oversight | Reviews metrics & flags | Escalate anomalies            |
| Researcher           | Experiments with rules  | Document changes              |

## 5. Data Sources

Synthetic credit application attributes provided by fixture JSON.

## 6. Model / Logic Description

Simple additive rule-based scoring; maps to risk bands A-D with recommended interest rates.

## 7. Performance & Metrics (Sample)

| Metric        | Value | Notes               |
| ------------- | ----- | ------------------- |
| Approval Rate | 0.67  | From sample metrics |
| Avg Score     | 68.3  | Synthetic           |

## 8. Policy & Governance

Policy flags (HIGH_DTI, HIGH_EXPOSURE) block approvals.

## 9. Lifecycle & Versioning

`model_version` and `rules_version` returned via `/health`.

## 10. Limitations & Risks

- No fairness auditing.
- Simplistic ratios; may under/over-estimate risk.

## 11. Logging & Traceability

Structured JSON logs per specification (see `LoggingSpec.md`).

## 12. Change Log

| Date       | Version | Change       |
| ---------- | ------- | ------------ |
| 2025-11-12 | 0.1.0   | Initial card |
