"""
Test cases for the REST API (rest_api.py) and the Vercel entry point
(api/index.py). GraphHopper is faked (see conftest.py).
Run: pytest tests/test_rest_api.py
"""
import pytest
# TestClient sends requests to the API without starting a real server
from fastapi.testclient import TestClient

import fake_graphhopper
from api.index import app as site
from rest_api import app

TRIP = {"stops": ["Manila", "Tagaytay", "Batangas City"]}


@pytest.fixture
def client(monkeypatch):
    """An API client, with the server's GRAPHHOPPER_KEY set to a fake key."""
    monkeypatch.setenv("GRAPHHOPPER_KEY", "FAKEKEY")
    return TestClient(app)


# ------------------------------------------------------------------ API key
def test_no_key_anywhere_gives_401(monkeypatch):
    monkeypatch.delenv("GRAPHHOPPER_KEY", raising=False)
    assert TestClient(app).get("/route", params=TRIP).status_code == 401


def test_key_in_header_works(monkeypatch):
    # what the web page sends
    monkeypatch.delenv("GRAPHHOPPER_KEY", raising=False)
    r = TestClient(app).get("/route", params=TRIP, headers={"X-GraphHopper-Key": "FAKEKEY"})
    assert r.status_code == 200


# ---------------------------------------------------------------- /route
def test_one_stop_gives_422(client):
    assert client.get("/route", params={"stops": ["Manila"]}).status_code == 422


def test_driving_gas_cost_is_split_per_person(client):
    r = client.get("/route", params={**TRIP, "people": 3}).json()
    # 120 km / 12 km per liter = 10 L, x 60 per liter = 600, / 3 people = 200
    assert (r["fuel_cost"], r["cost_per_person"]) == (600.0, 200.0)


def test_route_has_stops_legs_steps_and_line(client):
    r = client.get("/route", params=TRIP).json()
    assert r["stops"][1]["name"] == "Tagaytay, Test Province, Philippines"
    assert len(r["legs"]) == 2 and r["legs"][0]["Distance"] == 60.0
    assert r["steps"][-1]["Direction"] == "Arrive at destination"
    assert r["line"][0] == [r["stops"][0]["lat"], r["stops"][0]["lng"]]  # [lat, lng] for maps


def test_walking_gives_calories_instead_of_gas(client):
    r = client.get("/route", params={**TRIP, "mode": "foot"}).json()
    assert r["calories_kcal"] == 559
    assert "fuel_cost" not in r


def test_miles(client):
    r = client.get("/route", params={**TRIP, "unit": "mi"}).json()
    assert r["distance"] == pytest.approx(74.56, abs=0.01)
    assert r["distance_km"] == 120.0  # always km, whatever unit was asked for


def test_route_shows_climb_drop_and_hills(client):
    r = client.get("/route", params={"stops": ["Manila", "Hill"], "mode": "foot"}).json()
    # 200 m of climbing over 10 km = 20 m per km
    assert (r["ascend_m"], r["descend_m"], r["hills"]) == (200, 50, "Some hills")


def test_walking_uphill_burns_more_calories(client):
    flat = client.get("/route", params={"stops": ["Manila", "Pasig"], "mode": "foot"}).json()
    hill = client.get("/route", params={"stops": ["Manila", "Hill"], "mode": "foot"}).json()
    # 559 kcal for the walk + about 122 kcal to climb 200 m
    assert (flat["calories_kcal"], hill["calories_kcal"]) == (559, 681)


def test_long_drive_with_small_climb_is_flat(client):
    r = client.get("/route", params={"stops": ["Manila", "Hill"]}).json()
    assert r["hills"] == "Flat"  # 200 m over 120 km


def test_unknown_place_gives_404(client):
    assert client.get("/route", params={"stops": ["Manila", "Nowhere"]}).status_code == 404


def test_impossible_route_gives_502(client):
    r = client.get("/route", params={"stops": ["Manila", "Island"], "mode": "foot"})
    assert r.status_code == 502


def test_request_limit_gives_clear_message(monkeypatch):
    monkeypatch.setenv("GRAPHHOPPER_KEY", "LIMIT")
    r = TestClient(app).get("/route", params=TRIP)
    assert r.status_code == 502 and "request limit" in r.json()["detail"]


# --------------------------------------------------------------- /compare
def test_compare_shows_every_mode_and_why_one_failed(client):
    r = client.get("/compare", params={"stops": ["Manila", "Island"]}).json()
    assert r["modes"][1]["Time"] == "No route" and r["modes"][1]["Minutes"] is None
    assert r["errors"] == {"Walking": "Connection between locations not found"}
    assert r["lines"]["Walking"] is None and len(r["lines"]["Driving"]) == 2
    assert r["modes"][0]["distance_km"] == 120.0 and r["modes"][1]["distance_km"] is None
    assert r["fastest"] == "Cycling"


def test_compare_geocodes_each_stop_only_once(client):
    client.get("/compare", params={"stops": ["Manila", "Island"]})
    kinds = [kind for kind, _ in fake_graphhopper.calls]
    assert kinds.count("geocode") == 2 and kinds.count("route") == 3


# ------------------------------------------------------- saving requests
def test_repeat_trip_uses_no_graphhopper_requests(client):
    client.get("/route", params={"stops": ["Manila", "Island"]})
    fake_graphhopper.calls.clear()
    client.get("/route", params={"stops": ["Manila", "Island"]})
    assert fake_graphhopper.calls == []


def test_daily_credits_are_passed_on_and_kept_per_key(client):
    r = client.get("/route", params={"stops": ["Quezon City", "Pasig"]}).json()
    assert r["usage"]["limit"] == 500 and r["usage"]["used"] == 3  # 2 geocodes + 1 route
    assert client.get("/usage").json()["usage"] == r["usage"]
    assert client.get("/usage", headers={"X-GraphHopper-Key": "SOMEONE-ELSE"}).json()["usage"] is None


# ------------------------------------------------------------------ docs
def test_api_docs_load(client):
    assert client.get("/openapi.json").status_code == 200


# --------------------------------------------- Vercel entry point (site)
def test_site_serves_api_under_api_and_page_at_root(monkeypatch):
    monkeypatch.setenv("GRAPHHOPPER_KEY", "FAKEKEY")
    site_client = TestClient(site)
    assert site_client.get("/api/modes").json()["modes"][0]["mode"] == "car"
    assert site_client.get("/api/route", params=TRIP).json()["fuel_cost"] == 600.0
    page = site_client.get("/")
    assert page.status_code == 200 and "Route Planner" in page.text
    assert site_client.get("/app.js").status_code == 200
