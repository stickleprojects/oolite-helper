"""Minimal parser for OpenStep-style ASCII property lists, as Oolite uses.

Handles dictionaries { k = v; }, arrays ( a, b ), quoted and bare strings,
and // and /* */ comments. All scalars come back as str, including GNUstep's
extended forms: <*BY>/<*BN> as "YES"/"NO", <*I12> as "12", <*R1.5> as "1.5".
<hex data> comes back as bytes.
"""

import re
from os import PathLike
from typing import TypeAlias, cast

PlistValue: TypeAlias = str | bytes | list["PlistValue"] | dict[str, "PlistValue"]

_BARE = re.compile(r"[A-Za-z0-9_.$/:+\-]+")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


class PlistError(ValueError):
    pass


def loads(text: str) -> PlistValue:
    p = _Parser(text)
    value = p.value()
    p.skip()
    if p.i != len(p.s):
        raise p.error("trailing content")
    return value


def load(path: str | PathLike[str]) -> PlistValue:
    with open(path, encoding="utf-8") as f:
        return loads(f.read())


class _Parser:
    def __init__(self, s: str) -> None:
        self.s = s
        self.i = 0

    def error(self, msg: str) -> PlistError:
        line = self.s.count("\n", 0, self.i) + 1
        return PlistError(f"{msg} at line {line}")

    def skip(self) -> None:
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c.isspace():
                self.i += 1
            elif s.startswith("//", self.i):
                end = s.find("\n", self.i)
                self.i = len(s) if end < 0 else end + 1
            elif s.startswith("/*", self.i):
                end = s.find("*/", self.i + 2)
                if end < 0:
                    raise self.error("unterminated comment")
                self.i = end + 2
            else:
                break

    def peek(self) -> str:
        self.skip()
        return self.s[self.i] if self.i < len(self.s) else ""

    def expect(self, ch: str) -> None:
        if self.peek() != ch:
            raise self.error(f"expected {ch!r}")
        self.i += 1

    def value(self) -> PlistValue:
        c = self.peek()
        if c == "{":
            return self.dict()
        if c == "(":
            return self.array()
        if c == '"':
            return self.quoted()
        if c == "<":
            return self.angled()
        m = _BARE.match(self.s, self.i)
        if not m:
            raise self.error("unexpected character")
        self.i = m.end()
        return m.group()

    def dict(self) -> dict[str, PlistValue]:
        self.expect("{")
        d: dict[str, PlistValue] = {}
        while self.peek() != "}":
            key = cast(str, self.value())
            self.expect("=")
            d[key] = self.value()
            if self.peek() == ";":
                self.i += 1
        self.i += 1
        return d

    def array(self) -> list[PlistValue]:
        self.expect("(")
        items: list[PlistValue] = []
        while self.peek() != ")":
            items.append(self.value())
            if self.peek() == ",":
                self.i += 1
        self.i += 1
        return items

    def angled(self) -> str | bytes:
        end = self.s.find(">", self.i)
        if end < 0:
            raise self.error("unterminated <...>")
        body = self.s[self.i + 1 : end]
        value: str | bytes
        if body.startswith("*"):
            kind, text = body[1:2], body[2:].strip()
            if kind == "B" and text in ("Y", "N"):
                value = "YES" if text == "Y" else "NO"
            elif kind in ("I", "R", "D") and text:
                value = text
            else:
                raise self.error(f"unknown value <{body}>")
        else:
            try:
                value = bytes.fromhex(body)
            except ValueError:
                raise self.error("bad <hex data>") from None
        self.i = end + 1
        return value

    def quoted(self) -> str:
        self.i += 1  # opening quote
        out: list[str] = []
        s = self.s
        while True:
            if self.i >= len(s):
                raise self.error("unterminated string")
            c = s[self.i]
            if c == '"':
                self.i += 1
                return "".join(out)
            if c == "\\" and self.i + 1 < len(s):
                out.append(_ESCAPES.get(s[self.i + 1], s[self.i + 1]))
                self.i += 2
            else:
                out.append(c)
                self.i += 1
