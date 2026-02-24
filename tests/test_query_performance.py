"""
tests/test_query_performance.py
--------------------------------
Tests for QueryPerformance CRUD operations.
Uses an in-memory SQLite engine — no real DB needed.
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from sqlmodel import SQLModel, create_engine

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(autouse=True)
def in_memory_engine(monkeypatch):
    import src.storage as storage_mod
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(storage_mod, "_engine", engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def test_upsert_query_performance_inserts_new_row():
    from src.storage import upsert_query_performance, get_query_history
    upsert_query_performance(
        query="Junior Backend Engineer",
        source="baseline",
        run_date=date.today(),
        jobs_found=10,
        jobs_kept=8,
        avg_ai_score=0.75,
    )
    rows = get_query_history(days=1)
    assert len(rows) == 1
    assert rows[0].query == "Junior Backend Engineer"
    assert rows[0].junk_rate == pytest.approx(0.2)
    assert rows[0].is_active is True


def test_upsert_query_performance_updates_existing_row():
    from src.storage import upsert_query_performance, get_query_history
    today = date.today()
    upsert_query_performance(
        query="Junior Backend Engineer",
        source="baseline",
        run_date=today,
        jobs_found=10,
        jobs_kept=8,
        avg_ai_score=0.75,
    )
    # Second call same query + same date: should update, not insert a duplicate
    upsert_query_performance(
        query="Junior Backend Engineer",
        source="baseline",
        run_date=today,
        jobs_found=12,
        jobs_kept=10,
        avg_ai_score=0.80,
    )
    rows = get_query_history(days=1)
    assert len(rows) == 1
    assert rows[0].jobs_found == 12


def test_get_query_history_respects_days_window():
    from src.storage import upsert_query_performance, get_query_history
    today = date.today()
    old = today - timedelta(days=20)
    upsert_query_performance("query-old", "agent", old, 5, 5, 0.5)
    upsert_query_performance("query-new", "agent", today, 5, 5, 0.5)
    rows = get_query_history(days=14)
    queries = [r.query for r in rows]
    assert "query-new" in queries
    assert "query-old" not in queries


def test_get_active_agent_queries_returns_only_active():
    from src.storage import upsert_query_performance, retire_query, get_active_agent_queries
    today = date.today()
    upsert_query_performance("good-query", "agent", today, 10, 9, 0.8)
    upsert_query_performance("bad-query", "agent", today, 10, 2, 0.2)
    retire_query("bad-query")
    active = get_active_agent_queries()
    queries = [r.query for r in active]
    assert "good-query" in queries
    assert "bad-query" not in queries


def test_retire_query_sets_is_active_false():
    from src.storage import upsert_query_performance, retire_query, get_query_history
    upsert_query_performance("retiring-query", "agent", date.today(), 10, 1, 0.1)
    retire_query("retiring-query")
    rows = get_query_history(days=1)
    assert rows[0].is_active is False


def test_insert_agent_query_adds_new_active_row():
    from src.storage import insert_agent_query, get_active_agent_queries
    insert_agent_query("Junior Python Developer remote")
    active = get_active_agent_queries()
    assert any(r.query == "Junior Python Developer remote" for r in active)


def test_insert_agent_query_skips_duplicate():
    from src.storage import insert_agent_query, get_active_agent_queries
    insert_agent_query("duplicate-query")
    insert_agent_query("duplicate-query")  # second call should be a no-op
    active = get_active_agent_queries()
    matches = [r for r in active if r.query == "duplicate-query"]
    assert len(matches) == 1


def test_count_active_agent_queries():
    from src.storage import insert_agent_query, count_active_agent_queries
    insert_agent_query("query-a")
    insert_agent_query("query-b")
    assert count_active_agent_queries() == 2
