---
name: qc-behavioral-authority
description: Project-specific behavioral-review authority for trading-reconciler. Read by qc-behavioral at session start; enumerates the domain rules, semantic constraints, and authoritative references this project enforces beyond the generic harness contract.
harness: project
---

# Behavioral-review authority — trading-reconciler

What `qc-behavioral` enforces in addition to the generic protocol in
`.agents/agents/qc-behavioral.md`.

## Authoritative reference

`PHASE_1_SPEC.md` is the contract. Every behavioral finding cites a
specific section number from the spec. A reviewer who can't pin a
finding to a spec section should ask whether the spec needs an
update before rejecting the PR.

## Load-bearing semantic rules

These are the rules whose violation would defeat the project's
purpose. A PR that violates any of them is a hard reject.

### B1. Event-walk, not row-walk (§1.1, §5)

The cash-floor walk MUST process events (entry / exit / split / open-
position-entry) sorted by `(date, tie-break-rules-§5)`. Any
implementation that walks closed-trade rows atomically is wrong by
construction — it cannot detect the AAPL-class cliff that motivates
the entire project. The fixture `cash_floor_violation_event_walk.csv`
(#6 in §10) is the load-bearing test for this rule.

### B2. Strict realized-cash floor (§1.1, §6.3)

The cash-floor check compares walking-cash against `-epsilon_absolute`
only. Relative tolerance on cash is forbidden — it would mask
catastrophic divergences. Soft-floor with unrealized accumulator is
deferred to Phase 2 (§11).

### B3. Split-adjustment applied per §4.2

For positions held through a split, cost basis is divided by the
factor and quantity is multiplied. Same factor convention
(post-split shares per pre-split share). The boundary predicate is
strictly `entry_date < split_date <= exit_date` (§4.3). A row spanning
a known split without `--splits` provided MUST exit 2; silent
wrong-reconciliation is the failure mode this project exists to
prevent.

### B4. Open-position entry-event injection (§3.2)

`--open-positions` rows inject Entry events into the walk. Without
injection, walking-cash silently overstates available cash by the
sum of open-position entry costs. PRs that add `--open-positions`
parsing without injecting Entry events into the walk are rejected.

### B5. Severity-based exit codes (§9)

Walk-time violations (cash-floor, P&L mismatch, missing-final-price)
are gathered into `divergences[]` over the full walk. Exit code = max
severity observed (4 > 3 > 5 > 0). Short-circuit on first violation
is a behavioral failure.

### B6. P&L formula and percent denominator (§1.2, §1.3)

LONG: `(exit - entry) * qty - 2 * (per_share * qty + per_trade)`
SHORT: `(entry - exit) * qty - 2 * (per_share * qty + per_trade)`
Percent: `pnl_dollars / (entry_price * quantity) * 100`. Same
denominator both directions.

### B7. Tie-break order is stable (§5)

Sort key: `(date, layer, source-index)` where layer ∈
{splits, trades, open-positions} fires in that order. Within the
trades layer, same-row Entry-before-Exit. Sort must be stable.
Non-deterministic orderings are a behavioral failure.

## Test-fixture discipline

Each fixture in `PHASE_1_SPEC.md` §10 has a hand-computed expected
JSON output. The test asserts against that JSON. A finding
"fixture's expected output was derived from running the
implementation" is a hard reject — fixtures must be hand-derived
to serve as ground truth.

## What is NOT a behavioral concern

- Code style, formatting (structural).
- Module boundaries (structural).
- CLI flag spelling (mechanical — should be caught by spec
  cross-reference, not behavioral review).
