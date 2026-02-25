## 1. Dependencies and Config

- [x] 1.1 Add `anthropic>=0.40.0`, `pytest>=8.0.0`, `pytest-mock>=3.12.0`, `psycopg2-binary>=2.9.0` to `requirements.txt`
- [x] 1.2 Add `ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")` and `DATABASE_URL = os.getenv("DATABASE_URL", "")` to `src/config.py`; remove `DB_PATH`
- [x] 1.3 Add `ANTHROPIC_API_KEY` and `DATABASE_URL` to `.env.example`
- [x] 1.4 Run `pip install anthropic pytest pytest-mock psycopg2-binary`

## 2. DB Schema — UserProfile and New JobPosting Columns

- [x] 2.1 Create `tests/__init__.py` (empty)
- [x] 2.2 Create `tests/test_storage.py` with tests for `UserProfile`, `save_profile`, `get_profile`, `update_job_analysis`, `update_job_tracking` — run and verify they FAIL
- [x] 2.3 Update `src/storage.py`: replace `from src.config import DB_PATH` with `from src.config import DATABASE_URL`; change `create_engine` to use `DATABASE_URL` (postgres dialect); remove `expire_on_commit` workaround if unneeded
- [x] 2.4 Add `UserProfile` SQLModel table to `src/storage.py` (id=1, graduation_date, location, visa_status, skills, projects)
- [x] 2.5 Add `status`, `notes`, `ai_analysis` columns to `JobPosting` in `src/storage.py`
- [x] 2.6 Add `save_profile()`, `get_profile()`, `update_job_analysis()`, `update_job_tracking()` functions to `src/storage.py`
- [x] 2.7 Run `tests/test_storage.py` — verify all tests PASS

## 3. AI Analysis Module

- [x] 3.1 Create `tests/test_ai_analysis.py` with tests for `analyze_job()` and `parse_resume()` — run and verify they FAIL
- [x] 3.2 Create `src/ai_analysis.py` with `analyze_job(job, profile)` using `claude-haiku-4-5-20251001` and `parse_resume(pdf_bytes)` using `claude-sonnet-4-6`
- [x] 3.3 Run `tests/test_ai_analysis.py` — verify all tests PASS

## 4. Settings Routes (Backend)

- [x] 4.1 Add `redirect` to Flask imports in `src/web.py`
- [x] 4.2 Add imports for `UserProfile`, `get_profile`, `save_profile`, `update_job_tracking`, `parse_resume` in `src/web.py`
- [x] 4.3 Add `GET/POST /settings` route to `src/web.py`
- [x] 4.4 Add `POST /api/settings/parse-resume` route to `src/web.py`
- [x] 4.5 Add `PATCH /api/jobs/<job_id>` route to `src/web.py`
- [x] 4.6 Extend `api_jobs()` with `status`, `days`, and `dismissed` query params and filter logic
- [x] 4.7 Add `status`, `notes`, `ai_analysis`, `seen_today` fields to the `/api/jobs` JSON response

## 5. Settings Page UI

- [x] 5.1 Create `templates/settings.html` with resume upload section and profile form (graduation_date, location, visa_status, skills, projects)
- [x] 5.2 Add JS `parseResume()` function that posts to `/api/settings/parse-resume` and pre-fills form fields
- [x] 5.3 Add Settings link in `templates/index.html` header

## 6. Integrate AI Analysis into Scraper

- [x] 6.1 Add imports for `analyze_job`, `get_profile`, `update_job_analysis` in `src/scraper.py`
- [x] 6.2 After `new_jobs` loop in `run_scrape()`, call `analyze_job()` per new job if profile exists and persist result

## 7. Update Job Board UI

- [x] 7.1 Add pill-group CSS styles (status pills, date pills) to `templates/index.html`
- [x] 7.2 Add AI chip strip CSS (disqualifier, caution, match, requirements, ai-empty) to `templates/index.html`
- [x] 7.3 Add tracking cell CSS (status-select, notes-textarea, colour states) to `templates/index.html`
- [x] 7.4 Add dismissed row CSS (`tr.dismissed`) and new-badge CSS to `templates/index.html`
- [x] 7.5 Split controls into two rows: row 1 (existing), row 2 (status pills, date pills, show-dismissed toggle)
- [x] 7.6 Add JS pill group click handlers and `getActivePill()` helper
- [x] 7.7 Update `loadJobs()` to pass `status`, `days`, `dismissed` params
- [x] 7.8 Add `renderAnalysis(aiJson)` JS function (chip strip renderer)
- [x] 7.9 Add `renderStatusSelect(job)` JS function and `updateJob()` async helper
- [x] 7.10 Update row renderer to include AI strip, tracking cell (status select + notes textarea), and new-badge

## 8. Infrastructure — Supabase

- [x] 8.1 Remove `!jobs.db` exception from `.gitignore` (jobs.db no longer tracked in git)
- [x] 8.2 Remove "Commit updated database" step from `.github/workflows/scrape.yml`; add `DATABASE_URL` to the `env:` block in the scrape step
- [ ] 8.3 Add `DATABASE_URL` secret to GitHub Actions (repo Settings → Secrets → Actions)
- [ ] 8.4 Add `DATABASE_URL` and `ANTHROPIC_API_KEY` environment variables to Railway

## 9. Verification

- [x] 9.1 Run `pytest tests/ -v` — all tests PASS
- [ ] 9.2 Run `python main.py --web` and verify: `/settings` loads, form saves and persists, job cards show AI chips or "set up profile" prompt, status dropdown updates persist, notes save on blur, status and date filters work, dismissed rows hidden by default and revealed by toggle
- [ ] 9.3 Deploy to Railway and verify the app connects to Supabase successfully
