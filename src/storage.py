"""
storage.py
----------
SQLite database layer using SQLModel (SQLAlchemy + Pydantic).

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
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from src.config import DB_PATH

# ---------------------------------------------------------------------------
# Model
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


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# expire_on_commit=False keeps attribute values accessible after the session
# closes, so callers can read JobPosting fields without triggering a lazy reload.
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
_session_kwargs = {"expire_on_commit": False}


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    SQLModel.metadata.create_all(_engine)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def is_known(job_id: str) -> bool:
    """Return True if this Exa result ID is already in the database."""
    with Session(_engine) as session:
        result = session.get(JobPosting, job_id)
        return result is not None


def save_job(job: JobPosting) -> None:
    """Persist a new job posting. Silently skips duplicates."""
    with Session(_engine, **_session_kwargs) as session:
        session.add(job)
        session.commit()


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
        return session.exec(statement).all()


def get_all_jobs() -> list[JobPosting]:
    """Return every job posting in the database (for debugging / export)."""
    with Session(_engine) as session:
        return session.exec(select(JobPosting)).all()
