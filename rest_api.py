"""
rest_api.py  -  Route Planner REST API (FastAPI)

The same features as the Streamlit app, offered as JSON endpoints so other
programs (and the web page in public/) can use them. It reuses
graphhopper_api.py and calculations.py, so the numbers are identical to what
the Streamlit app shows.

Run locally:  uvicorn api.index:app --reload
  Web page:   http://127.0.0.1:8000
  API docs:   http://127.0.0.1:8000/api/docs
Run this file alone (API only, no /api prefix):  uvicorn rest_api:app --reload

The GraphHopper key comes from the X-GraphHopper-Key request header (the web
page sends the key saved in the user's browser), or else from the server's
GRAPHHOPPER_KEY environment variable. It is never part of a URL.
"""
import os
from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query

import calculations as calc
from graphhopper_api import (DRIVING_MODES, ROUTE_MODES, GraphHopperError,
                             LocationNotFound, fetch_route, geocode, usage)

app = FastAPI(
    title="Route Planner API",
    description="Multi-stop routes, travel mode comparison, gas cost and "
                "calorie estimates. Powered by the GraphHopper Geocoding and "
                "Routing APIs.",
)

# profile -> friendly name, e.g. "foot" -> "Walking"
MODE_LABELS = {profile: label for label, profile in ROUTE_MODES.items()}

# Literal types make FastAPI validate the values and show dropdowns in /docs
Profile = Literal["car", "foot", "bike"]
Unit = Literal["km", "mi"]

STOPS_HELP = "Repeat once per stop, start first and destination last"

# Remember places and routes already looked up, to stay under the free
# plan's per-minute request limit (failed lookups are not remembered)
cached_geocode = lru_cache(maxsize=256)(geocode)
cached_route = lru_cache(maxsize=128)(fetch_route)


def records(df):
    """DataFrame -> list of dicts, with missing values as null (JSON has no NaN)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def get_key(x_graphhopper_key: str | None = Header(
        None, description="Your GraphHopper API key (falls back to the "
                          "server's GRAPHHOPPER_KEY)")):
    key = x_graphhopper_key or os.getenv("GRAPHHOPPER_KEY")
    if not key:
        raise HTTPException(401, "No GraphHopper API key. Add your key in the settings.")
    return key


def find_places(key, stops):
    """Clean up the stops and geocode each one, turning errors into HTTP errors."""
    stops = [s.strip() for s in stops if s.strip()]
    if len(stops) < 2:
        raise HTTPException(422, "Give at least a start and a destination.")
    try:
        return [cached_geocode(key, stop) for stop in stops]
    except LocationNotFound as err:
        raise HTTPException(404, str(err))
    except GraphHopperError as err:
        raise HTTPException(502, str(err))


def get_route(key, places, profile):
    """Route through the geocoded places."""
    try:
        return cached_route(key, tuple((p["lat"], p["lng"]) for p in places), profile)
    except GraphHopperError as err:
        # 502 = the upstream service (GraphHopper) failed or found no route
        raise HTTPException(502, str(err))


@app.get("/modes")
def modes():
    """List the travel modes this API accepts."""
    return {"modes": [{"mode": p, "label": label} for p, label in MODE_LABELS.items()]}


@app.get("/usage")
def credits(key: str = Depends(get_key)):
    """
    Daily GraphHopper credits for your key (limit, remaining, used, and
    resets_at as Unix time), as of its last request through this server.
    Costs no credits; null until the key has made a request here.
    """
    return {"usage": usage(key)}


@app.get("/route")
def route(
    stops: list[str] = Query(..., description=STOPS_HELP),
    mode: Profile = "car",
    unit: Unit = "km",
    price_per_liter: float = Query(60.0, ge=0),
    km_per_liter: float = Query(12.0, gt=0),
    people: int = Query(1, ge=1, description="People splitting the gas cost"),
    weight_kg: float = Query(65.0, gt=0),
    key: str = Depends(get_key),
):
    """
    One route in one travel mode. Driving adds gas cost (split per person
    when people > 1); walking and cycling add estimated calories burned.
    "line" is the whole route as [lat, lng] points, for drawing a map.
    """
    places = find_places(key, stops)
    data = get_route(key, places, mode)
    summary = calc.summarize(data, unit)

    result = {
        "mode": MODE_LABELS[mode],
        "unit": unit,
        "stops": places,
        "distance": round(summary["distance"], 2),
        "seconds": round(summary["seconds"]),
        "time_text": summary["time_text"],
    }
    if mode in DRIVING_MODES:
        liters, cost = calc.estimate_cost(summary["distance_km"], km_per_liter,
                                          price_per_liter)
        result.update(
            liters=round(liters, 2),
            fuel_cost=round(cost, 2),
            people=people,
            cost_per_person=round(calc.split_cost(cost, people), 2),
        )
    else:
        kcal = calc.estimate_calories(MODE_LABELS[mode], summary["distance_km"],
                                      summary["seconds"], weight_kg)
        result["calories_kcal"] = round(kcal)

    typed = [p["query"] for p in places]
    result["legs"] = records(calc.legs_table(data, typed, unit))
    result["steps"] = records(calc.steps_table(data, unit))
    result["line"] = [[lat, lng] for lng, lat in data["line"]]
    result["usage"] = usage(key)
    return result


@app.get("/compare")
def compare(
    stops: list[str] = Query(..., description=STOPS_HELP),
    unit: Unit = "km",
    price_per_liter: float = Query(60.0, ge=0),
    km_per_liter: float = Query(12.0, gt=0),
    people: int = Query(1, ge=1),
    weight_kg: float = Query(65.0, gt=0),
    key: str = Depends(get_key),
):
    """
    The same trip in every travel mode. A mode GraphHopper cannot route
    (for example walking across the sea) comes back with null values, and
    "errors" says why. "lines" has each mode's route as [lat, lng] points
    (null for a mode with no route), for drawing them all on one map.
    """
    places = find_places(key, stops)  # geocode once, reuse for every mode
    results, errors = {}, {}
    for profile, label in MODE_LABELS.items():
        try:
            results[label] = get_route(key, places, profile)
        except HTTPException as err:
            results[label] = None
            errors[label] = err.detail

    table = calc.comparison_table(results, unit, km_per_liter, price_per_liter,
                                  people, weight_kg)
    ok = table.dropna(subset=["Minutes"])
    fastest = ok.loc[ok["Minutes"].idxmin(), "Mode"] if not ok.empty else None
    lines = {label: [[lat, lng] for lng, lat in data["line"]] if data else None
             for label, data in results.items()}
    return {"unit": unit, "stops": places, "modes": records(table),
            "fastest": fastest, "errors": errors, "lines": lines, "usage": usage(key)}
