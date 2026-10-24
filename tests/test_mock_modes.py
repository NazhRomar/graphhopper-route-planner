import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import requests

def man(n, d):
    return {"narrative": f"Turn {n}", "distance": d, "formattedTime": "00:05:00",
            "startPoint": {"lat": 14.5 + n * 0.01, "lng": 121.0 + n * 0.01}}

def route(dist, secs):
    return {"info": {"statuscode": 0}, "route": {"distance": dist, "time": secs,
        "legs": [{"distance": dist / 2, "time": secs / 2, "maneuvers": [man(1, dist / 2)]},
                 {"distance": dist / 2, "time": secs / 2, "maneuvers": [man(2, dist / 2)]}]}}

class Resp:
    def __init__(self, d): self.d = d
    def json(self): return self.d

def fake_post(url, params=None, json=None, timeout=None):
    t = json["options"]["routeType"]
    if t == "pedestrian": return Resp(route(10.0, 7200))
    if t == "bicycle": return Resp(route(10.0, 2400))
    return Resp(route(120.0, 5400))
requests.post = fake_post

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
at.sidebar.text_input[0].set_value("K")
at.run()
# driving, no carpool
at.button[0].click().run()
print("driving:", [(m.label, m.value) for m in at.metric], [e.value for e in at.exception])
# carpool on, 3 people
at.sidebar.checkbox[0].check().run()
at.button[0].click().run()
print("carpool:", [(m.label, m.value) for m in at.metric], [e.value for e in at.exception])
# walking
at.selectbox[0].select("Walking").run()
at.button[0].click().run()
print("walking:", [(m.label, m.value) for m in at.metric], [e.value for e in at.exception])
at.selectbox[0].select("Cycling").run()
at.button[0].click().run()
print("cycling:", [(m.label, m.value) for m in at.metric], [e.value for e in at.exception])
at.button[1].click().run()
print(at.dataframe[-1].value.to_string(), [e.value for e in at.exception])
