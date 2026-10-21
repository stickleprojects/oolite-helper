from datetime import UTC, datetime

from helper.browser import commodity_rows, sort_rows
from helper.state import GameState

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def market(**prices):
    # Shaped like station.market in 1.92.1: legality comes as strings.
    return {
        name: {"price": price, "quantity": 5, "legality_export": legal, "legality_import": "0"}
        for name, (price, legal) in prices.items()
    }


def state(docked=True, here=None, systems=None, current=7):
    s = GameState()
    s.apply({"type": "ready", "docked": docked, "alert": 0 if docked else 1})
    if here is not None:
        s.apply({"type": "market", "galaxy": 0, "systemID": current, "market": here})
    s.apply({"type": "systems", "galaxy": 0, "fuel": 7, "systems": systems or []})
    s.current_system = current
    return s


def remembered(system_id, name, prices, seen="2026-10-21T11:55:00+00:00"):
    return {
        "galaxy": 0,
        "system_id": system_id,
        "system_name": name,
        "station": "X",
        "seen_at": seen,
        "prices": prices,
    }


def by_name(rows):
    return {row.commodity: row for row in rows}


def test_best_price_prefers_remembered_real_prices_over_estimates():
    s = state(
        here=market(food=(40, "0"), furs=(700, "0")),
        systems=[
            {"id": 8, "name": "Zaonce", "distance": 6.5, "samplePrices": {"food": 90, "furs": 800}},
            {"id": 9, "name": "Diso", "distance": 3.0, "samplePrices": {"food": 60, "furs": 750}},
        ],
    )
    markets = [remembered(9, "Diso", market(food=(95, "0")))]
    rows = by_name(commodity_rows(s, markets, NOW))

    assert (rows["food"].best, rows["food"].where, rows["food"].best_note) == (95, "Diso", "5m ago")
    assert (rows["furs"].best, rows["furs"].where, rows["furs"].best_note) == (
        800,
        "Zaonce",
        "est.",
    )
    assert rows["food"].margin == 55
    assert rows["food"].here_note == ""  # live market while docked


def test_illegal_from_the_games_string_legality():
    s = state(here=market(food=(40, "0"), narcotics=(500, "2")))
    rows = by_name(commodity_rows(s, [], NOW))
    assert not rows["food"].illegal
    assert rows["narcotics"].illegal


def test_in_flight_uses_the_remembered_market_for_the_current_system():
    s = state(
        docked=False,
        systems=[{"id": 8, "name": "Zaonce", "distance": 6.5, "samplePrices": {"food": 90}}],
    )
    markets = [
        remembered(7, "Lave", market(food=(30, "0")), seen="2026-10-21T10:00:00+00:00"),
        remembered(7, "Lave", market(food=(42, "0")), seen="2026-10-21T11:00:00+00:00"),
    ]
    row = by_name(commodity_rows(s, markets, NOW))["food"]
    assert (row.here, row.here_note, row.margin) == (42, "1h ago", 48)


def test_no_data_gives_no_rows_and_unknown_values_sort_last():
    assert commodity_rows(state(docked=False), [], NOW) == []
    s = state(
        here=market(food=(40, "0"), gold=(400, "0")),
        systems=[{"id": 8, "name": "Zaonce", "distance": 6.5, "samplePrices": {"food": 90}}],
    )
    rows = commodity_rows(s, [], NOW)
    assert [row.commodity for row in sort_rows(rows, "margin")] == ["food", "gold"]
    assert [row.commodity for row in sort_rows(rows, "margin", descending=False)] == [
        "food",
        "gold",
    ]
    assert [row.commodity for row in sort_rows(rows, "here", descending=False)] == ["food", "gold"]


def test_other_galaxies_markets_are_ignored():
    s = state(
        here=market(food=(40, "0")),
        systems=[{"id": 8, "name": "Zaonce", "distance": 6.5, "samplePrices": {}}],
    )
    other = dict(remembered(8, "Zaonce", market(food=(999, "0"))), galaxy=1)
    assert by_name(commodity_rows(s, [other], NOW))["food"].best is None
