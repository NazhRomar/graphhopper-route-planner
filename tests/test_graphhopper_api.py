"""
Unit tests for graphhopper_api.py, the only file that calls GraphHopper.
GraphHopper is faked (see conftest.py).
Run: pytest tests/test_graphhopper_api.py
"""
import pytest
import requests

import graphhopper_api as gh

POINTS = [(14.0, 121.0), (14.5, 121.5), (15.0, 122.0)]


# ----------------------------------------------------------------- geocode
def test_geocode_returns_matched_place():
    place = gh.geocode("FAKEKEY", "Manila")
    assert place["query"] == "Manila"
    assert place["name"] == "Manila, Test Province, Philippines"
    assert place["type"] == "city"
    assert isinstance(place["lat"], float) and isinstance(place["lng"], float)


def test_geocode_unknown_place_raises_location_not_found():
    with pytest.raises(gh.LocationNotFound, match="Nowhere"):
        gh.geocode("FAKEKEY", "Nowhere")


# ------------------------------------------------------------------- route
def test_fetch_route_converts_to_km_and_seconds():
    route = gh.fetch_route("FAKEKEY", POINTS, "car")
    assert route["distance"] == 120.0
    assert route["time"] == 5400.0


def test_fetch_route_splits_legs_at_each_stop():
    route = gh.fetch_route("FAKEKEY", POINTS, "car")
    assert route["legs"] == [{"distance": 60.0, "time": 2700.0}, {"distance": 60.0, "time": 2700.0}]


def test_fetch_route_steps_and_line():
    route = gh.fetch_route("FAKEKEY", POINTS, "car")
    assert route["steps"][-1]["narrative"] == "Arrive at destination"
    assert route["line"][0] == [121.0, 14.0]  # GraphHopper order: [lng, lat]


def test_fetch_route_has_climb_and_drop():
    route = gh.fetch_route("FAKEKEY", [(14.0, 121.0), (14.3, 120.9)], "car")  # to "Hill"
    assert (route["ascend"], route["descend"]) == (200.0, 50.0)


def test_fetch_route_on_flat_ground_has_no_climb():
    route = gh.fetch_route("FAKEKEY", POINTS, "car")
    assert (route["ascend"], route["descend"]) == (0.0, 0.0)


def test_fetch_route_needs_two_points():
    with pytest.raises(gh.GraphHopperError):
        gh.fetch_route("FAKEKEY", POINTS[:1], "car")


def test_impossible_route_raises_with_graphhopper_message():
    with pytest.raises(gh.GraphHopperError, match="Connection between locations not found"):
        gh.fetch_route("FAKEKEY", [(14.0, 121.0), (13.0, 122.0)], "foot")


# ------------------------------------------------------------------ errors
def test_wrong_key_raises_with_graphhopper_message():
    with pytest.raises(gh.GraphHopperError, match="Wrong credentials"):
        gh.geocode("BAD", "Manila")


def test_request_limit_raises_friendly_message():
    with pytest.raises(gh.GraphHopperError, match="request limit"):
        gh.geocode("LIMIT", "Manila")


def test_no_connection_raises_friendly_message(monkeypatch):
    def offline(*args, **kwargs):
        raise requests.ConnectionError("no internet")
    monkeypatch.setattr(requests, "get", offline)
    with pytest.raises(gh.GraphHopperError, match="Could not reach GraphHopper"):
        gh.geocode("FAKEKEY", "Manila")


# ------------------------------------------------------------------- usage
def test_usage_is_none_before_the_first_request():
    assert gh.usage("FAKEKEY") is None


def test_usage_is_kept_per_key():
    gh.geocode("FAKEKEY", "Manila")
    assert gh.usage("FAKEKEY")["used"] == 1
    assert gh.usage("ANOTHER-KEY") is None
