## Context

The job scraper is a Python/SQLite/Flask app that scrapes junior engineering jobs via the Exa AI API and surfaces them in a web UI and Telegram digest. The DB uses SQLModel (SQLAlchemy + Pydantic). The single `JobPosting` table has no status tracking or AI analysis columns. There is no concept of a user profile. The web UI is a single-page app fetching from `/api/jobs` and `/api/stats`.

## Goals / Non-Goals

**Goals:**
- Single-user profile stored in SQLite, populated from resume upload or manual form entry
- Per-job AI analysis (disqualifiers, cautions, matched projects, key requirements) stored as JSON on the job row
- Application status (`none / interested / applied / interviewing / offer / rejected / dismissed`) and freeform notes per job, persisted to DB and editable inline in the UI
- Status and date-range filters in the web UI

**Non-Goals:**
- Multi-user support
- Real-time scrape triggering from the UI
- Email or push notifications for status changes
- Pagination (existing table behaviour)

## Decisions

### Decision 1: Store AI analysis as a JSON string column, not a separate table

The analysis is tightly coupled to a single job row and read together with it. A separate table would add join complexity for no structural benefit at this scale (hundreds of rows, single user). A JSON text column on `JobPosting` keeps the schema flat and the API serialisation trivial.

**Alternative considered:** Separate `job_analysis` table with FK. Rejected: over-engineered for single-user, single-scraper use.

### Decision 2: Use `claude-haiku` for per-job analysis, `claude-sonnet` for resume parsing

Per-job analysis runs on every new job in a scrape batch (potentially 50+ calls). Haiku is 10–20× cheaper and fast enough for structured JSON extraction from short snippets. Resume parsing is a one-time call on a full PDF document where accuracy matters more — Sonnet is appropriate.

### Decision 3: Add new columns via SQLite `ALTER TABLE` migration, not a full schema reset

The live DB (`jobs.db`) is tracked in git and deployed on Railway. Dropping and recreating the table would wipe accumulated job history. A `_migrate()` function in `init_db()` uses `PRAGMA table_info` to detect missing columns and adds them with `ALTER TABLE … ADD COLUMN`. SQLite supports adding columns with defaults, making this safe and idempotent.

### Decision 4: Single-row `UserProfile` table (id always = 1)

There is one user. A single-row table with a fixed PK is the simplest correct model. Upsert logic replaces the row if it exists. This avoids an `Optional[int]` PK pattern and keeps `get_profile()` a simple `session.get(UserProfile, 1)`.

## Risks / Trade-offs

- **Anthropic API key not set** → AI analysis silently skips (prints a notice). Jobs still save normally. Risk: user sees "No analysis" on all cards until they add the key.
- **Claude returns malformed JSON** → `json.loads()` raises, caught by the broad `except Exception`, returns `None`. Risk: analysis lost for that job. Mitigation: log the raw response for debugging.
- **SQLite migration is append-only** → Cannot rename or remove columns via `ALTER TABLE` in SQLite without recreating the table. Acceptable for this project's lifecycle; document if column removal is ever needed.
- **Resume PDF parsing accuracy** → Claude may misparse complex PDF layouts. Mitigation: the settings form is fully editable; parsed values are pre-fills, not locked-in writes.

## Migration Plan

1. Deploy updated `src/storage.py` — `init_db()` runs `_migrate()` on startup, adding columns to the existing `jobposting` table on Railway.
2. Add `ANTHROPIC_API_KEY` to Railway environment variables.
3. Old job rows will have `status = 'none'`, `notes = ''`, `ai_analysis = NULL` — correct defaults, no backfill needed.
4. Rollback: remove the new columns from the model and redeploy; the columns remain in the DB but are ignored by SQLModel.
