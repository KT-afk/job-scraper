"""
ai_analysis.py
--------------
AI-powered job analysis and resume parsing using the Anthropic API.

Functions
---------
analyze_job(job, profile) -> dict | None
    Analyzes a job posting against the user profile using claude-haiku.
    Returns a dict with keys: disqualifiers, caution, matched_projects,
    key_requirements. Returns None on any failure.

parse_resume(pdf_bytes) -> dict | None
    Parses a resume PDF using claude-sonnet and extracts profile fields.
    Returns a dict with keys: graduation_date, location, visa_status,
    skills, projects. Returns None on any failure.
"""

from __future__ import annotations

import base64
import json
from typing import Optional

import anthropic

import src.config as _cfg
from src.storage import JobPosting, UserProfile

# ---------------------------------------------------------------------------
# analyze_job
# ---------------------------------------------------------------------------

_ANALYSIS_SCHEMA = {
    "disqualifiers": "list[str] — hard blockers (wrong location, missing visa, too senior)",
    "caution": "list[str] — soft concerns worth noting",
    "matched_projects": "list[str] — names of the user's projects relevant to this role",
    "key_requirements": "list[str] — 3-5 bullet points of what this role needs",
}

_ANALYZE_SYSTEM = (
    "You are a job-hunt assistant. Given a job posting and a candidate profile, "
    "return ONLY a JSON object with exactly these keys: "
    "disqualifiers (hard blockers), caution (soft concerns), "
    "matched_projects (candidate's relevant projects), "
    "key_requirements (3-5 bullet points of what the role needs). "
    "No markdown, no explanation, just the JSON object."
)


def analyze_job(job: JobPosting, profile: UserProfile) -> Optional[dict]:
    """
    Analyze a job posting against the user profile.

    Returns a dict with keys: disqualifiers, caution, matched_projects,
    key_requirements. Returns None if the API key is missing or any error occurs.
    """
    if not _cfg.ANTHROPIC_API_KEY:
        print("[AI] ANTHROPIC_API_KEY not set — skipping analysis.")
        return None

    prompt = f"""## Candidate Profile
Graduation: {profile.graduation_date}
Location: {profile.location}
Visa status: {profile.visa_status}
Skills: {profile.skills}
Projects: {profile.projects}

## Job Posting
Title: {job.title}
Location tag: {job.location}
Role query: {job.role}
Snippet:
{job.snippet}

Return the JSON analysis object."""

    try:
        client = anthropic.Anthropic(api_key=_cfg.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_ANALYZE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        return json.loads(raw)
    except Exception as exc:
        print(f"[AI] analyze_job failed for {job.id}: {exc}")
        return None


# ---------------------------------------------------------------------------
# parse_resume
# ---------------------------------------------------------------------------

_RESUME_SYSTEM = (
    "You are a resume parser. Given a resume PDF, extract the candidate's information "
    "and return ONLY a JSON object with exactly these keys: "
    "graduation_date (string, e.g. '2025-06'), "
    "location (string, current city/country), "
    "visa_status (string, e.g. 'Requires sponsorship' or 'EU citizen'), "
    "skills (comma-separated string of technical skills), "
    "projects (JSON array of {name: string, desc: string} objects, max 5). "
    "No markdown, no explanation, just the JSON object."
)


def parse_resume(pdf_bytes: bytes) -> Optional[dict]:
    """
    Parse a resume PDF and extract profile fields.

    Returns a dict with keys: graduation_date, location, visa_status,
    skills, projects. Returns None on any error.
    """
    if not _cfg.ANTHROPIC_API_KEY:
        print("[AI] ANTHROPIC_API_KEY not set — cannot parse resume.")
        return None

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    try:
        client = anthropic.Anthropic(api_key=_cfg.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_RESUME_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract the profile fields from this resume.",
                        },
                    ],
                }
            ],
        )
        raw = message.content[0].text
        return json.loads(raw)
    except Exception as exc:
        print(f"[AI] parse_resume failed: {exc}")
        return None
