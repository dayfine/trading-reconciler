from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class Trade:
    row: int
    symbol: str
    side: Side
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: float
    pnl_dollars: float
    pnl_percent: float


class EventKind(StrEnum):
    SPLIT = "SPLIT"
    ENTRY = "ENTRY"
    EXIT = "EXIT"


LAYER_ORDER = {EventKind.SPLIT: 0, EventKind.ENTRY: 1, EventKind.EXIT: 1}


@dataclass(frozen=True)
class Event:
    date: date
    kind: EventKind
    symbol: str
    side: Side | None
    price: float
    quantity: float
    source_row: int
    is_open_position: bool = False

    def sort_key(self) -> tuple:
        layer = LAYER_ORDER[self.kind]
        if self.is_open_position:
            layer = 2
        within_row = 0 if self.kind == EventKind.ENTRY else 1
        return (self.date, layer, self.source_row, within_row)


@dataclass(frozen=True)
class Lot:
    symbol: str
    side: Side
    cost_basis_per_share: float
    quantity: float
    entry_date: date


@dataclass
class Divergence:
    type: str
    severity: int
    payload: dict


SEVERITY_CASH_FLOOR = 4
SEVERITY_PNL_MISMATCH = 3
SEVERITY_MISSING_PRICE = 5
