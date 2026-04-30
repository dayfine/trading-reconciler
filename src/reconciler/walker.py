from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .events import events_from_trades, sort_events
from .models import (
    SEVERITY_CASH_FLOOR,
    SEVERITY_PNL_MISMATCH,
    Divergence,
    Event,
    EventKind,
    Lot,
    Side,
    Trade,
)
from .pnl import compute_pnl, compute_pnl_percent, entry_cash_delta, exit_cash_delta
from .tolerance import Tolerance


@dataclass
class TradeResult:
    row: int
    symbol: str
    side: Side
    entry_date: date
    exit_date: date
    computed_pnl: float
    input_pnl: float
    divergence: float
    verdict: str


@dataclass
class OpenPositionResult:
    symbol: str
    side: Side
    entry_date: date
    cost_basis_per_share: float
    effective_quantity: float
    final_price: float | None = None
    unrealized_pnl: float | None = None


@dataclass
class WalkResult:
    initial_cash: float
    final_cash: float
    trade_results: list[TradeResult] = field(default_factory=list)
    open_positions: list[OpenPositionResult] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)


def walk(
    trades: list[Trade],
    initial_cash: float,
    *,
    tolerance: Tolerance,
    commission_per_share: float = 0.0,
    commission_per_trade: float = 0.0,
) -> WalkResult:
    events = sort_events(events_from_trades(trades))
    open_lots: dict[str, list[Lot]] = defaultdict(list)
    cash = initial_cash
    result = WalkResult(initial_cash=initial_cash, final_cash=cash)

    trade_by_row: dict[int, Trade] = {t.row: t for t in trades}

    for ev in events:
        cash = _apply(ev, cash, open_lots, commission_per_share, commission_per_trade)

        if ev.kind == EventKind.EXIT and not ev.is_open_position:
            t = trade_by_row[ev.source_row]
            computed = compute_pnl(
                t,
                commission_per_share=commission_per_share,
                commission_per_trade=commission_per_trade,
            )
            diff = computed - t.pnl_dollars
            verdict = "MATCH" if tolerance.matches(t.pnl_dollars, computed) else "MISMATCH"
            result.trade_results.append(
                TradeResult(
                    row=t.row,
                    symbol=t.symbol,
                    side=t.side,
                    entry_date=t.entry_date,
                    exit_date=t.exit_date,
                    computed_pnl=computed,
                    input_pnl=t.pnl_dollars,
                    divergence=diff,
                    verdict=verdict,
                )
            )
            if verdict == "MISMATCH":
                computed_pct = compute_pnl_percent(t, computed)
                result.divergences.append(
                    Divergence(
                        type="pnl_mismatch",
                        severity=SEVERITY_PNL_MISMATCH,
                        payload={
                            "row": t.row,
                            "symbol": t.symbol,
                            "input_pnl": t.pnl_dollars,
                            "computed_pnl": computed,
                            "diff": diff,
                            "input_pnl_percent": t.pnl_percent,
                            "computed_pnl_percent": computed_pct,
                        },
                    )
                )

        if tolerance.cash_floor_violated(cash):
            result.divergences.append(
                Divergence(
                    type="cash_floor",
                    severity=SEVERITY_CASH_FLOOR,
                    payload={
                        "date": ev.date.isoformat(),
                        "cash": cash,
                        "threshold": -tolerance.abs_,
                    },
                )
            )

    result.final_cash = cash
    for symbol, lots in open_lots.items():
        for lot in lots:
            result.open_positions.append(
                OpenPositionResult(
                    symbol=symbol,
                    side=lot.side,
                    entry_date=lot.entry_date,
                    cost_basis_per_share=lot.cost_basis_per_share,
                    effective_quantity=lot.quantity,
                )
            )
    result.open_positions.sort(key=lambda p: (p.symbol, p.entry_date))
    return result


def _apply(
    ev: Event,
    cash: float,
    open_lots: dict[str, list[Lot]],
    commission_per_share: float,
    commission_per_trade: float,
) -> float:
    if ev.kind == EventKind.ENTRY:
        cash += entry_cash_delta(
            ev.side,
            ev.price,
            ev.quantity,
            commission_per_share=commission_per_share,
            commission_per_trade=commission_per_trade,
        )
        open_lots[ev.symbol].append(
            Lot(
                symbol=ev.symbol,
                side=ev.side,
                cost_basis_per_share=ev.price,
                quantity=ev.quantity,
                entry_date=ev.date,
            )
        )
    elif ev.kind == EventKind.EXIT:
        cash += exit_cash_delta(
            ev.side,
            ev.price,
            ev.quantity,
            commission_per_share=commission_per_share,
            commission_per_trade=commission_per_trade,
        )
        if open_lots[ev.symbol]:
            open_lots[ev.symbol].pop(0)
            if not open_lots[ev.symbol]:
                del open_lots[ev.symbol]
    return cash
