# trading-reconciler

External P&L reconciliation tool for [`trading-1`](https://github.com/dayfine/trading)
backtest runs. Independent codebase that ingests a `trades.csv` + initial
cash and verifies realized / unrealized P&L from arithmetic alone — catches
accounting bugs that internal QC would miss because every internal check
uses the same code path.

## Why this lives in a separate repo

`trading-1`'s internal QC (audit harness, optimal-strategy counterfactual,
metrics-vs-baseline pins) all run inside the same OCaml codebase that
generated the trades. A bug in the simulator's accounting can pass every
internal test because both the test and the production code share the same
broken implementation.

This was demonstrated by the split-day broker-model regression on
2026-04-29: the simulator drove `goldens-sp500/sp500-2019-2023`'s
portfolio to **negative cash** on 2020-08-31 (impossible for a long-only
strategy), but every internal test passed. An external reconciler — written
against the trades.csv contract using only arithmetic, not shared
simulation code — would have flagged it pre-merge.

`trading-1` is also constrained to a single language (OCaml + Dune; see
`.claude/rules/no-python.md`). This repo can be polyglot — Python is the
recommended bootstrap language because Backtrader / pandas already model
brokerage-style FIFO accounting, so we reuse mature primitives instead of
re-inventing the math.

## Interface contract

The contract between the two repos is the CLI schema below. Both can iterate
independently as long as the schema stays stable.

### CLI shape

```
reconciler \
  --trades <path-to-trades.csv> \
  --initial-cash <float> \
  [--final-prices <path-to-final.csv>] \
  [--splits <path-to-splits.csv>] \
  [--format json|sexp] \
  [--strict-fp] \
  [--epsilon <float>]
```

### Inputs

#### `--trades` (required)

CSV matching `trading-1`'s post-G2 `trades.csv` schema (13 columns):

```
symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger
```

- `side`: `LONG` (Buy → Sell) or `SHORT` (Sell → Buy).
- `entry_date` / `exit_date`: `YYYY-MM-DD`.
- `entry_price` / `exit_price` / `entry_stop` / `exit_stop`: float USD.
- `quantity`: float (entry quantity — the value at the entry trade; for
  positions held through splits, this is pre-split, see §Splits below).
- `pnl_dollars` / `pnl_percent`: simulator-computed values; reconciler
  recomputes from arithmetic and asserts agreement.
- `exit_trigger`: free-text string (e.g. `stop_loss`, `force_liquidation`).

**Backward compatibility**: legacy 12-column `trades.csv` (no `side`
column) parses with `side = LONG` defaulted on every row. Bootstrap
implementations should accept both formats.

#### `--initial-cash` (required)

Float, e.g. `1000000.0`. Must match the simulator's `--initial-cash` flag.

#### `--final-prices` (optional)

CSV with `symbol,price` for each position still held at end of run. Required
to compute `unrealized_pnl`. If omitted, reconciler reports realized-only
metrics and warns that unrealized cannot be verified.

```
symbol,price
AAPL,189.42
MSFT,425.50
```

#### `--splits` (optional, Phase 2)

CSV listing split events that occurred during any held position's lifetime:

```
symbol,date,factor
AAPL,2020-08-31,4.0
TSLA,2020-08-31,5.0
```

When a held position spans a split, reconciler applies the factor to
quantity and divides cost-basis-per-share to compute the post-split state.
Without this input, reconciler refuses to verify trades that span known
split dates — the alternative is silent-wrong reconciliation, which defeats
the purpose.

#### `--format json|sexp` (optional)

Output format. Default `json`. Sexp is offered for ease of consumption from
the OCaml side without adding a JSON parser dep.

#### `--strict-fp` (optional)

Float comparisons require bit-equality. Default: relative-tolerance via
`--epsilon`.

#### `--epsilon <float>` (optional)

Relative tolerance for non-strict comparisons. Default `1e-6`.

### Outputs

JSON shape (sexp mirrors structurally):

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
      "quantity": 50,
      "cost_basis_per_share": 420.0,
      "final_price": 425.0,
      "unrealized_pnl": 250.0
    }
  ],
  "divergences": [
    {
      "row": 47,
      "symbol": "TSLA",
      "input_pnl": -2098.05,
      "computed_pnl": 1524.02,
      "diff": -3622.07,
      "type": "pnl_mismatch"
    }
  ]
}
```

### Exit codes

The exit code is the load-bearing CI signal:

| Code | Meaning |
|---|---|
| `0` | All trades reconciled within tolerance. No divergences. Cash floor positive. |
| `1` | Usage error (bad flag, missing required input). |
| `2` | Input parse error (malformed CSV, bad date, etc.). |
| `3` | Divergence detected — at least one trade's recomputed P&L disagrees with input beyond tolerance. |
| `4` | **Cash floor violated** — at any point during the trade sequence, computed cash dropped below zero. (For long-only strategies; short-side margin semantics are configurable.) |
| `5` | Open position references a symbol not in `--final-prices`; cannot compute unrealized P&L. |

Code `4` is the test that would have caught the AAPL split-day bug.

## How `trading-1` consumes this

A thin OCaml shim in `trading/trading/backtest/lib/reconciler_cli.ml`:

```ocaml
val reconcile :
  trades_csv:string ->
  initial_cash:float ->
  ?final_prices_csv:string ->
  ?splits_csv:string ->
  ?epsilon:float ->
  unit ->
  reconciliation_result
```

- Shells out to the `reconciler` binary.
- Parses the JSON / sexp output.
- Asserts internal-vs-external equality within tolerance.
- Surfaces divergence count in the per-scenario row of `release_perf_report`.
- Wires into tier-1/2/3 perf workflows as a quick sanity gate.

The binary is fetched in `trading-1`'s CI prep step via a pinned version +
SHA256 checksum, mirroring how `dev/lib/run-in-env.sh` already manages dev
tooling. Local devs run an installer script.

## Roadmap

| Phase | Scope | Effort |
|---|---|---|
| **Phase 1 — bootstrap** | Python + pytest reconciler. Accepts post-G2 13-column `trades.csv` + `--initial-cash` + optional `--final-prices`. JSON + sexp output. ~5 hand-computed gold fixtures (long-only happy path, mixed long/short, deliberately-wrong row that triggers divergence, empty trade list, single trade). Exit codes 0-3 + 5. | 1-2 days |
| **Phase 2 — splits** | `--splits` input. Hand-fixture for AAPL 2020-08-31 4:1 (the canonical bug). Exit code 4 (cash floor) hardened. | 1 day |
| **Phase 3 — `trading-1` integration** | OCaml shim + wire-in to `release_perf_report`. Per-scenario divergence column. | ½ day |
| **Phase 4 — CI + distribution** | Pinned version + checksum + installer script in both repos. GHA fetches binary in prep step. | ½ day |
| **Phase 5 — beyond-the-bootstrap** | Dividend handling. Reverse splits / spinoffs. PortfolioVisualizer cross-check (as a CI test against a known-good external system). Multi-currency. Margin / collateral semantics for shorts. | TBD |

## Validation reference

The reconciler's own test suite needs ground-truth seeds. Three sources
ranked by trustworthiness:

1. **Brokerage statement** from a live account (gold standard but requires
   real positions).
2. **PortfolioVisualizer** manual cross-check on a small synthetic trade
   log (web-driven; tedious but doable; bootstrap default).
3. **Hand-computed sample** in a spreadsheet committed to this repo
   (fastest; least authoritative; useful for unit tests).

Bootstrap with option 3 + option 2 cross-check on 1-2 representative
scenarios. Layer in option 1 once a live account accumulates history.

## Language choice

**Recommend: Python.** Reasons:

- `pandas` + `numpy` model FIFO accounting in 50 lines.
- `Backtrader` / `Zipline` / `bt` already exist as reference implementations
  if a pure-arithmetic version isn't trusted.
- Easy for users (and reviewers) to inspect line by line.
- No build step.
- pytest is industry-standard.

**Alternative: Rust.** Static binary, no runtime dep on the consumer. More
work to write the math but the artifact is easier to distribute.

The design doc doesn't fix the choice — bootstrapping in Python with
Backtrader as the validation cross-check is the path of least resistance.

## What this repo deliberately does NOT do

- **No strategy logic.** No entries, no exits, no signals. Just accounting
  on a given trade list.
- **No event handling beyond raw buy/sell + (Phase 2) splits.** No order
  management, no fill simulation, no commission models beyond a flat
  per-share / per-trade input.
- **No reverse engineering of strategy intent.** `exit_trigger` is treated
  as opaque metadata. Whether a stop fired correctly is `trading-1`'s job
  to assess.

The clear scope is what makes this useful: a small, transparent,
single-purpose tool. If `trading-1` and the reconciler disagree, the bug is
in `trading-1` (the reconciler's math is verifiable by hand).

## Status

**2026-04-29** — Repo bootstrapped with this design doc.

**2026-04-30** — `PHASE_1_SPEC.md` finalized. Phase 1 implemented in
PRs A/B/C. 12/13 fixtures green; #5 xfail pending spec clarification
in [#9](https://github.com/dayfine/trading-reconciler/issues/9).

Read order for implementers: this `README.md` (design rationale +
phases) → `PHASE_1_SPEC.md` (authoritative I/O contract + accounting).

## Quick start

```bash
pip install -e '.[dev]'
pytest -v

# Run against a trades file:
reconciler --trades trades.csv --initial-cash 1000000

# With splits + open positions + final prices:
reconciler \
  --trades trades.csv \
  --initial-cash 1000000 \
  --splits splits.csv \
  --open-positions opens.csv \
  --final-prices final.csv \
  --format json

# Sexp output for OCaml-side consumption:
reconciler --trades trades.csv --initial-cash 1000000 --format sexp
```

Exit code is the load-bearing CI signal — see `PHASE_1_SPEC.md` §9.

## Cross-references in `trading-1`

- `dev/notes/short-side-gaps-2026-04-29.md` — gap doc that motivated the
  reconciler proposal (the cliff-drop bug demonstrates why external
  verification matters).
- `dev/notes/session-followups-2026-04-29-evening.md` — captures the
  reconciler track as a future item.
- `dev/decisions.md` 2026-04-29 — the broker-model decision the reconciler
  exists to verify.
