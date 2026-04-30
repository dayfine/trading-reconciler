"""Tests pinned to spec ambiguities that PR-B surfaced.

Each xfail here links to a milestone issue. When the spec lands a
resolution, flip the test from xfail to a hard assertion."""
from __future__ import annotations

from pathlib import Path

import pytest

from reconciler.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.xfail(
    reason=(
        "Spec ambiguity: PHASE_1_SPEC.md §2.5/§4.3/§10 fixture #5 say exit 2 "
        "for held-through-split row without --splits, but the in-window "
        "predicate requires known splits. Current behavior: exit 3 "
        "(pnl_mismatch). See dayfine/trading-reconciler#9."
    ),
    strict=True,
)
def test_held_through_split_without_splits_exits_2():
    from reconciler.cli import EXIT_PARSE

    code = main(
        [
            "--trades",
            str(FIXTURES / "held_through_4to1_split.csv"),
            "--initial-cash",
            "50000",
        ]
    )
    assert code == EXIT_PARSE
