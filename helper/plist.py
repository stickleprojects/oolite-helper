"""Minimal parser for OpenStep-style ASCII property lists, as Oolite uses.

Handles dictionaries { k = v; }, arrays ( a, b ), quoted and bare strings,
and // and /* */ comments. All scalars come back as str.
"""

import re

_BARE = re.compile(r"[A-Za-z0-9_.$/:+\-]+")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


class PlistError(ValueError):
    pass


def loads(text):
    p = _Parser(text)
    value = p.value()
    p.skip()
    if p.i != len(p.s):
        raise p.error("trailing content")
    return value


def load(path):
    with open(path, encoding="utf-8") as f:
        return loads(f.read())


class _Parser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def error(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        return PlistError(f"{msg} at line {line}")

    def skip(self):
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

    def peek(self):
        self.skip()
        return self.s[self.i] if self.i < len(self.s) else ""

    def expect(self, ch):
        if self.peek() != ch:
            raise self.error(f"expected {ch!r}")
        self.i += 1

    def value(self):
        c = self.peek()
        if c == "{":
            return self.dict()
        if c == "(":
            return self.array()
        if c == '"':
            return self.quoted()
        m = _BARE.match(self.s, self.i)
        if not m:
            raise self.error("unexpected character")
        self.i = m.end()
        return m.group()

    def dict(self):
        self.expect("{")
        d = {}
        while self.peek() != "}":
            key = self.value()
            self.expect("=")
            d[key] = self.value()
            if self.peek() == ";":
                self.i += 1
        self.i += 1
        return d

    def array(self):
        self.expect("(")
        items = []
        while self.peek() != ")":
            items.append(self.value())
            if self.peek() == ",":
                self.i += 1
        self.i += 1
        return items

    def quoted(self):
        self.i += 1  # opening quote
        out = []
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
