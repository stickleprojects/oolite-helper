from datetime import UTC, datetime

from helper.browser import (
    buy_limit,
    commodity_offers,
    commodity_rows,
    held,
    sort_rows,
    trade_steps,
)
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


def test_offers_list_every_system_best_first_with_danger_and_legality():
    s = state(
        here=market(furs=(700, "0")),
        systems=[
            {
                "id": 8,
                "name": "Zaonce",
                "distance": 6.5,
                "government": 0,
                "economy": 5,
                "samplePrices": {"furs": 800},
            },
            {
                "id": 9,
                "name": "Diso",
                "distance": 3.0,
                "government": 6,
                "economy": 1,
                "samplePrices": {"furs": 750},
            },
        ],
    )
    markets = [remembered(9, "Diso", market(furs=(900, "1")))]
    offers = commodity_offers(s, markets, NOW, "furs")
    assert [(o.name, o.price, o.note) for o in offers] == [
        ("Diso", 900, "5m ago"),
        ("Zaonce", 800, "est."),
    ]
    assert offers[0].illegal is True and not offers[0].dangerous
    assert offers[1].illegal is None and offers[1].dangerous


def with_ship(s, credits, space):
    s.credits = credits
    s.cargo_space = {"available": space, "capacity": 20}
    return s


def test_buy_limit_follows_the_games_order_on_sale_then_credits_then_space():
    here = market(furs=(700, "0"))  # 5 on sale at 70.0 cr
    assert buy_limit(with_ship(state(here=here), 1000, 20), [], NOW, "furs") == (5, "on sale")
    assert buy_limit(with_ship(state(here=here), 150.5, 20), [], NOW, "furs") == (2, "credits")
    assert buy_limit(with_ship(state(here=here), 1000, 3), [], NOW, "furs") == (3, "cargo space")
    assert buy_limit(state(here=here), [], NOW, "gold") == (0, "not sold here")


def test_goods_in_kg_go_in_the_safe_so_cargo_space_does_not_limit_them():
    here = {"gold": {"price": 399, "quantity": 4, "quantity_unit": "1"}}
    assert buy_limit(with_ship(state(here=here), 1000, 0), [], NOW, "gold") == (4, "on sale")
    assert commodity_rows(state(here=here), [], NOW)[0].unit == "kg"


KEYS = {
    "key_gui_arrow_right": "→",
    "key_gui_arrow_left": "←",
    "key_gui_arrow_up": "↑",
    "key_gui_arrow_down": "↓",
    "key_gui_market": "8",
    "key_gui_chart_screens": "6",
    "key_launch_ship": "1",
    "key_hyperspace": "H",
    "key_ident_system": "R",
    "key_next_target": "+",
    "key_docking_clearance_request": "Shift+L",
    "key_autopilot": "C",
}.get


def zaonce(system_id=8):
    s = state(
        here=market(furs=(700, "0")),
        systems=[
            {"id": system_id, "name": "Zaonce", "distance": 6.5, "samplePrices": {"furs": 800}}
        ],
    )
    return commodity_offers(s, [], NOW, "furs")[0]


def at(target=3, docked=True, current=7):
    s = state(docked=docked, current=current)
    s.target_system = target
    return s


def test_steps_cover_buying_targeting_the_jump_docking_and_selling():
    steps = trade_steps(KEYS, "Furs", 5, 5, zaonce(), at())
    assert steps == [
        "Market 8 → ↑ / ↓ to Furs → Shift+→ buys the most you can (5)",
        "Chart 6 → move the cursor to Zaonce (on the galactic chart you can type its name)",
        "Launch 1, fly clear of other ships, then H jumps to Zaonce after a countdown "
        "(press it again to cancel)",
        "At Zaonce: target the station (R with it ahead, or +), Shift+L for clearance, "
        "C for the docking computer",
        "Docked at Zaonce: Market 8 → Furs → Shift+← sells all",
    ]


def test_steps_press_once_per_unit_and_skip_the_chart_when_already_targeted():
    steps = trade_steps(KEYS, "Furs", 3, 5, zaonce(), at(target=8))
    assert steps[0].endswith("→ ×3")
    assert not any(step.startswith("Chart") for step in steps)


def test_steps_after_buying_start_from_the_cargo_held():
    steps = trade_steps(KEYS, "Furs", 0, 0, zaonce(), at(target=8), holding=14)
    assert steps[0] == "You hold 14 Furs."
    assert steps[1].startswith("Launch 1, fly clear")
    in_flight = trade_steps(KEYS, "Furs", 0, 0, zaonce(), at(target=8, docked=False), holding=14)
    assert in_flight[1].startswith("Fly clear")


def test_steps_at_the_destination_are_just_selling():
    steps = trade_steps(KEYS, "Furs", 0, 0, zaonce(), at(current=8), holding=14)
    assert steps == ["You hold 14 Furs.", "Docked at Zaonce: Market 8 → Furs → Shift+← sells all"]


def test_steps_say_when_nothing_can_be_bought():
    steps = trade_steps(KEYS, "Furs", 0, 0, zaonce(), at(docked=False))
    assert steps == ["Nothing to buy: Furs isn't affordable or on sale here."]


def test_held_counts_the_commodity_in_the_manifest():
    s = state()
    s.manifest = [{"commodity": "furs", "quantity": 14, "unit": "t"}, {"commodity": "food"}]
    assert (held(s, "furs"), held(s, "food"), held(s, "gold")) == (14, 0, 0)
