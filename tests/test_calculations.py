"""
Unit tests for calculations.py: one or more test cases per function.
These need no network at all; calculations.py never calls GraphHopper.
Run: pytest tests/test_calculations.py
"""
import pytest

import calculations as calc

# A small route in the shape fetch_route() returns: 2 legs, 3 steps
ROUTE = {
    "distance": 120.0,
    "time": 5400.0,
    "legs": [{"distance": 70.0, "time": 3000.0}, {"distance": 50.0, "time": 2400.0}],
    "steps": [
        {"narrative": "Turn left", "distance": 70.0, "seconds": 3000.0, "lat": 14.0, "lng": 121.0},
        {"narrative": "Waypoint reached", "distance": 0.0, "seconds": 0.0, "lat": 14.5, "lng": 121.5},
        {"narrative": "Arrive at destination", "distance": 50.0, "seconds": 2400.0, "lat": 15.0, "lng": 122.0},
    ],
    "line": [[121.0, 14.0], [121.5, 14.5], [122.0, 15.0]],
}


# ------------------------------------------------------------ units and time
def test_convert_distance_km_stays_km():
    assert calc.convert_distance(10, "km") == 10


def test_convert_distance_km_to_miles():
    assert calc.convert_distance(1.609344, "mi") == pytest.approx(1.0)


@pytest.mark.parametrize("seconds, text", [(0, "0m"), (45 * 60, "45m"), (125 * 60, "2h 05m"), (5400, "1h 30m")])
def test_format_time(seconds, text):
    assert calc.format_time(seconds) == text


def test_format_clock():
    assert calc.format_clock(3725) == "01:02:05"


# ------------------------------------------------------------------ gas cost
def test_estimate_cost():
    liters, cost = calc.estimate_cost(120, 12, 60)
    assert (liters, cost) == (10, 600)


def test_estimate_cost_with_invalid_km_per_liter_is_zero():
    assert calc.estimate_cost(120, 0, 60) == (0.0, 0.0)


def test_split_cost_between_people():
    assert calc.split_cost(600, 3) == 200


def test_split_cost_never_divides_by_zero():
    assert calc.split_cost(600, 0) == 600


# ------------------------------------------------------------------ calories
def test_pick_met_uses_first_speed_limit_above_the_speed():
    assert calc.pick_met(3.0, calc.WALKING_MET, calc.WALKING_MET_FAST) == 2.8
    assert calc.pick_met(5.0, calc.WALKING_MET, calc.WALKING_MET_FAST) == 4.3


def test_pick_met_faster_than_the_table():
    assert calc.pick_met(99, calc.WALKING_MET, calc.WALKING_MET_FAST) == calc.WALKING_MET_FAST


def test_walking_calories():
    # 10 km in 2 hours = 5 km/h -> MET 4.3, x 65 kg x 2 hours = 559 kcal
    assert calc.estimate_calories("Walking", 10, 7200, 65) == pytest.approx(559)


def test_cycling_calories():
    # 10 km in 40 minutes = 15 km/h -> MET 4.0, x 65 kg x 2/3 hour = 173 kcal
    assert calc.estimate_calories("Cycling", 10, 2400, 65) == pytest.approx(173.33, abs=0.01)


def test_driving_burns_no_calories():
    assert calc.estimate_calories("Driving", 120, 5400, 65) == 0


@pytest.mark.parametrize("km, seconds, kg", [(0, 600, 65), (5, 0, 65), (5, 600, 0)])
def test_calories_are_zero_for_unusable_data(km, seconds, kg):
    assert calc.estimate_calories("Walking", km, seconds, kg) == 0


# ---------------------------------------------------------- elevation and hills
def test_climb_calories():
    # 65 kg x 9.81 x 100 m / 4184 / 0.25 = about 61 kcal
    assert calc.climb_calories(65, 100) == pytest.approx(60.96, abs=0.01)


@pytest.mark.parametrize("kg, meters", [(65, 0), (65, -20), (0, 100)])
def test_climb_calories_are_zero_without_a_climb(kg, meters):
    assert calc.climb_calories(kg, meters) == 0


def test_walking_calories_include_the_climb():
    flat = calc.estimate_calories("Walking", 10, 7200, 65)
    hilly = calc.estimate_calories("Walking", 10, 7200, 65, ascend_m=100)
    assert hilly - flat == pytest.approx(calc.climb_calories(65, 100))


def test_driving_burns_no_calories_even_uphill():
    assert calc.estimate_calories("Driving", 120, 5400, 65, ascend_m=500) == 0


@pytest.mark.parametrize("ascend_m, km, label", [
    (0, 10, "Flat"), (99, 10, "Flat"), (100, 10, "Some hills"),
    (249, 10, "Some hills"), (250, 10, "Hilly"), (50, 0, "Flat"),
])
def test_hilliness(ascend_m, km, label):
    assert calc.hilliness(ascend_m, km) == label


def test_summarize_includes_climb_and_drop():
    s = calc.summarize({**ROUTE, "ascend": 300.0, "descend": 120.0}, "km")
    assert (s["ascend"], s["descend"], s["hills"]) == (300.0, 120.0, "Flat")


def test_summarize_without_elevation_data_is_flat():
    s = calc.summarize(ROUTE, "km")
    assert (s["ascend"], s["descend"], s["hills"]) == (0.0, 0.0, "Flat")


# -------------------------------------------------------------------- tables
def test_summarize_in_miles():
    s = calc.summarize(ROUTE, "mi")
    assert s["distance"] == pytest.approx(74.56, abs=0.01)
    assert s["distance_km"] == 120.0
    assert s["seconds"] == 5400.0
    assert s["time_text"] == "1h 30m"


def test_stops_table_shows_typed_and_found_names():
    places = [{"query": "tagaytay", "name": "Tagaytay, Cavite, Philippines", "type": "city"}]
    row = calc.stops_table(places).iloc[0]
    assert (row["Stop"], row["You typed"], row["Found"], row["Type"]) == (1, "tagaytay", "Tagaytay, Cavite, Philippines", "city")


def test_legs_table_has_one_row_per_pair_of_stops():
    legs = calc.legs_table(ROUTE, ["Manila", "Tagaytay", "Batangas"], "km")
    assert list(legs["Leg"]) == ["1. Manila to Tagaytay", "2. Tagaytay to Batangas"]
    assert list(legs["Distance"]) == [70.0, 50.0]
    assert list(legs["Time"]) == ["50m", "40m"]


def test_steps_table():
    steps = calc.steps_table(ROUTE, "km")
    assert list(steps["Step"]) == [1, 2, 3]
    assert steps.iloc[0]["Direction"] == "Turn left"
    assert steps.iloc[0]["Time"] == "00:50:00"
    assert (steps.iloc[2]["lat"], steps.iloc[2]["lon"]) == (15.0, 122.0)


def test_map_view_centers_on_the_route():
    view = calc.map_view(ROUTE["line"])
    assert (view["latitude"], view["longitude"]) == (14.5, 121.5)
    assert 1 <= view["zoom"] <= 14


def test_map_view_does_not_zoom_in_past_14_for_one_point():
    assert calc.map_view([[121.0, 14.0]])["zoom"] == 14


def test_comparison_table():
    walk = {"distance": 10.0, "time": 7200.0, "ascend": 40.4}
    table = calc.comparison_table({"Driving": ROUTE, "Walking": walk, "Cycling": None},
                                  "km", km_per_liter=12, price_per_liter=60, people=2, weight_kg=65)
    rows = table.set_index("Mode")
    assert rows.loc["Driving", "Fuel cost"] == 600.0
    assert rows.loc["Driving", "Cost per person"] == 300.0
    assert rows.loc["Driving", "Calories (kcal)"] == 0
    assert rows.loc["Walking", "Calories (kcal)"] == round(559 + calc.climb_calories(65, 40.4))
    assert rows.loc["Walking", "Fuel cost"] == 0.0
    assert rows.loc["Walking", "Climb (m)"] == 40
    assert rows.loc["Driving", "Climb (m)"] == 0  # ROUTE has no elevation data
    assert rows.loc["Cycling", "Time"] == "No route"
