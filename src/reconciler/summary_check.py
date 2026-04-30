"""Cross-check reconciler-computed totals against simulator's summary.sexp.

Phase 1.5 — closes the gap that surfaced on goldens-broad/panel-golden-2019-full
where reconciler `realized_pnl_total` disagreed with simulator's `totalpnl`
metric (and `win_count`/`loss_count` disagreed with `wincount`/`losscount`)
even though every per-row P&L matched.

Format expected (from trading-1 backtest_runner output):

    ((start_date ...) (end_date ...) (universe_size ...) (n_steps ...)
     (initial_cash 1000000.00) (final_portfolio_value 999937.26)
     (n_round_trips 32)
     (metrics
      ((metric_types.metric_type.t.totalpnl -64597.51)
       (metric_types.metric_type.t.wincount 12)
       (metric_types.metric_type.t.losscount 20)
       ...)))
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import SEVERITY_PNL_MISMATCH, Divergence
from .sexp_reader import SexpReadError, loads
from .tolerance import Tolerance


@dataclass
class SimulatorSummary:
    n_round_trips: int | None = None
    totalpnl: float | None = None
    wincount: int | None = None
    losscount: int | None = None
    initial_cash: float | None = None


_METRIC_PREFIX = "metric_types.metric_type.t."


def parse_summary_sexp(path: str | Path) -> SimulatorSummary:
    p = Path(path)
    try:
        text = p.read_text()
    except OSError as e:
        raise SummaryParseError(f"{p}: {e}") from e
    try:
        tree = loads(text)
    except SexpReadError as e:
        raise SummaryParseError(f"{p}: {e}") from e

    if not isinstance(tree, list):
        raise SummaryParseError(f"{p}: top-level must be an s-expression list")

    fields = _alist_to_dict(tree)
    out = SimulatorSummary()

    if "n_round_trips" in fields:
        out.n_round_trips = _to_int(fields["n_round_trips"], path=p, key="n_round_trips")
    if "initial_cash" in fields:
        out.initial_cash = _to_float(fields["initial_cash"], path=p, key="initial_cash")

    if "metrics" in fields and isinstance(fields["metrics"], list):
        metrics = _alist_to_dict(fields["metrics"])
        for k, v in metrics.items():
            if not k.startswith(_METRIC_PREFIX):
                continue
            short = k[len(_METRIC_PREFIX):]
            if short == "totalpnl":
                out.totalpnl = _to_float(v, path=p, key=k)
            elif short == "wincount":
                out.wincount = _to_int_via_float(v, path=p, key=k)
            elif short == "losscount":
                out.losscount = _to_int_via_float(v, path=p, key=k)

    return out


class SummaryParseError(Exception):
    pass


def _alist_to_dict(items: list) -> dict[str, object]:
    out: dict[str, object] = {}
    for entry in items:
        if not isinstance(entry, list) or len(entry) < 1 or not isinstance(entry[0], str):
            continue
        key = entry[0]
        if len(entry) == 1:
            out[key] = None
        elif len(entry) == 2:
            out[key] = entry[1]
        else:
            out[key] = entry[1:]
    return out


def _to_float(v: object, *, path: Path, key: str) -> float:
    if not isinstance(v, str):
        raise SummaryParseError(f"{path}: {key} expected scalar, got {v!r}")
    try:
        return float(v)
    except ValueError as e:
        raise SummaryParseError(f"{path}: {key} not a float: {v!r}") from e


def _to_int(v: object, *, path: Path, key: str) -> int:
    if not isinstance(v, str):
        raise SummaryParseError(f"{path}: {key} expected scalar, got {v!r}")
    try:
        return int(v)
    except ValueError as e:
        raise SummaryParseError(f"{path}: {key} not an int: {v!r}") from e


def _to_int_via_float(v: object, *, path: Path, key: str) -> int:
    """OCaml emits some integer-valued metrics as floats (e.g. `12` or `12.0`)."""
    if not isinstance(v, str):
        raise SummaryParseError(f"{path}: {key} expected scalar, got {v!r}")
    try:
        f = float(v)
    except ValueError as e:
        raise SummaryParseError(f"{path}: {key} not numeric: {v!r}") from e
    if f != int(f):
        raise SummaryParseError(f"{path}: {key} expected integer-valued, got {v!r}")
    return int(f)


def cross_check(
    sim: SimulatorSummary,
    *,
    realized_pnl_total: float,
    win_count: int,
    loss_count: int,
    trade_count: int,
    tolerance: Tolerance,
) -> list[Divergence]:
    divergences: list[Divergence] = []

    if sim.totalpnl is not None and not tolerance.matches(sim.totalpnl, realized_pnl_total):
        divergences.append(
            Divergence(
                type="summary_mismatch",
                severity=SEVERITY_PNL_MISMATCH,
                payload={
                    "field": "realized_pnl_total",
                    "simulator_field": "metrics.totalpnl",
                    "simulator_value": sim.totalpnl,
                    "computed_value": realized_pnl_total,
                    "diff": realized_pnl_total - sim.totalpnl,
                },
            )
        )

    if sim.wincount is not None and sim.wincount != win_count:
        divergences.append(
            Divergence(
                type="summary_mismatch",
                severity=SEVERITY_PNL_MISMATCH,
                payload={
                    "field": "win_count",
                    "simulator_field": "metrics.wincount",
                    "simulator_value": sim.wincount,
                    "computed_value": win_count,
                    "diff": win_count - sim.wincount,
                },
            )
        )

    if sim.losscount is not None and sim.losscount != loss_count:
        divergences.append(
            Divergence(
                type="summary_mismatch",
                severity=SEVERITY_PNL_MISMATCH,
                payload={
                    "field": "loss_count",
                    "simulator_field": "metrics.losscount",
                    "simulator_value": sim.losscount,
                    "computed_value": loss_count,
                    "diff": loss_count - sim.losscount,
                },
            )
        )

    if sim.n_round_trips is not None and sim.n_round_trips != trade_count:
        divergences.append(
            Divergence(
                type="summary_mismatch",
                severity=SEVERITY_PNL_MISMATCH,
                payload={
                    "field": "trade_count",
                    "simulator_field": "n_round_trips",
                    "simulator_value": sim.n_round_trips,
                    "computed_value": trade_count,
                    "diff": trade_count - sim.n_round_trips,
                },
            )
        )

    return divergences
