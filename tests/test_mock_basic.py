import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import requests

def man(n, d):
    return {"narrative": f"Turn {n}", "distance": d, "formattedTime": "00:05:00",
            "startPoint": {"lat": 14.5 + n * 0.01, "lng": 121.0 + n * 0.01}}

class Resp:
    def __init__(self, code=0):
        self.code = code
    def json(self):
        if self.code:
            return {"info": {"statuscode": self.code, "messages": ["Bad location"]}}
        return {"info": {"statuscode": 0}, "route": {
            "distance": 100.0, "time": 7500,
            "legs": [{"distance": 60.0, "time": 4000, "maneuvers": [man(1, 30), man(2, 30)]},
                     {"distance": 40.0, "time": 3500, "maneuvers": [man(3, 40)]}]}}

def fake_post(url, params=None, json=None, timeout=None):
    if json["options"]["routeType"] == "pedestrian":
        return Resp(402)
    return Resp()
requests.post = fake_post

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
at.sidebar.text_input[0].set_value("FAKEKEY")
at.run()
at.button[0].click().run()
print("exceptions:", [e.value for e in at.exception])
print("errors:", [e.value for e in at.error])
print("metrics:", [(m.label, m.value) for m in at.metric])
at.button[1].click().run()
print("exceptions:", [e.value for e in at.exception])
for df in at.dataframe[-1:]:
    print(df.value)
print("success:", [s.value for s in at.success])
