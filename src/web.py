"""
web.py
------
Flask web server for browsing scraped job postings.

Routes
------
GET /          - main job board page (HTML)
GET /settings  - settings / profile page (HTML)
POST /settings - save profile and redirect
GET /api/jobs  - JSON endpoint, supports query params:
                   ?q=<search>            full-text search across title + snippet
                   ?discipline=<disc>     filter by discipline (Backend, Frontend, …)
                   ?location=<loc>        filter by location search term
                   ?visa=1                only visa-sponsored jobs
                   ?remote=1              only remote-ok jobs
                   ?sort=date|title       sort column (default: date desc)
                   ?status=<s>            filter by application status
                   ?days=<n>              filter jobs published within last N days
                   ?dismissed=1           include dismissed jobs (hidden by default)
GET /api/stats - summary counts (total, by discipline, by location)
POST /api/settings/parse-resume - upload PDF and return extracted profile fields
PATCH /api/jobs/<job_id> - update status and/or notes for a job
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlmodel import Session, select

from src.storage import (
    JobPosting,
    UserProfile,
    _engine,
    get_profile,
    init_db,
    save_profile,
    update_job_tracking,
)

# Flask looks for templates/ relative to the project root.
# __file__ is job-scraper/src/web.py, so we go one level up.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(_root, "templates"))

# Ensure the DB and tables exist when gunicorn imports this module on Railway.
init_db()
print(f"[web] DB ready. Templates: {os.path.join(_root, 'templates')}")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
def api_jobs():
    q           = (request.args.get("q") or "").strip().lower()
    discipline  = (request.args.get("discipline") or "").strip()
    location    = (request.args.get("location") or "").strip()
    visa_only   = request.args.get("visa") == "1"
    remote_only = request.args.get("remote") == "1"
    sort        = request.args.get("sort", "date")
    status_filter = (request.args.get("status") or "").strip()
    days_str    = (request.args.get("days") or "").strip()
    show_dismissed = request.args.get("dismissed") == "1"

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
        if status_filter:
            stmt = stmt.where(JobPosting.status == status_filter)
        if not show_dismissed:
            stmt = stmt.where(JobPosting.status != "dismissed")

        jobs = list(session.exec(stmt).all())

    # Full-text search in Python (DB-agnostic)
    if q:
        jobs = [
            j for j in jobs
            if q in j.title.lower() or q in (j.snippet or "").lower()
        ]

    # Date filter (by published date)
    if days_str and days_str.isdigit():
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days_str))).date().isoformat()
        jobs = [j for j in jobs if (j.published or "") >= cutoff]

    # Sorting
    if sort == "title":
        jobs = sorted(jobs, key=lambda j: j.title.lower())
    else:
        jobs = sorted(jobs, key=lambda j: j.published or "", reverse=True)

    today = datetime.now(timezone.utc).date().isoformat()

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
            "seen_today":    j.seen_at[:10] == today,
            "status":        j.status,
            "notes":         j.notes,
            "ai_analysis":   j.ai_analysis,
        }
        for j in jobs
    ])


@app.get("/api/stats")
def api_stats():
    with Session(_engine) as session:
        jobs = list(session.exec(select(JobPosting)).all())

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


@app.patch("/api/jobs/<job_id>")
def api_patch_job(job_id: str):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    notes = data.get("notes")

    found = update_job_tracking(job_id, status=status, notes=notes)
    if not found:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/settings/parse-resume")
def api_parse_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    pdf_bytes = f.read()

    try:
        from src.ai_analysis import parse_resume
        result = parse_resume(pdf_bytes)
        if result is None:
            return jsonify({"error": "Failed to parse resume"}), 500
        return jsonify(result)
    except Exception:
        logging.exception("parse_resume failed")
        return jsonify({"error": "Failed to parse resume"}), 500


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    with Session(_engine) as session:
        jobs = list(session.exec(select(JobPosting)).all())

    disciplines = sorted({j.discipline for j in jobs if j.discipline})
    locations   = sorted({j.location for j in jobs})

    return render_template(
        "index.html",
        disciplines=disciplines,
        locations=locations,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        profile = UserProfile(
            id=1,
            graduation_date=request.form.get("graduation_date", ""),
            location=request.form.get("location", ""),
            visa_status=request.form.get("visa_status", ""),
            skills=request.form.get("skills", ""),
            projects=request.form.get("projects", "[]"),
        )
        save_profile(profile)
        return redirect(url_for("settings"))

    profile = get_profile()
    return render_template("settings.html", profile=profile)


# ---------------------------------------------------------------------------
# Launch helper (called from main.py)
# ---------------------------------------------------------------------------

def run(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    print(f"\nJob board running at http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)
