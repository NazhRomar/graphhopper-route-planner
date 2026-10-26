# Route Planner (GraphHopper)

Plan multi-stop trips, compare travel modes, and estimate gas cost and
calories, using the GraphHopper Geocoding and Routing APIs. It builds on the
command-line app from DEVASC Lab 4.9.2 (Integrate a REST API in a Python
Application).

There are three ways to use it, all sharing the same logic:
- a **web page** (`public/`) with a **REST API** (FastAPI) behind it, deployable to Vercel
- the REST API on its own, for other programs
- a **Streamlit app** (`app.py`) to run locally

## What we added to the lab app
| Lab 4.9.2 | This project |
|---|---|
| Command line, one trip at a time | Web page, REST API and Streamlit app |
| Start and destination only | Any number of stops, with distance per leg |
| car, bike or foot | Same modes, plus a side-by-side comparison of all three |
| Distance and duration | Gas cost (with carpool split) and calories burned |
| Text directions | Map with the route drawn, charts, directions table, CSV download |
| Prints the matched place name | Table of what you typed next to the place found |
| API key written in the code | Key kept in the browser or an environment variable |

## Architecture
```
Web page (public/)                 Streamlit app (app.py)
      |  X-GraphHopper-Key header           |
REST API (rest_api.py)                      |
      \                                    /
       calculations.py    (math and tables, no UI, no network)
              |
       graphhopper_api.py (the only file that calls GraphHopper)
```
A fix in `calculations.py` or `graphhopper_api.py` shows up everywhere at once.

Each route takes two kinds of GraphHopper calls, as in the lab: the Geocoding
API turns every stop into latitude and longitude, then one Routing API call
gets the route through all the points.

## Features
- Multi-stop routes (one stop per line)
- Driving, walking, cycling (GraphHopper's free `car`, `foot`, `bike` profiles)
- Compare all modes side by side, with the reason when a mode has no route
- Driving: gas cost from the current gas price per liter and the car's km/L, with a carpool option that splits the cost per person
- Walking and cycling: estimated calories burned (kcal), based on body weight and average speed
- Kilometers or miles
- Map with the route line and stops, distance per leg, directions table, CSV download
- Clear errors for a wrong key, a place that cannot be found, a route that does not exist, or the request limit
- Web page: API key saved only in your browser, toasts for saved results and errors, and repeated trips are answered from the browser for 10 minutes without using GraphHopper requests

## Get a GraphHopper key
Sign up at https://www.graphhopper.com, open **API Keys**, click **Add API Key**.
Never commit your key to GitHub.

The free plan allows only a few requests per minute. Each stop is one
geocoding request and each mode is one routing request, so Compare with 3
stops costs about 6. Repeated trips are remembered (web page and Streamlit
for 10 minutes, REST API while the server runs), and going over the limit
shows a "wait a minute" message.

## Run locally
```
pip install -r requirements-dev.txt
```
- **Web page and REST API:** `uvicorn api.index:app --reload`, then open
  http://127.0.0.1:8000 and paste your key in the settings.
  API docs: http://127.0.0.1:8000/api/docs
- **Streamlit app:** set the key (Windows `setx GRAPHHOPPER_KEY "your_key"`
  then open a new terminal, Mac/Linux `export GRAPHHOPPER_KEY=your_key`), or
  paste it in the sidebar, then `streamlit run app.py`

## Deploy to Vercel
Streamlit cannot run on Vercel (it needs a server that stays on), so Vercel
hosts the web page and runs the REST API as a Python serverless function.
1. On https://vercel.com, click **Add New**, then **Project**, and import this GitHub repo
2. Keep the defaults (`vercel.json` already sets everything) and click **Deploy**
3. Every push to `main` deploys again automatically

Do not add a `GRAPHHOPPER_KEY` on Vercel: each visitor pastes their own key,
so nobody can use up yours.

Files involved: `vercel.json` (sends `/api/...` to the function and serves
`public/`), `api/index.py` (the function), `requirements.txt` (what the
function installs; Streamlit is only in `requirements-dev.txt` to keep the
function small), `.vercelignore` (files Vercel skips).

## REST API
| Endpoint | What it returns |
|---|---|
| `GET /api/modes` | Accepted travel modes |
| `GET /api/route` | One route: matched stops, distance, time, gas cost or calories, legs, steps, route line |
| `GET /api/compare` | The same trip in every mode, the fastest one, and why any mode failed |

Send the key in the `X-GraphHopper-Key` header (or set `GRAPHHOPPER_KEY` on
the server). Repeat `stops` once per stop, for example:
`/api/route?stops=Manila&stops=Tagaytay&mode=car&unit=km&people=3`

Modes: `car`, `foot`, `bike`.
Errors: 401 if there is no key, 422 for bad input, 404 if a stop cannot be
found, 502 if GraphHopper fails, finds no route, or hits the request limit.

## Tests
These use a fake GraphHopper (`tests/fake_graphhopper.py`), so they need no
key and no internet:
`python tests/test_mock_app.py` and `python tests/test_mock_api.py`

## Project layout
| File | Purpose | Good for team member working on |
|---|---|---|
| `graphhopper_api.py` | Geocoding and routing calls, error handling | API and error handling |
| `calculations.py` | Unit conversion, cost, calories, tables | Features and logic |
| `rest_api.py` | FastAPI REST endpoints | API and integration |
| `api/index.py`, `vercel.json` | Vercel entry point and config | Deployment |
| `public/` | Web page (HTML, CSS, JavaScript, Leaflet map) | Web UI |
| `app.py` | Streamlit interface, map and charts | Local UI and visualization |
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
- Make the Streamlit app call the REST API instead of the modules directly
- Rate limiting for the REST API
