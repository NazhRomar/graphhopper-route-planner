"""
api/index.py  -  Entry point for Vercel (and for running the site locally)

Vercel runs this file as a serverless function for every /api/... request
(see vercel.json) and serves the web page in public/ itself.

Locally, `uvicorn api.index:app --reload` serves both:
  http://127.0.0.1:8000           the web page
  http://127.0.0.1:8000/api/docs  the interactive API docs
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so the shared modules in the project root import

from rest_api import app as rest_api  # noqa: E402

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", rest_api)

# On Vercel the page is served by Vercel itself, so public/ may be missing here
PUBLIC = ROOT / "public"
if PUBLIC.is_dir():
    app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="site")
