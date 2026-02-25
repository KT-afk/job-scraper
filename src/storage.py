"""
storage.py
----------
Postgres database layer using SQLModel (SQLAlchemy + Pydantic).
Connects to Supabase via the session-mode pooler (DATABASE_URL env var).

Schema
------
JobPosting
    id            TEXT PRIMARY KEY  - Exa's URL-based unique ID
    url           TEXT              - job posting URL
    title         TEXT              - page title
    published     TEXT              - publication date (ISO string, nullable)
    author        TEXT              - site/author name (nullable)
    snippet       TEXT              - text preview (up to SNIPPET_MAX_CHARS)
    role          TEXT              - raw Exa query string used to find this job
    discipline    TEXT              - normalised discipline tag (Backend, Frontend, …)
    location      TEXT              - location search term used (Singapore, remote, …)
    visa_sponsored BOOL             - True if visa sponsorship keywords detected
    remote_ok     BOOL              - True if remote-work keywords detected
    seen_at       TEXT              - UTC timestamp when WE first saw it
    status        TEXT              - application status (none/interested/applied/…)
    notes         TEXT              - freeform notes
    ai_analysis   TEXT              - JSON string from AI analysis, nullable

UserProfile
    id            INT PRIMARY KEY   - always 1 (single-user)
    graduation_date TEXT            - e.g. "2025-06"
    location      TEXT              - current location
    visa_status   TEXT              - visa / work authorisation description
    skills        TEXT              - comma-separated skills
    projects      TEXT              - JSON array of {name, desc} objects
"""

from __future__ import annotations

import urllib.parse
from datetime import date as _date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import UniqueConstraint, func
from sqlmodel import Field, Session, SQLModel, create_engine, select

from src.config import DATABASE_URL

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class JobPosting(SQLModel, table=True):
    """Represents a single job posting stored in the database."""

    id: str = Field(primary_key=True)         # Exa result ID (URL-based)
    url: str
    title: str
    published: Optional[str] = None
    author: Optional[str] = None
    snippet: str = ""
    role: str                                  # raw query string
    discipline: str = ""                       # Backend / Frontend / FullStack / DevOps / Infra/SRE
    location: str
    visa_sponsored: bool = False
    remote_ok: bool = False
    seen_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Application tracking
    status: str = "none"                       # none/interested/applied/interviewing/offer/rejected/dismissed
    notes: str = ""
    # AI analysis (JSON string)
    ai_analysis: Optional[str] = None


class UserProfile(SQLModel, table=True):
    """Single-row user profile (id always = 1)."""

    id: int = Field(default=1, primary_key=True)
    graduation_date: str = ""
    location: str = ""
    visa_status: str = ""
    skills: str = ""
    projects: str = "[]"                       # JSON array of {name, desc}


class QueryPerformance(SQLModel, table=True):
    """Per-query performance record for one scrape run."""

    __table_args__ = (UniqueConstraint("query", "run_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str                              # the Exa query string
    source: str                             # 'baseline' or 'agent'
    run_date: str                           # ISO date string e.g. "2026-02-24"
    jobs_found: int = 0
    jobs_kept: int = 0
    junk_rate: Optional[float] = None       # 1 - jobs_kept/jobs_found
    avg_ai_score: Optional[float] = None
    is_active: bool = True                  # agent can retire by setting False


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _make_engine():
    """
    Build the SQLAlchemy engine.

    For Postgres (Supabase pooler) we parse DATABASE_URL and pass all
    credentials as explicit connect_args so libpq never parses the username
    string — which would truncate 'postgres.project-ref' at the dot.

    For SQLite (tests / local fallback) we pass the URL directly.
    """
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is not set. "
            "Add it to your .env file (local) or environment variables (Vercel/CI)."
        )

    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, echo=False)

    # urllib.parse.urlparse rejects '[' / ']' in passwords (Python 3.14+).
    # Use a regex to extract components directly from the URL instead.
    import re
    m = re.match(
        r"postgresql(?:\+\w+)?://"   # scheme
        r"([^:@]+)"                  # user (group 1)
        r"(?::([^@]*))?"             # :password (group 2, optional)
        r"@([^:/]+)"                 # @host (group 3)
        r"(?::(\d+))?"               # :port (group 4, optional)
        r"/([^?]*)"                  # /dbname (group 5)
        r"(?:\?(.*))?$",             # ?query (group 6, optional)
        DATABASE_URL,
    )
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {DATABASE_URL!r}")

    user, password, host, port, dbname, query = m.groups()
    # Strip literal brackets Supabase puts around placeholder passwords
    if password and password.startswith("[") and password.endswith("]"):
        password = password[1:-1]

    # Extract sslmode from query string if present
    sslmode = "require"
    if query:
        for part in query.split("&"):
            if part.startswith("sslmode="):
                sslmode = part.split("=", 1)[1]

    return create_engine(
        "postgresql+psycopg://",   # psycopg3 dialect; no creds in the URL
        connect_args={
            "host":     host,
            "port":     int(port) if port else 5432,
            "dbname":   dbname or "postgres",
            "user":     urllib.parse.unquote(user),
            "password": urllib.parse.unquote(password or ""),
            "sslmode":  sslmode,
        },
        echo=False,
    )


_engine = _make_engine()


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    SQLModel.metadata.create_all(_engine)


# ---------------------------------------------------------------------------
# JobPosting operations
# ---------------------------------------------------------------------------


def is_known(job_id: str) -> bool:
    """Return True if this Exa result ID is already in the database."""
    with Session(_engine) as session:
        result = session.get(JobPosting, job_id)
        return result is not None


def save_job(job: JobPosting) -> None:
    """Persist a new job posting. Silently skips duplicates."""
    with Session(_engine) as session:
        session.add(job)
        session.commit()
        session.expunge(job)  # keep object usable after session closes


def get_todays_jobs() -> list[JobPosting]:
    """
    Return all job postings seen today (UTC date match on seen_at).
    Used by the display layer to print the daily digest.
    """
    today = datetime.now(timezone.utc).date().isoformat()  # e.g. "2026-02-20"
    with Session(_engine) as session:
        statement = select(JobPosting).where(
            JobPosting.seen_at.startswith(today)  # type: ignore[union-attr]
        )
        results: Sequence[JobPosting] = session.exec(statement).all()
        return list(results)


def get_all_jobs() -> list[JobPosting]:
    """Return every job posting in the database (for debugging / export)."""
    with Session(_engine) as session:
        results: Sequence[JobPosting] = session.exec(select(JobPosting)).all()
        return list(results)


def update_job_analysis(job_id: str, ai_analysis_json: str) -> None:
    """Persist the AI analysis JSON string for a job. No-op if job not found."""
    with Session(_engine) as session:
        job = session.get(JobPosting, job_id)
        if job is None:
            return
        job.ai_analysis = ai_analysis_json
        session.add(job)
        session.commit()


def update_job_tracking(
    job_id: str,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    """
    Update status and/or notes for a job.
    Returns True if the job was found and updated, False if not found.
    """
    with Session(_engine) as session:
        job = session.get(JobPosting, job_id)
        if job is None:
            return False
        if status is not None:
            job.status = status
        if notes is not None:
            job.notes = notes
        session.add(job)
        session.commit()
    return True


# ---------------------------------------------------------------------------
# UserProfile operations
# ---------------------------------------------------------------------------


def save_profile(profile: UserProfile) -> None:
    """Upsert the single-user profile (id=1)."""
    profile.id = 1  # enforce single-row constraint
    with Session(_engine) as session:
        existing = session.get(UserProfile, 1)
        if existing is not None:
            session.delete(existing)
            session.commit()
        session.add(profile)
        session.commit()


def get_profile() -> Optional[UserProfile]:
    """Return the single user profile, or None if not yet configured."""
    with Session(_engine) as session:
        return session.get(UserProfile, 1)


# ---------------------------------------------------------------------------
# QueryPerformance operations
# ---------------------------------------------------------------------------


def upsert_query_performance(
    query: str,
    source: str,
    run_date: _date,
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
            if avg_ai_score is not None:
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
        statement = select(func.count()).select_from(QueryPerformance).where(
            QueryPerformance.source == "agent",
            QueryPerformance.is_active == True,  # noqa: E712
        )
        return len(list(session.exec(statement).all()))
