# api/index.py
# Vercel serverless entry point.
# Vercel imports this file and looks for a WSGI `app` callable.
from src.web import app  # noqa: F401 — re-exported for Vercel
