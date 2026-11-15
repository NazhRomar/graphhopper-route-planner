"""
Test cases for the Streamlit app (app.py). GraphHopper is faked (see conftest.py).
AppTest runs app.py without a browser. Each .run() is one page refresh.
Run: pytest tests/test_streamlit_app.py
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
GET_ROUTE, COMPARE = 0, 1  # the buttons, in the order they appear on the page


@pytest.fixture
def at():
    """The app, opened fresh, with a fake key typed in the sidebar."""
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.sidebar.text_input[0].set_value("FAKEKEY").run()
    return app


def metrics(at):
    """Every number box on the page, as {label: value}."""
    return {m.label: m.value for m in at.metric}


def check_ok(at):
    """Fail if the page crashed or showed an error message."""
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_driving_shows_gas_cost_and_time(at):
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Gas cost (total)"] == "PHP 600.00"
    assert metrics(at)["Trip time"] == "1h 30m"


def test_carpool_splits_gas_cost(at):
    at.sidebar.checkbox[0].check().run()  # carpool on, 3 people by default
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Per person (3 people)"] == "PHP 200.00"


def test_miles(at):
    at.sidebar.radio[0].set_value("Miles").run()
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Total distance"] == "74.6 mi"


def test_walking_shows_calories(at):
    at.selectbox[0].select("Walking").run()
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Calories burned"] == "559 kcal"


def test_cycling_shows_calories(at):
    at.selectbox[0].select("Cycling").run()
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Calories burned"] == "173 kcal"


def test_walking_uphill_shows_hills_and_more_calories(at):
    at.text_area[0].input("Manila\nHill").run()
    at.selectbox[0].select("Walking").run()
    at.button[GET_ROUTE].click().run()
    check_ok(at)
    assert metrics(at)["Calories burned"] == "681 kcal"
    assert any("Hills: Some hills. Climbs 200 m and drops 50 m" in c.value for c in at.caption)


def test_compare_explains_a_mode_with_no_route(at):
    # walking to the island is impossible in the fake world
    at.text_area[0].input("Manila\nIsland").run()
    at.button[COMPARE].click().run()
    assert not at.exception, [e.value for e in at.exception]
    table = at.dataframe[-1].value
    assert table.set_index("Mode").loc["Walking", "Time"] == "No route"
    assert at.warning[0].value == "Walking: Connection between locations not found"
    assert at.success[0].value == "Fastest option: Cycling (40m)"


def test_unknown_place_shows_error(at):
    at.text_area[0].input("Manila\nNowhere").run()
    at.button[GET_ROUTE].click().run()
    assert at.error[0].value == "Location not found: Nowhere"


def test_wrong_key_shows_error(at):
    at.sidebar.text_input[0].set_value("BAD").run()
    at.button[GET_ROUTE].click().run()
    assert "Wrong credentials" in at.error[0].value


def test_request_limit_shows_error(at):
    at.sidebar.text_input[0].set_value("LIMIT").run()
    at.button[GET_ROUTE].click().run()
    assert "request limit" in at.error[0].value
