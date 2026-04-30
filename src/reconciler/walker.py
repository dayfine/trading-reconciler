from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .events import (
    events_from_open_positions,
    events_from_splits,
    events_from_trades,
    sort_events,
)
from .models import (
    SEVERITY_CASH_FLOOR,
    SEVERITY_MISSING_PRICE,
    SEVERITY_PNL_MISMATCH,
    Divergence,
    EventKind,
    Lot,
    OpenPosition,
    Side,
    Split,
    Trade,
)
from .pnl import compute_pnl_lot, compute_pnl_percent, entry_cash_delta, exit_cash_delta
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
    unrealized_pnl_total: float | None = None


def walk(
    trades: list[Trade],
    initial_cash: float,
    *,
    tolerance: Tolerance,
    open_positions: list[OpenPosition] | None = None,
    splits: list[Split] | None = None,
    final_prices: dict[str, float] | None = None,
    commission_per_share: float = 0.0,
    commission_per_trade: float = 0.0,
) -> WalkResult:
    open_positions = open_positions or []
    splits = splits or []

    events = sort_events(
        events_from_trades(trades)
        + events_from_open_positions(open_positions)
        + events_from_splits(splits)
    )
    open_lots: dict[str, list[Lot]] = defaultdict(list)
    cash = initial_cash
    result = WalkResult(initial_cash=initial_cash, final_cash=cash)

    trade_by_row: dict[int, Trade] = {t.row: t for t in trades}

    for ev in events:
        if ev.kind == EventKind.ENTRY:
            assert ev.side is not None
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
            lots = open_lots.get(ev.symbol)
            if not lots:
                continue
            lot = lots.pop(0)
            if not lots:
                del open_lots[ev.symbol]
            assert ev.side is not None
            cash += exit_cash_delta(
                ev.side,
                ev.price,
                lot.quantity,
                commission_per_share=commission_per_share,
                commission_per_trade=commission_per_trade,
            )
            if not ev.is_open_position:
                t = trade_by_row[ev.source_row]
                computed = compute_pnl_lot(
                    cost_basis_per_share=lot.cost_basis_per_share,
                    exit_price=ev.price,
                    quantity=lot.quantity,
                    side=t.side,
                    commission_per_share=commission_per_share,
                    commission_per_trade=commission_per_trade,
                )
                _record_trade_result(result, t, computed, tolerance)

        elif ev.kind == EventKind.SPLIT:
            _apply_split(open_lots, ev.symbol, ev.price)

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
    _populate_open_positions(result, open_lots, final_prices)
    return result


def _apply_split(
    open_lots: dict[str, list[Lot]], symbol: str, factor: float
) -> None:
    if symbol not in open_lots:
        return
    open_lots[symbol] = [
        Lot(
            symbol=lot.symbol,
            side=lot.side,
            cost_basis_per_share=lot.cost_basis_per_share / factor,
            quantity=lot.quantity * factor,
            entry_date=lot.entry_date,
        )
        for lot in open_lots[symbol]
    ]


def _record_trade_result(
    result: WalkResult, t: Trade, computed: float, tolerance: Tolerance
) -> None:
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
                    "computed_pnl_percent": compute_pnl_percent(t, computed),
                },
            )
        )


def _populate_open_positions(
    result: WalkResult,
    open_lots: dict[str, list[Lot]],
    final_prices: dict[str, float] | None,
) -> None:
    unrealized_total = 0.0
    has_unrealized = final_prices is not None
    missing_symbols: list[str] = []
    for symbol, lots in open_lots.items():
        for lot in lots:
            r = OpenPositionResult(
                symbol=symbol,
                side=lot.side,
                entry_date=lot.entry_date,
                cost_basis_per_share=lot.cost_basis_per_share,
                effective_quantity=lot.quantity,
            )
            if has_unrealized:
                final_price = final_prices.get(symbol)
                if final_price is None:
                    missing_symbols.append(symbol)
                else:
                    r.final_price = final_price
                    if lot.side == Side.LONG:
                        r.unrealized_pnl = (final_price - lot.cost_basis_per_share) * lot.quantity
                    else:
                        r.unrealized_pnl = (lot.cost_basis_per_share - final_price) * lot.quantity
                    unrealized_total += r.unrealized_pnl
            result.open_positions.append(r)
    result.open_positions.sort(key=lambda p: (p.symbol, p.entry_date))
    if has_unrealized and not missing_symbols:
        result.unrealized_pnl_total = unrealized_total
    if missing_symbols:
        for sym in sorted(set(missing_symbols)):
            result.divergences.append(
                Divergence(
                    type="missing_open_position_price",
                    severity=SEVERITY_MISSING_PRICE,
                    payload={"symbol": sym},
                )
            )
        result.unrealized_pnl_total = None
