# Oversight SOP

## Purpose

Define a light-weight oversight process for the credit decision POC.

## Weekly Routine

1. Review health endpoint and error rates.
2. Inspect approval rate and score distribution.
3. Check policy flag counts (e.g., HIGH_DTI spikes).
4. Sample 5 decisions for manual review (reason completeness).

## Incident Response

- If approval rate deviates >15% week-over-week, open an investigation ticket.
- For repeated errors >2% five-minute rate: rollback latest change or raise to engineering.

## Change Management

- All rule changes documented in `PolicyRulesCard.md` and tagged via `RULES_VERSION`.
- Update `SystemCard.md` if user scope or risk profile changes.
