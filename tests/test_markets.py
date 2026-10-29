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

    assert store.data["markets"] == [] and store.data["lots"] == {}
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
    assert json.loads(path.read_text(encoding="utf-8"))["lots"]["food"][0]["units"] == 2


# -- lots (#95) -----------------------------------------------------------------

LAVE = {"galaxy": 0, "systemID": 7, "systemName": "Lave"}


def trade(store, kind, units, price, clock, commodity="food"):
    message = {"type": kind, **LAVE, "gameClock": clock, "commodity": commodity}
    store.apply({**message, "units": units, "price": price})


def hold(store, goods, cause="docked", contracts=()):
    manifest = [{"commodity": c, "quantity": q, "unit": "t"} for c, q in goods.items()]
    store.apply({"type": "hold", "cause": cause, "goods": manifest, "contracts": list(contracts)})


def lots(store, commodity="food"):
    return [
        (lot["units"], lot["price"], lot["from"]) for lot in store.data["lots"].get(commodity, [])
    ]


def test_a_purchase_adds_a_lot_with_where_it_was_bought(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    trade(store, "bought", 2, 42, 1.0)
    lot = store.data["lots"]["food"][0]
    assert (lot["units"], lot["price"], lot["system_name"], lot["from"]) == (
        2,
        42,
        "Lave",
        "bought",
    )


def test_a_sale_uses_up_the_oldest_lot_first(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    trade(store, "bought", 2, 42, 1.0)
    trade(store, "bought", 2, 50, 2.0)
    trade(store, "sold", 1, 55, 3.0)
    assert lots(store) == [(1, 42, "bought"), (2, 50, "bought")]


def test_a_sale_across_two_lots_takes_from_both(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    trade(store, "bought", 2, 42, 1.0)
    trade(store, "bought", 2, 50, 2.0)
    trade(store, "sold", 3, 55, 3.0)
    assert lots(store) == [(1, 50, "bought")]


def test_cargo_gone_from_the_hold_uses_up_the_oldest_lot(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    trade(store, "bought", 2, 42, 1.0)
    trade(store, "bought", 2, 50, 2.0)
    hold(store, {"food": 3}, cause="dumped")
    assert lots(store) == [(1, 42, "bought"), (2, 50, "bought")]


def test_scooped_cargo_is_a_lot_with_no_price(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    hold(store, {"food": 1}, cause="scooped")
    assert lots(store) == [(1, None, "scooped")]


def test_cargo_the_helper_never_saw_bought_is_of_unknown_origin(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    hold(store, {"furs": 35}, cause="start")
    assert lots(store, "furs") == [(35, None, "unknown")]


def test_contract_cargo_isnt_a_lot(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    hold(store, {"furs": 10}, contracts=[{"commodity": "furs", "quantity": 10}])
    assert lots(store, "furs") == []


def test_the_average_price_comes_from_the_priced_lots(tmp_path):
    store = MarketStore(tmp_path / "markets.json")
    trade(store, "bought", 2, 40, 1.0)
    hold(store, {"food": 3}, cause="scooped")
    assert store.cost_basis["food"] == {"units": 2, "total_cost": 80, "average_price": 40}


def test_a_version_1_average_is_read_as_one_lot_of_unknown_origin(tmp_path):
    path = tmp_path / "markets.json"
    basis = {"food": {"units": 5, "total_cost": 500, "average_price": 100}}
    path.write_text(json.dumps({"version": 1, "markets": [], "cost_basis": basis}))
    assert lots(MarketStore(path)) == [(5, 100, "unknown")]


def test_a_version_1_file_is_saved_as_version_2(tmp_path):
    path = tmp_path / "markets.json"
    basis = {"food": {"units": 5, "total_cost": 500, "average_price": 100}}
    path.write_text(json.dumps({"version": 1, "markets": [], "cost_basis": basis}))
    MarketStore(path)
    saved = json.loads(path.read_text())
    assert (saved["version"], "cost_basis" in saved) == (2, False)
