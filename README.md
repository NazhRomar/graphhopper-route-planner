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
- Driving: gas cost from the current gas price per liter and the car's km/L, with a carpool option that splits the cost per person; on the web page, the pencil on Gas cost edits these and the page redoes the math itself, so no API request is made
- Walking and cycling: estimated calories burned (kcal), based on body weight, average speed and the hills climbed
- Elevation and hills: how many meters the route climbs and drops, and whether it is Flat, has Some hills, or is Hilly (from the average climb per km)
- Kilometers or miles
- Map with the route line and stops, distance per leg, directions table, CSV download
- Web page: up to 3 route options for a trip with a start and a destination ("Show other routes" in Trip options), shown as buttons and as lines on the map
- Web page: save trips by name (stops and travel mode) and load them again later; they stay in your browser, and loading one uses no GraphHopper requests
- Clear errors for a wrong key, a place that cannot be found, a route that does not exist, or the request limit
- Web page: API key saved only in your browser, toasts for saved results and errors, and repeated trips are answered from the browser for 10 minutes without using GraphHopper requests
- Credits used today: the page shows how many of your key's daily GraphHopper credits are used, read from the `X-RateLimit-*` headers GraphHopper sends with every response, and warns when fewer than 10% are left

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
| `GET /api/route` | One route: matched stops, distance, time, gas cost or calories, climb and drop (`ascend_m`, `descend_m`, `hills`), legs, steps, route line. With `alternatives=true` and exactly 2 stops, also up to 2 other routes in `alternatives`, each with the same fields |
| `GET /api/compare` | The same trip in every mode, the fastest one, and why any mode failed |
| `GET /api/usage` | Your key's daily credits (limit, remaining, used, reset time) as of its last request; costs no credits |

`/route` and `/compare` also include a `usage` field with the same numbers.
They are kept per key, so people sharing the server never see each other's.

Send the key in the `X-GraphHopper-Key` header (or set `GRAPHHOPPER_KEY` on
the server). Repeat `stops` once per stop, for example:
`/api/route?stops=Manila&stops=Tagaytay&mode=car&unit=km&people=3`

Modes: `car`, `foot`, `bike`.
Errors: 401 if there is no key, 422 for bad input, 404 if a stop cannot be
found, 502 if GraphHopper fails, finds no route, or hits the request limit.

## Tests
The tests use a fake GraphHopper (`tests/fake_graphhopper.py`), so they need
no key and no internet. Run them all from the project folder with `pytest`
(it is in `requirements-dev.txt`). The saved-trips logic of the web page is
tested with Node's own test runner: `node --test tests/*.test.js`.

| File | What it tests |
|---|---|
| `tests/test_calculations.py` | Every function in `calculations.py`: units, time, gas cost, calories, tables, map zoom |
| `tests/test_graphhopper_api.py` | Geocoding, routing, legs, and each kind of GraphHopper error |
| `tests/test_rest_api.py` | Every REST endpoint, status codes, saved results, credits, the Vercel entry point |
| `tests/test_streamlit_app.py` | The Streamlit app, clicked through like a user |
| `tests/favorites.test.js` | Saved trips (`public/favorites.js`): add, replace, delete, broken saved data |
| `tests/conftest.py` | Swaps in the fake GraphHopper before each test |

## CI/CD pipeline (GitHub Actions)
`.github/workflows/tests.yml` runs on every push to any branch and on every
pull request into `main`. GitHub installs the libraries, checks the web
page's JavaScript for syntax errors, runs the JavaScript tests and then
`pytest`. The result shows as a
green check or a red X on the commit and the pull request (details in the
**Actions** tab).

`main` is protected by a ruleset on GitHub (Settings, then Rules): changes go
in only through a pull request, with one teammate's approval and the
"Run tests" check passing. Vercel deploys `main`, so only tested code goes live.

How to add a change:
1. Make a branch, for example `git switch -c feature/elevation`
2. Commit, push the branch, and open a pull request into `main`
3. Wait for the green check and a teammate's approval, then merge

## Project layout
| File | Purpose | Good for team member working on |
|---|---|---|
| `graphhopper_api.py` | Geocoding and routing calls, error handling | API and error handling |
| `calculations.py` | Unit conversion, cost, calories, tables | Features and logic |
| `rest_api.py` | FastAPI REST endpoints | API and integration |
| `api/index.py`, `vercel.json` | Vercel entry point and config | Deployment |
| `public/` | Web page (HTML, CSS, JavaScript, Leaflet map) | Web UI |
| `app.py` | Streamlit interface, map and charts | Local UI and visualization |
| `tests/`, `pytest.ini` | Fake GraphHopper and test cases | Testing |
| `.github/workflows/` | CI pipeline that runs the tests on GitHub | CI/CD |
| `README.md` | Docs for other teams | Documentation |

## How to continue the project (backlog)
Done in Project Activity 4:
- **Elevation and hills**: climb, drop and a Flat / Some hills / Hilly label for every route, and calories that count the climb
- **Alternative routes**: with "Show other routes" on (web page, Trip options), a trip with only a start and a destination asks GraphHopper for up to 3 routes (`algorithm=alternative_route`). The Route tab shows a button per route and the others as lighter lines on the map; click either to switch. If GraphHopper refuses alternatives, `fetch_route` quietly asks again for one route. Not in the Streamlit app yet
- **Save favorite trips**: "Save trip" on the Plan tab names the current stops and mode; "Saved trips" lists them (up to 20, newest first) to load or delete. The list logic is in `public/favorites.js` (tested with Node), the buttons in `public/app.js`, and the trips in the browser's local storage (`favorite_trips`)

Still planned, easiest first:
- **Export the trip as PDF**: a print stylesheet for the Route tab, or a small PDF library
- **Avoid tolls and highways**: GraphHopper custom models; check first whether the free plan allows them

Later ideas:
- Elevation chart along the route: add `elevation=true` to the route request, which gives every point a height (`fetch_route` already keeps only `[lng, lat]` for the map)
- Make the Streamlit app call the REST API instead of the modules directly
- Rate limiting for the REST API

Looked into and set aside: public transit and real-time traffic are not offered
by GraphHopper's hosted free plan, and there is no free official API for
Philippine gas prices (the DOE publishes weekly advisories as documents).
