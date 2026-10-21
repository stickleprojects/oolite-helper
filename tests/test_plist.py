import pytest

from helper import plist


def test_loads_nested_dicts_arrays_and_string_forms():
    assert plist.loads(
        '{ bare = value; quoted = "two words"; list = (one, "two", { nested = yes; }); }'
    ) == {
        "bare": "value",
        "quoted": "two words",
        "list": ["one", "two", {"nested": "yes"}],
    }


def test_loads_escapes_and_comments():
    assert plist.loads(
        r"""{
            // a line comment
            newline = "line\nnext";
            escaped = "quote: \" slash: \\ tab:\t";
            /* block
               comment */
            bare = word;
        }"""
    ) == {
        "newline": "line\nnext",
        "escaped": 'quote: " slash: \\ tab:\t',
        "bare": "word",
    }


def test_loads_real_trimmed_keyconfig_fixture():
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "keyconfig2.plist"
    data = plist.load(fixture)
    assert data["default"]["key_roll_left"] == [{"key": "arrowLeft"}]
    assert data["default"]["key_next_compass_mode"] == [{"key": "\\"}]


@pytest.mark.parametrize(
    ("source", "message", "line"),
    [
        ("{\n key = value;\n bad = @;\n}", "unexpected character", 3),
        ('{\n key = "unterminated\n}', "unterminated string", 3),
        ("{\n /* unterminated", "unterminated comment", 2),
        ("{}\nextra", "trailing content", 2),
    ],
)
def test_parse_errors_report_the_line(source, message, line):
    with pytest.raises(plist.PlistError, match=message) as exc:
        plist.loads(source)
    assert f"line {line}" in str(exc.value)


def test_loads_gnustep_extended_scalars():
    assert plist.loads("{ a = <*BY>; b = <*BN>; c = <*I42>; d = <*R1.5>; e = <0aff>; }") == {
        "a": "YES",
        "b": "NO",
        "c": "42",
        "d": "1.5",
        "e": b"\x0a\xff",
    }


@pytest.mark.parametrize("source", ["{ a = <*BX>; }", "{ a = <zz>; }", "{ a = <*BY; }"])
def test_bad_angled_values_raise(source):
    with pytest.raises(plist.PlistError):
        plist.loads(source)
