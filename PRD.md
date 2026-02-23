# Product Requirements Document
## Personal Job Scraper

**Version:** 1.0  
**Date:** February 2026  
**Author:** Personal project  

---

## 1. Overview

### 1.1 Problem Statement

Early-career engineers (0–2 years experience) waste significant time manually checking multiple job boards daily. Most job boards are designed for experienced hires, mix in irrelevant results (India-based roles, senior positions, aggregator pages), and offer no personalised filtering by discipline or visa/remote requirements.

### 1.2 Solution

A personal, automated job scraper that:
- Runs daily via GitHub Actions
- Searches for early-career roles across Backend, Frontend, Full Stack, DevOps, and Infra/SRE disciplines
- Filters aggressively to surface only relevant results
- Delivers a daily Telegram digest
- Provides a hosted web UI (Railway) for browsing and filtering the full archive

### 1.3 Target User

**Solo user — the owner of the project.** This is a personal tool, not a multi-tenant product. There is no authentication, no user accounts, no signup flow.

---

## 2. Goals

| Goal | Metric |
|---|---|
| Surface relevant junior job postings daily | ≥10 real postings per daily run |
| Eliminate junk results | 0 aggregator/listing pages in results |
| Never miss a day | GitHub Actions runs at 08:00 UTC, 365 days/year |
| Reduce manual job-search time | Check one Telegram message instead of 5+ job boards |
| Persistent browsable archive | Web UI shows all-time results with filters |

---

## 3. Non-Goals

- Multi-user support or authentication
- Applying to jobs automatically
- Tracking application status
- Parsing full job description text (only snippets)
- Supporting job boards other than Exa search results
- Mobile app

---

## 4. Features

### 4.1 Scraping Engine

| Feature | Detail |
|---|---|
| **Data source** | Exa AI neural search API (v1.1.7) |
| **Disciplines** | Backend, Frontend, Full Stack, DevOps, Infra/SRE |
| **Locations** | Singapore, Remote, Visa Sponsorship |
| **Experience target** | 0–2 years (junior/new grad queries) |
| **Schedule** | Daily at 08:00 UTC via GitHub Actions |
| **Manual trigger** | `python main.py --now` or GitHub Actions `workflow_dispatch` |
| **Deduplication** | URL-based Exa ID — same posting never stored twice |
| **Snippet size** | 1500 characters per result for context |

### 4.2 Filtering

| Filter | Behaviour |
|---|---|
| **Seniority exclusion** | Drops Senior, Sr., Staff, Principal, Lead, Manager, Director, VP titles |
| **Experience exclusion** | Drops results mentioning 3+ years and above |
| **Location exclusion** | Drops India and major Indian cities (Bangalore, Chennai, Mumbai, etc.) |
| **Junk domain filter** | Drops 40+ known aggregator domains (Indeed searches, Glassdoor listings, LinkedIn job search, RemoteOK, H1BConnect, Reddit, Medium, etc.) |
| **Junk title filter** | Drops listing-style titles ("Best Remote Jobs 2025", "X Jobs in Singapore (with Salaries)", "3000+", etc.) |

### 4.3 Enrichment

| Field | How it's set |
|---|---|
| **Discipline** | Mapped from the query string used (e.g. "Junior Backend Engineer" → `Backend`) |
| **Visa Sponsored** | True if visa keywords appear in title/snippet, or location search was "visa sponsorship" |
| **Remote OK** | True if remote keywords appear in title/snippet, or location search was "remote" |
| **Date** | Published date from Exa if available; falls back to scrape date marked as `(scraped)` |

### 4.4 Storage

| Detail | Value |
|---|---|
| **Database** | SQLite (`jobs.db`) |
| **ORM** | SQLModel (SQLAlchemy + Pydantic) |
| **Persistence on Railway** | `jobs.db` committed back to GitHub after each scrape; Railway redeploys from repo |
| **Schema** | `id`, `url`, `title`, `published`, `author`, `snippet`, `role`, `discipline`, `location`, `visa_sponsored`, `remote_ok`, `seen_at` |

### 4.5 Telegram Notifications

| Detail | Value |
|---|---|
| **Trigger** | Sent automatically after every scrape (scheduled or manual) |
| **Header** | Day + full date (e.g. "Saturday, 21 Feb 2026") + new posting count |
| **Per-job format** | Clickable title → URL, 📅 date (or scraped date), 🏷 discipline · location · visa/remote labels |
| **No results** | Sends "No new jobs found today" message |
| **Long digests** | Split into multiple messages (≤3800 chars each) |
| **Web UI link** | Footer links to hosted job board if `WEB_URL` is set |
| **Implementation** | Pure stdlib `urllib` — no extra dependencies |

### 4.6 Web UI

| Detail | Value |
|---|---|
| **Framework** | Flask + Gunicorn |
| **Hosting** | Railway (auto-deploys on git push) |
| **Search** | Live full-text search across title and snippet (debounced 250ms) |
| **Filters** | Discipline dropdown, Location dropdown, Visa Sponsored toggle, Remote toggle |
| **Sort** | Newest first (by published date) or Title A–Z |
| **Stats strip** | Total jobs, breakdown by discipline, visa count, remote count |
| **Design** | Dark theme, responsive, no external CSS framework |

### 4.7 CLI

| Command | Behaviour |
|---|---|
| `python main.py --now` | Scrape immediately, print results, send Telegram digest |
| `python main.py --web` | Start Flask dev server at localhost:5000 |
| `python main.py --list` | Print all jobs in DB as Rich table |
| `python main.py --today` | Print only today's jobs as Rich table |
| `python main.py --help` | Show usage |
| `python main.py` | Start APScheduler for daily runs at 08:00 UTC |

---

## 5. Architecture

```
┌─────────────────────────────────────────────┐
│              GitHub Actions                 │
│  Cron: 08:00 UTC daily                      │
│  python main.py --now                       │
│    │                                        │
│    ├── exa_client.py  (fetch)               │
│    ├── scraper.py     (filter + enrich)     │
│    ├── storage.py     (deduplicate + save)  │
│    ├── notify.py      (Telegram digest)     │
│    └── git commit jobs.db && git push       │
└────────────────────┬────────────────────────┘
                     │ push triggers redeploy
┌────────────────────▼────────────────────────┐
│                 Railway                     │
│  gunicorn src.web:app                       │
│  Flask web UI  ←  jobs.db (from repo)      │
│  https://your-app.up.railway.app            │
└─────────────────────────────────────────────┘

User receives:
  Telegram message → digest with links
  Browser → Railway web UI → full archive
```

---

## 6. Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `EXA_API_KEY` | Yes | Exa neural search API |
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | Your personal chat ID |
| `WEB_URL` | No | Hosted web UI URL (shown in Telegram footer) |

---

## 7. Constraints & Assumptions

- **Exa rate limit:** 10 QPS. With ~63 queries per run, runs take ~7–10 seconds. No throttling needed.
- **Exa cost:** ~$0.054/run × 30 days ≈ $1.62/month, within the $10 free tier.
- **Railway free tier:** 500 hours/month — sufficient for a low-traffic personal tool.
- **SQLite on Railway:** The DB is read-only on Railway (served from the committed file). Writes happen only in GitHub Actions.
- **Result quality:** Exa returns neural search results, not scraped listings. Some noise is expected; the junk filter handles most of it.

---

## 8. Future Considerations

| Idea | Notes |
|---|---|
| Company name extraction | Parse company from title/snippet for cleaner display |
| Salary detection | Flag postings that mention salary ranges |
| Apply tracking | Add an "applied / saved / rejected" status per posting |
| More sources | Add LinkedIn API, Greenhouse, Lever direct feeds |
| Weekly summary | Send a weekly roll-up of best postings |
| Slack notification | Alternative to Telegram |
| Search quality scoring | Rank results by relevance to profile, not just date |
