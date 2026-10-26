"""
A fake GraphHopper used by the tests, so they need no key and no internet.
Call install() before importing the app; it replaces requests.get.

Fake world:
  - Any place name geocodes to a point, except "Nowhere" (no hits).
  - Key "BAD" gets a 401 "Wrong credentials" like the real API.
  - car: 120 km in 1h 30m, foot: 10 km in 2h, bike: 10 km in 40m.
  - Walking to "Island" fails with "Connection between locations not found".
"""
import requests

GEOCODE_URL = "https://graphhopper.com/api/1/geocode"
ISLAND = (13.0, 122.0)
TRIPS = {"car": (120.0, 5400), "foot": (10.0, 7200), "bike": (10.0, 2400)}

calls = []  # (kind, detail) for every fake request, to check call counts


class Resp:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


def fake_geocode(q):
    if q == "Nowhere":
        return Resp({"hits": [], "locale": "default"})
    lat, lng = ISLAND if q == "Island" else (14.0 + len(q) * 0.01, 121.0)
    return Resp({"hits": [{"point": {"lat": lat, "lng": lng}, "name": q,
                           "state": "Test Province", "country": "Philippines",
                           "osm_value": "city"}], "locale": "default"})


def fake_route(profile, points):
    if profile == "foot" and ISLAND in points:
        return Resp({"message": "Connection between locations not found"}, 400)
    km, secs = TRIPS[profile]
    legs = len(points) - 1
    instructions = []
    for i in range(legs):
        instructions.append({"text": f"Continue to stop {i + 2}", "sign": 0,
                             "distance": km * 1000 / legs, "time": secs * 1000 / legs,
                             "interval": [i, i + 1]})
        last = i == legs - 1
        instructions.append({"text": "Arrive at destination" if last else "Waypoint reached",
                             "sign": 4 if last else 5, "distance": 0, "time": 0,
                             "interval": [i + 1, i + 1]})
    return Resp({"paths": [{
        "distance": km * 1000, "time": secs * 1000,
        "points": {"type": "LineString", "coordinates": [[lng, lat] for lat, lng in points]},
        "instructions": instructions}]})


def fake_get(url, params=None, timeout=None):
    # Geocoding sends a dict; routing sends (name, value) pairs so "point" can repeat
    pairs = list(params.items()) if isinstance(params, dict) else params
    single = dict(pairs)
    if single["key"] == "BAD":
        return Resp({"message": "Wrong credentials. Register and get a valid API key"}, 401)
    if url == GEOCODE_URL:
        calls.append(("geocode", single["q"]))
        return fake_geocode(single["q"])
    points = [tuple(float(x) for x in v.split(",")) for k, v in pairs if k == "point"]
    calls.append(("route", single["profile"]))
    return fake_route(single["profile"], points)


def install():
    requests.get = fake_get
