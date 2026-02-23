# Job Hunt Assistant — Design Doc
**Date:** 2026-02-23

## Problem

The scraper finds jobs but three friction points slow down the job search:

1. **Relevance** — Listings slip through with hard disqualifiers (must be based in X, graduation date requirements, no visa sponsorship) that only surface after reading the full listing.
2. **Tracking** — No way to track application status and notes per job. LinkedIn saves are insufficient.
3. **Speed** — Tailoring applications takes ~2hrs because it's unclear which projects to highlight per role.

## Solution

Extend the scraper into a personal job hunt assistant with three features:

1. **User Profile + Settings Page** — Store personal details once, parsed from resume upload.
2. **AI Pre-screening** — Claude analyzes each new job against the user profile and flags disqualifiers + tailoring hints before the user clicks through.
3. **Application Tracking** — Status and notes per job, filterable in the web UI.

---

## Design

### 1. User Profile (Settings Page)

**Flow:**
- User uploads resume (PDF) via settings page
- Claude parses resume and pre-fills profile form
- User reviews and saves

**Profile fields:**
- `graduation_date` — used to detect graduation year requirements
- `location` — current location / citizenship
- `visa_status` — e.g. "needs sponsorship", "on student visa", "open work permit"
- `projects` — JSON array of `{ name, description }` (2-3 lines each)
- `skills` — comma-separated list of languages and frameworks

**Storage:** Single-row `UserProfile` table in SQLite.

**Routes:**
- `GET /settings` — render settings form (pre-filled if profile exists)
- `POST /settings` — save profile
- `POST /api/settings/parse-resume` — upload PDF, return parsed profile JSON

---

### 2. AI Pre-screening

**Trigger:** After each new job is saved to DB during a scrape run.

**Input to Claude:**
- Job title + full snippet
- User profile (graduation date, location, visa status, projects, skills)

**Output (structured JSON):**
```json
{
  "disqualifiers": ["Must be based in US", "Requires 2022 graduation or later"],
  "caution": ["Prefers local candidates", "Mentions relocation budget limited"],
  "matched_projects": ["job-scraper", "portfolio-site"],
  "key_requirements": [
    "Python or Go backend",
    "Experience with REST APIs",
    "Strong fundamentals in data structures"
  ]
}
```

**Storage:** `ai_analysis` JSON column on `JobPosting`.

**Display:** Shown on each job card in the web UI — disqualifiers flagged prominently (red), cautions in amber, matched projects and key requirements as hints.

**Note:** Pre-screening only runs if a `UserProfile` exists. Jobs scraped before profile setup will show "No analysis — set up your profile in Settings."

---

### 3. Application Tracking

**Status values:** `none → interested → applied → interviewing → offer → rejected`

**Per-job fields:**
- `status` — enum string, default `none`
- `notes` — freeform text, e.g. "finish portfolio project first"

**UI:**
- Status dropdown on each job card (updates via PATCH request)
- Notes textarea (auto-saves on blur)
- Filter bar extended with status filter: view All / Interested / Applied / Interviewing

**Routes:**
- `PATCH /api/jobs/<id>` — update `status` and/or `notes`

---

## DB Changes

### New table: `userprofile`
| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | Always 1 (single row) |
| `graduation_date` | VARCHAR | e.g. "2024-06" |
| `location` | VARCHAR | e.g. "Singapore" |
| `visa_status` | VARCHAR | freeform |
| `skills` | VARCHAR | comma-separated |
| `projects` | TEXT | JSON array |

### Modified table: `jobposting`
| Column | Type | Default |
|---|---|---|
| `status` | VARCHAR | `"none"` |
| `notes` | TEXT | `""` |
| `ai_analysis` | TEXT | `null` (JSON) |

---

## New Dependencies

- `anthropic` — Claude API SDK for pre-screening and resume parsing

---

## New Files

- `src/ai_analysis.py` — Claude API calls: `analyze_job(job, profile)` and `parse_resume(pdf_text)`
- `templates/settings.html` — Settings page UI

## Modified Files

- `src/storage.py` — Add `UserProfile` model, new columns on `JobPosting`
- `src/scraper.py` — Call `analyze_job()` after saving each new job
- `src/web.py` — Add `/settings`, `PATCH /api/jobs/<id>` routes
- `templates/index.html` — Show AI analysis on job cards, status/notes controls, status filter
- `requirements.txt` — Add `anthropic`
