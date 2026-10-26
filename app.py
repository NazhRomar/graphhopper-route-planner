"""
app.py  -  Route Planner (Streamlit user interface)

Features:
  1. Multi-stop routing (2 or more stops, one per line), showing the place
     GraphHopper matched for each stop so you can check it
  2. Travel modes: driving, walking, cycling
  3. Compare all modes side by side with charts
  4. Driving: gas cost from gas price per liter and the car's km/L,
     with a carpool option that splits the cost between people
     Walking and cycling: estimated calories burned (kcal)
  5. Kilometers or miles
  6. Map with the route drawn as a line, charts, directions table
  7. Download directions as CSV

Run:  streamlit run app.py
Files: graphhopper_api.py (API calls), calculations.py (math and tables)
"""
import os

import pydeck as pdk
import streamlit as st

import calculations as calc
from graphhopper_api import (DRIVING_MODES, ROUTE_MODES, GraphHopperError,
                             fetch_route, geocode)

st.set_page_config(page_title="Route Planner", layout="wide")


# Cache API results for 10 minutes so changing units or gas price
# does not burn through the GraphHopper request quota
@st.cache_data(ttl=600, show_spinner=False)
def cached_geocode(key, location):
    return geocode(key, location)


@st.cache_data(ttl=600, show_spinner=False)
def cached_route(key, points, profile):
    return fetch_route(key, list(points), profile)


def find_places(key, stops):
    """Geocode every stop, or show the error and stop the page."""
    if not key:
        st.error("Enter your GraphHopper API key in the sidebar.")
        st.stop()
    if len(stops) < 2:
        st.error("Enter at least a start and a destination.")
        st.stop()
    try:
        return [cached_geocode(key, stop) for stop in stops]
    except GraphHopperError as err:
        st.error(str(err))
        st.stop()


def points_of(places):
    """(lat, lng) pairs in a tuple, so the route cache can use them as a key."""
    return tuple((p["lat"], p["lng"]) for p in places)


def draw_map(route, places):
    """Route as a blue line, stops as red dots (hover a dot for its name)."""
    path = pdk.Layer("PathLayer", data=[{"path": route["line"]}],
                     get_path="path", get_color=[37, 99, 235], width_min_pixels=4)
    dots = pdk.Layer("ScatterplotLayer",
                     data=[{"name": p["name"], "position": [p["lng"], p["lat"]]}
                           for p in places],
                     get_position="position", get_fill_color=[220, 38, 38],
                     radius_min_pixels=7, pickable=True)
    view = pdk.ViewState(**calc.map_view(route["line"]))
    st.pydeck_chart(pdk.Deck(layers=[path, dots], initial_view_state=view,
                             tooltip={"text": "{name}"}))


# ----------------------------------------------------------------- sidebar
st.sidebar.header("Settings")
key = st.sidebar.text_input(
    "GraphHopper API key", value=os.getenv("GRAPHHOPPER_KEY", ""), type="password"
)
unit = "km" if st.sidebar.radio("Units", ["Kilometers", "Miles"]) == "Kilometers" else "mi"

st.sidebar.subheader("Driving: gas cost")
currency = st.sidebar.text_input("Currency", "PHP")
price = st.sidebar.number_input("Current gas price per liter", min_value=0.0, value=60.0, step=0.5)
efficiency = st.sidebar.number_input("Car's average consumption (km/L)", min_value=1.0, value=12.0, step=0.5)
carpool = st.sidebar.checkbox("Carpool (split the gas cost)")
# Without carpool the driver pays everything, so people = 1
people = st.sidebar.number_input("People sharing the ride (including driver)",
                                 min_value=2, value=3, step=1) if carpool else 1

st.sidebar.subheader("Walking and cycling: calories")
weight = st.sidebar.number_input("Your weight (kg)", min_value=20.0, max_value=300.0,
                                 value=65.0, step=1.0)

# -------------------------------------------------------------------- main
st.title("Route Planner")
st.caption("Plan multi-stop trips, compare travel modes and estimate fuel cost. "
           "Powered by the GraphHopper Geocoding and Routing APIs.")

stops_text = st.text_area(
    "Stops (one per line: start first, destination last)",
    "Manila, Philippines\nTagaytay, Philippines\nBatangas City, Philippines",
    height=110,
)
stops = tuple(line.strip() for line in stops_text.splitlines() if line.strip())

mode_label = st.selectbox("Travel mode", list(ROUTE_MODES))

tab_route, tab_compare = st.tabs(["Route details", "Compare modes"])

# ------------------------------------------------------------ route details
with tab_route:
    if st.button("Get route", type="primary"):
        places = find_places(key, stops)
        try:
            route = cached_route(key, points_of(places), ROUTE_MODES[mode_label])
        except GraphHopperError as err:
            st.error(str(err))
            st.stop()

        summary = calc.summarize(route, unit)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total distance", f"{summary['distance']:.1f} {unit}")
        c2.metric("Trip time", summary["time_text"])

        if ROUTE_MODES[mode_label] in DRIVING_MODES:
            # Driving: gas needed and what it costs, split if carpooling
            liters, cost = calc.estimate_cost(summary["distance_km"], efficiency, price)
            c3.metric("Gas cost (total)", f"{currency} {cost:,.2f}")
            if carpool:
                c4.metric(f"Per person ({people} people)",
                          f"{currency} {calc.split_cost(cost, people):,.2f}")
            st.caption(f"About {liters:.1f} liters of gas.")
        else:
            # Walking or cycling: calories burned instead of gas
            kcal = calc.estimate_calories(mode_label, summary["distance_km"],
                                          summary["seconds"], weight)
            c3.metric("Calories burned", f"{kcal:,.0f} kcal")
            st.caption("Estimate based on your weight and average speed. "
                       "Real burn varies with fitness, hills and wind.")

        st.subheader("Map")
        draw_map(route, places)

        with st.expander("Places found for your stops"):
            st.dataframe(calc.stops_table(places), hide_index=True)

        # Chart 1: distance of each leg (only interesting with 3+ stops)
        legs = calc.legs_table(route, stops, unit)
        if len(legs) > 1:
            st.subheader("Distance per leg")
            st.bar_chart(legs.set_index("Leg")["Distance"])
            st.dataframe(legs, hide_index=True)

        # Chart 2 and 3: per step and cumulative
        steps = calc.steps_table(route, unit)
        left, right = st.columns(2)
        left.subheader(f"Distance per step ({unit})")
        left.bar_chart(steps.set_index("Step")["Distance"])
        right.subheader(f"Distance covered so far ({unit})")
        right.line_chart(steps.set_index("Step")["Distance"].cumsum())

        st.subheader("Step-by-step directions")
        shown = steps[["Step", "Direction", "Distance", "Time"]]
        st.dataframe(shown, hide_index=True)
        st.download_button("Download directions (CSV)",
                           shown.to_csv(index=False), "directions.csv", "text/csv")

# ------------------------------------------------------------ compare modes
with tab_compare:
    st.write("Runs the same trip in every travel mode and compares them.")
    if st.button("Compare all modes"):
        places = find_places(key, stops)  # geocode once, reuse for every mode

        results = {}
        with st.spinner("Asking GraphHopper for each mode..."):
            for label, profile in ROUTE_MODES.items():
                try:
                    results[label] = cached_route(key, points_of(places), profile)
                except GraphHopperError:
                    results[label] = None  # e.g. no walking route across the sea

        table = calc.comparison_table(results, unit, efficiency, price, people, weight)
        st.dataframe(table, hide_index=True)

        ok = table.dropna(subset=["Minutes"]).set_index("Mode")
        if ok.empty:
            st.warning("No mode returned a route for these stops.")
        else:
            a, b = st.columns(2)
            a.subheader("Travel time (minutes)")
            a.bar_chart(ok["Minutes"])
            b.subheader(f"Distance ({unit})")
            b.bar_chart(ok["Distance"])
            fastest = ok["Minutes"].idxmin()
            st.success(f"Fastest option: {fastest} ({ok.loc[fastest, 'Time']})")
