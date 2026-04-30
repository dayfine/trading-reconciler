---
name: qc-structural-authority
description: Project-specific structural-review authority for trading-reconciler. Read by qc-structural at session start; enumerates the lints, build gates, and architecture constraints this project enforces beyond the generic harness contract.
harness: project
---

# Structural-review authority — trading-reconciler

What `qc-structural` enforces in addition to the generic protocol in
`.agents/agents/qc-structural.md`.

## Build / lint / test gates

Run these in order. Any non-zero exit is a structural failure that
blocks merge.

```bash
ruff check .              # lint
ruff format --check .     # formatting
pytest -v                 # unit tests
```

CI (`.github/workflows/test.yml`) runs all three on every PR. A merge
that lands with red CI is itself a structural finding.

## Architecture constraints

- **Source layout**: `src/reconciler/` for code, `tests/` for tests.
  No top-level Python modules. `pyproject.toml` declares `src/` as
  the package root.
- **CLI entry point**: `reconciler:cli:main`. The `reconciler` script
  is registered in `pyproject.toml`. Code outside `src/reconciler/cli.py`
  must NOT call `sys.argv` or `argparse` directly.
- **Pure-arithmetic core**: the accounting math (P&L, cash deltas,
  split adjustment) lives in pure functions with no I/O. Parsers,
  emitters, and the CLI shell are separate modules. This is the
  whole point of the project — see `README.md` §"Why this lives in
  a separate repo".
- **No optional `pandas` dependency in core**: `pandas` may be
  imported by helper scripts or alternative parsers, but the core
  walker MUST run on stdlib. Re-introducing pandas as a hard
  dependency in the core is a structural rejection.
- **Floating-point comparisons**: never use `==` on floats outside
  `--strict-fp` paths. Use the hybrid tolerance defined in
  `PHASE_1_SPEC.md` §6.1.

## Module boundary rules

- `parser.py` — CSV parsing, validation. Returns typed records. No
  computation.
- `events.py` — event types, sort key. No I/O.
- `walker.py` — the cash-floor walk + split application. Pure
  function over a sorted event list. No I/O.
- `pnl.py` — P&L formulas (§1.2 of spec). Pure.
- `emit.py` — JSON / sexp formatting. No computation.
- `cli.py` — argparse, file I/O, exit-code mapping. Thin wrapper.
- `tolerance.py` — hybrid tolerance + `--strict-fp`. Pure.

A finding "implementation conflates parsing and walking" is a valid
structural rejection.

## What is NOT a structural concern

- Choice of test fixture data (that's behavioral — see
  `qc-behavioral-authority.md`).
- Whether a P&L formula is correct numerically (behavioral).
- API surface decisions on the OCaml shim side (out of scope).
