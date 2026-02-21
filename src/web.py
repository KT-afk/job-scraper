"""
web.py
------
Flask web server for browsing scraped job postings.

Routes
------
GET /          - main job board page (HTML)
GET /api/jobs  - JSON endpoint, supports query params:
                   ?q=<search>            full-text search across title + snippet
                   ?discipline=<disc>     filter by discipline (Backend, Frontend, …)
                   ?location=<loc>        filter by location search term
                   ?visa=1                only visa-sponsored jobs
                   ?remote=1              only remote-ok jobs
                   ?sort=date|title       sort column (default: date desc)
GET /api/stats - summary counts (total, by discipline, by location)
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, render_template, request
from sqlmodel import Session, select

from src.storage import JobPosting, _engine

# Flask looks for templates/ relative to the project root.
# __file__ is job-scraper/src/web.py, so we go one level up.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(_root, "templates"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
def api_jobs():
    q          = (request.args.get("q") or "").strip().lower()
    discipline = (request.args.get("discipline") or "").strip()
    location   = (request.args.get("location") or "").strip()
    visa_only  = request.args.get("visa") == "1"
    remote_only = request.args.get("remote") == "1"
    sort       = request.args.get("sort", "date")

    with Session(_engine) as session:
        stmt = select(JobPosting)

        if discipline:
            stmt = stmt.where(JobPosting.discipline == discipline)
        if location:
            stmt = stmt.where(JobPosting.location == location)
        if visa_only:
            stmt = stmt.where(JobPosting.visa_sponsored == True)  # noqa: E712
        if remote_only:
            stmt = stmt.where(JobPosting.remote_ok == True)        # noqa: E712

        jobs: list[JobPosting] = session.exec(stmt).all()

    # Full-text search in Python (DB-agnostic)
    if q:
        jobs = [
            j for j in jobs
            if q in j.title.lower() or q in (j.snippet or "").lower()
        ]

    # Sorting
    if sort == "title":
        jobs = sorted(jobs, key=lambda j: j.title.lower())
    else:
        jobs = sorted(jobs, key=lambda j: j.published or "", reverse=True)

    return jsonify([
        {
            "id":            j.id,
            "url":           j.url,
            "title":         j.title,
            "role":          j.role,
            "discipline":    j.discipline,
            "location":      j.location,
            "visa_sponsored": j.visa_sponsored,
            "remote_ok":     j.remote_ok,
            "published":     j.published or "",
            "snippet":       j.snippet or "",
            "seen_at":       j.seen_at[:10],
        }
        for j in jobs
    ])


@app.get("/api/stats")
def api_stats():
    with Session(_engine) as session:
        jobs = session.exec(select(JobPosting)).all()

    disciplines: dict[str, int] = {}
    locations: dict[str, int] = {}
    visa_count = 0
    remote_count = 0

    for j in jobs:
        disciplines[j.discipline or "Other"] = disciplines.get(j.discipline or "Other", 0) + 1
        locations[j.location] = locations.get(j.location, 0) + 1
        if j.visa_sponsored:
            visa_count += 1
        if j.remote_ok:
            remote_count += 1

    return jsonify({
        "total":       len(jobs),
        "disciplines": disciplines,
        "locations":   locations,
        "visa":        visa_count,
        "remote":      remote_count,
    })


# ---------------------------------------------------------------------------
# HTML route
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    with Session(_engine) as session:
        jobs = session.exec(select(JobPosting)).all()

    disciplines = sorted({j.discipline for j in jobs if j.discipline})
    locations   = sorted({j.location for j in jobs})

    return render_template(
        "index.html",
        disciplines=disciplines,
        locations=locations,
    )


# ---------------------------------------------------------------------------
# Launch helper (called from main.py)
# ---------------------------------------------------------------------------

def run(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    print(f"\nJob board running at http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)
