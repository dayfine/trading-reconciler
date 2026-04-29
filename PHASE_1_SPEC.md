# Phase 1 specification — accounting semantics + I/O contract

Definitive plan for the Phase 1 reconciler. Closes every underspecified
surface in `README.md` so the implementer can write code without
inventing answers.

Status: authoritative for Phase 1. Supersedes the prior split between
`PHASE_1_SPEC.md` (initial draft, row-walk) and
`PHASE_1_SPEC_RESOLUTIONS.md` (event-walk corrections). The corrections
are folded in.

---

## 1. Accounting semantics

### 1.1 Cash-floor walk — event-walk, strict realized-cash floor

The reconciler walks **events**, not closed-trade rows. Each row in
`trades.csv` generates two events; each row in `--open-positions`
generates one. Splits in `--splits` generate adjustment events with
zero cash impact. All events are sorted by `(date, tie-break)` (rules
in §5) and walked once.

```
events = []
for row in trades.csv:
  events.push(Event(date=entry_date, kind=Entry, side, price=entry_price, qty=quantity, source=trades_row[i]))
  events.push(Event(date=exit_date,  kind=Exit,  side, price=exit_price,  qty=quantity, source=trades_row[i]))
for row in --open-positions:
  events.push(Event(date=entry_date, kind=Entry, side, price=entry_price, qty=quantity, source=open_row[j]))
for row in --splits:
  events.push(Event(date=date, kind=Split, symbol, factor, source=split_row[k]))

sort events per §5
```

The walk:

```
cash = initial_cash
open_positions = {}        # symbol -> [{side, entry_price, qty, ...}]
divergences = []

for event in sorted_events:
  if event.kind == Entry:
    cash -= leg_cash(event)              # see §1.4
    open_positions[symbol].push(lot)
  elif event.kind == Exit:
    cash += leg_cash(event)              # see §1.4
    lot = open_positions[symbol].pop()   # FIFO; Phase 1 has no partial fills
    record realized P&L per §1.2; compare to row.pnl_dollars per §6
  elif event.kind == Split:
    apply factor to all matching open_positions lots (§4)

  if cash < -epsilon_absolute:
    divergences.push({type: cash_floor, date, cash, ...})
    # do NOT halt — continue walking to gather full picture (§9)
```

**Strict realized-cash floor.** No soft-floor accumulator. The cash
floor compares walking-cash to `-epsilon_absolute` only. Mid-trajectory
mark-to-market is not modeled in Phase 1 — that requires
`--daily-prices`, deferred to Phase 2.

This catches the AAPL-class bug (mass spurious stop-trigger exits
draining realized cash) because the realized cash trajectory is the
load-bearing signal. It does not catch buying-power violations in
which an open losing position would have force-closed in a real
broker; that's outside the reconciler's scope.

### 1.2 P&L formulas

For a single closed round-trip row:

```
LONG:  pnl_dollars = (exit_price - entry_price) * quantity
                     - 2 * commission_per_share * quantity
                     - 2 * commission_per_trade
SHORT: pnl_dollars = (entry_price - exit_price) * quantity
                     - 2 * commission_per_share * quantity
                     - 2 * commission_per_trade
```

The `2 *` factor covers entry + exit legs. Quantity is unsigned
(direction comes from `side`).

For default zero commissions:

```
LONG:  (exit - entry) * qty
SHORT: (entry - exit) * qty
```

For positions held through splits, replace `entry_price` and
`quantity` with their split-adjusted values per §4.

### 1.3 P&L percent denominator

```
pnl_percent = pnl_dollars / (entry_price * quantity) * 100
```

Return on capital deployed at entry (entry-leg notional). Same for
LONG and SHORT. Brokerage-report convention; not a true
capital-efficiency metric for shorts.

### 1.4 Short-side cash semantics — unsecured, no margin

Per-leg cash deltas:

```
LONG Entry  (Buy to open):    cash -= entry_price * quantity + commissions
LONG Exit   (Sell to close):  cash += exit_price  * quantity - commissions
SHORT Entry (Sell to open):   cash += entry_price * quantity - commissions
SHORT Exit  (Buy to cover):   cash -= exit_price  * quantity + commissions
```

`commissions = commission_per_share * quantity + commission_per_trade`
applied to each leg.

No margin lock, no collateral, no borrow interest. This intentionally
mirrors `trading-1`'s G3 (PR #694). Strict broker-margin semantics
deferred indefinitely (`trading-1` doesn't model them either).

### 1.5 `final_cash` and totals

`final_cash` is the walking-cash endpoint, AFTER all entry/exit/split
events have been applied — including entry-event debits from
`--open-positions` rows that never close.

```
final_cash = initial_cash
             + Σ closed-trade cash flows (signed per §1.4)
             - Σ open-position entry costs
```

Note: `final_cash != initial_cash + realized_pnl_total` when there are
open positions. The relationship is:

```
final_cash + Σ(open_position market_value) = initial_cash + realized_pnl_total + unrealized_pnl_total
```

Reported alongside:

| Field | Definition | Null condition |
|---|---|---|
| `realized_pnl_total` | `Σ row.computed_pnl` over all closed trades | never (always defined) |
| `unrealized_pnl_total` | `Σ open_position.unrealized_pnl` | null if `--open-positions` or `--final-prices` not provided |
| `total_value` | `final_cash + Σ open_position market_value` | null if unrealized_pnl_total null |
| `total_return_pct` | `(total_value - initial_cash) / initial_cash * 100` | null if total_value null |

The cash-floor exit-4 gate fires on walking-cash at any event, not on
`final_cash` alone. Walking-cash dipping below `-epsilon_absolute`
mid-walk triggers exit 4 even if it recovers by end.

---

## 2. `trades.csv` contract

### 2.1 Schema

Post-G2 13-column (canonical):

```
symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger
```

Legacy 12-column (back-compat; defaults `side = LONG` on every row):

```
symbol,entry_date,exit_date,days_held,entry_price,exit_price,quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger
```

Field semantics:

- `side`: `LONG` or `SHORT`. Case-sensitive.
- `entry_date` / `exit_date`: `YYYY-MM-DD`. Day resolution.
- `entry_price` / `exit_price` / `entry_stop` / `exit_stop`: float USD.
  **Raw prices, not split-adjusted.** See §4.
- `quantity`: positive float. Entry-leg quantity (per `trading-1` PR #690).
  Pre any held-through-split adjustments.
- `pnl_dollars` / `pnl_percent`: simulator-computed; reconciler verifies
  against §1.2/§1.3.
- `exit_trigger`: opaque free-text metadata. Not validated.

### 2.2 Header detection

Header row required. First non-empty line of the file is matched
against two literal constants:

```
HEADER_13_COL = "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger"
HEADER_12_COL = "symbol,entry_date,exit_date,days_held,entry_price,exit_price,quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger"
```

Match → mode set, parse remaining rows accordingly. No match → exit 2
(parse error) with stderr message naming both expected headers.
Headerless input rejected. No `--no-header` flag in Phase 1.

Pin both literals as constants in the implementation. Schema drift in
the simulator surfaces immediately as a header mismatch.

### 2.3 Row order is canonical

CSV row order is the canonical event-source order for tie-breaking
within a date (§5). The reconciler does not sort rows. The simulator
emits trades in `(step.date, step-internal order)`; the reconciler
replays that order verbatim.

### 2.4 Validation rules

Per row, enforce at parse time. Any failure → exit 2.

- `side ∈ {LONG, SHORT}` (or absent in 12-col mode).
- `entry_date <= exit_date` — equality permitted (intra-day round-trip,
  see §5 for event ordering); `exit_date < entry_date` rejected.
- `entry_price > 0`, `exit_price > 0`.
- `quantity > 0`.
- Both dates parse as `YYYY-MM-DD`.
- All numeric fields parse as float.

Rows that span a known split with no `--splits` provided also fail
parse-time validation (§4.3).

### 2.5 Split-adjusted vs raw prices

`entry_price` and `exit_price` are **raw** (not split-adjusted). This
matches the `trading-1` broker-model decision (raw OHLC for fills/MtM;
adjusted_close only for indicator math).

`quantity` is the **entry-leg quantity** (pre any held-through-split
adjustments).

For an AAPL position entered pre-2020-08-31 4:1 split and exited
post-split:

- `entry_price = $480` (pre-split raw)
- `exit_price = $130` (post-split raw)
- `quantity = 100` (pre-split entry quantity)

Naive `(exit - entry) * quantity = -$35,000` is catastrophically
wrong (real P&L on this example is +$4,000). Reconciler MUST handle
splits explicitly (§4) for any held-through-split row, else exit 2.
Silent wrong-reconciliation defeats the purpose.

---

## 3. Open positions

### 3.1 `--open-positions` input

Optional flag. Schema:

```
symbol,side,entry_date,entry_price,quantity
AAPL,LONG,2024-11-15,189.50,100
TSLA,SHORT,2025-02-04,420.00,50
```

Header row required. Same field semantics as §2 (raw prices,
unsigned quantity, etc.). Per-row validation:

- `side ∈ {LONG, SHORT}`
- `entry_price > 0`, `quantity > 0`
- `entry_date` parses

Failures → exit 2.

If flag omitted: `unrealized_pnl_total` reported as `null`,
`open_positions[]` reported as `[]`. Cash-floor walk still runs but
without open-position entry events.

### 3.2 Entry-event injection into the walk

Each row in `--open-positions` injects exactly **one** event: an Entry
event on `entry_date` that debits cash per §1.4, with no
corresponding Exit event. The position remains in the walk's open-
position state through end-of-walk.

This is required for the cash-floor walk to be accurate. Without
injection, the walk overstates cash by the sum of open-position entry
costs and may silently miss real cash-floor violations.

### 3.3 Unrealized P&L (end-of-run)

For each open position, after the walk:

```
LONG  unrealized = (final_price - cost_basis_per_share) * effective_quantity
SHORT unrealized = (cost_basis_per_share - final_price) * effective_quantity
```

`cost_basis_per_share` and `effective_quantity` reflect any
held-through-split adjustments (§4). `final_price` comes from
`--final-prices`.

If a symbol in `--open-positions` is missing from `--final-prices`:
**exit 5** (missing open-position price).

---

## 4. Splits

### 4.1 `--splits` input

Optional. Schema:

```
symbol,date,factor
AAPL,2020-08-31,4.0
TSLA,2020-08-31,5.0
NVDA,2021-07-20,4.0
GE,2021-08-02,0.125
```

Header required. `factor` convention: post-split shares per pre-split
share. Forward 4:1 = `4.0`. Reverse 1:5 = `0.2`. Reverse 8:1 = `0.125`.

Per-row validation (parse time):

- `date` parses as `YYYY-MM-DD`.
- `factor > 0` (zero or negative rejected).
- Multiple split events for the same `(symbol, date)` rejected
  (data-quality check).

Failures → exit 2.

### 4.2 Application during the walk

Split events fire during the event-walk. When a Split event for
`symbol S` with factor `f` fires, every open lot in `open_positions[S]`
is adjusted in place:

```
lot.quantity         *= f
lot.cost_basis_per_share /= f
```

Cash impact: zero.

For the AAPL example: a lot opened at `entry_price=$480, qty=100` has
its post-split state `cost_basis_per_share=$120, qty=400`. The
subsequent Exit event applies the standard formula on the adjusted
state:

```
LONG pnl = (exit_price - cost_basis_per_share) * quantity
        = ($130 - $120) * 400
        = +$4,000  ✓
```

For SHORT exits, the formula uses the same adjusted state with the
SHORT direction:

```
SHORT pnl = (cost_basis_per_share - exit_price) * quantity
```

### 4.3 Boundary convention

In-window predicate: `entry_date < split_date <= exit_date`.

- `entry_date == split_date`: **out of window**. Trade was entered AT
  or AFTER the split (split applied at market open; entry at any time
  during the day uses post-split prices).
- `exit_date == split_date`: **in window**. Position spanned the split.
  Adjust per §4.2 before the Exit event fires (per §5 ordering, Split
  events fire before same-date trade events for the same symbol).
- `entry_date == split_date == exit_date` (intra-split-day round-trip):
  out of window. Split is no-op for this row.

If a row spans a split (per the in-window predicate) but `--splits`
was not provided, OR was provided but missing the relevant split
event: exit 2 (parse error). Reconciler refuses to verify silently.

The check is performed at parse time over `(trades_csv ∪
open_positions)`: any held-through-split row without matching split
input fails the load.

---

## 5. Event-walk tie-break order

When multiple events share a date, deterministic ordering is required
so two runs on identical inputs produce identical event sequences.
Within a date, events sort in this order (top fires first):

```
1. Splits, sorted by --splits file row index
2. trades.csv events, sorted by trades.csv row index
   2a. within a single row where entry_date == exit_date:
       Entry before Exit
3. --open-positions Entry events, sorted by --open-positions file row index
```

Rationale per layer:

- **Splits first**: a split applies at market open; same-day trades
  execute at post-split prices.
- **Trades second, by row order**: row order is canonical (§2.3) and
  reflects the simulator's `step.trades` order.
- **Same-row Entry-before-Exit**: an intra-day round-trip's entry
  cannot legally precede its exit; ordering them debit-then-credit
  prevents spurious cash-floor relief from a ghost early credit.
- **Open-positions last**: there is no canonical inter-file ordering
  between `trades.csv` and `--open-positions`; this convention is
  arbitrary but stable. **Known limitation**: on days with both
  closed-trade events and open-position entries on the same date,
  intra-day floor-check minima depend on this convention. End-of-run
  cash is unaffected. Document in user-facing release notes.

Sort must be stable. Implementations using stable sort + a composite
key produce identical output across runs.

---

## 6. Numerics

### 6.1 Hybrid tolerance

Pure relative tolerance fails when `pnl = 0`. Use:

```
abs_diff = |input - computed|
threshold = max(epsilon_relative * max(|input|, |computed|), epsilon_absolute)
PASS if abs_diff <= threshold
```

CLI defaults:

```
--epsilon-relative <float>   default: 1e-6   (one part per million)
--epsilon-absolute <float>   default: 0.01   (one cent)
```

Both flags configurable independently.

### 6.2 `--strict-fp`

Boolean flag. **Always wins** over explicit epsilon flags regardless
of CLI argument order. Sets both epsilons to `0.0`. If `--epsilon-*`
flags are co-passed, log a stderr warning naming each ignored flag and
its value.

```
WARN: --strict-fp set; --epsilon-relative 0.5 ignored
WARN: --strict-fp set; --epsilon-absolute 1.0 ignored
```

### 6.3 Cash-floor tolerance is absolute-only

The cash-floor gate uses `epsilon_absolute` only:

```
violation if cash < -epsilon_absolute  at any event
```

Relative tolerance would mask catastrophic divergences (a portfolio at
`$-100,000` against `$1,000,000` starting is `1e-1` relative, which a
`1e-6` rel-tol gate would clear). The cash floor is the load-bearing
exit-4 gate; absolute-only is correct.

A walking-cash value of `-$0.005` (half a cent below zero from FP
rounding) is OK. `-$1.00` fires exit 4.

### 6.4 Commissions

Phase 1 supports the flags but defaults to zero:

```
--commission-per-share <float>   default: 0.0
--commission-per-trade <float>   default: 0.0
--slippage-bps <float>           default: 0.0   (reserved; ignored in Phase 1)
```

Commissions, when non-zero, apply uniformly to all four leg types
(LONG entry, LONG exit, SHORT entry, SHORT exit).

If `trading-1`'s simulator emits `pnl_dollars` net of commissions, the
reconciler's commission flags must match the simulator's commission
config. Mismatched commissions → divergence on every row → exit 3.
This is a documented user-error mode.

---

## 7. CLI surface

```
reconciler \
  --trades <path>                 # required, post-G2 13-col CSV (legacy 12-col accepted)
  --initial-cash <float>          # required
  --open-positions <path>         # optional, schema in §3.1
  --final-prices <path>           # optional, symbol,price CSV (header required)
  --splits <path>                 # optional, schema in §4.1
  --commission-per-share <float>  # optional, default 0.0
  --commission-per-trade <float>  # optional, default 0.0
  --slippage-bps <float>          # optional, reserved (Phase 2)
  --epsilon-relative <float>      # optional, default 1e-6
  --epsilon-absolute <float>      # optional, default 0.01
  --strict-fp                     # optional, sets both epsilons to 0
  --format json|sexp              # optional, default json
  --verbose                       # optional, INFO-level per-trade traces on stderr
```

`--daily-prices` is not part of Phase 1. Reserved for Phase 2 if
soft-floor reconciliation becomes necessary.

---

## 8. Output JSON

```json
{
  "summary": {
    "initial_cash": 1000000.0,
    "final_cash": 1083420.50,
    "realized_pnl_total": 83420.50,
    "unrealized_pnl_total": 12500.0,
    "total_value": 1095920.50,
    "total_return_pct": 9.59,
    "trade_count": 134,
    "win_count": 51,
    "loss_count": 83,
    "win_rate_pct": 38.06,
    "long_count": 120,
    "short_count": 14
  },
  "trades": [
    {
      "row": 1,
      "symbol": "AAPL",
      "side": "LONG",
      "entry_date": "2019-03-04",
      "exit_date": "2019-04-12",
      "computed_pnl": 570.0,
      "input_pnl": 570.0,
      "divergence": 0.0,
      "verdict": "MATCH"
    }
  ],
  "open_positions": [
    {
      "symbol": "MSFT",
      "side": "LONG",
      "entry_date": "2024-11-15",
      "cost_basis_per_share": 420.0,
      "effective_quantity": 50,
      "final_price": 425.0,
      "unrealized_pnl": 250.0
    }
  ],
  "divergences": [
    {
      "type": "pnl_mismatch",
      "row": 47,
      "symbol": "TSLA",
      "input_pnl": -2098.05,
      "computed_pnl": 1524.02,
      "diff": -3622.07
    },
    {
      "type": "cash_floor",
      "date": "2020-08-31",
      "cash": -42301.50,
      "threshold": -0.01
    }
  ]
}
```

`divergences[]` is always populated (possibly empty). It contains
every violation gathered during the walk. The exit code reflects the
worst-severity entry (§9).

Sexp output mirrors structurally. `null` encoding choice (e.g.
`(field ())` vs field omission) is documented in the implementation
README.

---

## 9. Exit codes — severity-based

The walk runs to completion. Violations accumulate in `divergences[]`.
Exit code = mapping of the worst severity observed.

| Internal severity | Exit code | Meaning | Triggers |
|---|---|---|---|
| `Catastrophic` | 4 | Cash floor violated | Walking-cash dropped below `-epsilon_absolute` at any event |
| `Real-bug` | 3 | P&L mismatch | One or more rows' recomputed P&L disagrees with input beyond tolerance |
| `Data-missing` | 5 | Missing open-position price | A symbol in `--open-positions` not in `--final-prices` |
| `Clean` | 0 | All reconciled | No violations |

Severity ordering: `Catastrophic > Real-bug > Data-missing > Clean`.
Exit codes are POSIX-style status, not numeric severity (5 < 4
numerically but 5 ranks below 4 in severity).

Pre-walk failures short-circuit:

| Code | Meaning | Triggers |
|---|---|---|
| 1 | Usage error | Bad flag, missing required input |
| 2 | Input parse error | Malformed CSV, bad date, held-through-split-without-splits-input, validation rule failure |

Exit codes are exclusive: process exits with exactly one code. The
caller inspects `divergences[]` for the full picture.

---

## 10. Test fixtures

Hand-computed scenarios that pin every code path. Each fixture comes
with a hand-computed expected JSON output that the test asserts
against.

| # | Fixture | Inputs | Expected exit |
|---|---|---|---|
| 1 | `simple_long.csv` | 3 LONG round-trips, no splits, all profitable | 0 |
| 2 | `simple_short.csv` | 2 SHORT round-trips, no splits, mixed P&L | 0 |
| 3 | `mixed_long_short.csv` | combined LONG+SHORT, some same symbol sequentially | 0 |
| 4 | `held_through_4to1_split.csv` + matching splits | the AAPL case | 0 |
| 5 | `held_through_4to1_split_no_splits_input.csv` | same as 4 without `--splits` | 2 |
| 6 | `cash_floor_violation_event_walk.csv` | mass entries on day 1 exceed initial cash; exits scattered later | 4 |
| 7 | `pnl_disagrees.csv` | row with deliberately-wrong `pnl_dollars` | 3 |
| 8 | `commission_match.csv` + matching `--commission-per-share` | commissions handled correctly | 0 |
| 9 | `commission_mismatch.csv` without commission flag set | commission divergence on every row | 3 |
| 10 | `open_position_missing_price.csv` | `--open-positions` references symbol absent from `--final-prices` | 5 |
| 11 | `legacy_12col.csv` | old format, all rows default to LONG | 0 |
| 12 | `intra_day_round_trip.csv` | `entry_date == exit_date` round-trips; verify Entry-before-Exit ordering doesn't trip floor | 0 |
| 13 | `open_positions_with_split.csv` | open position spans a split; verify cost basis + effective quantity propagate to unrealized | 0 |

**Fixture #6 design hardening (load-bearing).** This fixture must
fail under a row-walk implementation and pass under event-walk. Shape:

- Day 1: 5 entry events, total entry-cost > initial_cash. All
  positions exit on Day 30+ at small profit each.
- Row-walk applies net per-row cash deltas, never sees Day 1
  overdraft. Walks clean → exit 0 (wrong).
- Event-walk applies 5 entry debits on Day 1, sees overdraft → exit 4
  (correct).

A passing #6 is the implementation's load-bearing proof of correct
walk semantics.

---

## 11. What this spec deliberately does NOT cover (Phase 2+)

- Soft-floor / buying-power gate using mid-trajectory MtM (`--daily-prices`).
- Margin / collateral semantics for shorts.
- Wash-sale rules.
- Tax-lot accounting (FIFO / LIFO / specific-lot beyond Phase 1's
  trivial single-lot-per-row model).
- Multi-currency.
- Dividend reinvestment / accrual.
- Spinoffs / mergers / special distributions.
- Partial fills, partial exits, lot subdivision.
- Real-time / streaming reconciliation.
- Survivorship-aware universe filtering (that's `trading-1`'s
  ops-data track, not the reconciler's job).

---

## 12. Implementer-discretion items

These do not block implementation. Document the chosen convention in
the implementation README.

### 12.1 Sexp encoding

Recommended:

| OCaml type | Sexp |
|---|---|
| `bool` | `true` / `false` (atoms) |
| `'a option` (None) | `()` |
| `'a option` (Some x) | `(x)` |
| Field with null value | `(field ())` (always-present) or omit field — pick one and stay consistent |

### 12.2 Logging

Stderr-only. Default: silent on success. WARN-level for
tolerance-near-fail rows and `--strict-fp` co-passed-flag warnings.
ERROR for parse failures (these also become exit 2). Under
`--verbose`: INFO per-trade computation traces. No log levels exposed
via CLI in Phase 1; only `--verbose`.

### 12.3 Performance

Target: `O(N + S + P)` walk plus `O((N + S + P) log (N + S + P))`
sort, where N is trade events, S is splits, P is open positions.
Per-event work is O(1) amortized (HashMap of open positions).

Decade-scale (~150 trades): expected <100 ms. 30-year multi-asset
(~1500–3000 trades): expected <500 ms. 100k trades: expected <10 s. No
formal benchmark in Phase 1; profile if production hits scale issues.

### 12.4 Determinism

Same input → bit-identical output. No system time, no random, no
hash-set iteration order leaking through to output. Sort must be
stable. Hash-map iteration over `open_positions` must not appear in
output ordering — sort by symbol when emitting `open_positions[]`.

---

## 13. Implementation roadmap (Phase 1 only)

1. Parser: trades.csv (both header variants), open-positions, splits,
   final-prices. Validation rules per §2.4, §3.1, §4.1.
2. Event constructor + sorter with §5 tie-break key.
3. Walker: cash + open-position state machine, §1.4 leg-cash, §4.2
   split application, §1.1 floor check.
4. Per-row P&L recompute + tolerance compare per §1.2 + §6.1.
5. End-of-run aggregation: realized/unrealized/total totals per §1.5,
   per §3.3.
6. Output emitter: JSON (default) + sexp.
7. Exit-code mapping per §9.
8. Test fixtures #1–13 from §10 with hand-computed expected outputs.

Each step has a corresponding fixture in §10. TDD-friendly: write the
fixture's expected JSON first, then implement until the fixture
passes.
