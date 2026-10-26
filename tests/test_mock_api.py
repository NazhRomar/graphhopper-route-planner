"""
Mocked-API checks for the REST API (api.py). No real GraphHopper calls.
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
from api import app

client = TestClient(app)
TRIP = {"stops": ["Manila", "Tagaytay", "Batangas City"]}

# no key set -> clear server error
os.environ.pop("GRAPHHOPPER_KEY", None)
r = client.get("/route", params=TRIP)
print("no key:", r.status_code, r.json())
assert r.status_code == 500

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

fake_graphhopper.calls.clear()
r = client.get("/compare", params={"stops": ["Manila", "Island"]}).json()
for row in r["modes"]:
    print("  ", row)
print("fastest:", r["fastest"])
assert r["modes"][1]["Time"] == "No route" and r["modes"][1]["Minutes"] is None
assert r["fastest"] == "Cycling"
kinds = [kind for kind, _ in fake_graphhopper.calls]
assert kinds.count("geocode") == 2 and kinds.count("route") == 3  # geocoded once

assert client.get("/openapi.json").status_code == 200
print("all API checks passed")
