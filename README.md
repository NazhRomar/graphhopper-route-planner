# Route Planner (GraphHopper)

A Streamlit web app that plans multi-stop trips, compares travel modes, and
estimates fuel cost, using the GraphHopper Geocoding and Routing APIs. It
builds on the command-line app from DEVASC Lab 4.9.2 (Integrate a REST API in
a Python Application). The same features are also available as a REST API
built with FastAPI, so other programs can use them.

## What we added to the lab app
| Lab 4.9.2 | This project |
|---|---|
| Command line, one trip at a time | Web app (Streamlit) and REST API (FastAPI) |
| Start and destination only | Any number of stops, with distance per leg |
| car, bike or foot | Same modes, plus a side-by-side comparison of all three |
| Distance and duration | Gas cost (with carpool split) and calories burned |
| Text directions | Map with the route drawn, charts, directions table, CSV download |
| Prints the matched place name | Table of what you typed next to the place found |

## Architecture
```
Streamlit UI (app.py)      REST API (api.py)
            \                 /
     calculations.py   (math and tables, no UI, no network)
            |
     graphhopper_api.py (the only file that calls GraphHopper)
```
Both front doors share the same logic, so a fix in `calculations.py` or
`graphhopper_api.py` shows up in the web app and the API at once.

Each route takes two kinds of GraphHopper calls, as in the lab: the Geocoding
API turns every stop into latitude and longitude, then one Routing API call
gets the route through all the points.

## Features
- Multi-stop routes (one stop per line)
- Driving, walking, cycling (GraphHopper's free `car`, `foot`, `bike` profiles)
- Compare all modes side by side, with charts
- Driving: gas cost from the current gas price per liter and the car's km/L, with a carpool option that splits the cost per person
- Walking and cycling: estimated calories burned (kcal), based on body weight and average speed
- Kilometers or miles
- Map with the route line and stops, charts (per leg, per step, cumulative), directions table, CSV download
- Clear errors for a wrong key, a place that cannot be found, or a route that does not exist
- REST API with JSON endpoints and an interactive docs page

## Setup
1. Get a free key: sign up at https://www.graphhopper.com, open **API Keys**, click **Add API Key**
2. Install: `pip install -r requirements.txt`
3. Set the key (or paste it into the sidebar):
   - Windows: `setx GRAPHHOPPER_KEY "your_key"` (then open a new terminal)
   - Mac/Linux: `export GRAPHHOPPER_KEY=your_key`
4. Run the web app: `streamlit run app.py`

Never commit your API key to GitHub.

The free GraphHopper plan allows only a few requests per minute. Each stop
is one geocoding request and each mode is one routing request, so Compare
modes with 3 stops costs about 6. Results are remembered for 10 minutes (web
app) or while the server runs (API, places only), and going over the limit
shows a "wait a minute" message.

## REST API
Run `uvicorn api:app --reload`, then open http://127.0.0.1:8000/docs to try
every endpoint in the browser. The API reads the key only from `GRAPHHOPPER_KEY`.

| Endpoint | What it returns |
|---|---|
| `GET /modes` | Accepted travel modes |
| `GET /route` | One route: matched stops, distance, time, gas cost or calories, legs, steps |
| `GET /compare` | The same trip in every mode, plus the fastest one |

Repeat `stops` once per stop, for example:
`/route?stops=Manila&stops=Tagaytay&mode=car&unit=km&people=3`

Modes: `car`, `foot`, `bike`.
Errors: 422 for bad input, 404 if a stop cannot be found, 500 if the key is
missing, 502 if GraphHopper fails or finds no route.

## Tests
These use a fake GraphHopper (`tests/fake_graphhopper.py`), so they need no
key and no internet:
`python tests/test_mock_app.py` and `python tests/test_mock_api.py`

## Project layout
| File | Purpose | Good for team member working on |
|---|---|---|
| `graphhopper_api.py` | Geocoding and routing calls, error handling | API and error handling |
| `calculations.py` | Unit conversion, cost, calories, tables | Features and logic |
| `app.py` | Streamlit interface, map and charts | UI and visualization |
| `api.py` | FastAPI REST endpoints | API and integration |
| `tests/` | Fake GraphHopper and test scripts | Testing |
| `README.md` | Docs for other teams | Documentation |

## How to continue the project (backlog)
- Avoid tolls, highways or ferries (GraphHopper custom models, paid plans)
- Shortest instead of fastest route
- Public transit mode
- Real-time traffic and departure time
- Auto-fetch the current gas price
- Save and reload favorite trips
- Export the trip as PDF
- Unit tests for each function in `calculations.py`
- Deploy to Streamlit Community Cloud
- Make the Streamlit app call the REST API instead of the modules directly
- API keys or rate limiting for the REST API
