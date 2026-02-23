# Vercel Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the Flask web dashboard to Vercel as a serverless function, replacing the original Railway plan, while keeping GitHub Actions as the scraper runner and Supabase as the database.

**Architecture:** Vercel routes all HTTP requests to the Flask WSGI app via a thin `api/index.py` entry point and a `vercel.json` routing config. The Flask app itself is unchanged — no gunicorn, Vercel handles the WSGI adapter. Supabase connection is identical; `DATABASE_URL` becomes a Vercel environment variable instead of a Railway one.

**Tech Stack:** Flask (existing), Vercel Python runtime, Supabase Postgres (existing), psycopg v3 (existing)

---

### Task 1: Verify DB connection is working locally

Before any deployment work, confirm the Supabase connection is healthy. This unblocks everything downstream.

**Files:**
- Read: `.env` (already contains `DATABASE_URL`)

**Step 1: Run the connection test**

```bash
.venv/bin/python -c "
from dotenv import load_dotenv
load_dotenv()
from src.storage import init_db
init_db()
print('DB connection OK')
"
```

Expected output: `DB connection OK`

If you see `password authentication failed`, go to Supabase dashboard → Settings → Database → reveal the password and update `.env` with the exact value (no brackets).

If you see an SSL or import error, run:
```bash
.venv/bin/pip install "psycopg[binary]>=3.1.0"
```
then retry.

**Step 2: Run the full test suite to confirm nothing is broken**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 16 tests pass (9 in test_storage.py, 7 in test_ai_analysis.py). These use SQLite in-memory so they pass even if Supabase is down.

---

### Task 2: Add `vercel.json`

Vercel needs to know (a) this is a Python project, (b) all routes go to `api/index.py`.

**Files:**
- Create: `vercel.json`

**Step 1: Create the file**

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ]
}
```

**Step 2: Verify the file was created**

```bash
cat vercel.json
```

Expected: the JSON content printed above.

---

### Task 3: Add `api/index.py` (Vercel entry point)

Vercel's Python runtime looks for an ASGI/WSGI `app` object in the file specified by `builds[].src`. We point it at a thin module that just re-exports the Flask `app`.

**Files:**
- Create: `api/index.py`

**Step 1: Create the `api/` directory and entry point**

```python
# api/index.py
# Vercel serverless entry point.
# Vercel imports this file and looks for a WSGI `app` callable.
from src.web import app  # noqa: F401 — re-exported for Vercel
```

That's the entire file. Vercel handles the WSGI ↔ serverless bridging automatically.

**Step 2: Verify the import works locally**

```bash
.venv/bin/python -c "from api.index import app; print('import OK')"
```

Expected: `import OK`

> **Note on `init_db()`:** `src/web.py` already calls `init_db()` at module import time (line 51), so tables are created on the first cold start in Vercel automatically.

---

### Task 4: Smoke-test the Flask app locally

Run the web server locally and manually verify the UI loads and API endpoints respond.

**Step 1: Start the web server**

```bash
.venv/bin/python main.py --web
```

Expected output:
```
Job board running at http://127.0.0.1:5000
```

**Step 2: Open in browser and verify**

Visit `http://127.0.0.1:5000` — the job board should load (may show 0 jobs if DB is empty, that's fine).

Visit `http://127.0.0.1:5000/settings` — the settings/profile page should load.

Visit `http://127.0.0.1:5000/api/jobs` — should return a JSON array.

**Step 3: Stop the server** — `Ctrl+C`

---

### Task 5: Install Vercel CLI and deploy

**Step 1: Install Vercel CLI (if not already installed)**

```bash
npm install -g vercel
```

Verify: `vercel --version` → should print a version number.

**Step 2: Log in to Vercel**

```bash
vercel login
```

Follow the browser prompt to authenticate.

**Step 3: Deploy (first time — interactive setup)**

```bash
vercel
```

When prompted:
- **Set up and deploy?** → Yes
- **Which scope?** → your personal account
- **Link to existing project?** → No (create new)
- **Project name?** → `job-scraper` (or any name you like)
- **Which directory?** → `.` (current directory)
- **Override settings?** → No

Vercel will build and deploy. It will print a preview URL like:
`https://job-scraper-xxxx.vercel.app`

**Step 4: Set environment variables in Vercel**

```bash
vercel env add DATABASE_URL
```
When prompted, paste the full `DATABASE_URL` value from `.env` (without quotes).
Select: **Production**, **Preview**, **Development** (all three).

Repeat for:
```bash
vercel env add ANTHROPIC_API_KEY
vercel env add EXA_API_KEY
vercel env add TELEGRAM_BOT_TOKEN
vercel env add TELEGRAM_CHAT_ID
```

> `TELEGRAM_*` vars are used by the scraper (GitHub Actions), not the web app, but setting them here is harmless and keeps config centralised.

**Step 5: Redeploy to production with env vars**

```bash
vercel --prod
```

This triggers a production deployment. Vercel will print the final production URL:
`https://job-scraper.vercel.app` (or similar).

---

### Task 6: Update GitHub Actions secrets

The scraper workflow (`scrape.yml`) needs `DATABASE_URL` and `ANTHROPIC_API_KEY` as GitHub Actions secrets. This is a manual step in the GitHub UI.

**Step 1: Go to GitHub → your repo → Settings → Secrets and variables → Actions**

**Step 2: Add/update these secrets:**

| Secret name | Value |
|---|---|
| `DATABASE_URL` | Full Supabase connection string from `.env` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key from `.env` |

These should already exist from previous setup — just confirm they're present and correct.

**Step 3: Trigger the scraper manually to verify**

Go to GitHub → Actions → "Daily Job Scrape" → Run workflow.

Check the run completes without errors. New jobs should appear in the Vercel-hosted dashboard.

---

### Task 7: Update `WEB_URL` secret in GitHub Actions (optional but recommended)

The scraper sends Telegram notifications that include a link to the web dashboard. Update `WEB_URL` to point to the new Vercel URL.

**Step 1: In GitHub → Settings → Secrets**, update:

| Secret name | Value |
|---|---|
| `WEB_URL` | `https://your-project.vercel.app` |

---

### Task 8: Final verification

**Step 1: Visit the production Vercel URL** in a browser. Confirm:
- [ ] Job board loads
- [ ] `/settings` page loads
- [ ] `/api/jobs` returns JSON
- [ ] `/api/stats` returns JSON

**Step 2: (Optional) Upload a resume on the settings page** and confirm AI parsing works (requires `ANTHROPIC_API_KEY` to be set in Vercel).

**Step 3: Commit the new files**

```bash
git add vercel.json api/index.py docs/plans/2026-02-23-vercel-deployment.md
git commit -m "feat: add Vercel deployment config"
git push
```

---

## Summary of files changed

| File | Action |
|---|---|
| `vercel.json` | **Created** — Vercel build + routing config |
| `api/index.py` | **Created** — thin WSGI entry point for Vercel |
| `railway.toml` | **Unchanged** — can delete later if desired |
| `Procfile` | **Unchanged** — can delete later if desired |
| All `src/` files | **Unchanged** |
| GitHub Actions | **Manual** — confirm secrets exist |
