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
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Public URL of the web UI — shown at the bottom of Telegram digests.
# Leave blank if you're not hosting the web UI publicly.
WEB_URL: str = os.getenv("WEB_URL", "")

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
    q: disc for disc, queries in DISCIPLINE_QUERIES.items() for q in queries
}

# ------------------------------------------------------------------
# Location filters (appended to each Exa query)
# ------------------------------------------------------------------
LOCATIONS: list[str] = [
    "Singapore",
    "remote",
    "visa sponsorship",  # catches global roles that sponsor visas
]

# ------------------------------------------------------------------
# Seniority / experience targeting
# ------------------------------------------------------------------
# Targeting ~0–1 year experience (new grad / junior).
# Jobs requiring more than this are excluded.
TARGET_MAX_YEARS: int = 2  # exclude "X+ years" where X > this

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


# Combined exclude list (location + seniority keywords).
# Note: numeric "X+ years" patterns are now handled by the regex-based
# _exceeds_experience_limit() in scraper.py, which is more accurate.
EXCLUDE_KEYWORDS: list[str] = EXCLUDE_LOCATIONS + EXCLUDE_SENIORITY

# ------------------------------------------------------------------
# Junk result filtering
# ------------------------------------------------------------------

# URL substrings that indicate aggregator/listing pages, not real postings.
# These sites show lists of jobs rather than a single job application page.
EXCLUDE_DOMAINS: list[str] = [
    # Job listing aggregators
    "linkedin.com/jobs/search",
    "linkedin.com/jobs/",
    "sg.linkedin.com/jobs",
    "ca.linkedin.com/jobs",
    "mx.linkedin.com/jobs",
    "indeed.com/jobs",
    "ca.indeed.com",
    "glassdoor.com/Jobs",
    "glassdoor.com/job-listing",
    "glassdoor.com/listings",
    "builtin.com/jobs",
    "builtinnyc.com/jobs",
    "builtinsf.com/jobs",
    "builtinla.com/jobs",
    "builtinboston.com/jobs",
    "builtinchicago.com/jobs",
    "builtinseattle.com/jobs",
    "builtinaustin.com/jobs",
    "builtincolorado.com/jobs",
    "builtinlondon.uk/job",
    "levels.fyi/jobs",
    "h1bconnect.com",
    "h1bdata.info",
    "myvisajobs.com",
    "simplyhired.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
    "dice.com",
    "hired.com/jobs",
    "angel.co/jobs",
    "wellfound.com/jobs",
    "wellfound.com/role/",
    "otta.com/jobs",
    "remoteok.com",
    "weworkremotely.com",
    "jobstreet.com",
    "jobsdb.com",
    "seek.com",
    "careers.gov.sg",
    "mycareersfuture.gov.sg",
    "reddit.com",
    "quora.com",
    "medium.com",
    "dev.to",
    "hackernews",
    "news.ycombinator.com",
    "rubyonremote.com",
    "jobstreet.com.sg",
    "jobstreetexpress.com",
    "remoterocketship.com",
    "workatastartup.com",
    "jora.com/",
    "trovit.com",
    "arc.dev/remote-jobs/",
    "turing.com/jobs/",
    "devjobsscanner.com",
    "opentoworkremote.com",
    "jobright.ai",
    "exa.ai/library/",
    "simplify.jobs/l/",
    "visasponsor.jobs/api/jobs",
    "japan-dev.com/japan-jobs",
    "findajob.dwp.gov.uk",
    "remotive.com",
    "wayup.com",
    "github.com/SimplifyJobs",
    "foundit.sg",
    "jaabz.com",
    "pyjobs.com",
    "themuse.com",
    "rkycareers.com",
    "jobsite.co.uk",
    "meet.jobs",  # re-lists old/expired jobs
    "workingnomads.com",
    "weekday.works",
    "hubmub.com",
    "prosple.com",
    "sg.prosple.com",
    "beehiiv.com",
    "recruit.hirebridge.com",
    # Non-SWE job boards
    "wfhremoteboard.com",
    "hiresociall.com",
    "workingmomjobs.com",
    "flexjobs.com",
    "jobgether.com",  # aggregator listing pages
    "geekladder.com",  # company-page stub, not a job posting
    "joindevops.com",  # job board for DevOps roles (aggregator)
    "optnation.com",  # H1B/visa aggregator
    "naukri.com",  # India job board
    "dr.job",  # job aggregator
    "freelancer.com",  # freelance platform, not SWE jobs
    "vanhack.com",  # aggregator / relocation platform
    "arbeitnow.com",  # Germany visa-sponsorship aggregator
    "jobsbac.com",
    "jobisite.com",
    "rise.com/jobs",  # generic job board
    "himalayas.app",  # remote job board
    "crossover.com",  # aggregator
    "reeracoen.com",  # Japan/SG agency aggregator
    "hitmarker.net",  # gaming-industry job board
]

# Title/snippet keywords that indicate a non-SWE role.
EXCLUDE_ROLE_KEYWORDS: list[str] = [
    "chat support",
    "chat assistant",
    "copywriter",
    "customer support",
    "customer service",
    "data entry",
    "virtual assistant",
    "content writer",
    "social media",
    "sales representative",
    "account manager",
    "recruiter",
    "marketing",
    "graphic design",
    "video editor",
    "transcription",
    "proofreader",
    "translator",
    "accounting",
    "bookkeeping",
    "payroll",
    "finance manager",
]

# Merge role keywords into the main exclude list
EXCLUDE_KEYWORDS = EXCLUDE_KEYWORDS + EXCLUDE_ROLE_KEYWORDS

# Title patterns that indicate a listing/article page, not a single job posting.
# Checked case-insensitively against the result title.
EXCLUDE_TITLE_PATTERNS: list[str] = [
    # Aggregator-style titles
    "jobs in singapore",
    "jobs in malaysia",
    "jobs in new zealand",
    "jobs in uk",
    "jobs in japan",
    "jobs in europe",
    "jobs in germany",
    "jobs with salaries",
    "best remote",
    "top remote",
    "remote jobs 2025",
    "remote jobs 2024",
    "remote jobs 2026",
    "engineering jobs",  # e.g. "H1B Engineering Jobs | Find..."
    "find h-1b",
    "h1b sponsorship",
    "job board",
    "jobs near you",
    "search jobs",
    "browse jobs",
    "apply now",  # generic CTA pages
    "salary guide",
    "salary report",
    "hiring now",
    "we're hiring",
    "is hiring",
    # Article/listicle titles
    "how to get",
    "how to land",
    "tips for",
    "guide to",
    "everything you need",
    "what is a",
    "career guide",
    "interview questions",
    "interview tips",
    # Plural listing indicators
    " jobs | ",  # e.g. "Backend Jobs | Glassdoor"
    " jobs - ",  # e.g. "Junior Jobs - Indeed"
    "3000+",
    "1000+",
    "500+",
    "200+",
    "100+",
    # Aggregator-style job listing titles
    "remote jobs",
    " developer jobs",
    " engineer jobs",
    "new grad positions",
    "visa sponsorship jobs",
    "find visa sponsorship",
    "tech jobs with visa",
    "jobs with visa sponsorship",
    # Known junk page titles
    "careers at cisco",
    "visa u.s. careers",
    "visa students and early careers",
    "job vacancies in",
    "job offers in",
    "vacancies in",
    "empleos de ",  # Spanish listing pages
    "entry level jobs in",
    "architecture jobs in",
    "fresh graduate",  # listing pages (e.g. "Fresh Graduate SWE jobs in...")
]

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

VISA_NEGATIONS: list[str] = [
    "not eligible",
    "no sponsorship",
    "does not sponsor",
    "do not sponsor",
    "unable to sponsor",
    "cannot sponsor",
    "not able to sponsor",
    "not sponsoring",
    "without sponsorship",
    "sponsorship is not available",
    "not provide sponsorship",
    "ineligible for sponsorship",
    "visa sponsorship is not offered",
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

# Drop jobs whose published date is older than this many days.
# Jobs with no published date are allowed through (Exa often omits it).
MAX_JOB_AGE_DAYS: int = 90

SEARCH_TYPE: str = "auto"

# Characters of page text to fetch per result.
# 1500 gives enough context for junk detection, visa/remote keywords,
# and a meaningful snippet to display.
SNIPPET_MAX_CHARS: int = 1500

# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------

# Supabase (Postgres) connection string.
# Set this in your .env file locally and as a secret in Railway / GitHub Actions.
# Format: postgresql://postgres.[project-ref]:[password]@aws-X-[region].pooler.supabase.com:5432/postgres
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# ------------------------------------------------------------------
# Anthropic AI
# ------------------------------------------------------------------

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------
SCHEDULE_HOUR: int = 8
SCHEDULE_MINUTE: int = 0

# ------------------------------------------------------------------
# ATS company slugs — direct API sources
# Add/remove companies here to control which career pages we scrape.
# ------------------------------------------------------------------

GREENHOUSE_COMPANIES: list[str] = [
    "canva",
    "figma",
    "notion",
    "stripe",
    "coinbase",
    "airbnb",
    "dropbox",
    "hubspot",
    "asana",
    "twilio",
    "zendesk",
    "cloudflare",
    "hashicorp",
    "mongodb",
    "elastic",
    "gitlab",
    "automattic",
    "squarespace",
    "brex",
    "robinhood",
    "plaid",
    "affirm",
    "checkr",
    "rippling",
    "lattice",
    "gusto",
    "benchling",
    "samsara",
    "podium",
    "greenhouse",
]

LEVER_COMPANIES: list[str] = [
    "datadog",
    "carta",
    "mixpanel",
    "segment",
    "amplitude",
    "heap",
    "retool",
    "glean",
    "scale-ai",
    "weights-biases",
    "anyscale",
    "prefect",
    "dbt-labs",
    "airbyte",
    "mux",
    "stytch",
    "courier",
    "knock",
    "liveblocks",
    "baseten",
]

ASHBY_COMPANIES: list[str] = [
    "linear",
    "vercel",
    "supabase",
    "railway",
    "turso",
    "trigger",
    "inngest",
    "posthog",
    "metabase",
    "cal",
    "dub",
    "plane",
    "opencollective",
    "replit",
    "cursor",
    "codeium",
    "sourcegraph",
    "grafbase",
    "highlight",
    "infisical",
]

# Title substrings that indicate a junior/entry-level role.
# ATS APIs return ALL jobs — we pre-filter to these before the main pipeline.
ATS_JUNIOR_SIGNALS: list[str] = [
    "junior",
    "entry level",
    "entry-level",
    "graduate",
    "grad ",
    "new grad",
    "associate",
    "early career",
    "intern",
    "apprentice",
]
