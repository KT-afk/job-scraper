"""
config.py
---------
Central configuration for the job scraper.
Edit ROLES, DISCIPLINES, and LOCATIONS to suit your search criteria.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Exa API
# ------------------------------------------------------------------
EXA_API_KEY: str = os.getenv("EXA_API_KEY", "")

# ------------------------------------------------------------------
# Notifications
# ------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

# ------------------------------------------------------------------
# Discipline → query terms mapping
# Each key becomes a DB tag; values are the query strings used by Exa.
# ------------------------------------------------------------------
DISCIPLINE_QUERIES: dict[str, list[str]] = {
    "Backend": [
        "Junior Backend Engineer",
        "Junior Backend Developer",
        "Graduate Backend Engineer",
        "Entry Level Backend Developer",
    ],
    "Frontend": [
        "Junior Frontend Engineer",
        "Junior Frontend Developer",
        "Graduate Frontend Engineer",
        "Entry Level Frontend Developer",
    ],
    "FullStack": [
        "Junior Full Stack Engineer",
        "Junior Full Stack Developer",
        "Graduate Software Engineer",
        "Entry Level Software Engineer",
    ],
    "DevOps": [
        "Junior DevOps Engineer",
        "Junior Platform Engineer",
        "Graduate DevOps Engineer",
        "Entry Level DevOps",
    ],
    "Infra/SRE": [
        "Junior SRE",
        "Junior Site Reliability Engineer",
        "Junior Infrastructure Engineer",
        "Graduate Cloud Engineer",
        "Entry Level SRE",
    ],
}

# Flat list of all role query strings (used by exa_client).
ROLES: list[str] = [q for queries in DISCIPLINE_QUERIES.values() for q in queries]

# Mapping from query string back to discipline (for tagging DB rows).
QUERY_TO_DISCIPLINE: dict[str, str] = {
    q: disc
    for disc, queries in DISCIPLINE_QUERIES.items()
    for q in queries
}

# ------------------------------------------------------------------
# Location filters (appended to each Exa query)
# ------------------------------------------------------------------
LOCATIONS: list[str] = [
    "Singapore",
    "remote",
    "visa sponsorship",   # catches global roles that sponsor visas
]

# ------------------------------------------------------------------
# Seniority / experience targeting
# ------------------------------------------------------------------
# Targeting ~0–1 year experience (new grad / junior).
# Jobs requiring more than this are excluded.
TARGET_MAX_YEARS: int = 2   # exclude "X+ years" where X > this

# Keywords in title/snippet that indicate too-senior a role.
# These are checked case-insensitively.
EXCLUDE_SENIORITY: list[str] = [
    "Senior",
    "Sr.",
    "Sr ",
    "Staff Engineer",
    "Staff Software",
    "Principal Engineer",
    "Principal Software",
    "Lead Engineer",
    "Lead Developer",
    "Engineering Manager",
    "Head of Engineering",
    "VP of Engineering",
    "Director of Engineering",
    # Dynamic year filters are generated from TARGET_MAX_YEARS:
    # "3+ years", "4+ years", ... "15+ years" are added at runtime.
]

# Countries / cities to exclude (checked in title + snippet).
EXCLUDE_LOCATIONS: list[str] = [
    "India",
    "Bangalore",
    "Bengaluru",
    "Chennai",
    "Hyderabad",
    "Mumbai",
    "Pune",
    "Delhi",
    "Noida",
    "Gurugram",
    "Gurgaon",
]

# Combined exclude list (location + seniority, plus generated year patterns).
def _build_exclude_keywords() -> list[str]:
    years = [f"{y}+ years" for y in range(TARGET_MAX_YEARS + 1, 16)]
    years += [f"{y}+ year" for y in range(TARGET_MAX_YEARS + 1, 16)]
    return EXCLUDE_LOCATIONS + EXCLUDE_SENIORITY + years

EXCLUDE_KEYWORDS: list[str] = _build_exclude_keywords()

# ------------------------------------------------------------------
# Visa / remote signal keywords
# (used to tag each result in the DB — not to exclude results)
# ------------------------------------------------------------------
VISA_KEYWORDS: list[str] = [
    "visa sponsor",
    "visa sponsorship",
    "sponsorship available",
    "we sponsor",
    "will sponsor",
    "relocation",
    "relocation package",
]

REMOTE_KEYWORDS: list[str] = [
    "remote",
    "work from home",
    "wfh",
    "fully remote",
    "distributed team",
    "anywhere",
]

# ------------------------------------------------------------------
# Exa query settings
# ------------------------------------------------------------------
RESULTS_PER_QUERY: int = 10

# Only return pages crawled within the last N days.
CRAWL_DAYS_BACK: int = 1

SEARCH_TYPE: str = "auto"

# Characters of page text to fetch per result.
# 800 gives enough context for visa/remote keyword detection.
SNIPPET_MAX_CHARS: int = 800

# ------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------
DB_PATH: str = "jobs.db"

# ------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------
SCHEDULE_HOUR: int = 8
SCHEDULE_MINUTE: int = 0
