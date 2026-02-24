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
    if not _cfg.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
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
    history = get_query_history(days=14)
    profile = get_profile()

    # Build the prompt
    history_lines = []
    for row in history:
        junk_rate = f"{row.junk_rate:.2f}" if row.junk_rate is not None else "N/A"
        avg_score = f"{row.avg_ai_score:.2f}" if row.avg_ai_score is not None else "N/A"
        history_lines.append(
            f"  query={row.query!r} source={row.source} date={row.run_date} "
            f"found={row.jobs_found} kept={row.jobs_kept} "
            f"junk_rate={junk_rate} "
            f"avg_score={avg_score} "
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
        block = message.content[0]
        raw = block.text  # type: ignore[union-attr]
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
