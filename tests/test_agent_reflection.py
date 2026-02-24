"""
tests/test_agent_reflection.py
-------------------------------
Tests for the agent reflection logic in src/agent.py.
Claude calls are fully mocked — no real API calls.
"""
from __future__ import annotations

import json
import pytest
from datetime import date, timedelta
from sqlmodel import SQLModel, create_engine
from unittest.mock import patch, MagicMock

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(autouse=True)
def in_memory_engine(monkeypatch):
    import src.storage as storage_mod
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(storage_mod, "_engine", engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def _seed_query(query, source="agent", days_ago=0, junk_rate=0.1, avg_score=0.8, is_active=True):
    """Helper: insert a QueryPerformance row."""
    from src.storage import upsert_query_performance, retire_query
    run_date = date.today() - timedelta(days=days_ago)
    upsert_query_performance(query, source, run_date, 10, int(10 * (1 - junk_rate)), avg_score)
    if not is_active:
        retire_query(query)


def _mock_claude_response(retire=None, generate=None):
    """Return a mock Anthropic message with a JSON payload."""
    retire = retire or []
    generate = generate or []
    payload = json.dumps({"retire": retire, "generate": generate})
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=payload)]
    return mock_msg


def test_reflect_retires_bad_queries():
    from src.agent import reflect
    from src.storage import get_active_agent_queries

    _seed_query("bad-query", junk_rate=0.9)

    mock_response = _mock_claude_response(retire=["bad-query"], generate=[])
    with patch("src.agent._call_claude", return_value=mock_response):
        reflect()

    active = [r.query for r in get_active_agent_queries()]
    assert "bad-query" not in active


def test_reflect_inserts_new_queries():
    from src.agent import reflect
    from src.storage import get_active_agent_queries, save_profile, UserProfile

    # Seed a profile so reflect() enters the generate block
    save_profile(UserProfile(id=1, graduation_date="2025-06", location="Singapore",
                             visa_status="Requires sponsorship", skills="Python, Go", projects="[]"))

    mock_response = _mock_claude_response(generate=["Junior Python Developer remote"])
    with patch("src.agent._call_claude", return_value=mock_response):
        reflect()

    active = [r.query for r in get_active_agent_queries()]
    assert "Junior Python Developer remote" in active


def test_reflect_skips_duplicate_queries():
    from src.agent import reflect
    from src.storage import get_active_agent_queries, count_active_agent_queries

    _seed_query("existing-query")

    mock_response = _mock_claude_response(generate=["existing-query"])
    with patch("src.agent._call_claude", return_value=mock_response):
        reflect()

    # Should still only be one row for this query
    active = [r for r in get_active_agent_queries() if r.query == "existing-query"]
    assert len(active) == 1


def test_reflect_enforces_max_cap():
    from src.agent import reflect, MAX_AGENT_QUERIES
    from src.storage import count_active_agent_queries, save_profile, UserProfile

    # Seed a profile so reflect() enters the generate block
    save_profile(UserProfile(id=1, graduation_date="2025-06", location="Singapore",
                             visa_status="Requires sponsorship", skills="Python, Go", projects="[]"))

    # Fill up to the cap
    for i in range(MAX_AGENT_QUERIES):
        _seed_query(f"query-{i}")

    # Agent tries to add 3 more
    mock_response = _mock_claude_response(generate=["new-a", "new-b", "new-c"])
    with patch("src.agent._call_claude", return_value=mock_response):
        reflect()

    # Should not exceed cap
    assert count_active_agent_queries() <= MAX_AGENT_QUERIES


def test_reflect_returns_gracefully_on_claude_error():
    from src.agent import reflect

    with patch("src.agent._call_claude", side_effect=Exception("API down")):
        # Should not raise — just log and return
        reflect()


def test_reflect_skips_generation_with_no_profile():
    from src.agent import reflect
    from src.storage import get_active_agent_queries, count_active_agent_queries

    # No profile in DB — generation should be skipped
    mock_response = _mock_claude_response(generate=["some-query"])
    with patch("src.agent._call_claude", return_value=mock_response):
        # Even if Claude returns generate entries, nothing is inserted when there is no profile
        with patch("src.agent.get_profile", return_value=None):
            reflect()

    # Nothing should be inserted
    assert count_active_agent_queries() == 0
