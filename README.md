# Route Planner (MapQuest)

A Streamlit web app that plans multi-stop trips, compares travel modes, and
estimates fuel cost, using the MapQuest Directions API. The same features are
also available as a REST API built with FastAPI, so other programs can use them.

## Architecture
```
Streamlit UI (app.py)      REST API (api.py)
            \                 /
     calculations.py   (math and tables, no UI, no network)
            |
     mapquest_api.py   (the only file that calls MapQuest)
```
Both front doors share the same logic, so a fix in `calculations.py` or
`mapquest_api.py` shows up in the web app and the API at once.

## Features
- Multi-stop routes (one stop per line)
- Driving (fastest or shortest), walking, cycling
- Compare all modes side by side, with charts
- Driving: gas cost from the current gas price per liter and the car's km/L, with a carpool option that splits the cost per person
- Walking and cycling: estimated calories burned (kcal), based on body weight and average speed
- Avoid tolls, highways, ferries, unpaved roads (driving only)
- Kilometers or miles
- Charts (per leg, per step, cumulative), map, directions table, CSV download
- REST API with JSON endpoints and an interactive docs page

## Setup
1. Get a free key at https://developer.mapquest.com
2. Install: `pip install -r requirements.txt`
3. Set the key (or paste it into the sidebar):
   - Windows: `set MAPQUEST_KEY=your_key`
   - Mac/Linux: `export MAPQUEST_KEY=your_key`
4. Run the web app: `streamlit run app.py`

Never commit your API key to GitHub.

## REST API
Run `uvicorn api:app --reload`, then open http://127.0.0.1:8000/docs to try
every endpoint in the browser. The API reads the key only from `MAPQUEST_KEY`.

| Endpoint | What it returns |
|---|---|
| `GET /modes` | Accepted travel modes and avoid options |
| `GET /route` | One route: distance, time, gas cost or calories, legs, steps |
| `GET /compare` | The same trip in every mode, plus the fastest one |

Repeat `stops` once per stop, for example:
`/route?stops=Manila&stops=Tagaytay&mode=fastest&unit=km&people=3&avoid=tolls`

Modes: `fastest`, `shortest`, `pedestrian`, `bicycle`.
Avoid (driving only): `tolls`, `highways`, `ferries`, `unpaved`.
Errors: 422 for bad input, 500 if the key is missing, 502 if MapQuest fails
or finds no route.

## Tests
These use a fake MapQuest, so they need no key and no internet:
`python tests/test_mock_modes.py`, `python tests/test_mock_basic.py`,
`python tests/test_mock_api.py`

## Project layout
| File | Purpose | Good for team member working on |
|---|---|---|
| `mapquest_api.py` | Talks to MapQuest, handles errors | API and error handling |
| `calculations.py` | Unit conversion, cost, tables | Features and logic |
| `app.py` | Streamlit interface and charts | UI and visualization |
| `api.py` | FastAPI REST endpoints | API and integration |
| `tests/` | Mocked-API test scripts | Testing |
| `README.md` | Docs for other teams | Documentation |

## How to continue the project (backlog)
- Route drawn as a line on the map (currently shows step points)
- Save and reload favorite trips
- Public transit mode (MapQuest `multimodal`)
- Real-time traffic and departure time
- Export the trip as PDF
- Unit tests for `calculations.py`
- Deploy to Streamlit Community Cloud
- Make the Streamlit app call the REST API instead of the modules directly
- API keys or rate limiting for the REST API
