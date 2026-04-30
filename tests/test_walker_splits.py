from datetime import date
from pathlib import Path

from reconciler.models import OpenPosition, Side, Split
from reconciler.parser import (
    parse_final_prices,
    parse_open_positions,
    parse_splits,
    parse_trades,
)
from reconciler.tolerance import Tolerance
from reconciler.walker import walk

FIXTURES = Path(__file__).parent / "fixtures"


def test_held_through_4to1_split_with_splits_input():
    trades = parse_trades(FIXTURES / "held_through_4to1_split.csv")
    splits = parse_splits(FIXTURES / "held_through_4to1_split.splits.csv")
    r = walk(trades, 50_000.0, tolerance=Tolerance.default(), splits=splits)
    assert len(r.trade_results) == 1
    tr = r.trade_results[0]
    assert tr.verdict == "MATCH"
    assert tr.computed_pnl == 4000.0
    assert r.divergences == []
    assert r.final_cash == 54_000.0


def test_open_position_with_split_propagates_to_unrealized():
    trades = parse_trades(FIXTURES / "open_positions_with_split.trades.csv")
    opens = parse_open_positions(FIXTURES / "open_positions_with_split.opens.csv")
    splits = parse_splits(FIXTURES / "open_positions_with_split.splits.csv")
    prices = parse_final_prices(FIXTURES / "open_positions_with_split.prices.csv")
    r = walk(
        trades,
        50_000.0,
        tolerance=Tolerance.default(),
        open_positions=opens,
        splits=splits,
        final_prices=prices,
    )
    assert len(r.open_positions) == 1
    op = r.open_positions[0]
    assert op.symbol == "AAPL"
    assert op.cost_basis_per_share == 120.0
    assert op.effective_quantity == 400.0
    assert op.final_price == 130.0
    assert op.unrealized_pnl == 4000.0
    assert r.unrealized_pnl_total == 4000.0
    assert r.divergences == []


def test_open_position_missing_final_price_emits_exit5_divergence():
    trades = parse_trades(FIXTURES / "open_position_missing_price.trades.csv")
    opens = parse_open_positions(FIXTURES / "open_position_missing_price.opens.csv")
    prices = parse_final_prices(FIXTURES / "open_position_missing_price.prices.csv")
    r = walk(
        trades,
        1_000_000.0,
        tolerance=Tolerance.default(),
        open_positions=opens,
        final_prices=prices,
    )
    missing = [d for d in r.divergences if d.type == "missing_open_position_price"]
    assert len(missing) == 1
    assert missing[0].payload["symbol"] == "MSFT"
    assert r.unrealized_pnl_total is None


def test_short_position_with_split_adjusts_correctly():
    """A short held through a 2:1 split. cost_basis halves, qty doubles."""
    opens = [
        OpenPosition(
            row=1,
            symbol="X",
            side=Side.SHORT,
            entry_date=date(2024, 1, 1),
            entry_price=100.0,
            quantity=10,
        )
    ]
    splits = [Split(row=1, symbol="X", date=date(2024, 2, 1), factor=2.0)]
    prices = {"X": 40.0}
    r = walk(
        trades=[],
        initial_cash=10_000.0,
        tolerance=Tolerance.default(),
        open_positions=opens,
        splits=splits,
        final_prices=prices,
    )
    assert len(r.open_positions) == 1
    op = r.open_positions[0]
    assert op.cost_basis_per_share == 50.0
    assert op.effective_quantity == 20.0
    # SHORT unrealized = (cost_basis - final) * qty = (50 - 40) * 20 = 200
    assert op.unrealized_pnl == 200.0
