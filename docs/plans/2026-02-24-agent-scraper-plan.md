# Agentic Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `query_performance` table and an AI agent that learns from each scrape run — retiring bad queries and generating new ones — without any user feedback.

**Architecture:** New `QueryPerformance` SQLModel table stores per-query stats per run. `src/agent.py` reads 14 days of history, calls Claude to retire underperformers and generate new queries. `src/scraper.py` loads active agent queries at run start and records stats after each query.

**Tech Stack:** Python, SQLModel, Anthropic Claude (claude-haiku-4-5-20251001), Supabase/Postgres, pytest with SQLite in-memory for tests.

---

## Task 1: Add `QueryPerformance` model and CRUD to `src/storage.py`

**Files:**
- Modify: `src/storage.py`
- Test: `tests/test_query_performance.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_query_performance.py`:

```python
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
```

**Step 2: Run to verify all fail**

```bash
.venv/bin/pytest tests/test_query_performance.py -v
```

Expected: `ERROR` — `upsert_query_performance` not found.

**Step 3: Add `QueryPerformance` model and CRUD to `src/storage.py`**

Add the following to `src/storage.py`, after the `UserProfile` class and before the engine section:

```python
class QueryPerformance(SQLModel, table=True):
    """Per-query performance record for one scrape run."""

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str                              # the Exa query string
    source: str                             # 'baseline' or 'agent'
    run_date: str                           # ISO date string e.g. "2026-02-24"
    jobs_found: int = 0
    jobs_kept: int = 0
    junk_rate: Optional[float] = None       # 1 - jobs_kept/jobs_found
    avg_ai_score: Optional[float] = None
    is_active: bool = True                  # agent can retire by setting False
```

Then add these CRUD functions after the `get_profile` function:

```python
# ---------------------------------------------------------------------------
# QueryPerformance operations
# ---------------------------------------------------------------------------

from datetime import date as _date

def upsert_query_performance(
    query: str,
    source: str,
    run_date: "_date",
    jobs_found: int,
    jobs_kept: int,
    avg_ai_score: Optional[float],
) -> None:
    """
    Insert or update a QueryPerformance row for (query, run_date).
    Calculates junk_rate automatically.
    """
    run_date_str = run_date.isoformat()
    junk_rate = None
    if jobs_found > 0:
        junk_rate = 1.0 - jobs_kept / jobs_found

    with Session(_engine) as session:
        statement = select(QueryPerformance).where(
            QueryPerformance.query == query,
            QueryPerformance.run_date == run_date_str,
        )
        existing = session.exec(statement).first()
        if existing:
            existing.jobs_found = jobs_found
            existing.jobs_kept = jobs_kept
            existing.junk_rate = junk_rate
            existing.avg_ai_score = avg_ai_score
            session.add(existing)
        else:
            row = QueryPerformance(
                query=query,
                source=source,
                run_date=run_date_str,
                jobs_found=jobs_found,
                jobs_kept=jobs_kept,
                junk_rate=junk_rate,
                avg_ai_score=avg_ai_score,
            )
            session.add(row)
        session.commit()


def get_query_history(days: int = 14) -> list[QueryPerformance]:
    """Return all QueryPerformance rows from the last `days` days."""
    from datetime import timedelta, timezone
    cutoff = (_date.today() - timedelta(days=days)).isoformat()
    with Session(_engine) as session:
        statement = select(QueryPerformance).where(
            QueryPerformance.run_date >= cutoff
        )
        return list(session.exec(statement).all())


def get_active_agent_queries() -> list[QueryPerformance]:
    """
    Return one row per active agent query (most recent run_date).
    Used to load agent queries at scrape start.
    """
    with Session(_engine) as session:
        # Get distinct active agent queries (latest row per query)
        statement = select(QueryPerformance).where(
            QueryPerformance.source == "agent",
            QueryPerformance.is_active == True,  # noqa: E712
        )
        rows = list(session.exec(statement).all())
    # Deduplicate: keep only the most recent row per query string
    seen: dict[str, QueryPerformance] = {}
    for row in rows:
        if row.query not in seen or row.run_date > seen[row.query].run_date:
            seen[row.query] = row
    return list(seen.values())


def retire_query(query: str) -> None:
    """Set is_active=False for all rows with this query string."""
    with Session(_engine) as session:
        statement = select(QueryPerformance).where(
            QueryPerformance.query == query
        )
        rows = list(session.exec(statement).all())
        for row in rows:
            row.is_active = False
            session.add(row)
        session.commit()


def insert_agent_query(query: str) -> None:
    """
    Insert a new agent-generated query as a placeholder row (no stats yet).
    No-op if the query already exists and is active.
    """
    with Session(_engine) as session:
        statement = select(QueryPerformance).where(
            QueryPerformance.query == query,
            QueryPerformance.source == "agent",
            QueryPerformance.is_active == True,  # noqa: E712
        )
        existing = session.exec(statement).first()
        if existing:
            return  # duplicate — skip
        row = QueryPerformance(
            query=query,
            source="agent",
            run_date=_date.today().isoformat(),
            jobs_found=0,
            jobs_kept=0,
        )
        session.add(row)
        session.commit()


def count_active_agent_queries() -> int:
    """Return the count of currently active agent-generated queries."""
    with Session(_engine) as session:
        statement = select(QueryPerformance).where(
            QueryPerformance.source == "agent",
            QueryPerformance.is_active == True,  # noqa: E712
        )
        return len(list(session.exec(statement).all()))
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_query_performance.py -v
```

Expected: all 8 tests PASS.

**Step 5: Run full test suite to check nothing broke**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/storage.py tests/test_query_performance.py
git commit -m "feat: add QueryPerformance model and CRUD to storage"
```

---

## Task 2: Create `src/agent.py` — reflection logic

**Files:**
- Create: `src/agent.py`
- Test: `tests/test_agent_reflection.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_agent_reflection.py`:

```python
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
    from src.storage import get_active_agent_queries

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
    from src.storage import count_active_agent_queries

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
    from src.storage import get_active_agent_queries

    # No profile in DB — generation should be skipped
    mock_response = _mock_claude_response(generate=["some-query"])
    with patch("src.agent._call_claude", return_value=mock_response):
        # Even if Claude returns something, we don't call Claude at all when no profile
        with patch("src.agent.get_profile", return_value=None):
            reflect()

    # Nothing should be inserted
    assert count_active_agent_queries() == 0


def count_active_agent_queries():
    from src.storage import count_active_agent_queries as _count
    return _count()
```

**Step 2: Run to verify all fail**

```bash
.venv/bin/pytest tests/test_agent_reflection.py -v
```

Expected: `ERROR` — `src.agent` not found.

**Step 3: Create `src/agent.py`**

```python
"""
agent.py
--------
AI agent that reflects on query performance after each scrape run.

reflect() is the entry point:
  1. Load 14 days of query_performance history from the DB.
  2. Load the user profile.
  3. Call Claude to decide which agent queries to retire and what new ones to add.
  4. Apply those decisions to the DB.

If no user profile exists, query generation is skipped (retirement still runs).
If Claude fails for any reason, the error is logged and we return — the scrape
data is already saved and the next run will proceed unchanged.
"""
from __future__ import annotations

import json
import logging

import anthropic

import src.config as _cfg
from src.storage import (
    count_active_agent_queries,
    get_active_agent_queries,
    get_profile,
    get_query_history,
    insert_agent_query,
    retire_query,
)

logger = logging.getLogger(__name__)

MAX_AGENT_QUERIES = 20

_REFLECT_SYSTEM = (
    "You are a job-search query optimizer. You receive a history of search query "
    "performance and a candidate profile. You must return ONLY a JSON object with "
    "exactly two keys: "
    "'retire' (list of query strings to retire — queries that consistently perform "
    "poorly: junk_rate > 0.6 for 3+ runs, or 0 results for 3+ runs), "
    "'generate' (list of new query strings to try — max 5, targeted to the candidate "
    "profile, inspired by what has worked well). "
    "Only include agent-generated queries in 'retire' (never retire baseline queries). "
    "No markdown, no explanation, just the JSON object."
)


def _call_claude(prompt: str) -> anthropic.types.Message:
    """Call Claude and return the raw message. Separated for easy mocking in tests."""
    client = anthropic.Anthropic(api_key=_cfg.ANTHROPIC_API_KEY)
    return client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_REFLECT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )


def reflect() -> None:
    """
    Run the agent reflection cycle. Called once after each scrape run.
    Logs and returns on any error — never raises.
    """
    if not _cfg.ANTHROPIC_API_KEY:
        logger.warning("[Agent] ANTHROPIC_API_KEY not set — skipping reflection.")
        return

    history = get_query_history(days=14)
    profile = get_profile()

    # Build the prompt
    history_lines = []
    for row in history:
        history_lines.append(
            f"  query={row.query!r} source={row.source} date={row.run_date} "
            f"found={row.jobs_found} kept={row.jobs_kept} "
            f"junk_rate={row.junk_rate:.2f if row.junk_rate is not None else 'N/A'} "
            f"avg_score={row.avg_ai_score:.2f if row.avg_ai_score is not None else 'N/A'} "
            f"active={row.is_active}"
        )

    active_count = count_active_agent_queries()
    slots_available = MAX_AGENT_QUERIES - active_count

    profile_text = "No profile available — skip query generation."
    if profile:
        profile_text = (
            f"Graduation: {profile.graduation_date}\n"
            f"Location: {profile.location}\n"
            f"Visa: {profile.visa_status}\n"
            f"Skills: {profile.skills}\n"
            f"Projects: {profile.projects}"
        )

    prompt = (
        f"## Query Performance History (last 14 days)\n"
        + "\n".join(history_lines or ["  (no history yet)"])
        + f"\n\n## Candidate Profile\n{profile_text}"
        + f"\n\n## Constraints\n"
        + f"Active agent query slots available: {slots_available} of {MAX_AGENT_QUERIES}. "
        + "Do not generate more queries than slots available. "
        + "If no profile is available, return an empty 'generate' list."
    )

    try:
        message = _call_claude(prompt)
        raw = message.content[0].text
        decision = json.loads(raw)
    except Exception as exc:
        logger.warning(f"[Agent] Reflection failed: {exc}")
        return

    # Apply retirements
    for query in decision.get("retire", []):
        logger.info(f"[Agent] Retiring query: {query!r}")
        retire_query(query)

    # Apply new queries (skip if no profile, skip duplicates, respect cap)
    if profile:
        for query in decision.get("generate", []):
            if count_active_agent_queries() >= MAX_AGENT_QUERIES:
                logger.info("[Agent] Cap reached — stopping query generation.")
                break
            logger.info(f"[Agent] Adding new query: {query!r}")
            insert_agent_query(query)
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_agent_reflection.py -v
```

Expected: all 6 tests PASS.

**Step 5: Run full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/agent.py tests/test_agent_reflection.py
git commit -m "feat: add agent reflection module"
```

---

## Task 3: Update `src/scraper.py` to load agent queries and record per-query stats

**Files:**
- Modify: `src/scraper.py`
- Modify: `src/exa_client.py` (check if per-query tracking is possible)

**Context:** Currently `fetch_jobs()` in `exa_client.py` runs all queries internally and returns a flat list. We need per-query counts (jobs_found, jobs_kept, avg_ai_score) to record in `query_performance`. The simplest approach: after the scrape loop, group results by `result["role"]` and compute stats per query.

**Step 1: Update `run_scrape()` in `src/scraper.py`**

At the top of the file, add the new imports:

```python
from datetime import date as _date
from src.storage import (
    JobPosting, get_profile, is_known, save_job, update_job_analysis,
    get_active_agent_queries, upsert_query_performance,
)
```

In `run_scrape()`, before calling `fetch_jobs()`, load agent queries and pass them along:

```python
def run_scrape() -> list[JobPosting]:
    # Load active agent queries to pass to Exa
    agent_query_rows = get_active_agent_queries()
    agent_queries = [r.query for r in agent_query_rows]
    
    print("\n[Scraper] Starting fetch from Exa...")
    print(f"[Scraper] Loaded {len(agent_queries)} active agent queries.")
    raw_results = fetch_jobs(extra_queries=agent_queries)
    ...
```

After the scrape loop and before the AI analysis block, add per-query stat recording:

```python
    # --- Record per-query performance ---
    today = _date.today()
    # Determine source per query
    baseline_queries = set(ROLES)
    query_found: dict[str, int] = {}
    query_kept: dict[str, int] = {}
    for result in raw_results:
        q = result["role"]
        query_found[q] = query_found.get(q, 0) + 1
    for job in new_jobs:
        q = job.role
        query_kept[q] = query_kept.get(q, 0) + 1
    for q, found in query_found.items():
        kept = query_kept.get(q, 0)
        source = "baseline" if q in baseline_queries else "agent"
        upsert_query_performance(q, source, today, found, kept, avg_ai_score=None)
    # avg_ai_score will be updated after AI analysis runs (Task 4)
```

**Step 2: Update `src/exa_client.py` to accept `extra_queries`**

Open `src/exa_client.py` and check the signature of `fetch_jobs()`. Add an `extra_queries` parameter:

```python
def fetch_jobs(extra_queries: list[str] | None = None) -> list[dict]:
    all_queries = list(ROLES)
    if extra_queries:
        all_queries.extend(extra_queries)
    ...  # rest of function unchanged, just uses all_queries instead of ROLES
```

**Step 3: Run existing tests to verify nothing broke**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add src/scraper.py src/exa_client.py
git commit -m "feat: scraper loads agent queries and records per-query stats"
```

---

## Task 4: Update per-query avg_ai_score after AI analysis

**Files:**
- Modify: `src/scraper.py`

**Context:** After the AI analysis loop runs in `run_scrape()`, we have enough data to compute avg_ai_score per query. Update the `query_performance` rows with the scores.

**Step 1: Modify the AI analysis block in `run_scrape()`**

After the existing AI analysis loop, collect scores per query and upsert:

```python
    if new_jobs:
        profile = get_profile()
        if profile:
            print(f"[Scraper] Running AI analysis on {len(new_jobs)} new job(s)...")
            query_scores: dict[str, list[float]] = {}
            for job in new_jobs:
                analysis = analyze_job(job, profile)
                if analysis:
                    update_job_analysis(job.id, json.dumps(analysis))
                    print(f"  [AI] Analysed: {job.title[:60]}")
                    # Collect score if present
                    score = analysis.get("overall_score")
                    if isinstance(score, (int, float)):
                        query_scores.setdefault(job.role, []).append(float(score))
            # Update avg_ai_score for each query that got scores
            for q, scores in query_scores.items():
                avg = sum(scores) / len(scores)
                source = "baseline" if q in baseline_queries else "agent"
                found = query_found.get(q, 0)
                kept = query_kept.get(q, 0)
                upsert_query_performance(q, source, today, found, kept, avg_ai_score=avg)
        else:
            print("[Scraper] No user profile found — skipping AI analysis.")
```

Note: `overall_score` may not be in the current AI analysis schema. Check `ai_analysis.py` — if it's absent, skip this step and just leave `avg_ai_score=None` for now. This is a best-effort field.

**Step 2: Run full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 3: Commit**

```bash
git add src/scraper.py
git commit -m "feat: update avg_ai_score in query_performance after analysis"
```

---

## Task 5: Wire agent reflection into `run_scrape()`

**Files:**
- Modify: `src/scraper.py`

**Step 1: Add import and call to `reflect()`**

At the top of `src/scraper.py`, add:

```python
from src.agent import reflect
```

At the very end of `run_scrape()`, after the AI analysis block and before the `return`:

```python
    # --- Agent reflection: evaluate query performance, retire bad queries, generate new ones ---
    print("[Scraper] Running agent reflection...")
    reflect()
    print("[Scraper] Agent reflection complete.")

    return new_jobs
```

**Step 2: Run full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 3: Manual smoke test (optional, requires real API keys)**

```bash
DATABASE_URL=sqlite:///./test_local.db .venv/bin/python -c "
from src.storage import init_db
init_db()
from src.agent import reflect
reflect()
print('Reflection complete')
"
```

Expected: runs without error, prints `[Agent] ANTHROPIC_API_KEY not set` if key absent, or reflection log lines if key present.

**Step 4: Commit**

```bash
git add src/scraper.py
git commit -m "feat: wire agent reflection into scrape run"
```

---

## Task 6: Add `overall_score` to AI analysis output (if not already present)

**Files:**
- Modify: `src/ai_analysis.py`
- Test: `tests/test_ai_analysis.py`

**Context:** The `avg_ai_score` field in `query_performance` requires a numeric score per job. Currently `analyze_job()` returns `disqualifiers`, `caution`, `matched_projects`, `key_requirements`. Add `overall_score` (0.0–1.0) to the schema.

**Step 1: Check existing test expectations in `tests/test_ai_analysis.py`**

Read the file before modifying to understand what's already tested.

**Step 2: Update `_ANALYZE_SYSTEM` prompt in `src/ai_analysis.py`**

Add `overall_score` to the required JSON schema description:

```python
_ANALYZE_SYSTEM = (
    "You are a job-hunt assistant. Given a job posting and a candidate profile, "
    "return ONLY a JSON object with exactly these keys: "
    "disqualifiers (hard blockers), caution (soft concerns), "
    "matched_projects (candidate's relevant projects), "
    "key_requirements (3-5 bullet points of what the role needs), "
    "overall_score (float 0.0–1.0, how well this job matches the candidate). "
    "No markdown, no explanation, just the JSON object."
)
```

**Step 3: Update the schema doc dict** (for reference only, not used at runtime):

```python
_ANALYSIS_SCHEMA = {
    "disqualifiers": "list[str] — hard blockers",
    "caution": "list[str] — soft concerns",
    "matched_projects": "list[str] — names of the user's projects relevant to this role",
    "key_requirements": "list[str] — 3-5 bullet points of what this role needs",
    "overall_score": "float 0.0–1.0 — overall match quality",
}
```

**Step 4: Add a test for `overall_score` in `tests/test_ai_analysis.py`**

Find the existing mock test for `analyze_job` and add an assertion:

```python
assert "overall_score" in result
assert 0.0 <= result["overall_score"] <= 1.0
```

**Step 5: Run full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/ai_analysis.py tests/test_ai_analysis.py
git commit -m "feat: add overall_score to AI analysis output"
```

---

## Task 7: Run full test suite and verify

```bash
.venv/bin/pytest -v
```

Expected: all tests PASS (existing + new).

If any fail, fix them before proceeding.

---

## Task 8: Push and verify CI

```bash
git push
```

Check GitHub Actions: the `scrape.yml` workflow should still pass. The new code paths (reflection) only run when `ANTHROPIC_API_KEY` is set, so CI won't break if the key is absent in the test environment.
