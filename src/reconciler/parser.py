from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .models import OpenPosition, Side, Split, Trade

HEADER_OPEN_POSITIONS = "symbol,side,entry_date,entry_price,quantity"
HEADER_SPLITS = "symbol,date,factor"
HEADER_FINAL_PRICES = "symbol,price"

HEADER_13_COL = (
    "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,"
    "quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger"
)
HEADER_12_COL = (
    "symbol,entry_date,exit_date,days_held,entry_price,exit_price,"
    "quantity,pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger"
)


class ParseError(Exception):
    """Maps to exit code 2."""


def _parse_date(s: str, *, field: str, row: int) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise ParseError(f"row {row}: {field} not YYYY-MM-DD: {s!r}") from e


def _parse_float(s: str, *, field: str, row: int) -> float:
    try:
        return float(s)
    except ValueError as e:
        raise ParseError(f"row {row}: {field} not a float: {s!r}") from e


def _parse_side(s: str, *, row: int) -> Side:
    if s == "LONG":
        return Side.LONG
    if s == "SHORT":
        return Side.SHORT
    raise ParseError(f"row {row}: side must be LONG or SHORT, got {s!r}")


def parse_trades(path: str | Path) -> list[Trade]:
    p = Path(path)
    with p.open() as f:
        reader = csv.reader(f)
        try:
            header_row = next(reader)
        except StopIteration as e:
            raise ParseError(f"{p}: empty file") from e

        header = ",".join(header_row)
        if header == HEADER_13_COL:
            mode_13 = True
        elif header == HEADER_12_COL:
            mode_13 = False
        else:
            raise ParseError(
                f"{p}: header must match canonical 13-col or 12-col schema; got: {header!r}"
            )

        trades: list[Trade] = []
        for i, raw in enumerate(reader, start=1):
            expected = 13 if mode_13 else 12
            if len(raw) != expected:
                raise ParseError(
                    f"row {i}: expected {expected} columns, got {len(raw)}"
                )

            if mode_13:
                (
                    symbol, side_s, entry_d, exit_d, _days,
                    entry_p, exit_p, qty,
                    pnl_d, pnl_p, _e_stop, _x_stop, _trigger,
                ) = raw
                side = _parse_side(side_s, row=i)
            else:
                (
                    symbol, entry_d, exit_d, _days,
                    entry_p, exit_p, qty,
                    pnl_d, pnl_p, _e_stop, _x_stop, _trigger,
                ) = raw
                side = Side.LONG

            entry_date = _parse_date(entry_d, field="entry_date", row=i)
            exit_date = _parse_date(exit_d, field="exit_date", row=i)
            if exit_date < entry_date:
                raise ParseError(
                    f"row {i}: exit_date {exit_date} precedes entry_date {entry_date}"
                )

            entry_price = _parse_float(entry_p, field="entry_price", row=i)
            exit_price = _parse_float(exit_p, field="exit_price", row=i)
            quantity = _parse_float(qty, field="quantity", row=i)
            if entry_price <= 0:
                raise ParseError(f"row {i}: entry_price must be > 0, got {entry_price}")
            if exit_price <= 0:
                raise ParseError(f"row {i}: exit_price must be > 0, got {exit_price}")
            if quantity <= 0:
                raise ParseError(f"row {i}: quantity must be > 0, got {quantity}")

            trades.append(
                Trade(
                    row=i,
                    symbol=symbol,
                    side=side,
                    entry_date=entry_date,
                    exit_date=exit_date,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    pnl_dollars=_parse_float(pnl_d, field="pnl_dollars", row=i),
                    pnl_percent=_parse_float(pnl_p, field="pnl_percent", row=i),
                )
            )

        return trades


def parse_open_positions(path: str | Path) -> list[OpenPosition]:
    p = Path(path)
    with p.open() as f:
        reader = csv.reader(f)
        try:
            header_row = next(reader)
        except StopIteration as e:
            raise ParseError(f"{p}: empty file") from e

        if ",".join(header_row) != HEADER_OPEN_POSITIONS:
            raise ParseError(
                f"{p}: header must be {HEADER_OPEN_POSITIONS!r}; got: {','.join(header_row)!r}"
            )

        rows: list[OpenPosition] = []
        for i, raw in enumerate(reader, start=1):
            if len(raw) != 5:
                raise ParseError(f"open-positions row {i}: expected 5 columns, got {len(raw)}")
            symbol, side_s, entry_d, entry_p, qty = raw
            side = _parse_side(side_s, row=i)
            entry_date = _parse_date(entry_d, field="entry_date", row=i)
            entry_price = _parse_float(entry_p, field="entry_price", row=i)
            quantity = _parse_float(qty, field="quantity", row=i)
            if entry_price <= 0:
                raise ParseError(
                    f"open-positions row {i}: entry_price must be > 0, got {entry_price}"
                )
            if quantity <= 0:
                raise ParseError(f"open-positions row {i}: quantity must be > 0, got {quantity}")
            rows.append(
                OpenPosition(
                    row=i,
                    symbol=symbol,
                    side=side,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    quantity=quantity,
                )
            )
        return rows


def parse_splits(path: str | Path) -> list[Split]:
    p = Path(path)
    with p.open() as f:
        reader = csv.reader(f)
        try:
            header_row = next(reader)
        except StopIteration as e:
            raise ParseError(f"{p}: empty file") from e

        if ",".join(header_row) != HEADER_SPLITS:
            raise ParseError(
                f"{p}: header must be {HEADER_SPLITS!r}; got: {','.join(header_row)!r}"
            )

        rows: list[Split] = []
        seen: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=1):
            if len(raw) != 3:
                raise ParseError(f"splits row {i}: expected 3 columns, got {len(raw)}")
            symbol, date_s, factor_s = raw
            split_date = _parse_date(date_s, field="date", row=i)
            factor = _parse_float(factor_s, field="factor", row=i)
            if factor <= 0:
                raise ParseError(f"splits row {i}: factor must be > 0, got {factor}")
            key = (symbol, date_s)
            if key in seen:
                raise ParseError(f"splits row {i}: duplicate ({symbol}, {date_s})")
            seen.add(key)
            rows.append(Split(row=i, symbol=symbol, date=split_date, factor=factor))
        return rows


def parse_final_prices(path: str | Path) -> dict[str, float]:
    p = Path(path)
    with p.open() as f:
        reader = csv.reader(f)
        try:
            header_row = next(reader)
        except StopIteration as e:
            raise ParseError(f"{p}: empty file") from e

        if ",".join(header_row) != HEADER_FINAL_PRICES:
            raise ParseError(
                f"{p}: header must be {HEADER_FINAL_PRICES!r}; got: {','.join(header_row)!r}"
            )

        prices: dict[str, float] = {}
        for i, raw in enumerate(reader, start=1):
            if len(raw) != 2:
                raise ParseError(f"final-prices row {i}: expected 2 columns, got {len(raw)}")
            symbol, price_s = raw
            price = _parse_float(price_s, field="price", row=i)
            if price <= 0:
                raise ParseError(f"final-prices row {i}: price must be > 0, got {price}")
            if symbol in prices:
                raise ParseError(f"final-prices row {i}: duplicate symbol {symbol}")
            prices[symbol] = price
        return prices
