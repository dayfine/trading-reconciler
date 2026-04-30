"""Minimal s-expression reader for parsing simulator summary.sexp.

Handles atoms (bare or double-quoted with backslash escapes), parenthesized
lists, line comments starting with `;`, and arbitrary whitespace. Returns
nested Python lists of strings.
"""

from __future__ import annotations


class SexpReadError(Exception):
    pass


def loads(text: str) -> list:
    parser = _Parser(text)
    parser._skip_ws()
    if parser._eof():
        raise SexpReadError("empty input")
    value = parser._read_value()
    parser._skip_ws()
    if not parser._eof():
        raise SexpReadError(f"trailing input at offset {parser.i}")
    return value


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0

    def _eof(self) -> bool:
        return self.i >= len(self.text)

    def _peek(self) -> str:
        return self.text[self.i] if not self._eof() else ""

    def _skip_ws(self) -> None:
        while not self._eof():
            c = self.text[self.i]
            if c.isspace():
                self.i += 1
            elif c == ";":
                while not self._eof() and self.text[self.i] != "\n":
                    self.i += 1
            else:
                return

    def _read_value(self):
        self._skip_ws()
        if self._eof():
            raise SexpReadError("unexpected EOF")
        c = self._peek()
        if c == "(":
            return self._read_list()
        if c == ")":
            raise SexpReadError(f"unexpected ')' at offset {self.i}")
        if c == '"':
            return self._read_quoted()
        return self._read_bare_atom()

    def _read_list(self) -> list:
        assert self._peek() == "("
        self.i += 1
        out: list = []
        while True:
            self._skip_ws()
            if self._eof():
                raise SexpReadError("unterminated list")
            if self._peek() == ")":
                self.i += 1
                return out
            out.append(self._read_value())

    def _read_quoted(self) -> str:
        assert self._peek() == '"'
        self.i += 1
        chars: list[str] = []
        while True:
            if self._eof():
                raise SexpReadError("unterminated quoted atom")
            c = self.text[self.i]
            if c == '"':
                self.i += 1
                return "".join(chars)
            if c == "\\":
                self.i += 1
                if self._eof():
                    raise SexpReadError("dangling backslash")
                chars.append(self.text[self.i])
                self.i += 1
                continue
            chars.append(c)
            self.i += 1

    def _read_bare_atom(self) -> str:
        start = self.i
        while not self._eof():
            c = self.text[self.i]
            if c.isspace() or c in "()\";":
                break
            self.i += 1
        return self.text[start:self.i]
