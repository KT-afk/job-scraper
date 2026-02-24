"""
tests/test_ai_analysis.py
-------------------------
Tests for analyze_job() and parse_resume(). Uses mocks to avoid hitting
the real Anthropic API.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# analyze_job()
# ---------------------------------------------------------------------------

def _make_job():
    from src.storage import JobPosting
    return JobPosting(
        id="job-test-1",
        url="https://example.com/job",
        title="Junior Backend Engineer",
        role="Junior Backend Engineer",
        location="Singapore",
        snippet="We are looking for a Python developer with Kubernetes experience.",
    )


def _make_profile():
    from src.storage import UserProfile
    return UserProfile(
        id=1,
        graduation_date="2025-06",
        location="Singapore",
        visa_status="Requires sponsorship",
        skills="Python, Go, Kubernetes",
        projects=json.dumps([{"name": "JobScraper", "desc": "AI job hunting tool"}]),
    )


GOOD_ANALYSIS = {
    "disqualifiers": [],
    "caution": ["contract role"],
    "matched_projects": ["JobScraper"],
    "key_requirements": ["Python", "Kubernetes", "3+ years (borderline)"],
    "overall_score": 0.75,
}


def _mock_anthropic_response(content: str):
    """Build a mock Anthropic message response."""
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.text = content
    mock_msg.content = [mock_block]
    return mock_msg


def test_analyze_job_returns_dict_with_all_keys(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import analyze_job

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = _mock_anthropic_response(
            json.dumps(GOOD_ANALYSIS)
        )

        result = analyze_job(_make_job(), _make_profile())

    assert result is not None
    assert "disqualifiers" in result
    assert "caution" in result
    assert "matched_projects" in result
    assert "key_requirements" in result
    assert "overall_score" in result
    assert isinstance(result["overall_score"], float)


def test_analyze_job_returns_none_on_api_exception(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import analyze_job

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = Exception("API error")

        result = analyze_job(_make_job(), _make_profile())

    assert result is None


def test_analyze_job_returns_none_on_malformed_json(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import analyze_job

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = _mock_anthropic_response("not valid json {{{")

        result = analyze_job(_make_job(), _make_profile())

    assert result is None


def test_analyze_job_returns_none_when_api_key_missing(monkeypatch):
    from src.ai_analysis import analyze_job
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "")

    result = analyze_job(_make_job(), _make_profile())
    assert result is None


# ---------------------------------------------------------------------------
# parse_resume()
# ---------------------------------------------------------------------------

GOOD_RESUME_RESULT = {
    "graduation_date": "2025-06",
    "location": "Singapore",
    "visa_status": "Requires sponsorship",
    "skills": "Python, Go",
    "projects": [{"name": "JobScraper", "desc": "AI job hunting"}],
}


def test_parse_resume_returns_dict_with_all_keys(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import parse_resume

    fake_pdf = b"%PDF-1.4 fake pdf bytes"

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = _mock_anthropic_response(
            json.dumps(GOOD_RESUME_RESULT)
        )

        result = parse_resume(fake_pdf)

    assert result is not None
    assert "graduation_date" in result
    assert "location" in result
    assert "visa_status" in result
    assert "skills" in result
    assert "projects" in result


def test_parse_resume_returns_none_on_api_exception(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import parse_resume

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = Exception("timeout")

        result = parse_resume(b"fake pdf")

    assert result is None


def test_parse_resume_returns_none_on_malformed_json(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test-key")
    from src.ai_analysis import parse_resume

    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = _mock_anthropic_response("garbage output")

        result = parse_resume(b"fake pdf")

    assert result is None
