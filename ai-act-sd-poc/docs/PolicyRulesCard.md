# Policy & Rules Card

## Policy Principles

- Customer protection: reject when risk flags HIGH_DTI or HIGH_EXPOSURE.
- Transparency: return bands and reasons.
- Proportionality: keep data minimal for the task.

## Rule Summary

- Base score derived from normalized credit_score (0-100)
- DTI penalty for > 0.4 (moderate), > 0.6 (high)
- Existing loans penalty at 2+ and 4+
- Duration penalty for >60 and >84 months

## Approval Policy

- Approve if score >= 50 AND no blocking policy flags.

## Change Control

- Update `backend/rules.py` and bump `RULES_VERSION` env.
- Record changes in this card and `docs/LoggingSpec.md`.
