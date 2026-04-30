"""Tests for the simulator-summary cross-check (Phase 1.5).

Closes the panel-golden-class gap: simulator may emit per-row P&L
that recomputes correctly while reporting an aggregate `totalpnl` /
`wincount` / `losscount` / `n_round_trips` that disagrees with the
sum/count over the trades themselves.
"""

import json
from pathlib import Path

import pytest

from reconciler.cli import EXIT_OK, EXIT_PARSE, EXIT_PNL_MISMATCH, main
from reconciler.summary_check import (
    SimulatorSummary,
    SummaryParseError,
    cross_check,
    parse_summary_sexp,
)
from reconciler.tolerance import Tolerance

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_summary_extracts_known_fields():
    s = parse_summary_sexp(FIXTURES / "simple_long.summary_match.sexp")
    assert s.n_round_trips == 3
    assert s.totalpnl == 1600.00
    assert s.wincount == 3
    assert s.losscount == 0
    assert s.initial_cash == 1000000.0


def test_parse_summary_real_panel_golden_format(tmp_path: Path):
    # Mirrors the actual trading-1 backtest_runner output that surfaced
    # the bug. wincount/losscount as floats (`3.00`).
    sexp = """
((start_date 2019-05-01) (end_date 2020-01-03) (universe_size 7)
 (n_steps 171) (initial_cash 1000000.00) (final_portfolio_value 1022887.87)
 (n_round_trips 7)
 (metrics
  ((metric_types.metric_type.t.totalpnl -10034.63)
   (metric_types.metric_type.t.avgholdingdays 18)
   (metric_types.metric_type.t.wincount 3)
   (metric_types.metric_type.t.losscount 6)
   (metric_types.metric_type.t.winrate 33.33))))
"""
    p = tmp_path / "summary.sexp"
    p.write_text(sexp)
    s = parse_summary_sexp(p)
    assert s.n_round_trips == 7
    assert s.totalpnl == -10034.63
    assert s.wincount == 3
    assert s.losscount == 6


def test_parse_summary_unknown_keys_ignored(tmp_path: Path):
    sexp = "((n_round_trips 2) (some_future_field 42) (metrics ()))"
    p = tmp_path / "s.sexp"
    p.write_text(sexp)
    s = parse_summary_sexp(p)
    assert s.n_round_trips == 2


def test_parse_summary_malformed_raises(tmp_path: Path):
    p = tmp_path / "bad.sexp"
    p.write_text("((unterminated")
    with pytest.raises(SummaryParseError):
        parse_summary_sexp(p)


def test_cross_check_match_returns_no_divergences():
    sim = SimulatorSummary(n_round_trips=3, totalpnl=1600.0, wincount=3, losscount=0)
    out = cross_check(
        sim,
        realized_pnl_total=1600.0,
        win_count=3,
        loss_count=0,
        trade_count=3,
        tolerance=Tolerance.default(),
    )
    assert out == []


def test_cross_check_pnl_diverges_emits_one():
    sim = SimulatorSummary(n_round_trips=3, totalpnl=1500.0, wincount=3, losscount=0)
    out = cross_check(
        sim,
        realized_pnl_total=1600.0,
        win_count=3,
        loss_count=0,
        trade_count=3,
        tolerance=Tolerance.default(),
    )
    assert len(out) == 1
    d = out[0]
    assert d.type == "summary_mismatch"
    assert d.severity == 3
    assert d.payload["field"] == "realized_pnl_total"
    assert d.payload["simulator_value"] == 1500.0
    assert d.payload["computed_value"] == 1600.0
    assert d.payload["diff"] == 100.0


def test_cross_check_count_mismatch_emits_per_field():
    sim = SimulatorSummary(n_round_trips=5, totalpnl=1600.0, wincount=4, losscount=1)
    out = cross_check(
        sim,
        realized_pnl_total=1600.0,
        win_count=3,
        loss_count=0,
        trade_count=3,
        tolerance=Tolerance.default(),
    )
    fields = {d.payload["field"] for d in out}
    assert fields == {"win_count", "loss_count", "trade_count"}
    assert all(d.severity == 3 for d in out)


def test_cross_check_missing_simulator_field_skipped():
    # Forward-compat: a summary missing one metric key shouldn't error,
    # just skip that comparison.
    sim = SimulatorSummary(n_round_trips=3, totalpnl=None, wincount=3, losscount=0)
    out = cross_check(
        sim,
        realized_pnl_total=99999.0,
        win_count=3,
        loss_count=0,
        trade_count=3,
        tolerance=Tolerance.default(),
    )
    assert out == []


def test_cross_check_uses_hybrid_tolerance_for_pnl():
    # Diff 1e-9 should pass under default rel=1e-6; diff 1.0 should fail.
    sim_close = SimulatorSummary(totalpnl=1600.0)
    assert cross_check(
        sim_close,
        realized_pnl_total=1600.0 + 1e-9,
        win_count=0,
        loss_count=0,
        trade_count=0,
        tolerance=Tolerance.default(),
    ) == []
    sim_far = SimulatorSummary(totalpnl=1600.0)
    assert len(cross_check(
        sim_far,
        realized_pnl_total=1601.0,
        win_count=0,
        loss_count=0,
        trade_count=0,
        tolerance=Tolerance.default(),
    )) == 1


def test_cli_summary_match_exits_0(capsys):
    code = main([
        "--trades", str(FIXTURES / "simple_long.csv"),
        "--initial-cash", "1000000",
        "--summary", str(FIXTURES / "simple_long.summary_match.sexp"),
    ])
    assert code == EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["divergences"] == []


def test_cli_summary_pnl_diverges_exits_3(capsys):
    code = main([
        "--trades", str(FIXTURES / "simple_long.csv"),
        "--initial-cash", "1000000",
        "--summary", str(FIXTURES / "simple_long.summary_pnl_diverges.sexp"),
    ])
    assert code == EXIT_PNL_MISMATCH
    out = json.loads(capsys.readouterr().out)
    summary_div = [d for d in out["divergences"] if d["type"] == "summary_mismatch"]
    assert len(summary_div) == 1
    assert summary_div[0]["field"] == "realized_pnl_total"
    assert summary_div[0]["simulator_value"] == 1500.0


def test_cli_summary_counts_diverge_exits_3(capsys):
    code = main([
        "--trades", str(FIXTURES / "simple_long.csv"),
        "--initial-cash", "1000000",
        "--summary", str(FIXTURES / "simple_long.summary_count_diverges.sexp"),
    ])
    assert code == EXIT_PNL_MISMATCH
    out = json.loads(capsys.readouterr().out)
    fields = {d["field"] for d in out["divergences"] if d["type"] == "summary_mismatch"}
    assert fields == {"win_count", "loss_count", "trade_count"}


def test_cli_summary_malformed_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.sexp"
    bad.write_text("((((")
    code = main([
        "--trades", str(FIXTURES / "simple_long.csv"),
        "--initial-cash", "1000000",
        "--summary", str(bad),
    ])
    assert code == EXIT_PARSE


def test_cli_summary_missing_path_exits_2(tmp_path, capsys):
    code = main([
        "--trades", str(FIXTURES / "simple_long.csv"),
        "--initial-cash", "1000000",
        "--summary", str(tmp_path / "does_not_exist.sexp"),
    ])
    assert code == EXIT_PARSE
