import json

import pytest

from helper.markets import MarketStore


def test_missing_file_starts_empty_without_a_warning(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    assert store.load_error is None
    assert store.data["markets"] == []


@pytest.mark.parametrize(
    "content",
    [
        '{"markets": [',  # truncated
        "\xff\xfe not text",
        "[]",  # not an object
        '{"markets": {}, "cost_basis": {}}',
        '{"markets": [], "cost_basis": []}',
        '{"markets": [], "trade_events": "x"}',
    ],
)
def test_damaged_file_is_kept_aside_and_store_starts_fresh(tmp_path, content):
    path = tmp_path / "markets.json"
    path.write_bytes(content.encode("latin-1"))
    store = MarketStore(path)

    assert store.data["markets"] == [] and store.data["cost_basis"] == {}
    assert "kept as markets.json.bad" in store.load_error
    assert (tmp_path / "markets.json.bad").read_bytes() == content.encode("latin-1")
    assert not path.exists()

    store.apply(
        {
            "type": "bought",
            "galaxy": 0,
            "systemID": 7,
            "gameClock": 1.0,
            "commodity": "food",
            "units": 2,
            "price": 40,
        }
    )
    assert json.loads(path.read_text(encoding="utf-8"))["cost_basis"]["food"]["units"] == 2
