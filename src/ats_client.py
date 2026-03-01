"""
ats_client.py
-------------
Fetches jobs directly from Greenhouse, Lever, and Ashby ATS public APIs.

Each fetcher returns normalized result dicts in the same format as exa_client:
    id                - unique string (job posting URL)
    url               - job posting URL
    title             - job title
    published         - ISO date string or None
    author            - company name/slug
    text              - plain-text description snippet (≤ SNIPPET_MAX_CHARS chars)
    role              - matched junior signal phrase (e.g. "junior", "graduate")
    location_searched - "Singapore", "remote", or "visa sponsorship"

Only jobs whose title contains an ATS_JUNIOR_SIGNALS substring are returned.
All other filtering (seniority, location exclude, junk) is done by scraper.py.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config import (
    ASHBY_COMPANIES,
    ATS_JUNIOR_SIGNALS,
    GREENHOUSE_COMPANIES,
    LEVER_COMPANIES,
    SNIPPET_MAX_CHARS,
)

_TIMEOUT = httpx.Timeout(10.0)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags, decode HTML entities, and collapse whitespace."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _html.unescape(text)
    return " ".join(text.split())


# "intern" needs a word-boundary check: plain substring would match
# "internal" and "international", pulling in Director/Manager/Auditor ATS roles.
# Pattern: "intern" not immediately followed by "al" or "atio" (covers both).
_INTERN_RE = re.compile(r"\bintern(?!al|atio)\w*", re.IGNORECASE)


def _is_junior(title: str) -> bool:
    """Return True if the title contains any ATS_JUNIOR_SIGNALS substring."""
    title_lower = title.lower()
    for sig in ATS_JUNIOR_SIGNALS:
        if sig == "intern":
            # Word-boundary-aware check: matches "intern", "interns", "internship"
            # but NOT "internal" or "international".
            if _INTERN_RE.search(title_lower):
                return True
        elif sig in title_lower:
            return True
    return False


def _infer_location(location_name: str, is_remote: bool = False) -> str:
    """
    Map a freeform location string to one of our three standard location buckets:
    'Singapore', 'remote', or 'visa sponsorship'.
    Defaults to 'remote' if nothing matches.
    """
    if is_remote:
        return "remote"
    loc = location_name.lower()
    if "singapore" in loc:
        return "Singapore"
    if any(kw in loc for kw in ("remote", "anywhere", "worldwide", "global")):
        return "remote"
    # Jobs with explicit visa mentions
    if "visa" in loc or "sponsor" in loc:
        return "visa sponsorship"
    return "remote"  # default — remote is the most permissive bucket


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------


def fetch_greenhouse_jobs(
    companies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch junior jobs from Greenhouse boards for all listed company slugs.
    Skips companies that return a non-200 response (company may not use Greenhouse).
    """
    companies = companies if companies is not None else GREENHOUSE_COMPANIES
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with httpx.Client(timeout=_TIMEOUT) as client:
        for slug in companies:
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                continue
            except Exception as exc:
                print(f"[ATS/greenhouse] Unexpected error for {slug!r}: {exc}")
                continue

            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not _is_junior(title):
                    continue

                job_url = job.get("absolute_url", "")
                if not job_url or job_url in seen_ids:
                    continue
                seen_ids.add(job_url)

                # updated_at format: "2026-01-15T10:30:00.000Z"
                published = None
                raw_date = job.get("updated_at")
                if raw_date:
                    published = raw_date[:10]  # keep YYYY-MM-DD

                location_name = (job.get("location") or {}).get("name", "")
                location_bucket = _infer_location(location_name)

                content = job.get("content", "") or ""
                snippet = _strip_html(content)[:SNIPPET_MAX_CHARS]

                # Determine which junior signal matched (used as 'role' field)
                matched_signal = next(
                    (sig for sig in ATS_JUNIOR_SIGNALS if sig in title.lower()),
                    "junior",
                )

                results.append(
                    {
                        "id": job_url,
                        "url": job_url,
                        "title": title,
                        "published": published,
                        "author": slug,
                        "text": snippet,
                        "role": matched_signal,
                        "location_searched": location_bucket,
                        "source": "greenhouse",
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------


def fetch_lever_jobs(
    companies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch junior jobs from Lever postings API for all listed company slugs.
    """
    companies = companies if companies is not None else LEVER_COMPANIES
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with httpx.Client(timeout=_TIMEOUT) as client:
        for slug in companies:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                jobs = resp.json()
                if not isinstance(jobs, list):
                    continue
            except (httpx.HTTPError, ValueError):
                continue
            except Exception as exc:
                print(f"[ATS/lever] Unexpected error for {slug!r}: {exc}")
                continue

            for job in jobs:
                title = job.get("text", "")
                if not _is_junior(title):
                    continue

                job_url = job.get("hostedUrl", "")
                if not job_url or job_url in seen_ids:
                    continue
                seen_ids.add(job_url)

                # createdAt is milliseconds since epoch
                published = None
                created_at = job.get("createdAt")
                if created_at:
                    try:
                        dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                        published = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                categories = job.get("categories") or {}
                location_name = categories.get("location", "")
                location_bucket = _infer_location(location_name)

                description = job.get("descriptionPlain", "") or ""
                snippet = _strip_html(description)[:SNIPPET_MAX_CHARS]

                matched_signal = next(
                    (sig for sig in ATS_JUNIOR_SIGNALS if sig in title.lower()),
                    "junior",
                )

                results.append(
                    {
                        "id": job_url,
                        "url": job_url,
                        "title": title,
                        "published": published,
                        "author": slug,
                        "text": snippet,
                        "role": matched_signal,
                        "location_searched": location_bucket,
                        "source": "lever",
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Ashby
# ---------------------------------------------------------------------------


def fetch_ashby_jobs(
    companies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch junior jobs from Ashby job board API for all listed company slugs.
    """
    companies = companies if companies is not None else ASHBY_COMPANIES
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with httpx.Client(timeout=_TIMEOUT) as client:
        for slug in companies:
            api_url = "https://jobs.ashbyhq.com/api/non-user-facing/job-board/jobs"
            try:
                resp = client.post(
                    api_url,
                    json={"organizationHostedJobsPageName": slug},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                continue
            except Exception as exc:
                print(f"[ATS/ashby] Unexpected error for {slug!r}: {exc}")
                continue

            for job in data.get("jobPostings", []):
                title = job.get("title", "")
                if not _is_junior(title):
                    continue

                job_url = job.get("jobUrl", "")
                if not job_url or job_url in seen_ids:
                    continue
                seen_ids.add(job_url)

                published = None
                raw_date = job.get("publishedDate")
                if raw_date:
                    published = raw_date[:10]

                is_remote = job.get("isRemote", False)
                location_name = job.get("locationName", "")
                location_bucket = _infer_location(location_name, is_remote=is_remote)

                desc_html = job.get("descriptionHtml", "") or ""
                snippet = _strip_html(desc_html)[:SNIPPET_MAX_CHARS]

                matched_signal = next(
                    (sig for sig in ATS_JUNIOR_SIGNALS if sig in title.lower()),
                    "junior",
                )

                results.append(
                    {
                        "id": job_url,
                        "url": job_url,
                        "title": title,
                        "published": published,
                        "author": slug,
                        "text": snippet,
                        "role": matched_signal,
                        "location_searched": location_bucket,
                        "source": "ashby",
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def fetch_all_ats_jobs() -> list[dict[str, Any]]:
    """
    Fetch junior jobs from all three ATS sources and return a combined,
    deduplicated list. Called by scraper.run_scrape().
    """
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    gh = fetch_greenhouse_jobs()
    lv = fetch_lever_jobs()
    ab = fetch_ashby_jobs()

    for job in gh + lv + ab:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            results.append(job)

    print(
        f"[ATS] greenhouse={len(gh)}, lever={len(lv)}, ashby={len(ab)}, "
        f"total={len(results)} junior jobs."
    )
    return results
