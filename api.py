"""
api.py  -  Route Planner REST API (FastAPI)

The same features as the Streamlit app, offered as JSON endpoints so other
programs can use them. It reuses mapquest_api.py and calculations.py, so the
numbers are identical to what the web app shows.

Run:   uvicorn api:app --reload
Docs:  http://127.0.0.1:8000/docs  (interactive page to try every endpoint)

The MapQuest key is read only from the MAPQUEST_KEY environment variable,
so it never appears in request URLs or server logs.
"""
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

import calculations as calc
from mapquest_api import (AVOID_OPTIONS, DRIVING_MODES, ROUTE_MODES,
                          MapQuestError, fetch_route)

app = FastAPI(
    title="Route Planner API",
    description="Multi-stop routes, travel mode comparison, gas cost and "
                "calorie estimates. Powered by the MapQuest Directions API.",
)

# routeType -> friendly name, e.g. "pedestrian" -> "Walking"
MODE_LABELS = {route_type: label for label, route_type in ROUTE_MODES.items()}

# Short query values -> friendly names used in AVOID_OPTIONS
AVOID_KEYS = {
    "tolls": "Toll roads",
    "highways": "Highways",
    "ferries": "Ferries",
    "unpaved": "Unpaved roads",
}

# Literal types make FastAPI validate the values and show dropdowns in /docs
RouteType = Literal["fastest", "shortest", "pedestrian", "bicycle"]
AvoidKey = Literal["tolls", "highways", "ferries", "unpaved"]
Unit = Literal["km", "mi"]

STOPS_HELP = "Repeat once per stop, start first and destination last"


def records(df):
    """DataFrame -> list of dicts, with missing values as null (JSON has no NaN)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def clean_stops(stops):
    """Drop blank stops and reject trips with fewer than 2 stops."""
    stops = [s.strip() for s in stops if s.strip()]
    if len(stops) < 2:
        raise HTTPException(422, "Give at least a start and a destination.")
    return stops


def get_route(stops, route_type, avoid):
    """Call MapQuest and turn its errors into HTTP errors."""
    key = os.getenv("MAPQUEST_KEY")
    if not key:
        raise HTTPException(500, "MAPQUEST_KEY is not set on the server.")
    avoids = [AVOID_OPTIONS[AVOID_KEYS[a]] for a in avoid]
    try:
        return fetch_route(key, stops, route_type, avoids)
    except MapQuestError as err:
        # 502 = the upstream service (MapQuest) failed or found no route
        raise HTTPException(502, str(err))


@app.get("/modes")
def modes():
    """List the travel modes and avoid options this API accepts."""
    return {
        "modes": [{"mode": t, "label": label} for t, label in MODE_LABELS.items()],
        "avoid": list(AVOID_KEYS),
    }


@app.get("/route")
def route(
    stops: list[str] = Query(..., description=STOPS_HELP),
    mode: RouteType = "fastest",
    unit: Unit = "km",
    price_per_liter: float = Query(60.0, ge=0),
    km_per_liter: float = Query(12.0, gt=0),
    people: int = Query(1, ge=1, description="People splitting the gas cost"),
    weight_kg: float = Query(65.0, gt=0),
    avoid: list[AvoidKey] = Query([], description="Driving only"),
):
    """
    One route in one travel mode. Driving adds gas cost (split per person
    when people > 1); walking and cycling add estimated calories burned.
    """
    stops = clean_stops(stops)
    data = get_route(stops, mode, avoid)
    summary = calc.summarize(data, unit)

    result = {
        "mode": MODE_LABELS[mode],
        "unit": unit,
        "distance": round(summary["distance"], 2),
        "seconds": summary["seconds"],
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

    result["legs"] = records(calc.legs_table(data, stops, unit))
    result["steps"] = records(calc.steps_table(data, unit))
    return result


@app.get("/compare")
def compare(
    stops: list[str] = Query(..., description=STOPS_HELP),
    unit: Unit = "km",
    price_per_liter: float = Query(60.0, ge=0),
    km_per_liter: float = Query(12.0, gt=0),
    people: int = Query(1, ge=1),
    weight_kg: float = Query(65.0, gt=0),
    avoid: list[AvoidKey] = Query([], description="Driving only"),
):
    """
    The same trip in every travel mode. A mode MapQuest cannot route
    (for example walking across the sea) comes back with null values.
    Costs 4 MapQuest requests per call.
    """
    stops = clean_stops(stops)
    results = {}
    for route_type, label in MODE_LABELS.items():
        try:
            results[label] = get_route(stops, route_type, avoid)
        except HTTPException as err:
            if err.status_code != 502:
                raise  # e.g. missing key: every mode would fail the same way
            results[label] = None

    table = calc.comparison_table(results, unit, km_per_liter, price_per_liter,
                                  people, weight_kg)
    ok = table.dropna(subset=["Minutes"])
    fastest = ok.loc[ok["Minutes"].idxmin(), "Mode"] if not ok.empty else None
    return {"unit": unit, "modes": records(table), "fastest": fastest}
