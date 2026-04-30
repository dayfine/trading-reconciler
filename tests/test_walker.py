from pathlib import Path

from reconciler.parser import parse_trades
from reconciler.tolerance import Tolerance
from reconciler.walker import walk

FIXTURES = Path(__file__).parent / "fixtures"


def _walk(name: str, initial_cash: float):
    trades = parse_trades(FIXTURES / name)
    return walk(trades, initial_cash, tolerance=Tolerance.default())


def test_simple_long_clean():
    r = _walk("simple_long.csv", 1_000_000.0)
    assert len(r.trade_results) == 3
    assert all(t.verdict == "MATCH" for t in r.trade_results)
    assert r.divergences == []
    realized = sum(t.computed_pnl for t in r.trade_results)
    assert realized == 1600.0
    assert r.final_cash == 1_001_600.0


def test_simple_short_clean():
    r = _walk("simple_short.csv", 1_000_000.0)
    assert all(t.verdict == "MATCH" for t in r.trade_results)
    assert r.divergences == []
    realized = sum(t.computed_pnl for t in r.trade_results)
    assert realized == 200.0
    assert r.final_cash == 1_000_200.0


def test_mixed_long_short_clean():
    r = _walk("mixed_long_short.csv", 1_000_000.0)
    assert all(t.verdict == "MATCH" for t in r.trade_results)
    assert r.divergences == []
    realized = sum(t.computed_pnl for t in r.trade_results)
    assert realized == 1950.0


def test_legacy_12col_clean():
    r = _walk("legacy_12col.csv", 1_000_000.0)
    assert len(r.trade_results) == 2
    assert all(t.verdict == "MATCH" for t in r.trade_results)
    assert r.divergences == []


def test_intra_day_round_trip_clean():
    r = _walk("intra_day_round_trip.csv", 10_000.0)
    assert len(r.trade_results) == 2
    assert all(t.verdict == "MATCH" for t in r.trade_results)
    assert r.divergences == []
    assert r.final_cash == 10_200.0


def test_pnl_disagrees_emits_divergence():
    r = _walk("pnl_disagrees.csv", 1_000_000.0)
    assert len(r.trade_results) == 1
    assert r.trade_results[0].verdict == "MISMATCH"
    assert any(d.type == "pnl_mismatch" for d in r.divergences)


def test_cash_floor_violation_event_walk_LOAD_BEARING():
    """Day-1 stacked entries exceed initial cash. Detectable only by event-walk.

    A row-walk would apply each row's net cash delta atomically (entry+exit
    together = +$200 per row → $11,000 final, no floor). Event-walk applies
    5 entry debits on day 1 → cash = $10,000 - $15,000 = -$5,000 → floor
    violation. This fixture is the load-bearing proof of correct walk
    semantics.
    """
    r = _walk("cash_floor_violation_event_walk.csv", 10_000.0)
    cash_floor_divs = [d for d in r.divergences if d.type == "cash_floor"]
    assert cash_floor_divs, "event-walk must detect cash floor violation"
    first = cash_floor_divs[0]
    assert first.payload["date"] == "2024-01-02"
    assert first.payload["cash"] < 0
    assert all(t.verdict == "MATCH" for t in r.trade_results)
