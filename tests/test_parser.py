from datetime import date
from pathlib import Path

import pytest

from reconciler.models import Side
from reconciler.parser import ParseError, parse_trades

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_13col_simple_long():
    trades = parse_trades(FIXTURES / "simple_long.csv")
    assert len(trades) == 3
    t = trades[0]
    assert t.row == 1
    assert t.symbol == "AAPL"
    assert t.side == Side.LONG
    assert t.entry_date == date(2024, 1, 2)
    assert t.exit_date == date(2024, 2, 15)
    assert t.entry_price == 150.0
    assert t.exit_price == 160.0
    assert t.quantity == 100.0
    assert t.pnl_dollars == 1000.0


def test_parses_legacy_12col_defaults_long():
    trades = parse_trades(FIXTURES / "legacy_12col.csv")
    assert len(trades) == 2
    assert all(t.side == Side.LONG for t in trades)


def test_parses_short_side():
    trades = parse_trades(FIXTURES / "simple_short.csv")
    assert all(t.side == Side.SHORT for t in trades)


def test_rejects_wrong_header(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("symbol,foo,bar\nA,1,2\n")
    with pytest.raises(ParseError, match="header must match"):
        parse_trades(p)


def test_rejects_headerless(tmp_path):
    p = tmp_path / "headerless.csv"
    p.write_text("AAPL,LONG,2024-01-02,2024-02-15,44,150,160,100,1000,6.67,140,160,target\n")
    with pytest.raises(ParseError, match="header must match"):
        parse_trades(p)


def test_rejects_exit_before_entry(tmp_path):
    p = tmp_path / "bad-dates.csv"
    p.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,LONG,2024-02-15,2024-01-02,-44,150,160,100,1000,6.67,140,160,target\n"
    )
    with pytest.raises(ParseError, match="exit_date.*precedes entry_date"):
        parse_trades(p)


def test_rejects_negative_price(tmp_path):
    p = tmp_path / "neg-price.csv"
    p.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,LONG,2024-01-02,2024-02-15,44,-150,160,100,1000,6.67,140,160,target\n"
    )
    with pytest.raises(ParseError, match="entry_price must be > 0"):
        parse_trades(p)


def test_rejects_zero_quantity(tmp_path):
    p = tmp_path / "zero-qty.csv"
    p.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,LONG,2024-01-02,2024-02-15,44,150,160,0,0,0,140,160,target\n"
    )
    with pytest.raises(ParseError, match="quantity must be > 0"):
        parse_trades(p)


def test_rejects_invalid_side(tmp_path):
    p = tmp_path / "bad-side.csv"
    p.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,DOG,2024-01-02,2024-02-15,44,150,160,100,1000,6.67,140,160,target\n"
    )
    with pytest.raises(ParseError, match="side must be LONG or SHORT"):
        parse_trades(p)


def test_rejects_bad_date(tmp_path):
    p = tmp_path / "bad-date.csv"
    p.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,LONG,not-a-date,2024-02-15,44,150,160,100,1000,6.67,140,160,target\n"
    )
    with pytest.raises(ParseError, match="entry_date not YYYY-MM-DD"):
        parse_trades(p)
