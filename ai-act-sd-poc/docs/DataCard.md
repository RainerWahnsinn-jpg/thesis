# Data Card - Credit Decision POC

## Dataset Summary

Synthetic small dataset used for demonstration and testing.

## Motivation

Provide reproducible examples to test API and oversight tooling.

## Composition

- Fields: application_id, customer_id, income, amount, duration_months, credit_score, existing_loans.
- Instances: ~3 in fixtures; expandable.

## Collection Process

Generated manually; no personal real-world data.

## Preprocessing

None.

## Uses

- Unit tests
- Demo scenarios

## Ethical Considerations

- Avoids real PII; synthetic values only.

## Distribution

Local project files under `data/`.
