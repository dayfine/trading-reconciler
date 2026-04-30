from datetime import date

from reconciler.models import Side, Trade
from reconciler.pnl import (
    compute_pnl,
    compute_pnl_percent,
    entry_cash_delta,
    exit_cash_delta,
)


def _trade(side: Side, entry: float, exit_: float, qty: float) -> Trade:
    return Trade(
        row=1,
        symbol="X",
        side=side,
        entry_date=date(2024, 1, 1),
        exit_date=date(2024, 2, 1),
        entry_price=entry,
        exit_price=exit_,
        quantity=qty,
        pnl_dollars=0.0,
        pnl_percent=0.0,
    )


def test_long_pnl_default_no_commission():
    t = _trade(Side.LONG, 150.0, 160.0, 100)
    assert compute_pnl(t) == 1000.0


def test_short_pnl_profit():
    t = _trade(Side.SHORT, 300.0, 290.0, 50)
    assert compute_pnl(t) == 500.0


def test_short_pnl_loss():
    t = _trade(Side.SHORT, 500.0, 510.0, 30)
    assert compute_pnl(t) == -300.0


def test_pnl_with_commissions():
    t = _trade(Side.LONG, 100.0, 110.0, 10)
    pnl = compute_pnl(t, commission_per_share=0.01, commission_per_trade=1.0)
    assert pnl == 100.0 - 2 * (0.10 + 1.0)


def test_pnl_percent_long():
    t = _trade(Side.LONG, 150.0, 160.0, 100)
    pct = compute_pnl_percent(t, 1000.0)
    assert abs(pct - 6.66667) < 1e-3


def test_pnl_percent_short_uses_entry_notional():
    t = _trade(Side.SHORT, 300.0, 290.0, 50)
    pct = compute_pnl_percent(t, 500.0)
    assert abs(pct - 3.33333) < 1e-3


def test_long_entry_cash_delta_negative():
    assert entry_cash_delta(Side.LONG, 100.0, 50) == -5000.0


def test_short_entry_cash_delta_positive():
    assert entry_cash_delta(Side.SHORT, 100.0, 50) == 5000.0


def test_long_exit_cash_delta_positive():
    assert exit_cash_delta(Side.LONG, 110.0, 50) == 5500.0


def test_short_exit_cash_delta_negative():
    assert exit_cash_delta(Side.SHORT, 90.0, 50) == -4500.0


def test_long_round_trip_cash_matches_pnl():
    t = _trade(Side.LONG, 150.0, 160.0, 100)
    cash = entry_cash_delta(Side.LONG, 150.0, 100) + exit_cash_delta(Side.LONG, 160.0, 100)
    assert cash == compute_pnl(t)


def test_short_round_trip_cash_matches_pnl():
    t = _trade(Side.SHORT, 300.0, 290.0, 50)
    cash = entry_cash_delta(Side.SHORT, 300.0, 50) + exit_cash_delta(Side.SHORT, 290.0, 50)
    assert cash == compute_pnl(t)
