# User Flow
## Personal Job Scraper

---

## Flow 1: Daily Automated Run (Primary Flow)

This is the main flow — runs every day without any user action.

```
08:00 UTC
   │
   ▼
GitHub Actions triggers cron job
   │
   ▼
python main.py --now
   │
   ├──► init_db()
   │       └── Creates jobs.db tables if they don't exist
   │
   ├──► exa_client.fetch_jobs()
   │       ├── For each discipline × location pair (63 combinations):
   │       │     "Junior Backend Engineer jobs in Singapore posted recently"
   │       │     "Junior Backend Engineer jobs remote posted recently"
   │       │     "Junior Backend Engineer jobs in visa sponsorship posted recently"
   │       │     ... (repeat for Frontend, FullStack, DevOps, Infra/SRE)
   │       ├── Exa API returns up to 10 results per query
   │       ├── Deduplicates within the fetch run (same URL across queries)
   │       └── Returns flat list of raw result dicts
   │
   ├──► scraper.run_scrape()
   │       For each raw result:
   │         ├── _is_junk()?
   │         │     YES → skip (aggregator site, listing page, article)
   │         │     NO  → continue
   │         ├── _is_excluded()?
   │         │     YES → skip (Senior/5+ years/India keywords)
   │         │     NO  → continue
   │         ├── is_known(id)?
   │         │     YES → skip (already in DB)
   │         │     NO  → continue
   │         ├── Enrich:
   │         │     discipline   ← mapped from query string
   │         │     visa_sponsored ← keyword detection
   │         │     remote_ok    ← keyword detection
   │         └── save_job() → written to jobs.db
   │
   ├──► display.print_jobs()
   │       Prints Rich table to GitHub Actions log
   │       (visible in Actions run output for debugging)
   │
   ├──► notify.send_digest()
   │       ├── Builds message:
   │       │     📋 Job Digest — Saturday, 21 Feb 2026
   │       │     12 new postings found
   │       │     ────────────────────────────────
   │       │
   │       │     1. Junior Backend Engineer at Stripe
   │       │        📅 2026-02-21
   │       │        🏷 Backend · Singapore · Visa Sponsor
   │       │
   │       │     2. Graduate SRE Role - Cloudflare
   │       │        📅 2026-02-21 (scraped)
   │       │        🏷 Infra/SRE · Remote
   │       │     ...
   │       │     🌐 View full job board → https://your-app.railway.app
   │       │
   │       ├── Splits into chunks if > 3800 chars
   │       └── POSTs to Telegram Bot API
   │
   ├──► git add jobs.db
   ├──► git commit "chore: daily scrape 2026-02-21"
   └──► git push
           └── Railway detects new commit → redeploys web UI
```

**User experience at this point:**
- Telegram message arrives in chat
- User taps a job title → opens job posting in browser
- User taps "View full job board" → opens Railway web UI

---

## Flow 2: Browsing the Web UI

```
User opens https://your-app.railway.app
   │
   ▼
Flask renders index.html
   │
   ├── Discipline dropdown populated from DB
   ├── Location dropdown populated from DB
   └── Stats strip + job table loaded via /api/jobs and /api/stats
   │
   ▼
Default view: all jobs, sorted by newest first
   │
   ├── Stats strip shows:
   │     Total: 247  |  Backend: 68  Frontend: 54  FullStack: 89  ...
   │     52 Visa   89 Remote (right-aligned)
   │
   └── Table shows:
         #  │  Job (title + snippet)  │  Discipline  │  Tags  │  Published  │  Seen  │  Link
         1  │  Junior Backend Eng...  │  [Backend]   │  [Singapore] [Visa]  │  2026-02-21  │  ...
         2  │  Graduate SRE - Cloud   │  [Infra/SRE] │  [Remote]            │  2026-02-21  │  ...
         ...

User filters:
   ├── Types in search box → debounced 250ms → /api/jobs?q=python
   ├── Selects "Backend" from discipline dropdown → /api/jobs?discipline=Backend
   ├── Clicks "Visa Sponsored" toggle → /api/jobs?visa=1
   ├── Clicks "Remote" toggle → /api/jobs?remote=1
   ├── Selects location → /api/jobs?location=Singapore
   └── Changes sort → /api/jobs?sort=title

User clicks "Open ↗" → job posting URL opens in new tab
```

---

## Flow 3: Manual Scrape (Ad-hoc)

Two ways to trigger manually:

**Option A — GitHub Actions UI:**
```
github.com → repo → Actions tab
   └── "Daily Job Scrape" workflow
         └── "Run workflow" button → Run
               └── Same as Flow 1, triggered immediately
```

**Option B — Local terminal:**
```
Terminal
   └── python main.py --now
         └── Same as Flow 1, but:
               ├── Uses local .env credentials
               ├── Writes to local jobs.db
               └── Does NOT commit/push to GitHub
```

---

## Flow 4: Browsing via CLI

```
Terminal
   └── python main.py --list
         └── Rich table of ALL jobs in DB
               Columns: # | Role | Title | Loc | Published | URL

   └── python main.py --today
         └── Rich table of TODAY's jobs only (filtered by seen_at date)
```

---

## Flow 5: First-Time Setup

```
1. Clone repo
      git clone https://github.com/you/job-scraper

2. Create .env
      cp .env.example .env
      # Fill in EXA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

3. Install dependencies
      python -m venv .venv && source .venv/bin/activate
      pip install -r requirements.txt

4. Test run
      python main.py --now
      # Should scrape, print table, send Telegram message

5. Deploy web UI (Railway)
      ├── railway.app → New Project → Deploy from GitHub
      ├── Add secrets: EXA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
      └── Copy Railway URL → add as WEB_URL secret in GitHub Actions

6. Activate daily scraping (GitHub Actions)
      ├── Push repo to GitHub
      └── Add secrets:
            EXA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEB_URL
      └── Runs automatically at 08:00 UTC from now on
```

---

## Flow 6: Error States

| Situation | What happens |
|---|---|
| Exa API key invalid | Scraper raises `EnvironmentError`, Actions run fails, no Telegram message |
| Exa query fails (one query) | Warning printed, run continues with remaining queries |
| Telegram credentials missing | Prints warning, skips notification, DB still updated |
| No new jobs found | Sends "No new jobs found today" Telegram message |
| Railway health check fails | Railway retries, check deployment logs |
| DB missing on Railway | `init_db()` creates it on first request |

---

## Data Flow Summary

```
Exa API
  │  raw results (title, url, snippet, date)
  ▼
scraper.py
  │  filtered + enriched results
  ▼
jobs.db (SQLite)
  │
  ├──► notify.py ──► Telegram (daily digest)
  │
  └──► web.py ──► Browser (Railway web UI)
```
