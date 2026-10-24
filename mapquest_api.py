"""
mapquest_api.py

All communication with the MapQuest Directions API lives here, so the rest of
the app never has to know what the raw JSON looks like.

Docs: https://developer.mapquest.com/documentation/directions-api/
"""
import requests

API_URL = "https://www.mapquestapi.com/directions/v2/route"

# Friendly name shown in the UI -> routeType value the API expects
ROUTE_MODES = {
    "Driving (fastest)": "fastest",
    "Driving (shortest)": "shortest",
    "Walking": "pedestrian",
    "Cycling": "bicycle",
}

# Only driving routes can avoid tolls, highways, etc.
DRIVING_MODES = {"fastest", "shortest"}

# Friendly name -> value for the API "avoids" option
AVOID_OPTIONS = {
    "Toll roads": "Toll Road",
    "Highways": "Limited Access",
    "Ferries": "Ferry",
    "Unpaved roads": "Unpaved",
}


class MapQuestError(Exception):
    """Raised for any problem we want to show nicely to the user."""


def fetch_route(key, stops, route_type="fastest", avoids=None):
    """
    Ask MapQuest for a route through the given stops (2 or more addresses).

    We always request kilometers. Converting to miles is done later in
    calculations.py, which keeps one source of truth for distances.

    Returns the "route" part of the JSON response.
    Raises MapQuestError with a readable message if anything goes wrong.
    """
    if len(stops) < 2:
        raise MapQuestError("Please enter at least a start and a destination.")

    options = {"unit": "k", "routeType": route_type}
    if avoids and route_type in DRIVING_MODES:
        options["avoids"] = avoids

    body = {"locations": stops, "options": options}

    try:
        response = requests.post(API_URL, params={"key": key}, json=body, timeout=20)
        data = response.json()
    except requests.RequestException as err:
        raise MapQuestError(f"Could not reach MapQuest: {err}")
    except ValueError:
        raise MapQuestError("MapQuest sent back something unreadable. Check your API key.")

    # statuscode 0 means success; anything else comes with messages
    info = data.get("info", {})
    if info.get("statuscode") != 0:
        messages = ", ".join(info.get("messages", [])) or "Unknown error"
        raise MapQuestError(f"No route found: {messages}")

    return data["route"]
