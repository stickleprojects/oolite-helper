from helper.state import GameState
from helper.trade import chart_advice


def chart_state(selected=None, market=None, manifest=None, current=7, systems=None, fuel=7):
    state = GameState()
    state.apply({"type": "systems", "fuel": fuel, "systems": systems or []})
    state.apply(
        {
            "type": "chart_target",
            "infoSystem": 8,
            "targetSystem": 8,
            "currentSystem": current,
            "system": {
                "id": 8,
                "name": "Zaonce",
                "distance": 6.5,
                "economy": 5,
                "government": 6,
                "techLevel": 9,
                "samplePrices": {},
                **(selected or {}),
            },
            "originMarket": market or {},
            "manifest": manifest or [],
        }
    )
    return state


def line(advice, prefix):
    return next(row for row in advice.splitlines() if row.startswith(prefix))


def test_no_selected_system_gives_no_advice():
    assert chart_advice(GameState()) == ""


def test_tech_level_shown_one_based_like_the_game():
    assert "Tech level 10" in chart_advice(chart_state())


def test_unknown_economy_and_government_are_named_by_number():
    advice = chart_advice(chart_state({"economy": 12, "government": None, "techLevel": None}))
    assert "Economy 12 · Government None · Tech level ?" in advice


def test_current_system_shows_details_without_trade_lines():
    advice = chart_advice(
        chart_state(
            {"id": 7, "samplePrices": {"food": 90}}, market={"food": {"price": 40, "quantity": 9}}
        )
    )
    assert advice.splitlines()[0] == "Zaonce — current system"
    assert "Buy here" not in advice and "Sell from hold" not in advice
    assert "Nearest agricultural" in advice


def test_buy_skips_out_of_stock_and_marks_illegal_goods():
    advice = chart_advice(
        chart_state(
            {"samplePrices": {"food": 60, "narcotics": 900, "furs": 800}},
            market={
                "food": {"price": 40, "quantity": 9, "legality_export": 0, "legality_import": 0},
                "narcotics": {"price": 500, "quantity": 2, "legality_export": 2},
                "furs": {"price": 100, "quantity": 0},
            },
        )
    )
    assert line(advice, "Buy here") == (
        "Buy here: Narcotics (+40.0 cr/unit, illegal), Food (+2.0 cr/unit)"
    )


def test_sell_from_hold_ranks_by_total_profit():
    advice = chart_advice(
        chart_state(
            {"samplePrices": {"food": 60, "computers": 900, "furs": 500}},
            market={
                "food": {"price": 40, "quantity": 9},
                "computers": {"price": 880, "quantity": 9},
            },
            manifest=[
                {"name": "computers", "displayName": "Computers", "quantity": 1},
                {"name": "food", "displayName": "Food", "quantity": 10},
                {"name": "furs", "displayName": "Furs", "quantity": 1},
            ],
        )
    )
    # Food +2.0 × 10 beats Computers +2.0 × 1; Furs has no local price, so it's last.
    assert line(advice, "Sell from hold") == (
        "Sell from hold: Food ×10 (6.0 cr/unit, +2.0 vs here), "
        "Computers ×1 (90.0 cr/unit, +2.0 vs here), Furs ×1 (50.0 cr/unit)"
    )


def test_nearest_systems_need_fuel_information():
    state = chart_state(systems=[{"name": "Lave", "distance": 1.0, "economy": 5}])
    state.fuel = None
    assert "Nearest agricultural: none in range" in chart_advice(state)
