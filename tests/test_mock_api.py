"""
Mocked-API checks for api.py. No real MapQuest calls are made.
Run: python tests/test_mock_api.py
"""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import requests

def man(n, d):
    return {"narrative": f"Turn {n}", "distance": d, "formattedTime": "00:05:00",
            "startPoint": {"lat": 14.5 + n * 0.01, "lng": 121.0 + n * 0.01}}

def route(dist, secs):
    return {"info": {"statuscode": 0}, "route": {"distance": dist, "time": secs,
        "legs": [{"distance": dist / 2, "time": secs / 2, "maneuvers": [man(1, dist / 2)]},
                 {"distance": dist / 2, "time": secs / 2, "maneuvers": [man(2, dist / 2)]}]}}

class Resp:
    def __init__(self, d): self.d = d
    def json(self): return self.d

def fake_post(url, params=None, json=None, timeout=None):
    t = json["options"]["routeType"]
    # "Island" stands in for a place you cannot walk to
    if "Island" in json["locations"] and t == "pedestrian":
        return Resp({"info": {"statuscode": 402, "messages": ["No walking route"]}})
    if t == "pedestrian": return Resp(route(10.0, 7200))
    if t == "bicycle": return Resp(route(10.0, 2400))
    return Resp(route(120.0, 5400))
requests.post = fake_post

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)
TRIP = {"stops": ["Manila", "Tagaytay", "Batangas City"]}

# no key set -> clear server error
os.environ.pop("MAPQUEST_KEY", None)
r = client.get("/route", params=TRIP)
print("no key:", r.status_code, r.json())
assert r.status_code == 500

os.environ["MAPQUEST_KEY"] = "FAKEKEY"

r = client.get("/route", params={"stops": ["Manila"]})
print("one stop:", r.status_code)
assert r.status_code == 422

r = client.get("/route", params={**TRIP, "people": 3}).json()
print("driving:", {k: r[k] for k in ("distance", "time_text", "fuel_cost", "cost_per_person")})
assert (r["fuel_cost"], r["cost_per_person"]) == (600.0, 200.0)
assert len(r["legs"]) == 2 and len(r["steps"]) == 2

r = client.get("/route", params={**TRIP, "mode": "pedestrian"}).json()
print("walking:", r["calories_kcal"], "kcal")
assert r["calories_kcal"] == 559

r = client.get("/route", params={**TRIP, "unit": "mi"}).json()
print("miles:", r["distance"])
assert abs(r["distance"] - 74.56) < 0.01

r = client.get("/route", params={"stops": ["Manila", "Island"], "mode": "pedestrian"})
print("no walking route:", r.status_code, r.json())
assert r.status_code == 502

r = client.get("/compare", params={"stops": ["Manila", "Island"]}).json()
for row in r["modes"]:
    print("  ", row)
print("fastest:", r["fastest"])
assert r["modes"][2]["Time"] == "No route" and r["modes"][2]["Minutes"] is None
assert r["fastest"] == "Cycling"

assert client.get("/openapi.json").status_code == 200
print("all API checks passed")
