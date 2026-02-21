"""
scraper.py
----------
Orchestrates one full scrape cycle:

1. Fetch raw results from Exa (exa_client).
2. Filter out excluded keywords (seniority, India locations).
3. Detect visa sponsorship and remote signals.
4. Tag each result with its discipline (Backend, Frontend, etc.).
5. Deduplicate against the database (storage.is_known).
6. Persist new postings (storage.save_job).
7. Return the list of NEW postings found this run.
"""

from __future__ import annotations

from typing import Any

from src.config import (
    EXCLUDE_DOMAINS,
    EXCLUDE_KEYWORDS,
    EXCLUDE_TITLE_PATTERNS,
    QUERY_TO_DISCIPLINE,
    REMOTE_KEYWORDS,
    VISA_KEYWORDS,
)
from src.exa_client import fetch_jobs
from src.storage import JobPosting, is_known, save_job


def _is_excluded(result: dict[str, Any]) -> bool:
    """
    Return True if the result should be dropped.
    Checks title + snippet against EXCLUDE_KEYWORDS (case-insensitive).
    """
    haystack = f"{result.get('title', '')} {result.get('text', '')}".lower()
    return any(kw.lower() in haystack for kw in EXCLUDE_KEYWORDS)


def _is_junk(result: dict[str, Any]) -> bool:
    """
    Return True if the result is an aggregator/listing page rather than
    an actual individual job posting.

    Two checks:
      1. URL contains a known aggregator domain/path pattern.
      2. Title matches a known listing/article pattern.
    """
    url   = result.get("url", "").lower()
    title = result.get("title", "").lower()

    if any(domain.lower() in url for domain in EXCLUDE_DOMAINS):
        return True

    if any(pat.lower() in title for pat in EXCLUDE_TITLE_PATTERNS):
        return True

    return False


def _detect_visa(result: dict[str, Any]) -> bool:
    """
    Return True if the job text or location tag indicates visa sponsorship.
    Also triggers when the search location was 'visa sponsorship'.
    """
    if "visa" in result.get("location_searched", "").lower():
        return True
    haystack = f"{result.get('title', '')} {result.get('text', '')}".lower()
    return any(kw.lower() in haystack for kw in VISA_KEYWORDS)


def _detect_remote(result: dict[str, Any]) -> bool:
    """
    Return True if the job is remote-friendly.
    Triggers when the search location was 'remote' or remote keywords appear
    in the title / snippet.
    """
    if result.get("location_searched", "").lower() == "remote":
        return True
    haystack = f"{result.get('title', '')} {result.get('text', '')}".lower()
    return any(kw.lower() in haystack for kw in REMOTE_KEYWORDS)


def run_scrape() -> list[JobPosting]:
    """
    Execute one full scrape cycle and return only the NEW postings
    that were inserted into the database during this run.
    """
    print("\n[Scraper] Starting fetch from Exa...")
    raw_results = fetch_jobs()
    print(f"[Scraper] Exa returned {len(raw_results)} raw results.")

    new_jobs: list[JobPosting] = []
    skipped_excluded = 0
    skipped_junk = 0
    skipped_duplicate = 0

    for result in raw_results:
        # --- Step 1: Drop aggregator / listing pages ---
        if _is_junk(result):
            skipped_junk += 1
            print(f"  [JUNK] {result.get('title', '')[:80]}")
            continue

        # --- Step 2: Drop unwanted seniority / location results ---
        if _is_excluded(result):
            skipped_excluded += 1
            continue

        # --- Step 3: Deduplicate by Exa ID (URL-based) ---
        if is_known(result["id"]):
            skipped_duplicate += 1
            continue

        # --- Step 3: Enrich with derived fields ---
        discipline = QUERY_TO_DISCIPLINE.get(result["role"], "")
        visa_sponsored = _detect_visa(result)
        remote_ok = _detect_remote(result)

        # --- Step 4: Build model and persist ---
        job = JobPosting(
            id=result["id"],
            url=result["url"],
            title=result["title"],
            published=result.get("published"),
            author=result.get("author"),
            snippet=result.get("text", ""),
            role=result["role"],
            discipline=discipline,
            location=result["location_searched"],
            visa_sponsored=visa_sponsored,
            remote_ok=remote_ok,
        )
        save_job(job)
        new_jobs.append(job)

    print(
        f"[Scraper] Done. "
        f"New: {len(new_jobs)} | "
        f"Junk skipped: {skipped_junk} | "
        f"Excluded by keyword: {skipped_excluded} | "
        f"Duplicates skipped: {skipped_duplicate}"
    )

    return new_jobs
