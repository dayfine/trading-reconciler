from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerance:
    rel: float
    abs_: float

    @classmethod
    def default(cls) -> "Tolerance":
        return cls(rel=1e-6, abs_=0.01)

    @classmethod
    def strict(cls) -> "Tolerance":
        return cls(rel=0.0, abs_=0.0)

    def matches(self, input_v: float, computed_v: float) -> bool:
        diff = abs(input_v - computed_v)
        threshold = max(self.rel * max(abs(input_v), abs(computed_v)), self.abs_)
        return diff <= threshold

    def cash_floor_violated(self, cash: float) -> bool:
        return cash < -self.abs_
