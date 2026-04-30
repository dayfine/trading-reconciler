import json
from pathlib import Path

from reconciler.cli import (
    EXIT_CASH_FLOOR,
    EXIT_OK,
    EXIT_PARSE,
    EXIT_PNL_MISMATCH,
    main,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_exit_0_simple_long(capsys):
    code = main(["--trades", str(FIXTURES / "simple_long.csv"), "--initial-cash", "1000000"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["summary"]["realized_pnl_total"] == 1600.0
    assert parsed["summary"]["trade_count"] == 3
    assert parsed["divergences"] == []


def test_exit_0_simple_short():
    code = main(["--trades", str(FIXTURES / "simple_short.csv"), "--initial-cash", "1000000"])
    assert code == EXIT_OK


def test_exit_0_mixed():
    code = main(["--trades", str(FIXTURES / "mixed_long_short.csv"), "--initial-cash", "1000000"])
    assert code == EXIT_OK


def test_exit_0_legacy():
    code = main(["--trades", str(FIXTURES / "legacy_12col.csv"), "--initial-cash", "1000000"])
    assert code == EXIT_OK


def test_exit_0_intra_day():
    code = main(["--trades", str(FIXTURES / "intra_day_round_trip.csv"), "--initial-cash", "10000"])
    assert code == EXIT_OK


def test_exit_3_pnl_disagrees():
    code = main(["--trades", str(FIXTURES / "pnl_disagrees.csv"), "--initial-cash", "1000000"])
    assert code == EXIT_PNL_MISMATCH


def test_exit_4_cash_floor_load_bearing(capsys):
    code = main(
        [
            "--trades",
            str(FIXTURES / "cash_floor_violation_event_walk.csv"),
            "--initial-cash",
            "10000",
        ]
    )
    assert code == EXIT_CASH_FLOOR
    out = capsys.readouterr().out
    parsed = json.loads(out)
    cash_floor = [d for d in parsed["divergences"] if d["type"] == "cash_floor"]
    assert cash_floor


def test_exit_4_wins_over_3_when_both_present(tmp_path):
    """Severity ordering: cash_floor > pnl_mismatch."""
    csv = tmp_path / "both.csv"
    csv.write_text(
        "symbol,side,entry_date,exit_date,days_held,entry_price,exit_price,quantity,"
        "pnl_dollars,pnl_percent,entry_stop,exit_stop,exit_trigger\n"
        "A,LONG,2024-01-02,2024-02-01,30,30,32,100,9999,100,28,32,target\n"
        "B,LONG,2024-01-02,2024-02-15,44,30,32,100,200,6.67,28,32,target\n"
        "C,LONG,2024-01-02,2024-03-01,59,30,32,100,200,6.67,28,32,target\n"
        "D,LONG,2024-01-02,2024-03-15,73,30,32,100,200,6.67,28,32,target\n"
        "E,LONG,2024-01-02,2024-04-01,90,30,32,100,200,6.67,28,32,target\n"
    )
    code = main(["--trades", str(csv), "--initial-cash", "10000"])
    assert code == EXIT_CASH_FLOOR


def test_exit_2_parse_error(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("not,a,valid,header\n")
    code = main(["--trades", str(bad), "--initial-cash", "1000000"])
    assert code == EXIT_PARSE


def test_strict_fp_warns_on_explicit_epsilon(capsys):
    main(
        [
            "--trades",
            str(FIXTURES / "simple_long.csv"),
            "--initial-cash",
            "1000000",
            "--strict-fp",
            "--epsilon-relative",
            "0.5",
        ]
    )
    err = capsys.readouterr().err
    assert "--strict-fp set" in err
    assert "--epsilon-relative" in err
