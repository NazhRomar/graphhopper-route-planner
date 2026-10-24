"""
calculations.py

Pure functions that turn the raw MapQuest route into numbers and tables the UI
can show. No Streamlit and no network calls here, so these are easy to test.
"""
import pandas as pd

KM_PER_MILE = 1.609344


def convert_distance(km, unit):
    """Convert kilometers to the unit the user picked ('km' or 'mi')."""
    return km / KM_PER_MILE if unit == "mi" else km


def format_time(seconds):
    """Turn a number of seconds into text like '2h 05m'."""
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def estimate_cost(distance_km, km_per_liter, price_per_liter):
    """
    Estimate fuel used (liters) and cost for a driving trip.
    Returns (liters, cost). Returns (0, 0) if efficiency is not valid.
    """
    if km_per_liter <= 0:
        return 0.0, 0.0
    liters = distance_km / km_per_liter
    return liters, liters * price_per_liter


def split_cost(total_cost, people):
    """Split a fuel cost evenly between everyone in the car (carpool)."""
    return total_cost / max(int(people), 1)


# MET = how hard an activity is compared with sitting still (1 MET).
# Values are simplified from the Compendium of Physical Activities.
# Each pair is (speed limit in km/h, MET); the first limit the speed is
# below wins. Speed comes from the real route: distance divided by time.
WALKING_MET = [(3.2, 2.8), (4.0, 3.0), (4.8, 3.5), (5.6, 4.3), (6.4, 5.0)]
WALKING_MET_FAST = 6.3   # faster than the table above
CYCLING_MET = [(16.0, 4.0), (19.3, 6.8), (22.5, 8.0), (25.7, 10.0)]
CYCLING_MET_FAST = 12.0  # faster than the table above


def pick_met(speed_kmh, table, fastest):
    """Find the MET value for a given speed."""
    for limit, met in table:
        if speed_kmh < limit:
            return met
    return fastest


def estimate_calories(mode, distance_km, seconds, weight_kg):
    """
    Estimate kcal burned for a walking or cycling trip.

        kcal = MET x body weight (kg) x time (hours)

    Returns 0 for driving, or if the data is not usable.
    This is a rough estimate. Real burn depends on fitness, hills and wind.
    """
    if seconds <= 0 or weight_kg <= 0 or distance_km <= 0:
        return 0.0
    hours = seconds / 3600
    speed = distance_km / hours
    if mode.startswith("Walking"):
        met = pick_met(speed, WALKING_MET, WALKING_MET_FAST)
    elif mode.startswith("Cycling"):
        met = pick_met(speed, CYCLING_MET, CYCLING_MET_FAST)
    else:
        return 0.0
    return met * weight_kg * hours


def summarize(route, unit):
    """Headline numbers for a route, in the user's chosen unit."""
    return {
        "distance": convert_distance(route["distance"], unit),
        "distance_km": route["distance"],
        "seconds": route["time"],
        "time_text": format_time(route["time"]),
    }


def legs_table(route, stops, unit):
    """
    One row per leg (the part of the trip between two stops).
    A trip with 3 stops has 2 legs.
    """
    rows = []
    for i, leg in enumerate(route["legs"]):
        rows.append(
            {
                "Leg": f"{i + 1}. {stops[i]} to {stops[i + 1]}",
                "Distance": round(convert_distance(leg["distance"], unit), 1),
                "Time": format_time(leg["time"]),
            }
        )
    return pd.DataFrame(rows)


def steps_table(route, unit):
    """
    One row per turn-by-turn step, across all legs.
    Includes lat/lon so the same table can feed the map.
    """
    rows = []
    number = 0
    for leg in route["legs"]:
        for m in leg["maneuvers"]:
            number += 1
            rows.append(
                {
                    "Step": number,
                    "Direction": m["narrative"],
                    "Distance": round(convert_distance(m["distance"], unit), 2),
                    "Time": m["formattedTime"],
                    "lat": m["startPoint"]["lat"],
                    "lon": m["startPoint"]["lng"],
                }
            )
    return pd.DataFrame(rows)


def comparison_table(results, unit, km_per_liter, price_per_liter,
                     people, weight_kg):
    """
    Build the 'compare modes' table.
    `results` maps a mode name to its route (or None if that mode failed).
    Driving rows get fuel cost; walking and cycling rows get calories.
    """
    rows = []
    for mode, route in results.items():
        if route is None:
            rows.append({"Mode": mode, "Distance": None, "Minutes": None,
                         "Time": "No route", "Fuel cost": None,
                         "Cost per person": None, "Calories (kcal)": None})
            continue
        is_driving = mode.startswith("Driving")
        _, cost = estimate_cost(route["distance"], km_per_liter, price_per_liter)
        kcal = estimate_calories(mode, route["distance"], route["time"], weight_kg)
        rows.append(
            {
                "Mode": mode,
                "Distance": round(convert_distance(route["distance"], unit), 1),
                "Minutes": round(route["time"] / 60),
                "Time": format_time(route["time"]),
                "Fuel cost": round(cost, 2) if is_driving else 0.0,
                "Cost per person": round(split_cost(cost, people), 2) if is_driving else 0.0,
                "Calories (kcal)": round(kcal) if not is_driving else 0,
            }
        )
    return pd.DataFrame(rows)
