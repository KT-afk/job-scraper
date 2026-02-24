"""
exa_client.py
-------------
Thin wrapper around the Exa Python SDK (v1.1.7).

Responsibilities:
- Build search queries from (role, location) pairs.
- Call Exa search_and_contents() with date filters.
- Return raw result dicts for the scraper to process.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from exa_py import Exa  # type: ignore[import-untyped]

from src.config import (
    CRAWL_DAYS_BACK,
    EXA_API_KEY,
    LOCATIONS,
    RESULTS_PER_QUERY,
    ROLES,
    SEARCH_TYPE,
    SNIPPET_MAX_CHARS,
)


def _build_query(role: str, location: str) -> str:
    """
    Compose a natural-language query for Exa.

    Example output:
        "Junior Backend Engineer jobs in Singapore posted recently"
    """
    loc_phrase = f"in {location}" if location.lower() not in ("remote",) else "remote"
    return f"{role} jobs {loc_phrase} posted recently"


def _cutoff_date() -> str:
    """Return an ISO-8601 datetime string N days in the past (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=CRAWL_DAYS_BACK)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_jobs(extra_queries: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Run all (role, location) combinations through Exa and return
    a flat list of raw result dicts.

    Each dict contains:
        id                - Exa's unique URL-based ID
        url               - job posting URL
        title             - page title
        published         - publication date string (may be None)
        author            - site/author name (may be None)
        text              - text snippet from the page
        role              - raw query string used (added by us)
        location_searched - location term used (added by us)

    Args:
        extra_queries: Optional list of additional query strings to search
                       (e.g. agent-generated queries). Run in addition to ROLES.
    """
    if not EXA_API_KEY:
        raise EnvironmentError(
            "EXA_API_KEY is not set. Add it to your .env file."
        )

    client = Exa(api_key=EXA_API_KEY)
    cutoff = _cutoff_date()
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    all_roles = list(ROLES) + (extra_queries or [])

    for role in all_roles:
        for location in LOCATIONS:
            query = _build_query(role, location)

            print(f"  Querying Exa: {query!r}")

            try:
                # v1.1.7: use search_and_contents(); text= is a flat kwarg.
                response = client.search_and_contents(
                    query,
                    type=SEARCH_TYPE,
                    num_results=RESULTS_PER_QUERY,
                    start_crawl_date=cutoff,
                    text={"max_characters": SNIPPET_MAX_CHARS},
                    use_autoprompt=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [WARNING] Exa query failed for ({role!r}, {location!r}): {exc}")
                continue

            for result in response.results:
                # Deduplicate within this fetch run (same URL may appear
                # in multiple queries).
                if result.id in seen_ids:
                    continue
                seen_ids.add(result.id)

                results.append(
                    {
                        "id": result.id,
                        "url": result.url,
                        "title": result.title or "",
                        "published": getattr(result, "published_date", None),
                        "author": getattr(result, "author", None),
                        "text": (getattr(result, "text", None) or "")[:SNIPPET_MAX_CHARS],
                        "role": role,
                        "location_searched": location,
                    }
                )

    return results
