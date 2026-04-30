from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .emit import to_json
from .models import (
    SEVERITY_CASH_FLOOR,
    SEVERITY_MISSING_PRICE,
    SEVERITY_PNL_MISMATCH,
)
from .parser import ParseError, parse_trades
from .tolerance import Tolerance
from .walker import walk

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_PARSE = 2
EXIT_PNL_MISMATCH = 3
EXIT_CASH_FLOOR = 4
EXIT_MISSING_PRICE = 5


SEVERITY_TO_EXIT = {
    SEVERITY_CASH_FLOOR: EXIT_CASH_FLOOR,
    SEVERITY_PNL_MISMATCH: EXIT_PNL_MISMATCH,
    SEVERITY_MISSING_PRICE: EXIT_MISSING_PRICE,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reconciler")
    p.add_argument("--trades", required=True, type=Path)
    p.add_argument("--initial-cash", required=True, type=float)
    p.add_argument("--commission-per-share", type=float, default=0.0)
    p.add_argument("--commission-per-trade", type=float, default=0.0)
    p.add_argument("--epsilon-relative", type=float, default=1e-6)
    p.add_argument("--epsilon-absolute", type=float, default=0.01)
    p.add_argument("--strict-fp", action="store_true")
    p.add_argument("--format", choices=["json"], default="json")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code != 0 else EXIT_OK

    if args.strict_fp:
        if args.epsilon_relative != 1e-6:
            print(
                f"WARN: --strict-fp set; --epsilon-relative {args.epsilon_relative} ignored",
                file=sys.stderr,
            )
        if args.epsilon_absolute != 0.01:
            print(
                f"WARN: --strict-fp set; --epsilon-absolute {args.epsilon_absolute} ignored",
                file=sys.stderr,
            )
        tolerance = Tolerance.strict()
    else:
        tolerance = Tolerance(rel=args.epsilon_relative, abs_=args.epsilon_absolute)

    try:
        trades = parse_trades(args.trades)
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_PARSE

    result = walk(
        trades,
        args.initial_cash,
        tolerance=tolerance,
        commission_per_share=args.commission_per_share,
        commission_per_trade=args.commission_per_trade,
    )
    print(to_json(result))

    if not result.divergences:
        return EXIT_OK
    worst = max(d.severity for d in result.divergences)
    return SEVERITY_TO_EXIT[worst]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
