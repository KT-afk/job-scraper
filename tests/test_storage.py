"""
tests/test_storage.py
---------------------
Tests for UserProfile, save_profile, get_profile, update_job_analysis,
update_job_tracking. Uses an in-memory SQLite engine to avoid needing a
real Supabase connection.
"""

from __future__ import annotations

import json
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from unittest.mock import patch

# Patch the engine before importing storage functions
TEST_DATABASE_URL = "sqlite://"  # in-memory SQLite


@pytest.fixture(autouse=True)
def in_memory_engine(monkeypatch):
    """Replace the module-level _engine with an in-memory SQLite engine."""
    import src.storage as storage_mod

    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(storage_mod, "_engine", engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------

def test_get_profile_returns_none_when_no_profile_exists():
    from src.storage import get_profile
    assert get_profile() is None


def test_save_and_get_profile_roundtrip():
    from src.storage import UserProfile, save_profile, get_profile

    profile = UserProfile(
        id=1,
        graduation_date="2025-06",
        location="Singapore",
        visa_status="Requires sponsorship",
        skills="Python, Go, Kubernetes",
        projects=json.dumps([{"name": "JobScraper", "desc": "AI job hunting tool"}]),
    )
    save_profile(profile)

    result = get_profile()
    assert result is not None
    assert result.graduation_date == "2025-06"
    assert result.location == "Singapore"
    assert result.visa_status == "Requires sponsorship"
    assert result.skills == "Python, Go, Kubernetes"


def test_save_profile_overwrites_existing():
    from src.storage import UserProfile, save_profile, get_profile

    save_profile(UserProfile(id=1, graduation_date="2024-12", location="London",
                             visa_status="EU citizen", skills="Java", projects="[]"))
    save_profile(UserProfile(id=1, graduation_date="2025-06", location="Singapore",
                             visa_status="Requires sponsorship", skills="Python", projects="[]"))

    result = get_profile()
    assert result is not None
    assert result.location == "Singapore"
    assert result.graduation_date == "2025-06"


# ---------------------------------------------------------------------------
# update_job_analysis
# ---------------------------------------------------------------------------

def _make_job(job_id: str = "test-job-1"):
    from src.storage import JobPosting, save_job
    job = JobPosting(
        id=job_id,
        url=f"https://example.com/{job_id}",
        title="Junior Backend Engineer",
        role="Junior Backend Engineer",
        location="Singapore",
    )
    save_job(job)
    return job


def test_update_job_analysis_persists():
    from src.storage import update_job_analysis, _engine
    _make_job("job-ai-1")

    analysis = {"disqualifiers": [], "caution": ["contract role"], "matched_projects": [], "key_requirements": ["Python"]}
    update_job_analysis("job-ai-1", json.dumps(analysis))

    from src.storage import JobPosting
    with Session(_engine) as session:
        job = session.get(JobPosting, "job-ai-1")
        assert job is not None
        assert job.ai_analysis is not None
        stored = json.loads(job.ai_analysis)
        assert stored["caution"] == ["contract role"]


def test_update_job_analysis_unknown_id_no_crash():
    from src.storage import update_job_analysis
    # Should not raise even if job doesn't exist
    update_job_analysis("nonexistent-id", "{}")


# ---------------------------------------------------------------------------
# update_job_tracking
# ---------------------------------------------------------------------------

def test_update_job_tracking_status_persists():
    from src.storage import update_job_tracking, _engine, JobPosting
    _make_job("job-track-1")

    result = update_job_tracking("job-track-1", status="applied")
    assert result is True

    with Session(_engine) as session:
        job = session.get(JobPosting, "job-track-1")
        assert job is not None
        assert job.status == "applied"


def test_update_job_tracking_notes_persists():
    from src.storage import update_job_tracking, _engine, JobPosting
    _make_job("job-track-2")

    update_job_tracking("job-track-2", notes="Follow up next week")

    with Session(_engine) as session:
        job = session.get(JobPosting, "job-track-2")
        assert job is not None
        assert job.notes == "Follow up next week"


def test_update_job_tracking_unknown_id_returns_false():
    from src.storage import update_job_tracking
    result = update_job_tracking("does-not-exist", status="applied")
    assert result is False


def test_new_job_has_default_status_none():
    from src.storage import _engine, JobPosting
    _make_job("job-default-status")

    with Session(_engine) as session:
        job = session.get(JobPosting, "job-default-status")
        assert job is not None
        assert job.status == "none"
