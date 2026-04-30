from __future__ import annotations

from .models import Side, Trade


def commissions_per_leg(quantity: float, per_share: float, per_trade: float) -> float:
    return per_share * quantity + per_trade


def compute_pnl(
    trade: Trade,
    *,
    commission_per_share: float = 0.0,
    commission_per_trade: float = 0.0,
) -> float:
    leg = commissions_per_leg(trade.quantity, commission_per_share, commission_per_trade)
    if trade.side == Side.LONG:
        gross = (trade.exit_price - trade.entry_price) * trade.quantity
    else:
        gross = (trade.entry_price - trade.exit_price) * trade.quantity
    return gross - 2.0 * leg


def compute_pnl_percent(trade: Trade, pnl_dollars: float) -> float:
    notional = trade.entry_price * trade.quantity
    if notional == 0:
        return 0.0
    return pnl_dollars / notional * 100.0


def entry_cash_delta(
    side: Side,
    price: float,
    quantity: float,
    *,
    commission_per_share: float = 0.0,
    commission_per_trade: float = 0.0,
) -> float:
    leg = commissions_per_leg(quantity, commission_per_share, commission_per_trade)
    proceeds = price * quantity
    if side == Side.LONG:
        return -(proceeds + leg)
    return proceeds - leg


def exit_cash_delta(
    side: Side,
    price: float,
    quantity: float,
    *,
    commission_per_share: float = 0.0,
    commission_per_trade: float = 0.0,
) -> float:
    leg = commissions_per_leg(quantity, commission_per_share, commission_per_trade)
    proceeds = price * quantity
    if side == Side.LONG:
        return proceeds - leg
    return -(proceeds + leg)
