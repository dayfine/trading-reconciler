from datetime import date
from pathlib import Path

import pytest

from reconciler.models import Side
from reconciler.parser import (
    ParseError,
    parse_final_prices,
    parse_open_positions,
    parse_splits,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_open_positions():
    opens = parse_open_positions(FIXTURES / "open_position_missing_price.opens.csv")
    assert len(opens) == 1
    o = opens[0]
    assert o.symbol == "MSFT"
    assert o.side == Side.LONG
    assert o.entry_date == date(2024, 1, 5)
    assert o.entry_price == 300.0
    assert o.quantity == 50.0


def test_parses_splits():
    splits = parse_splits(FIXTURES / "held_through_4to1_split.splits.csv")
    assert len(splits) == 1
    s = splits[0]
    assert s.symbol == "AAPL"
    assert s.date == date(2020, 8, 31)
    assert s.factor == 4.0


def test_parses_final_prices():
    prices = parse_final_prices(FIXTURES / "open_position_missing_price.prices.csv")
    assert prices == {"AAPL": 160.0}


def test_open_positions_rejects_bad_header(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("symbol,xxx\n")
    with pytest.raises(ParseError, match="header must be"):
        parse_open_positions(p)


def test_splits_rejects_zero_factor(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("symbol,date,factor\nAAPL,2024-01-01,0\n")
    with pytest.raises(ParseError, match="factor must be > 0"):
        parse_splits(p)


def test_splits_rejects_duplicate(tmp_path):
    p = tmp_path / "dup.csv"
    p.write_text("symbol,date,factor\nAAPL,2024-01-01,2\nAAPL,2024-01-01,3\n")
    with pytest.raises(ParseError, match="duplicate"):
        parse_splits(p)


def test_final_prices_rejects_duplicate(tmp_path):
    p = tmp_path / "dup.csv"
    p.write_text("symbol,price\nAAPL,160\nAAPL,170\n")
    with pytest.raises(ParseError, match="duplicate symbol"):
        parse_final_prices(p)
