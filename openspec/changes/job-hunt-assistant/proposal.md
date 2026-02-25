## Why

The scraper finds jobs but three friction points slow down the actual job hunt: disqualifiers (wrong location, graduation requirements, no visa) only surface after reading the full listing; there's no way to track application status and notes per job; and tailoring applications is slow because it's unclear which projects to highlight per role. Extending the scraper with AI pre-screening and tracking turns a passive feed into an active job hunt assistant.

## What Changes

- User can upload a resume PDF and save a personal profile (graduation date, location, visa status, skills, projects)
- After each scrape, Claude analyzes every new job against the profile and flags disqualifiers, cautions, matched projects, and key requirements
- Each job card in the web UI displays the AI analysis inline
- Each job has a status dropdown (`none → interested → applied → interviewing → offer → rejected / dismissed`) and a notes textarea, both persisted to the DB
- The filter bar gains status, date-range, and show-dismissed controls

## Capabilities

### New Capabilities
- `user-profile`: Store and manage a single-user profile parsed from a resume upload
- `ai-job-screening`: Analyze each new job posting against the user profile using Claude
- `application-tracking`: Track per-job application status and freeform notes

### Modified Capabilities

## Impact

- `src/storage.py`: Add `UserProfile` model; add `status`, `notes`, `ai_analysis` columns to `JobPosting`; add migration step in `init_db()`
- `src/web.py`: Add `/settings` (GET/POST), `/api/settings/parse-resume` (POST), `PATCH /api/jobs/<id>` routes; extend `/api/jobs` with status, days, and dismissed filters
- `src/scraper.py`: Call AI analysis after saving each new job
- `templates/index.html`: Two-row controls, AI chip strip per card, status/notes tracking column, date and status filters
- New: `src/ai_analysis.py`, `templates/settings.html`
- New dependency: `anthropic>=0.40.0`
