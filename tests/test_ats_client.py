"""
tests/test_ats_client.py
------------------------
Unit tests for ats_client helpers and fetchers (using mocked httpx).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.ats_client import (
    _is_junior,
    _strip_html,
    _infer_location,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_ashby_jobs,
    fetch_all_ats_jobs,
)


# ---------------------------------------------------------------------------
# _is_junior
# ---------------------------------------------------------------------------

def test_is_junior_matches_junior():
    assert _is_junior("Junior Backend Engineer") is True

def test_is_junior_matches_entry_level():
    assert _is_junior("Entry Level Software Engineer") is True

def test_is_junior_matches_graduate():
    assert _is_junior("Graduate Software Engineer") is True

def test_is_junior_matches_new_grad():
    assert _is_junior("New Grad SWE") is True

def test_is_junior_rejects_senior():
    assert _is_junior("Senior Backend Engineer") is False

def test_is_junior_rejects_staff():
    assert _is_junior("Staff Engineer") is False

def test_is_junior_case_insensitive():
    assert _is_junior("JUNIOR FRONTEND DEVELOPER") is True


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------

def test_strip_html_removes_tags():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

def test_strip_html_collapses_whitespace():
    assert _strip_html("<p>  Hello   </p>") == "Hello"

def test_strip_html_plain_text_passthrough():
    assert _strip_html("no html here") == "no html here"


# ---------------------------------------------------------------------------
# _infer_location
# ---------------------------------------------------------------------------

def test_infer_location_singapore():
    assert _infer_location("Singapore") == "Singapore"

def test_infer_location_remote_flag():
    assert _infer_location("", is_remote=True) == "remote"

def test_infer_location_remote_keyword():
    assert _infer_location("Remote - Worldwide") == "remote"

def test_infer_location_unknown_defaults_remote():
    assert _infer_location("New York, NY") == "remote"


# ---------------------------------------------------------------------------
# fetch_greenhouse_jobs (mocked)
# ---------------------------------------------------------------------------

def _make_greenhouse_response(jobs: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"jobs": jobs}
    return mock_resp


def test_greenhouse_returns_junior_jobs(monkeypatch):
    jobs_payload = [
        {
            "title": "Junior Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/123",
            "updated_at": "2026-01-15T10:00:00.000Z",
            "location": {"name": "Singapore"},
            "content": "<p>We are looking for a junior engineer.</p>",
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _make_greenhouse_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_greenhouse_jobs(companies=["testco"])

    assert len(results) == 1
    assert results[0]["title"] == "Junior Backend Engineer"
    assert results[0]["location_searched"] == "Singapore"
    assert results[0]["published"] == "2026-01-15"
    assert results[0]["source"] == "greenhouse"


def test_greenhouse_skips_senior_jobs(monkeypatch):
    jobs_payload = [
        {
            "title": "Senior Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/999",
            "updated_at": "2026-01-15T10:00:00.000Z",
            "location": {"name": "Singapore"},
            "content": "",
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _make_greenhouse_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_greenhouse_jobs(companies=["testco"])

    assert results == []


def test_greenhouse_skips_non_200(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_greenhouse_jobs(companies=["notacompany"])

    assert results == []


# ---------------------------------------------------------------------------
# fetch_lever_jobs (mocked)
# ---------------------------------------------------------------------------

def _make_lever_response(jobs: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = jobs
    return mock_resp


def test_lever_returns_junior_jobs(monkeypatch):
    jobs_payload = [
        {
            "text": "Entry Level Frontend Engineer",
            "hostedUrl": "https://jobs.lever.co/testco/abc-123",
            "createdAt": 1737000000000,  # ms epoch
            "descriptionPlain": "Join our team as an entry level engineer.",
            "categories": {"location": "Remote"},
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _make_lever_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_lever_jobs(companies=["testco"])

    assert len(results) == 1
    assert results[0]["title"] == "Entry Level Frontend Engineer"
    assert results[0]["location_searched"] == "remote"
    assert results[0]["source"] == "lever"


def test_lever_skips_senior_jobs(monkeypatch):
    jobs_payload = [
        {
            "text": "Staff Engineer",
            "hostedUrl": "https://jobs.lever.co/testco/xyz",
            "createdAt": 1737000000000,
            "descriptionPlain": "",
            "categories": {},
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _make_lever_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_lever_jobs(companies=["testco"])

    assert results == []


# ---------------------------------------------------------------------------
# fetch_ashby_jobs (mocked)
# ---------------------------------------------------------------------------

def _make_ashby_response(job_postings: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"jobPostings": job_postings}
    return mock_resp


def test_ashby_returns_junior_jobs(monkeypatch):
    jobs_payload = [
        {
            "title": "Graduate Software Engineer",
            "jobUrl": "https://jobs.ashbyhq.com/linear/some-uuid",
            "publishedDate": "2026-02-01",
            "locationName": "Singapore",
            "isRemote": False,
            "descriptionHtml": "<p>We are hiring a graduate engineer.</p>",
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = _make_ashby_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_ashby_jobs(companies=["linear"])

    assert len(results) == 1
    assert results[0]["title"] == "Graduate Software Engineer"
    assert results[0]["location_searched"] == "Singapore"
    assert results[0]["published"] == "2026-02-01"
    assert results[0]["source"] == "ashby"


def test_ashby_remote_flag_sets_remote(monkeypatch):
    jobs_payload = [
        {
            "title": "Junior DevOps Engineer",
            "jobUrl": "https://jobs.ashbyhq.com/vercel/dev-uuid",
            "publishedDate": "2026-02-10",
            "locationName": "US",
            "isRemote": True,
            "descriptionHtml": "",
        }
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = _make_ashby_response(jobs_payload)

    with patch("src.ats_client.httpx.Client", return_value=mock_client):
        results = fetch_ashby_jobs(companies=["vercel"])

    assert results[0]["location_searched"] == "remote"


# ---------------------------------------------------------------------------
# fetch_all_ats_jobs — deduplication
# ---------------------------------------------------------------------------

def test_fetch_all_deduplicates(monkeypatch):
    """Same URL from two sources should appear only once."""
    shared_url = "https://boards.greenhouse.io/co/jobs/1"
    greenhouse_job = {
        "id": shared_url, "url": shared_url, "title": "Junior Engineer",
        "published": None, "author": "co", "text": "", "role": "junior",
        "location_searched": "remote", "source": "greenhouse",
    }
    lever_job = {**greenhouse_job, "source": "lever"}

    with patch("src.ats_client.fetch_greenhouse_jobs", return_value=[greenhouse_job]):
        with patch("src.ats_client.fetch_lever_jobs", return_value=[lever_job]):
            with patch("src.ats_client.fetch_ashby_jobs", return_value=[]):
                results = fetch_all_ats_jobs()

    assert len(results) == 1
