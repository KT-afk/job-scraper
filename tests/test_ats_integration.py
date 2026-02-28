"""
tests/test_ats_integration.py
------------------------------
Integration tests: ATS results flow through the full scraper filter pipeline.
"""
from unittest.mock import patch, MagicMock
import pytest


def _ats_job(title, url, location="remote", text=""):
    return {
        "id": url,
        "url": url,
        "title": title,
        "published": "2026-02-20",
        "author": "testco",
        "text": text,
        "role": "junior",
        "location_searched": location,
        "source": "greenhouse",
    }


def test_senior_ats_job_excluded_by_pipeline():
    """A senior-titled ATS job should be dropped by _is_excluded."""
    from src.scraper import _is_excluded
    result = _ats_job("Senior Backend Engineer", "https://jobs.greenhouse.io/co/999")
    assert _is_excluded(result) is True


def test_junior_ats_job_not_excluded():
    """A junior-titled ATS job with no seniority keywords should pass."""
    from src.scraper import _is_excluded
    result = _ats_job(
        "Junior Backend Engineer",
        "https://jobs.greenhouse.io/co/123",
        text="0-2 years of experience. Python, Django.",
    )
    assert _is_excluded(result) is False


def test_ats_job_with_experience_over_limit_excluded():
    """ATS job requiring 5+ years should be dropped by experience filter."""
    from src.scraper import _is_excluded
    result = _ats_job(
        "Junior Software Engineer",
        "https://jobs.greenhouse.io/co/456",
        text="Requires at least 5 years of professional experience.",
    )
    assert _is_excluded(result) is True


def test_ats_job_india_location_excluded():
    """ATS job with India location signal in text should be dropped."""
    from src.scraper import _is_excluded
    result = _ats_job(
        "Junior Developer",
        "https://jobs.greenhouse.io/co/789",
        text="Position based in Bangalore, India.",
    )
    assert _is_excluded(result) is True


def test_ats_job_closed_signal_is_junk():
    """ATS job snippet containing closed signal should be junk."""
    from src.scraper import _is_junk
    result = _ats_job(
        "Junior Engineer",
        "https://jobs.greenhouse.io/co/000",
        text="This job is no longer accepting applicants.",
    )
    assert _is_junk(result) is True
