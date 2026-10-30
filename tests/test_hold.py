"""The hold topic (#95): lots from the market store, worth at the last market."""

from datetime import UTC, datetime

from helper.hold import time_text
from helper.markets import MarketStore
from helper.model import Model
from helper.state import GameState

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def model(tmp_path, clock=None):
    clock = clock or Clock()
    store = MarketStore(tmp_path / "markets.json", now=lambda: NOW)
    return Model(state=GameState(clock=clock), markets=store, clock=clock)


def bought(m, commodity, units, price, system=7, name="Lave", at=1000.0):
    m.dispatch(
        {
            "type": "bought",
            "galaxy": 0,
            "systemID": system,
            "systemName": name,
            "gameClock": at,
            "commodity": commodity,
            "units": units,
            "price": price,
        }
    )


def market(m, prices, name="Lave", at=2000.0):
    m.dispatch(
        {
            "type": "market",
            "galaxy": 0,
            "systemID": 7,
            "systemName": name,
            "station": "Coriolis Station",
            "gameClock": at,
            "market": prices,
        }
    )


def hold(m, goods=(), at=3000.0, **lists):
    m.dispatch({"type": "hold", "cause": "bought", "goods": list(goods), "gameClock": at, **lists})


def food(quantity):
    return {"commodity": "food", "quantity": quantity, "unit": "t"}


def test_there_is_no_hold_before_the_game_sends_one(tmp_path):
    assert model(tmp_path).topic("hold") is None


def test_an_empty_hold_has_no_rows_but_its_space(tmp_path):
    m = model(tmp_path)
    hold(m, space={"used": 0, "capacity": 35})
    assert m.topic("hold")["goods"] == [] and m.topic("hold")["space"]["capacity"] == 35


def test_each_lot_is_a_row_with_where_it_was_bought(tmp_path):
    m = model(tmp_path)
    bought(m, "food", 3, 40, system=7, name="Lave")
    bought(m, "food", 2, 50, system=129, name="Zaonce")
    hold(m, [food(5)])
    rows = m.topic("hold")["goods"]
    assert [(r["units"], r["paid_each"], r["from"]["name"]) for r in rows] == [
        (3, 40, "Lave"),
        (2, 50, "Zaonce"),
    ]


def test_worth_comes_from_the_last_market_seen(tmp_path):
    m = model(tmp_path)
    bought(m, "food", 3, 40)
    market(m, {"food": {"price": 55}})
    hold(m, [food(3)])
    [row] = m.topic("hold")["goods"]
    assert (row["worth_each"], row["worth"], row["profit"]) == (55, 165, 45)


def test_a_commodity_the_last_market_doesnt_list_is_worth_null(tmp_path):
    m = model(tmp_path)
    bought(m, "food", 3, 40)
    market(m, {"furs": {"price": 700}})
    hold(m, [food(3)])
    [row] = m.topic("hold")["goods"]
    assert (row["worth"], row["profit"]) == (None, None)


def test_worth_at_names_the_market_and_its_age(tmp_path):
    m = model(tmp_path)
    market(m, {})
    hold(m)
    assert m.topic("hold")["worth_at"] == {
        "system": "Lave",
        "station": "Coriolis Station",
        "age": "just now",
    }


def test_scooped_units_are_a_row_from_scooped_with_no_price(tmp_path):
    m = model(tmp_path)
    m.dispatch({"type": "hold", "cause": "scooped", "goods": [food(1)], "gameClock": 1.0})
    [row] = m.topic("hold")["goods"]
    assert (row["from"], row["paid_each"], row["profit"]) == ("scooped", None, None)


def test_units_no_lot_accounts_for_are_a_row_of_unknown_origin(tmp_path):
    m = model(tmp_path)
    bought(m, "food", 2, 40)
    m.markets.data["lots"]["food"][0]["units"] = 1  # the store lags behind the game
    hold(m, [food(2)])
    rows = m.topic("hold")["goods"]
    assert [(r["units"], r["from"]) for r in rows][-1] == (1, None)


def test_contract_cargo_is_not_counted_as_goods(tmp_path):
    m = model(tmp_path)
    contract = {"commodity": "food", "quantity": 4, "destination": 3, "eta": 600, "fee": 900}
    hold(m, [food(4)], contracts=[contract])
    assert m.topic("hold")["goods"] == []


def test_time_left_counts_down_from_the_eta_sent(tmp_path):
    clock = Clock()
    m = model(tmp_path, clock)
    passenger = {"name": "Ann", "destinationName": "Zaonce", "eta": 7200, "fee": 120}
    hold(m, passengers=[passenger])
    clock.now = 1800.0
    [row] = m.topic("hold")["passengers"]
    assert (row["time_left"], row["time_left_text"], row["late"]) == (5400, "1h 30m", False)


def test_a_passenger_past_their_eta_is_late(tmp_path):
    m = model(tmp_path)
    hold(m, passengers=[{"name": "Ann", "eta": -3600, "fee": 120}])
    [row] = m.topic("hold")["passengers"]
    assert (row["late"], row["time_left_text"]) == (True, "late 1h 0m")


def test_a_contract_is_named_by_its_commodity(tmp_path):
    m = model(tmp_path)
    hold(m, contracts=[{"commodity": "furs", "quantity": 10, "eta": 600, "fee": 900}])
    assert m.topic("hold")["contracts"][0]["name"] == "Furs"


def test_time_text_shows_days_and_hours_for_long_times():
    assert time_text(2 * 86400 + 3 * 3600 + 59) == "2d 3h"


def test_time_text_shows_minutes_alone_under_an_hour():
    assert time_text(12 * 60 + 5) == "12m"
