import os

from helper.sources import LogSource


def line(message):
    import json

    return f'12:00:00.000 [ctxkeys]: {json.dumps(message)}\n'


def test_missing_file_then_new_file(tmp_path):
    path = tmp_path / "Latest.log"
    source = LogSource(path)
    assert source.poll() == []

    path.write_text(line({"type": "ready", "docked": False}), encoding="utf-8")
    assert source.poll() == [
        {"type": "session"},
        {"type": "ready", "docked": False},
    ]
    source._file.close()


def test_partial_lines_are_buffered(tmp_path):
    path = tmp_path / "Latest.log"
    path.write_text("", encoding="utf-8")
    source = LogSource(path)
    assert source.poll() == [{"type": "session"}]
    with path.open("a", encoding="utf-8") as log:
        log.write('12:00:00.000 [ctxkeys]: {"type":"rea')
    assert source.poll() == []
    with path.open("a", encoding="utf-8") as log:
        log.write('dy"}\n')
    assert source.poll() == [{"type": "ready"}]
    source._file.close()


def test_new_inode_reopens_from_start(tmp_path):
    path = tmp_path / "Latest.log"
    path.write_text(line({"type": "ready", "docked": False}), encoding="utf-8")
    source = LogSource(path)
    assert [m["type"] for m in source.poll()] == ["session", "ready"]

    replacement = tmp_path / "replacement.log"
    replacement.write_text(line({"type": "ready", "docked": True}), encoding="utf-8")
    os.replace(replacement, path)
    assert source.poll() == [{"type": "session"}, {"type": "ready", "docked": True}]
    source._file.close()


def test_truncated_file_reopens_and_reads_from_start(tmp_path):
    path = tmp_path / "Latest.log"
    path.write_text("ignored line long enough to move file position\n", encoding="utf-8")
    source = LogSource(path)
    assert source.poll() == [{"type": "session"}]

    path.write_text(line({"type": "ready"}), encoding="utf-8")
    assert source.poll() == [{"type": "session"}, {"type": "ready"}]
    source._file.close()


def test_closing_log_line_emits_closed_message(tmp_path):
    path = tmp_path / "Latest.log"
    path.write_text("Closing log at 2026-10-21 16:31:26 +1100.\n", encoding="utf-8")
    source = LogSource(path)
    assert source.poll() == [{"type": "session"}, {"type": "closed"}]
    source._file.close()
