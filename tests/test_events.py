from datetime import date

from reconciler.events import events_from_trades, sort_events
from reconciler.models import EventKind, Side, Trade


def _trade(row: int, entry: date, exit_: date, symbol: str = "X") -> Trade:
    return Trade(
        row=row,
        symbol=symbol,
        side=Side.LONG,
        entry_date=entry,
        exit_date=exit_,
        entry_price=10.0,
        exit_price=11.0,
        quantity=10,
        pnl_dollars=10.0,
        pnl_percent=10.0,
    )


def test_each_trade_yields_two_events():
    trades = [_trade(1, date(2024, 1, 1), date(2024, 2, 1))]
    events = events_from_trades(trades)
    assert len(events) == 2
    assert {e.kind for e in events} == {EventKind.ENTRY, EventKind.EXIT}


def test_sort_orders_by_date():
    trades = [
        _trade(1, date(2024, 3, 1), date(2024, 4, 1)),
        _trade(2, date(2024, 1, 1), date(2024, 2, 1)),
    ]
    events = sort_events(events_from_trades(trades))
    assert events[0].date == date(2024, 1, 1)
    assert events[-1].date == date(2024, 4, 1)


def test_sort_breaks_tie_by_csv_row():
    d = date(2024, 1, 1)
    trades = [
        _trade(1, d, date(2024, 2, 1), symbol="A"),
        _trade(2, d, date(2024, 2, 1), symbol="B"),
    ]
    events = sort_events(events_from_trades(trades))
    same_day = [e for e in events if e.date == d]
    assert [e.symbol for e in same_day] == ["A", "B"]


def test_intra_day_round_trip_orders_entry_before_exit():
    d = date(2024, 1, 1)
    trades = [_trade(1, d, d)]
    events = sort_events(events_from_trades(trades))
    assert events[0].kind == EventKind.ENTRY
    assert events[1].kind == EventKind.EXIT


def test_two_intra_day_round_trips_interleave_correctly():
    d = date(2024, 1, 1)
    trades = [_trade(1, d, d, symbol="A"), _trade(2, d, d, symbol="B")]
    events = sort_events(events_from_trades(trades))
    pattern = [(e.kind, e.symbol) for e in events]
    assert pattern == [
        (EventKind.ENTRY, "A"),
        (EventKind.EXIT, "A"),
        (EventKind.ENTRY, "B"),
        (EventKind.EXIT, "B"),
    ]
