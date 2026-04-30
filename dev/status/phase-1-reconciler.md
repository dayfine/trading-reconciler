# Track: phase-1-reconciler

**Status**: COMPLETE (modulo merge of PR-C)
**Owner**: unassigned
**Milestone**: [Phase 1 — bootstrap](https://github.com/dayfine/trading-reconciler/milestone/1)
**Spec**: [`PHASE_1_SPEC.md`](../../PHASE_1_SPEC.md) (authoritative)

Single sequential track for the entire Phase 1 reconciler. Three
stacked PRs (A → B → C), each landing a coherent slice of the spec
with its corresponding fixtures green.

---

## PR chain

### PR-A — parser + event-walk core (closed-trade only)

Tracking issue: [#3](https://github.com/dayfine/trading-reconciler/issues/3)

**Scope**: foundation that makes simple round-trips reconcile.

- Parser for `--trades` (both 13-col and 12-col headers per §2.2).
- Validation rules per §2.4.
- Event constructor + sort key per §5 (no splits, no open-positions yet).
- Walker: cash + open-position state, per-leg cash deltas per §1.4.
- Per-row P&L recompute per §1.2; tolerance compare per §6.1.
- Cash-floor check per §1.1 + §6.3.
- JSON output emitter (sexp deferred to PR-C).
- Exit-code mapping per §9.

**Fixtures green**: #1 `simple_long`, #2 `simple_short`, #3
`mixed_long_short`, #6 `cash_floor_violation_event_walk`, #7
`pnl_disagrees`, #11 `legacy_12col`, #12 `intra_day_round_trip`.

**Critical**: fixture #6 is the load-bearing test for event-walk
semantics. PR-A does not land without it green.

**Out of scope**: splits, open-positions, commissions, sexp output,
`--strict-fp`, `--verbose`.

**Estimated size**: 600–900 lines (impl + tests).

---

### PR-B — splits + open-positions + unrealized

Tracking issue: [#4](https://github.com/dayfine/trading-reconciler/issues/4)

**Scope**: held-through-split + end-of-run reporting.

- `--splits` parser + Split events per §4.
- Split application during walk per §4.2; boundary convention §4.3.
- `--open-positions` parser + entry-event injection per §3.2.
- `--final-prices` parser; unrealized P&L per §3.3.
- End-of-run aggregation: `realized_pnl_total`, `unrealized_pnl_total`,
  `total_value`, `total_return_pct` per §1.5.
- Exit code 5 (missing open-position price).

**Fixtures green** (in addition to PR-A's): #4
`held_through_4to1_split`, #5 `held_through_4to1_split_no_splits_input`,
#10 `open_position_missing_price`, #13 `open_positions_with_split`.

**Out of scope**: commissions, sexp output, `--strict-fp`,
`--verbose`.

**Estimated size**: 400–600 lines.

---

### PR-C — commissions + tolerance polish + sexp emitter

Tracking issue: [#5](https://github.com/dayfine/trading-reconciler/issues/5)

**Scope**: spec completion.

- `--commission-per-share` + `--commission-per-trade` flags wired into
  P&L formulas (§1.2) and per-leg cash deltas (§1.4).
- `--strict-fp` mode + co-passed-flag warnings per §6.2.
- `--epsilon-relative` / `--epsilon-absolute` flag plumbing (likely
  already wired in PR-A; verify).
- Sexp emitter; encoding documented in implementation README.
- `--verbose` flag → stderr INFO traces.
- `--slippage-bps` flag accepted but ignored (reserved for Phase 2).

**Fixtures green** (in addition to PR-A + PR-B): #8 `commission_match`,
#9 `commission_mismatch`.

**Out of scope**: anything in §11 (Phase 2+).

**Estimated size**: 300–500 lines.

---

## Branch + base layout

PRs stack on each other; each based on the prior PR's branch:

```
main
 └── feat/phase-1-reconciler/parser-and-event-walk    (PR-A)
      └── feat/phase-1-reconciler/splits-and-opens    (PR-B, base = PR-A)
           └── feat/phase-1-reconciler/commissions-and-sexp  (PR-C, base = PR-B)
```

Per `dev/agent-feature-workflow.md`: never branch from a feature
branch directly; PR-B opens only after PR-A merges to main, etc.
This serializes the chain but keeps each PR reviewable in isolation.

If parallel work becomes desirable later (e.g. PR-B and PR-C both
depend on PR-A but not on each other), split into multiple tracks.

---

## Definition of done

- All 13 fixtures from `PHASE_1_SPEC.md` §10 green via `pytest`.
- `bin/agent-harness-check.sh` passes.
- `README.md` updated with reconciler installation + invocation
  example.
- Implementation README documents sexp encoding choice (per §12.1)
  and any deviation from the spec.
- All `<TODO: ...>` placeholders in `.agents/agents/lead-orchestrator.md`
  + `.github/workflows/orchestrator.yml` resolved (orchestrator can
  actually run; or, alternatively, the orchestrator workflow is
  disabled until Phase 2 — decide before PR-A merges).

---

## Next task

Phase 1 complete after PR-C merges. Phase 2 work (soft-floor with
mid-trajectory MtM via `--daily-prices`, splits/ops research,
trading-1 integration) starts in a new track — see
`PHASE_1_SPEC.md` §11 for deferred items and `README.md` §Roadmap
Phase 2+ for sequencing.

Open question still pending: spec ambiguity #9 (held-through-split
without `--splits` exit code). Resolution flips
`tests/test_phase_1_open_questions.py` from xfail to a hard
assertion.

## Fixtures landed (13/13)

| # | Fixture | PR | Status |
|---|---|---|---|
| 1 | `simple_long.csv` | PR-A | green |
| 2 | `simple_short.csv` | PR-A | green |
| 3 | `mixed_long_short.csv` | PR-A | green |
| 4 | `held_through_4to1_split.csv` + matching splits | PR-B | green |
| 5 | `held_through_4to1_split_no_splits_input` | PR-B | xfail (#9) |
| 6 | `cash_floor_violation_event_walk.csv` | PR-A | green (load-bearing) |
| 7 | `pnl_disagrees.csv` | PR-A | green |
| 8 | `commission_match.csv` | PR-C | green |
| 9 | `commission_mismatch.csv` | PR-C | green |
| 10 | `open_position_missing_price.*` | PR-B | green |
| 11 | `legacy_12col.csv` | PR-A | green |
| 12 | `intra_day_round_trip.csv` | PR-A | green |
| 13 | `open_positions_with_split.*` | PR-B | green |
