from __future__ import annotations

import json
from typing import Any

from .models import Side
from .walker import OpenPositionResult, TradeResult, WalkResult


def _trade_to_dict(t: TradeResult) -> dict[str, Any]:
    return {
        "row": t.row,
        "symbol": t.symbol,
        "side": t.side.value,
        "entry_date": t.entry_date.isoformat(),
        "exit_date": t.exit_date.isoformat(),
        "computed_pnl": t.computed_pnl,
        "input_pnl": t.input_pnl,
        "divergence": t.divergence,
        "verdict": t.verdict,
    }


def _open_to_dict(o: OpenPositionResult) -> dict[str, Any]:
    d: dict[str, Any] = {
        "symbol": o.symbol,
        "side": o.side.value,
        "entry_date": o.entry_date.isoformat(),
        "cost_basis_per_share": o.cost_basis_per_share,
        "effective_quantity": o.effective_quantity,
    }
    d["final_price"] = o.final_price
    d["unrealized_pnl"] = o.unrealized_pnl
    return d


def _summary(result: WalkResult, unrealized_total: float | None) -> dict[str, Any]:
    realized = sum(t.computed_pnl for t in result.trade_results)
    long_count = sum(1 for t in result.trade_results if t.side == Side.LONG)
    short_count = sum(1 for t in result.trade_results if t.side == Side.SHORT)
    win_count = sum(1 for t in result.trade_results if t.computed_pnl > 0)
    loss_count = sum(1 for t in result.trade_results if t.computed_pnl < 0)
    trade_count = len(result.trade_results)
    win_rate_pct = (win_count / trade_count * 100.0) if trade_count else 0.0

    if unrealized_total is None:
        total_value: float | None = None
        total_return_pct: float | None = None
    else:
        market_value = sum(
            (op.unrealized_pnl or 0.0) + op.cost_basis_per_share * op.effective_quantity
            for op in result.open_positions
        )
        total_value = result.final_cash + market_value
        total_return_pct = (
            (total_value - result.initial_cash) / result.initial_cash * 100.0
            if result.initial_cash
            else 0.0
        )

    return {
        "initial_cash": result.initial_cash,
        "final_cash": result.final_cash,
        "realized_pnl_total": realized,
        "unrealized_pnl_total": unrealized_total,
        "total_value": total_value,
        "total_return_pct": total_return_pct,
        "trade_count": trade_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate_pct": win_rate_pct,
        "long_count": long_count,
        "short_count": short_count,
    }


def to_json(result: WalkResult, *, unrealized_total: float | None = None) -> str:
    payload = {
        "summary": _summary(result, unrealized_total),
        "trades": [_trade_to_dict(t) for t in result.trade_results],
        "open_positions": [_open_to_dict(o) for o in result.open_positions],
        "divergences": [
            {"type": d.type, **d.payload} for d in result.divergences
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False)
