# Agentic Scraper Design

**Date:** 2026-02-24

## Overview

Extend the job scraper with an AI agent that autonomously improves its search queries over time. The agent learns from each run's results — retiring underperforming queries and generating new ones — without requiring any user feedback.

The approach is hybrid: hardcoded baseline queries in `config.py` always run, and the agent adds supplementary queries on top.

---

## Data Model

New table: `query_performance`

| Column | Type | Notes |
|--------|------|-------|
| `id` | serial PK | |
| `query` | text | The query string |
| `source` | text | `'baseline'` or `'agent'` |
| `run_date` | date | Date of the scrape run |
| `jobs_found` | int | Raw count from Exa |
| `jobs_kept` | int | After junk filtering |
| `junk_rate` | float | `1 - jobs_kept / jobs_found` |
| `avg_ai_score` | float | Avg `overall_score` of kept jobs, null if none |
| `is_active` | bool | Agent can set false to retire a query |

Baseline queries always run regardless of `is_active`. Only agent-generated queries (`source = 'agent'`) can be retired.

---

## Agent Workflow

Each scrape run proceeds in this order:

### 1. Load queries
- Baseline queries from `config.py` (always included)
- Active agent-generated queries: `SELECT * FROM query_performance WHERE source = 'agent' AND is_active = true`

### 2. Run scrape
- Execute all queries against Exa as today
- Track per-query: `jobs_found`, `jobs_kept`, `avg_ai_score`

### 3. Persist performance
- Upsert a row into `query_performance` for each query executed today

### 4. Agent reflection
- Claude reads the last 14 days of `query_performance` history
- Claude reads the user's resume/profile from the DB
- Claude is prompted to:
  - Retire underperforming agent queries (`is_active = false`) — e.g. junk rate > 60% for 3+ consecutive runs
  - Generate up to 5 new supplementary queries based on what's working + user profile
  - Insert new queries with `source = 'agent'`, `is_active = true`

### 5. Done
Next run automatically picks up the newly active queries.

Agent reflection runs inside the same GitHub Actions cron job, after the scrape completes. No separate workflow needed.

---

## Error Handling & Guardrails

| Failure | Behaviour |
|---------|-----------|
| Claude API error during reflection | Log warning, do not fail the job. Existing queries unchanged. |
| Agent generates a duplicate query | Check for existing query string before insert; skip duplicates. |
| Too many agent queries accumulate | Hard cap of 20 active agent queries. Claude is told this in its prompt and must retire before adding. |
| Exa returns 0 results for 3+ consecutive runs | Auto-retire query without Claude. |
| No user profile in DB | Skip query generation; retirement still runs normally. |

---

## Module Structure

| File | Responsibility |
|------|---------------|
| `src/agent.py` | Agent reflection logic: load history, call Claude, retire/insert queries |
| `src/storage.py` | New CRUD functions for `query_performance` table |
| `src/scraper.py` | Updated to load agent queries and record per-query stats |

---

## Testing Strategy

**Unit tests (mocked):**
- `tests/test_query_performance.py` — CRUD on the new table (insert, upsert, fetch last N days, retire)
- `tests/test_agent_reflection.py` — mock Claude, verify: bad queries retired, new queries inserted, duplicate detection, cap enforcement

**Integration test (optional, requires `TEST_DB` env var):**
- Full reflection cycle against real DB with fixture data

**Existing tests unchanged:**
- `tests/test_storage.py` and `tests/test_ai_analysis.py` continue to pass
