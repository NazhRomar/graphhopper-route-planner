"""
Mocked-API checks for the Streamlit app (app.py). No real GraphHopper calls.
Run: python tests/test_mock_app.py
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fake_graphhopper
fake_graphhopper.install()

from streamlit.testing.v1 import AppTest


def metrics(at):
    return {m.label: m.value for m in at.metric}


def check_ok(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
at.sidebar.text_input[0].set_value("FAKEKEY").run()
GET_ROUTE, COMPARE = 0, 1

# driving, no carpool
at.button[GET_ROUTE].click().run()
check_ok(at)
print("driving:", metrics(at))
assert metrics(at)["Gas cost (total)"] == "PHP 600.00"
assert metrics(at)["Trip time"] == "1h 30m"

# carpool on, 3 people
at.sidebar.checkbox[0].check().run()
at.button[GET_ROUTE].click().run()
check_ok(at)
print("carpool:", metrics(at))
assert metrics(at)["Per person (3 people)"] == "PHP 200.00"

# miles
at.sidebar.radio[0].set_value("Miles").run()
at.button[GET_ROUTE].click().run()
print("miles:", metrics(at)["Total distance"])
assert metrics(at)["Total distance"] == "74.6 mi"
at.sidebar.radio[0].set_value("Kilometers").run()

# walking and cycling calories
at.selectbox[0].select("Walking").run()
at.button[GET_ROUTE].click().run()
check_ok(at)
print("walking:", metrics(at))
assert metrics(at)["Calories burned"] == "559 kcal"

at.selectbox[0].select("Cycling").run()
at.button[GET_ROUTE].click().run()
check_ok(at)
print("cycling:", metrics(at))
assert metrics(at)["Calories burned"] == "173 kcal"

# compare, where walking to the island is impossible
at.text_area[0].input("Manila\nIsland").run()
at.button[COMPARE].click().run()
assert not at.exception, [e.value for e in at.exception]
table = at.dataframe[-1].value
print(table.to_string())
assert table.set_index("Mode").loc["Walking", "Time"] == "No route"
assert at.warning[0].value == "Walking: Connection between locations not found"
assert at.success[0].value == "Fastest option: Cycling (40m)"

# a stop that cannot be found
at.text_area[0].input("Manila\nNowhere").run()
at.button[GET_ROUTE].click().run()
print("not found:", [e.value for e in at.error])
assert at.error[0].value == "Location not found: Nowhere"

# a wrong API key
at.sidebar.text_input[0].set_value("BAD").run()
at.button[GET_ROUTE].click().run()
print("bad key:", [e.value for e in at.error])
assert "Wrong credentials" in at.error[0].value

# over the free plan's per-minute limit
at.sidebar.text_input[0].set_value("LIMIT").run()
at.button[GET_ROUTE].click().run()
print("rate limit:", [e.value for e in at.error])
assert "request limit" in at.error[0].value

print("all app checks passed")
