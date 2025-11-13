# Oversight UI Concept

## Goals

- Show REVIEW queue.
- Allow override with reason & second-approval flag.
- Display decision rationale & thresholds side-by-side.

## Screens (MVP)

1. Dashboard: counts (ALLOW/REVIEW/BLOCK), near-threshold %.
2. Review Queue: table of REVIEW decisions (decision_id, score, rationale, age).
3. Detail Drawer: full request + response JSON, override form.

## Override Form Fields

- New decision: ALLOW or BLOCK (cannot choose REVIEW again).
- Reason (textarea, min length 15 chars).
- Second approval checkbox (simulated).

### Validation Rules

- `reason` length ≥ 15 characters (Override reason quality KPI = 100%).
- Second approval must be checked for any BLOCK-to-ALLOW override (four_eyes_rate KPI).

## Data Access

- GET `/o2c/credit/review-queue` returns pending REVIEW decisions.
- GET `/o2c/credit/decision/{decision_id}` detailed view.
- POST `/o2c/credit/override/{decision_id}` applies override (logs event).

## Visual Indicators

- Near-threshold highlight (yellow tag) if `near_threshold=true`.
- Policy flags (if future) as chips.

## Non-Goals

- Authentication (out of thesis scope) – assume trusted internal user.

## Future Extensions

- Timeline chart of override rate.
- Drift indicator comparing last batch distribution.
