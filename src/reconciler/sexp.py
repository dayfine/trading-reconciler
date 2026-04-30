"""Minimal s-expression serializer for OCaml-side consumption.

Encoding choices (documented per PHASE_1_SPEC.md §12.1):
- None       → `()`
- True/False → `true` / `false`
- str/date   → bare atom if no whitespace/parens, else double-quoted
- int/float  → bare numeric atom (Python repr)
- dict       → `((k1 v1) (k2 v2) ...)`
- list       → `(v1 v2 ...)`
"""

from __future__ import annotations

from typing import Any

_QUOTE_CHARS = set(" \t\n()\"")


def _atom(s: str) -> str:
    if not s:
        return '""'
    if any(c in _QUOTE_CHARS for c in s):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def encode(value: Any) -> str:
    if value is None:
        return "()"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _atom(value)
    if isinstance(value, dict):
        parts = [f"({_atom(str(k))} {encode(v)})" for k, v in value.items()]
        return "(" + " ".join(parts) + ")"
    if isinstance(value, (list, tuple)):
        parts = [encode(v) for v in value]
        return "(" + " ".join(parts) + ")"
    raise TypeError(f"sexp encode: unsupported type {type(value).__name__}")
