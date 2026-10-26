"""
Mocked-API checks for the REST API (rest_api.py) and the Vercel entry point
(api/index.py). No real GraphHopper calls.
Run: python tests/test_mock_api.py
"""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fake_graphhopper
fake_graphhopper.install()

from fastapi.testclient import TestClient
from rest_api import app, cached_geocode, cached_route

client = TestClient(app)
TRIP = {"stops": ["Manila", "Tagaytay", "Batangas City"]}

# no key anywhere -> clear error
os.environ.pop("GRAPHHOPPER_KEY", None)
r = client.get("/route", params=TRIP)
print("no key:", r.status_code, r.json())
assert r.status_code == 401

# key in the request header (what the web page sends)
r = client.get("/route", params=TRIP, headers={"X-GraphHopper-Key": "FAKEKEY"})
print("header key:", r.status_code)
assert r.status_code == 200

# key from the server's environment
os.environ["GRAPHHOPPER_KEY"] = "FAKEKEY"

r = client.get("/route", params={"stops": ["Manila"]})
print("one stop:", r.status_code)
assert r.status_code == 422

r = client.get("/route", params={**TRIP, "people": 3}).json()
print("driving:", {k: r[k] for k in ("distance", "time_text", "fuel_cost", "cost_per_person")})
assert (r["fuel_cost"], r["cost_per_person"]) == (600.0, 200.0)
assert r["stops"][1]["name"] == "Tagaytay, Test Province, Philippines"
assert len(r["legs"]) == 2 and r["legs"][0]["Distance"] == 60.0
assert r["steps"][-1]["Direction"] == "Arrive at destination"
assert r["line"][0] == [r["stops"][0]["lat"], r["stops"][0]["lng"]]  # [lat, lng] for maps

r = client.get("/route", params={**TRIP, "mode": "foot"}).json()
print("walking:", r["calories_kcal"], "kcal")
assert r["calories_kcal"] == 559

r = client.get("/route", params={**TRIP, "unit": "mi"}).json()
print("miles:", r["distance"])
assert abs(r["distance"] - 74.56) < 0.01

r = client.get("/route", params={"stops": ["Manila", "Nowhere"]})
print("not found:", r.status_code, r.json())
assert r.status_code == 404

r = client.get("/route", params={"stops": ["Manila", "Island"], "mode": "foot"})
print("no walking route:", r.status_code, r.json())
assert r.status_code == 502

cached_geocode.cache_clear()
cached_route.cache_clear()
fake_graphhopper.calls.clear()
r = client.get("/compare", params={"stops": ["Manila", "Island"]}).json()
for row in r["modes"]:
    print("  ", row)
print("fastest:", r["fastest"], "errors:", r["errors"])
assert r["modes"][1]["Time"] == "No route" and r["modes"][1]["Minutes"] is None
assert r["errors"] == {"Walking": "Connection between locations not found"}
assert r["fastest"] == "Cycling"
kinds = [kind for kind, _ in fake_graphhopper.calls]
assert kinds.count("geocode") == 2 and kinds.count("route") == 3  # geocoded once

# the same trip again is answered from memory, with no GraphHopper calls
fake_graphhopper.calls.clear()
client.get("/route", params={"stops": ["Manila", "Island"]})
assert fake_graphhopper.calls == []

# over the free plan's per-minute limit
os.environ["GRAPHHOPPER_KEY"] = "LIMIT"
r = client.get("/route", params=TRIP)
print("rate limit:", r.status_code, r.json())
assert r.status_code == 502 and "request limit" in r.json()["detail"]
os.environ["GRAPHHOPPER_KEY"] = "FAKEKEY"

# daily credits: passed on with results, readable for free, and kept per key
fake_graphhopper.calls.clear()
r = client.get("/route", params={"stops": ["Quezon City", "Pasig"]}).json()
print("usage:", r["usage"])
assert r["usage"]["limit"] == 500 and r["usage"]["used"] == 3  # 2 geocodes + 1 route
assert client.get("/usage").json()["usage"] == r["usage"]
assert client.get("/usage", headers={"X-GraphHopper-Key": "SOMEONE-ELSE"}).json()["usage"] is None

assert client.get("/openapi.json").status_code == 200

# Vercel entry point: the API under /api and the web page at /
from api.index import app as site
site_client = TestClient(site)
assert site_client.get("/api/modes").json()["modes"][0]["mode"] == "car"
assert site_client.get("/api/route", params=TRIP).json()["fuel_cost"] == 600.0
page = site_client.get("/")
assert page.status_code == 200 and "Route Planner" in page.text
assert site_client.get("/app.js").status_code == 200
print("all API checks passed")
