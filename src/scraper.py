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

import html as _html
import json
import re
from datetime import date as _date, timedelta
from typing import Any

from src.config import (
    EXCLUDE_DOMAINS,
    EXCLUDE_LOCATIONS,
    EXCLUDE_ROLE_KEYWORDS,
    EXCLUDE_SENIORITY,
    EXCLUDE_TITLE_PATTERNS,
    JUNK_SNIPPET_SIGNALS,
    MAX_JOB_AGE_DAYS,
    QUERY_TO_DISCIPLINE,
    REMOTE_KEYWORDS,
    ROLES,
    TARGET_MAX_YEARS,
    VISA_KEYWORDS,
    VISA_NEGATIONS,
)
from src.agent import reflect
from src.ai_analysis import analyze_job
from src.ats_client import fetch_all_ats_jobs
from src.exa_client import fetch_jobs
from src.storage import (
    JobPosting,
    get_active_agent_queries,
    get_profile,
    is_known,
    save_job,
    update_job_analysis,
    upsert_query_performance,
)


_HTML_TAG_RE = re.compile(r"<[^>]+>")


# Title keyword → discipline mapping for ATS results (which have no Exa query string).
# Checked in order; first match wins. Defaults to "FullStack" for generic SWE titles.
_TITLE_DISCIPLINE: list[tuple[str, str]] = [
    ("backend", "Backend"),
    ("back-end", "Backend"),
    ("back end", "Backend"),
    ("frontend", "Frontend"),
    ("front-end", "Frontend"),
    ("front end", "Frontend"),
    ("full stack", "FullStack"),
    ("fullstack", "FullStack"),
    ("full-stack", "FullStack"),
    ("devops", "DevOps"),
    ("dev ops", "DevOps"),
    ("platform engineer", "DevOps"),
    ("site reliability", "Infra/SRE"),
    ("infrastructure", "Infra/SRE"),
    (" sre", "Infra/SRE"),
    ("cloud engineer", "Infra/SRE"),
]


def _infer_discipline_from_title(title: str) -> str:
    """Infer discipline from job title keywords. Used as fallback for ATS results."""
    t = title.lower()
    for keyword, discipline in _TITLE_DISCIPLINE:
        if keyword in t:
            return discipline
    return "FullStack"


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting from Exa page text before storing as snippet."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # ATX headers
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # italic
    return text


def _clean_snippet(text: str) -> str:
    """Strip HTML tags and decode entities, then remove markdown formatting."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _html.unescape(text)
    text = " ".join(text.split())  # normalize whitespace
    return _strip_markdown(text)


def _is_too_old(result: dict[str, Any]) -> bool:
    """
    Return True if the published date is older than MAX_JOB_AGE_DAYS.
    Jobs with no published date are allowed through — Exa often omits it
    for legitimate postings, so we don't want to over-filter.
    """
    published = result.get("published")
    if not published:
        return False
    try:
        # Exa returns ISO-8601 strings like "2026-01-14T00:00:00.000Z"
        pub_date = _date.fromisoformat(published[:10])
        cutoff = _date.today() - timedelta(days=MAX_JOB_AGE_DAYS)
        return pub_date < cutoff
    except (ValueError, TypeError):
        return False


def _is_excluded(result: dict[str, Any]) -> bool:
    """
    Return True if the result should be dropped.

    Three keyword sub-checks, then an experience regex check:
    1. Location keywords (India cities) — checked against full title+snippet.
       A job physically located in an excluded city is relevant wherever it appears.
    2. Seniority keywords (Senior, Staff, Principal…) — title only.
       Snippets routinely say "work alongside Senior Engineers"; we must not
       exclude a Junior role because its description mentions senior teammates.
    3. Role keywords (QA, support, sales, finance…) — title only.
       Legitimate SWE snippets commonly mention "quality assurance standards",
       "financial services platform", "accounting software" etc. — checking
       these against the snippet would produce many false positives.
    4. Experience requirement — regex over full haystack, with a heuristic to
       skip company-history statements.
    """
    title = result.get("title", "").lower()
    text = result.get("text", "").lower()
    haystack = f"{title} {text}"

    # --- 1. Location check (full haystack) ---
    if any(kw.lower() in haystack for kw in EXCLUDE_LOCATIONS):
        return True

    # --- 2. Seniority check (title only) ---
    if any(kw.lower() in title for kw in EXCLUDE_SENIORITY):
        return True

    # --- 3. Role keyword check (title only) ---
    if any(kw.lower() in title for kw in EXCLUDE_ROLE_KEYWORDS):
        return True

    # --- 4. Experience requirement check ---
    if _exceeds_experience_limit(haystack):
        return True

    return False


# Written-out number words → digit values (up to 15).
_WORD_TO_NUM: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}

# Matches patterns like:
#   "2 years", "2+ years", "2-4 years", "2 to 4 years",
#   "two years", "three or more years", "minimum 2 years",
#   "at least 3 years", "2 years of experience"
_EXP_RE = re.compile(
    r"""
    (?:
        # Optional preamble: "minimum", "at least", "requires", etc.
        (?:minimum|at\s+least|requires?|need|must\s+have|ideally|preferably)
        \s+
    )?
    # The number part — digit(s) or written-out word
    (?P<lo>
        \d+                          # plain digit(s): 2, 10
        | (?:"""
    + "|".join(_WORD_TO_NUM.keys())
    + r""")
    )
    # Optional range upper bound: "2-4", "2 to 4", "2 or more"
    (?:
        \s*[-–]\s*\d+
        | \s+to\s+\d+
        | \s+or\s+more
        | \+                         # "2+" immediately after digit
    )?
    \s+years?                        # "year" or "years"
    (?:\s+of)?                       # optional "of"
    (?:\s+(?:relevant\s+|related\s+|professional\s+|work\s+)?experience)?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _exceeds_experience_limit(haystack: str) -> bool:
    """
    Return True if the text contains an experience requirement that
    exceeds TARGET_MAX_YEARS.

    Uses the LOWER bound of any range (e.g. "1-3 years" → 1, allowed;
    "2-4 years" → 2, allowed if TARGET_MAX_YEARS >= 2).
    Ignores statements that are clearly about the company's history
    ("we have 10 years of experience building...").
    """
    for m in _EXP_RE.finditer(haystack):
        lo_str = m.group("lo")
        # Convert written-out word to int if needed
        lo = _WORD_TO_NUM.get(lo_str.lower(), None)
        if lo is None:
            try:
                lo = int(lo_str)
            except ValueError:
                continue

        # Heuristic: skip if context describes the company or equity, not a requirement.
        # Check prefix (what comes BEFORE the N-year match).
        start = max(0, m.start() - 40)
        prefix = haystack[start : m.start()].lower()
        if any(
            tok in prefix
            for tok in ("our ", "we have", "we've", "with over", "company", "firm",
                        "founded", "established")
        ):
            continue

        # Check suffix (what comes AFTER): equity vesting language like
        # "4 year vesting schedule" or "1 year cliff".
        suffix = haystack[m.end() : m.end() + 30].lower()
        if any(tok in suffix for tok in ("vesting", "cliff", "vest")):
            continue

        if lo > TARGET_MAX_YEARS:
            return True

    return False


CLOSED_JOB_SIGNALS: list[str] = [
    "no longer accepting applicants",
    "no longer accepting applications",
    "this job is no longer",
    "position has been filled",
    "position is no longer available",
    "this position is no longer",
    "this role is no longer",
    "listing is no longer",
    "job listing has expired",
    "job has expired",
    "posting has expired",
    "posting is expired",
    "application period has closed",
    "applications are closed",
    "vacancy has been filled",
    "this vacancy is closed",
    "an error has occurred",  # Cisco-style error pages
]


def _is_junk(result: dict[str, Any]) -> bool:
    """
    Return True if the result is an aggregator/listing page rather than
    an actual individual job posting, or if the posting is closed/expired.

    Checks:
      1. URL contains a known aggregator domain/path pattern.
      2. Title matches a known listing/article pattern.
      3. Snippet contains a closed/expired job signal.
    """
    url = result.get("url", "").lower()
    title = result.get("title", "").lower()
    text = result.get("text", "").lower()

    if any(domain.lower() in url for domain in EXCLUDE_DOMAINS):
        return True

    if any(pat.lower() in title for pat in EXCLUDE_TITLE_PATTERNS):
        return True

    if any(signal in text for signal in CLOSED_JOB_SIGNALS):
        return True

    if any(signal.lower() in text for signal in JUNK_SNIPPET_SIGNALS):
        return True

    return False


def _detect_visa(result: dict[str, Any]) -> bool:
    """
    Return True if the job text or location tag indicates visa sponsorship.
    Also triggers when the search location was 'visa sponsorship'.
    Negation phrases (e.g. 'not eligible for sponsorship') return False.
    """
    if "visa" in result.get("location_searched", "").lower():
        return True
    haystack = f"{result.get('title', '')} {result.get('text', '')}".lower()
    if any(neg in haystack for neg in VISA_NEGATIONS):
        return False
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
    # Load active agent queries to supplement baseline
    agent_query_rows = get_active_agent_queries()
    agent_queries = [r.query for r in agent_query_rows]

    print("\n[Scraper] Starting fetch from Exa...")
    print(
        f"[Scraper] Baseline queries: {len(ROLES)} | Agent queries: {len(agent_queries)}"
    )
    raw_results = fetch_jobs(extra_queries=agent_queries)
    print(f"[Scraper] Exa returned {len(raw_results)} raw results.")

    print("[Scraper] Fetching from ATS sources (Greenhouse, Lever, Ashby)...")
    ats_results = fetch_all_ats_jobs()
    raw_results = raw_results + ats_results
    print(f"[Scraper] Total raw results after ATS merge: {len(raw_results)}")

    new_jobs: list[JobPosting] = []
    skipped_excluded = 0
    skipped_junk = 0
    skipped_old = 0
    skipped_duplicate = 0
    query_found: dict[str, int] = {}
    for result in raw_results:
        # --- Step 1: Drop aggregator / listing / closed pages ---
        if _is_junk(result):
            skipped_junk += 1
            print(f"  [JUNK] {result.get('title', '')[:80]}")
            continue

        # --- Step 2: Drop jobs older than MAX_JOB_AGE_DAYS ---
        if _is_too_old(result):
            skipped_old += 1
            print(
                f"  [OLD]  {result.get('published', '')[:10]} {result.get('title', '')[:70]}"
            )
            continue

        # --- Step 3: Drop unwanted seniority / location results ---
        if _is_excluded(result):
            skipped_excluded += 1
            continue

        q = result["role"]
        query_found[q] = query_found.get(q, 0) + 1
        # --- Step 3: Deduplicate by Exa ID (URL-based) ---
        if is_known(result["id"]):
            skipped_duplicate += 1
            continue

        # --- Step 3: Enrich with derived fields ---
        discipline = QUERY_TO_DISCIPLINE.get(result["role"]) or _infer_discipline_from_title(result["title"])
        visa_sponsored = _detect_visa(result)
        remote_ok = _detect_remote(result)

        # --- Step 4: Build model and persist ---
        job = JobPosting(
            id=result["id"],
            url=result["url"],
            title=result["title"],
            published=result.get("published"),
            author=result.get("author"),
            snippet=_clean_snippet(result.get("text", "")),
            role=result["role"],
            discipline=discipline,
            location=result["location_searched"],
            visa_sponsored=visa_sponsored,
            remote_ok=remote_ok,
            source=result.get("source", "exa"),
        )
        save_job(job)
        new_jobs.append(job)

    print(
        f"[Scraper] Done. "
        f"New: {len(new_jobs)} | "
        f"Junk skipped: {skipped_junk} | "
        f"Too old: {skipped_old} | "
        f"Excluded by keyword: {skipped_excluded} | "
        f"Duplicates skipped: {skipped_duplicate}"
    )

    # --- Record per-query performance stats ---
    today = _date.today()
    baseline_set = set(ROLES)
    query_kept: dict[str, int] = {}

    for job in new_jobs:
        q = job.role
        query_kept[q] = query_kept.get(q, 0) + 1
    for q, found in query_found.items():
        kept = query_kept.get(q, 0)
        source = "baseline" if q in baseline_set else "agent"
        upsert_query_performance(q, source, today, found, kept, avg_ai_score=None)

    # --- AI analysis: run per new job if a user profile exists ---
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
                    score = analysis.get("overall_score")
                    if isinstance(score, (int, float)):
                        query_scores.setdefault(job.role, []).append(float(score))
            # Update avg_ai_score for each query that has scores
            for q, scores in query_scores.items():
                avg = sum(scores) / len(scores)
                source = "baseline" if q in baseline_set else "agent"
                found = query_found.get(q, 0)
                kept = query_kept.get(q, 0)
                upsert_query_performance(
                    q, source, today, found, kept, avg_ai_score=avg
                )
        else:
            print("[Scraper] No user profile found — skipping AI analysis.")

    # --- Agent reflection: retire underperformers, generate new queries ---
    print("[Scraper] Running agent reflection...")
    reflect()

    return new_jobs
