"""
graphhopper_api.py

All communication with the GraphHopper APIs lives here, so the rest of the
app never has to know what the raw JSON looks like. Like lab 4.9.2, it works
in two steps:
  1. Geocoding API: turn a place name into latitude and longitude
  2. Routing API: get a route through all the points

GraphHopper reports meters and milliseconds. This file converts them to
kilometers and seconds, so the rest of the app uses one set of units.

Docs: https://docs.graphhopper.com/
"""
import requests

GEOCODE_URL = "https://graphhopper.com/api/1/geocode"
ROUTE_URL = "https://graphhopper.com/api/1/route"

# Friendly name shown in the UI -> profile the API expects
# (the free plan offers car, bike and foot, same as the lab)
ROUTE_MODES = {
    "Driving": "car",
    "Walking": "foot",
    "Cycling": "bike",
}

DRIVING_MODES = {"car"}

# Instruction "sign" GraphHopper uses when a stop in the middle is reached
SIGN_VIA_REACHED = 5


class GraphHopperError(Exception):
    """Raised for any problem we want to show nicely to the user."""


class LocationNotFound(GraphHopperError):
    """The Geocoding API found no place for what the user typed."""


def _get(url, params):
    """GET a GraphHopper URL and return the JSON, or raise GraphHopperError."""
    try:
        response = requests.get(url, params=params, timeout=20)
        data = response.json()
    except requests.RequestException as err:
        raise GraphHopperError(f"Could not reach GraphHopper: {err}")
    except ValueError:
        raise GraphHopperError("GraphHopper sent back something unreadable.")

    # The free plan allows only a few requests per minute
    if response.status_code == 429:
        raise GraphHopperError("GraphHopper's free plan request limit was reached. "
                               "Wait a minute and try again.")
    # Other errors come with a "message", e.g. "Wrong credentials..." for a bad
    # key or "Connection between locations not found" for an impossible route
    if response.status_code != 200:
        raise GraphHopperError(data.get("message", f"HTTP {response.status_code}"))
    return data


def geocode(key, location):
    """
    Find one place for the text the user typed.

    Returns a dict with the matched name (for example "Tagaytay, Cavite,
    Philippines"), lat, lng and the place type (city, town, ...).
    """
    data = _get(GEOCODE_URL, {"q": location, "limit": 1, "key": key})
    if not data.get("hits"):
        raise LocationNotFound(f"Location not found: {location}")

    hit = data["hits"][0]
    # state and country are missing for some places, so skip empty parts
    parts = [hit.get("name", location), hit.get("state"), hit.get("country")]
    return {
        "query": location,
        "name": ", ".join(p for p in parts if p),
        "lat": hit["point"]["lat"],
        "lng": hit["point"]["lng"],
        "type": hit.get("osm_value", ""),
    }


def fetch_route(key, points, profile="car"):
    """
    Ask GraphHopper for a route through the given (lat, lng) points, in order.

    Returns a dict:
      distance  total km
      time      total seconds
      legs      one {"distance", "time"} per part between two stops
      steps     turn-by-turn {"narrative", "distance", "seconds", "lat", "lng"}
      line      every point of the route as [lng, lat], for drawing the map
    """
    if len(points) < 2:
        raise GraphHopperError("Please enter at least a start and a destination.")

    # A list of pairs lets "point" repeat once per stop.
    # The lab passed vehicle=car; current GraphHopper docs call it profile.
    params = [("key", key), ("profile", profile), ("locale", "en"),
              ("instructions", "true"), ("points_encoded", "false")]
    params += [("point", f"{lat},{lng}") for lat, lng in points]

    path = _get(ROUTE_URL, params)["paths"][0]
    line = path["points"]["coordinates"]

    # The free plan returns no per-leg data, so split the instructions at
    # each "via point reached" to get the distance and time between stops
    legs = [{"distance": 0.0, "time": 0.0}]
    steps = []
    for ins in path["instructions"]:
        km, seconds = ins["distance"] / 1000, ins["time"] / 1000
        lng, lat = line[ins["interval"][0]][:2]
        steps.append({"narrative": ins["text"], "distance": km,
                      "seconds": seconds, "lat": lat, "lng": lng})
        legs[-1]["distance"] += km
        legs[-1]["time"] += seconds
        if ins["sign"] == SIGN_VIA_REACHED:
            legs.append({"distance": 0.0, "time": 0.0})

    return {
        "distance": path["distance"] / 1000,
        "time": path["time"] / 1000,
        "legs": legs,
        "steps": steps,
        "line": [pt[:2] for pt in line],
    }
