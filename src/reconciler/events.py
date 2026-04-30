from __future__ import annotations

from .models import Event, EventKind, OpenPosition, Split, Trade


def events_from_trades(trades: list[Trade]) -> list[Event]:
    events: list[Event] = []
    for t in trades:
        events.append(
            Event(
                date=t.entry_date,
                kind=EventKind.ENTRY,
                symbol=t.symbol,
                side=t.side,
                price=t.entry_price,
                quantity=t.quantity,
                source_row=t.row,
            )
        )
        events.append(
            Event(
                date=t.exit_date,
                kind=EventKind.EXIT,
                symbol=t.symbol,
                side=t.side,
                price=t.exit_price,
                quantity=t.quantity,
                source_row=t.row,
            )
        )
    return events


def events_from_open_positions(opens: list[OpenPosition]) -> list[Event]:
    return [
        Event(
            date=o.entry_date,
            kind=EventKind.ENTRY,
            symbol=o.symbol,
            side=o.side,
            price=o.entry_price,
            quantity=o.quantity,
            source_row=o.row,
            is_open_position=True,
        )
        for o in opens
    ]


def events_from_splits(splits: list[Split]) -> list[Event]:
    return [
        Event(
            date=s.date,
            kind=EventKind.SPLIT,
            symbol=s.symbol,
            side=None,
            price=s.factor,
            quantity=0.0,
            source_row=s.row,
        )
        for s in splits
    ]


def sort_events(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda e: e.sort_key())
