"""Tests for PR-C: commissions wired through CLI, sexp output, --verbose, --slippage-bps."""
from __future__ import annotations

import json
from pathlib import Path

from reconciler.cli import EXIT_OK, EXIT_PNL_MISMATCH, main

FIXTURES = Path(__file__).parent / "fixtures"


def test_commission_match_with_correct_flag():
    code = main(
        [
            "--trades",
            str(FIXTURES / "commission_match.csv"),
            "--initial-cash",
            "1000000",
            "--commission-per-share",
            "0.01",
        ]
    )
    assert code == EXIT_OK


def test_commission_mismatch_without_flag_diverges():
    code = main(
        [
            "--trades",
            str(FIXTURES / "commission_mismatch.csv"),
            "--initial-cash",
            "1000000",
        ]
    )
    assert code == EXIT_PNL_MISMATCH


def test_commission_per_trade_flag():
    """Per-trade commission applies to each leg → 2x per round-trip."""
    # Simple LONG: 100 → 105, qty 100 → gross 500. With $5 per-trade × 2 legs = -$10.
    # Net 490.
    csv = FIXTURES.parent / "fixtures_tmp_commission_per_trade.csv"
    csv.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "AAPL,LONG,2024-01-02,2024-02-15,44,100,105,100,490,4.9,95,105,target\n"
    )
    try:
        code = main(
            [
                "--trades",
                str(csv),
                "--initial-cash",
                "1000000",
                "--commission-per-trade",
                "5.0",
            ]
        )
        assert code == EXIT_OK
    finally:
        csv.unlink()


def test_sexp_format_well_formed(capsys):
    code = main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
            "--format",
            "sexp",
        ]
    )
    assert code == EXIT_OK
    out = capsys.readouterr().out.strip()
    assert out.startswith("((summary")
    # Balanced parens
    assert out.count("(") == out.count(")")


def test_sexp_format_does_not_quote_iso_dates(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
            "--format",
            "sexp",
        ]
    )
    out = capsys.readouterr().out
    assert "2024-01-02" in out
    assert '"2024-01-02"' not in out


def test_json_format_remains_default(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
        ]
    )
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "summary" in parsed


def test_slippage_bps_warns(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
            "--slippage-bps",
            "5",
        ]
    )
    err = capsys.readouterr().err
    assert "--slippage-bps" in err
    assert "Phase 2" in err


def test_slippage_bps_default_does_not_warn(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
        ]
    )
    err = capsys.readouterr().err
    assert "slippage" not in err.lower()


def test_verbose_emits_info_to_stderr(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
            "--verbose",
        ]
    )
    err = capsys.readouterr().err
    assert "INFO" in err
    assert "tolerance" in err
    assert "walked 3 trades" in err


def test_quiet_default_emits_no_info(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
        ]
    )
    err = capsys.readouterr().err
    assert "INFO" not in err
