"""
Shared setup for every test. pytest loads this file by itself.

Every test talks to a fake GraphHopper (fake_graphhopper.py) instead of the
real one, so the tests need no API key and no internet, and they run the same
on a laptop and on GitHub Actions.
"""
import pytest
import requests

import fake_graphhopper
import graphhopper_api
import rest_api


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    """Before each test: swap in the fake GraphHopper and forget earlier results."""
    # monkeypatch puts the real requests.get back after the test
    monkeypatch.setattr(requests, "get", fake_graphhopper.fake_get)
    fake_graphhopper.calls.clear()
    rest_api.cached_geocode.cache_clear()
    rest_api.cached_route.cache_clear()
    graphhopper_api._usage.clear()
