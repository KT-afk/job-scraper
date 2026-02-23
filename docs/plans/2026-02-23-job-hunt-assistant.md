s# Job Hunt Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the job scraper into a personal job hunt assistant with AI pre-screening per job, application status/notes tracking, and a settings page with resume upload.

**Architecture:** Add `UserProfile` DB model and three new columns to `JobPosting` (`status`, `notes`, `ai_analysis`). A new `src/ai_analysis.py` module calls the Anthropic API to screen each new job against the user's profile and parse uploaded resumes. The Flask web UI gains a `/settings` page, a `PATCH /api/jobs/<id>` endpoint, and job cards updated to show AI analysis + tracking controls.

**Tech Stack:** Python, SQLModel, Flask, Anthropic Python SDK (`claude-haiku-4-5-20251001` for per-job analysis, `claude-sonnet-4-6` for resume parsing), pytest, pytest-mock

---

### Task 1: Add Dependencies and Config

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py`
- Modify: `.env.example`

**Step 1: Add to requirements.txt**

Append these lines:
```
anthropic>=0.40.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

**Step 2: Add ANTHROPIC_API_KEY to src/config.py**

After the existing `EXA_API_KEY` line, add:
```python
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
```

**Step 3: Add to .env.example**

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

**Step 4: Install**

```bash
pip install anthropic pytest pytest-mock
```

**Step 5: Commit**

```bash
git add requirements.txt src/config.py .env.example
git commit -m "chore: add anthropic SDK and pytest dependencies"
```

---

### Task 2: DB Schema — UserProfile Model + New JobPosting Columns

**Files:**
- Modify: `src/storage.py`
- Create: `tests/__init__.py`
- Create: `tests/test_storage.py`

**Context:** `storage.py` uses a module-level `_engine`. The `init_db()` function only creates tables with `SQLModel.metadata.create_all(_engine)` — it won't add new columns to *existing* tables. We need a migration step. We also need to expose `_engine` as replaceable for testing.

**Step 1: Write failing tests**

Create `tests/__init__.py` (empty file).

Create `tests/test_storage.py`:
```python
import pytest
from sqlmodel import create_engine
import src.storage as storage_module
from src.storage import (
    init_db, UserProfile, save_profile, get_profile,
    JobPosting, save_job, update_job_analysis, update_job_tracking
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point storage at a fresh temp DB for each test."""
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    monkeypatch.setattr(storage_module, "_engine", engine)
    init_db()
    return engine


def test_get_profile_returns_none_when_empty():
    assert get_profile() is None


def test_save_and_get_profile():
    profile = UserProfile(
        graduation_date="2024-06",
        location="Singapore",
        visa_status="needs sponsorship",
        skills="Python, Flask",
        projects='[{"name": "job-scraper", "description": "automated scraper"}]',
    )
    save_profile(profile)
    result = get_profile()
    assert result.graduation_date == "2024-06"
    assert result.location == "Singapore"


def test_save_profile_overwrites_existing():
    save_profile(UserProfile(graduation_date="2023-06", location="SG", visa_status="", skills="", projects="[]"))
    save_profile(UserProfile(graduation_date="2024-06", location="SG", visa_status="", skills="", projects="[]"))
    assert get_profile().graduation_date == "2024-06"


def test_job_posting_defaults():
    job = JobPosting(
        id="test-1", url="https://example.com", title="Junior Engineer",
        snippet="test", role="Junior Engineer", location="Singapore", seen_at="2026-02-23",
    )
    assert job.status == "none"
    assert job.notes == ""
    assert job.ai_analysis is None


def test_update_job_analysis():
    job = JobPosting(
        id="test-2", url="https://example.com", title="Backend Eng",
        snippet="test", role="Backend", location="Singapore", seen_at="2026-02-23",
    )
    save_job(job)
    update_job_analysis("test-2", '{"disqualifiers": ["US only"]}')
    from sqlmodel import Session
    with Session(storage_module._engine) as s:
        saved = s.get(JobPosting, "test-2")
        assert saved.ai_analysis == '{"disqualifiers": ["US only"]}'


def test_update_job_tracking():
    job = JobPosting(
        id="test-3", url="https://example.com", title="Frontend Eng",
        snippet="test", role="Frontend", location="remote", seen_at="2026-02-23",
    )
    save_job(job)
    update_job_tracking("test-3", status="applied", notes="finish project first")
    from sqlmodel import Session
    with Session(storage_module._engine) as s:
        saved = s.get(JobPosting, "test-3")
        assert saved.status == "applied"
        assert saved.notes == "finish project first"
```

**Step 2: Run tests — verify they fail**

```bash
pytest tests/test_storage.py -v
```
Expected: FAIL (ImportError on `UserProfile`, `save_profile`, etc.)

**Step 3: Update src/storage.py**

Add these imports at the top:
```python
from sqlalchemy import text
```

Add the `UserProfile` model after `JobPosting`:
```python
class UserProfile(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)  # always row 1
    graduation_date: str = ""
    location: str = ""
    visa_status: str = ""
    skills: str = ""
    projects: str = ""  # JSON array string
```

Add new columns to `JobPosting` (after `seen_at`):
```python
    status: str = Field(default="none")        # none/interested/applied/interviewing/offer/rejected
    notes: str = Field(default="")
    ai_analysis: Optional[str] = Field(default=None)  # JSON string
```

Update `init_db()` to also run a migration:
```python
def init_db() -> None:
    """Create all tables and migrate existing ones."""
    SQLModel.metadata.create_all(_engine)
    _migrate()


def _migrate() -> None:
    """Add new columns to jobposting if upgrading from an older schema."""
    new_cols = [
        ("status", "VARCHAR DEFAULT 'none'"),
        ("notes", "TEXT DEFAULT ''"),
        ("ai_analysis", "TEXT"),
    ]
    with _engine.connect() as conn:
        existing = [row[1] for row in conn.execute(text("PRAGMA table_info(jobposting)"))]
        for col, definition in new_cols:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE jobposting ADD COLUMN {col} {definition}"))
        conn.commit()
```

Add new functions at the bottom of `storage.py`:
```python
def save_profile(profile: UserProfile) -> None:
    """Upsert the single user profile row."""
    profile.id = 1
    with Session(_engine, **_session_kwargs) as session:
        existing = session.get(UserProfile, 1)
        if existing:
            for key, val in profile.dict(exclude={"id"}).items():
                setattr(existing, key, val)
            session.add(existing)
        else:
            session.add(profile)
        session.commit()


def get_profile() -> Optional[UserProfile]:
    """Return the user profile, or None if not set up yet."""
    with Session(_engine) as session:
        return session.get(UserProfile, 1)


def update_job_analysis(job_id: str, analysis_json: str) -> None:
    """Store the AI analysis JSON on a job posting."""
    with Session(_engine, **_session_kwargs) as session:
        job = session.get(JobPosting, job_id)
        if job:
            job.ai_analysis = analysis_json
            session.add(job)
            session.commit()


def update_job_tracking(job_id: str, status: str = None, notes: str = None) -> bool:
    """Update status and/or notes on a job. Returns False if job not found."""
    with Session(_engine, **_session_kwargs) as session:
        job = session.get(JobPosting, job_id)
        if not job:
            return False
        if status is not None:
            job.status = status
        if notes is not None:
            job.notes = notes
        session.add(job)
        session.commit()
        return True
```

**Step 4: Run tests — verify they pass**

```bash
pytest tests/test_storage.py -v
```
Expected: All PASS

**Step 5: Commit**

```bash
git add src/storage.py tests/__init__.py tests/test_storage.py
git commit -m "feat: add UserProfile model and status/notes/ai_analysis to JobPosting"
```

---

### Task 3: AI Analysis Module

**Files:**
- Create: `src/ai_analysis.py`
- Create: `tests/test_ai_analysis.py`

**Step 1: Write failing tests**

Create `tests/test_ai_analysis.py`:
```python
import json
import pytest
from unittest.mock import MagicMock, patch
from src.storage import UserProfile, JobPosting
from src.ai_analysis import analyze_job, parse_resume


@pytest.fixture
def profile():
    return UserProfile(
        graduation_date="2024-06",
        location="Singapore",
        visa_status="needs sponsorship",
        skills="Python, Flask, React",
        projects='[{"name": "job-scraper", "description": "automated job scraper using Exa API"}]',
    )


@pytest.fixture
def job():
    return JobPosting(
        id="test-1", url="https://example.com/job",
        title="Junior Backend Engineer",
        snippet="Must be based in US. 0-2 years experience. Python preferred.",
        role="Junior Backend Engineer", location="Singapore",
        seen_at="2026-02-23", discipline="Backend",
    )


def _mock_client(response_text):
    mock_msg = MagicMock()
    mock_msg.content[0].text = response_text
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


def test_analyze_job_returns_structured_result(profile, job):
    response = json.dumps({
        "disqualifiers": ["Must be based in US"],
        "caution": [],
        "matched_projects": ["job-scraper"],
        "key_requirements": ["Python backend", "REST APIs"],
    })
    with patch("src.ai_analysis.anthropic.Anthropic", return_value=_mock_client(response)):
        result = analyze_job(job, profile)
    assert result["disqualifiers"] == ["Must be based in US"]
    assert result["matched_projects"] == ["job-scraper"]
    assert len(result["key_requirements"]) == 2


def test_analyze_job_returns_none_on_api_error(profile, job):
    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = Exception("API error")
        result = analyze_job(job, profile)
    assert result is None


def test_parse_resume_returns_profile_fields():
    response = json.dumps({
        "graduation_date": "2024-06",
        "location": "Singapore",
        "visa_status": "student visa, needs sponsorship",
        "skills": "Python, Flask, React",
        "projects": [{"name": "job-scraper", "description": "automated scraper"}],
    })
    with patch("src.ai_analysis.anthropic.Anthropic", return_value=_mock_client(response)):
        result = parse_resume(b"fake pdf bytes")
    assert result["graduation_date"] == "2024-06"
    assert result["location"] == "Singapore"
    assert isinstance(result["projects"], list)


def test_parse_resume_returns_none_on_error():
    with patch("src.ai_analysis.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = Exception("timeout")
        result = parse_resume(b"fake pdf bytes")
    assert result is None
```

**Step 2: Run tests — verify they fail**

```bash
pytest tests/test_ai_analysis.py -v
```
Expected: FAIL (ImportError on `src.ai_analysis`)

**Step 3: Create src/ai_analysis.py**

```python
"""
ai_analysis.py
--------------
Anthropic API calls for:
  - analyze_job(): screen a job posting against the user's profile
  - parse_resume(): extract profile fields from a PDF resume
"""

from __future__ import annotations

import base64
import json
from typing import Optional

import anthropic

from src.config import ANTHROPIC_API_KEY
from src.storage import JobPosting, UserProfile

_ANALYSIS_MODEL = "claude-haiku-4-5-20251001"
_PARSE_MODEL = "claude-sonnet-4-6"


def analyze_job(job: JobPosting, profile: UserProfile) -> Optional[dict]:
    """
    Analyze a job posting against the user profile.
    Returns a dict with keys: disqualifiers, caution, matched_projects, key_requirements.
    Returns None on any error (API failure, parse failure).
    """
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        projects = json.loads(profile.projects) if profile.projects else []
        project_lines = "\n".join(
            f"  - {p['name']}: {p.get('description', '')}" for p in projects
        )

        prompt = f"""You are helping a job seeker decide whether to apply for a role.

User Profile:
- Graduation date: {profile.graduation_date}
- Location / Citizenship: {profile.location}
- Visa status: {profile.visa_status}
- Skills: {profile.skills}
- Projects:
{project_lines}

Job Posting:
Title: {job.title}
Content: {job.snippet}

Return ONLY valid JSON with exactly these keys:
{{
  "disqualifiers": ["hard blockers e.g. must be US citizen, must have graduated before X date"],
  "caution": ["soft concerns worth noting e.g. prefers local candidates"],
  "matched_projects": ["names of the user's projects most relevant to this role"],
  "key_requirements": ["3-5 bullet points of what the role actually needs"]
}}"""

        response = client.messages.create(
            model=_ANALYSIS_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.content[0].text)

    except Exception as e:
        print(f"[ai_analysis] Error analyzing job {job.id}: {e}")
        return None


def parse_resume(pdf_bytes: bytes) -> Optional[dict]:
    """
    Parse a resume PDF and extract profile fields.
    Returns a dict with keys: graduation_date, location, visa_status, skills, projects.
    Returns None on any error.
    """
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model=_PARSE_MODEL,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.b64encode(pdf_bytes).decode(),
                            },
                        },
                        {
                            "type": "text",
                            "text": """Extract information from this resume. Return ONLY valid JSON:
{
  "graduation_date": "most recent graduation in YYYY-MM format, or empty string",
  "location": "current location or citizenship",
  "visa_status": "visa or work authorisation info, or empty string",
  "skills": "comma-separated technical skills",
  "projects": [{"name": "project name", "description": "2-3 line description"}]
}""",
                        },
                    ],
                }
            ],
        )
        return json.loads(response.content[0].text)

    except Exception as e:
        print(f"[ai_analysis] Error parsing resume: {e}")
        return None
```

**Step 4: Run tests — verify they pass**

```bash
pytest tests/test_ai_analysis.py -v
```
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ai_analysis.py tests/test_ai_analysis.py
git commit -m "feat: add AI analysis module for job pre-screening and resume parsing"
```

---

### Task 4: Settings Page — Backend Routes

**Files:**
- Modify: `src/web.py`

**Context:** `web.py` imports `_engine` directly from `storage` at module level. The `app` is defined at module level too. Add new routes after the existing ones.

**Step 1: Add imports to src/web.py**

At the top where other imports are, add:
```python
import json
from flask import redirect, request as flask_request
from src.storage import UserProfile, get_profile, save_profile, update_job_tracking
from src.ai_analysis import parse_resume
```

Note: `request` is already imported from flask. The `redirect` needs to be added. Update the existing flask import line to:
```python
from flask import Flask, jsonify, redirect, render_template, request
```

**Step 2: Add settings routes to src/web.py**

Add after the existing routes, before `run()`:
```python
@app.route("/settings", methods=["GET", "POST"])
def settings():
    profile = get_profile()
    if request.method == "POST":
        new_profile = UserProfile(
            graduation_date=request.form.get("graduation_date", ""),
            location=request.form.get("location", ""),
            visa_status=request.form.get("visa_status", ""),
            skills=request.form.get("skills", ""),
            projects=request.form.get("projects", "[]"),
        )
        save_profile(new_profile)
        return redirect("/settings")
    return render_template("settings.html", profile=profile)


@app.post("/api/settings/parse-resume")
def api_parse_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    pdf_bytes = request.files["resume"].read()
    result = parse_resume(pdf_bytes)
    if result is None:
        return jsonify({"error": "Failed to parse resume"}), 500
    return jsonify(result)


@app.route("/api/jobs/<job_id>", methods=["PATCH"])
def api_update_job(job_id):
    data = request.get_json() or {}
    found = update_job_tracking(
        job_id,
        status=data.get("status"),
        notes=data.get("notes"),
    )
    if not found:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})
```

**Step 3: Update /api/jobs to include new fields + date/dismissed filters**

In `api_jobs()`, add these query params after the existing filters:
```python
days_filter      = request.args.get("days", "").strip()       # "1","2","3","7"
status_filter    = request.args.get("status", "").strip()     # "interested","applied",etc.
show_dismissed   = request.args.get("dismissed") == "1"
```

Add WHERE clauses:
```python
# Hide dismissed by default
if not show_dismissed:
    stmt = stmt.where(JobPosting.status != "dismissed")

if status_filter:
    stmt = stmt.where(JobPosting.status == status_filter)

if days_filter.isdigit():
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days_filter))).date().isoformat()
    stmt = stmt.where(JobPosting.published >= cutoff)
```

Update the dict inside `jsonify([...])` to add:
```python
            "status":        j.status,
            "notes":         j.notes or "",
            "ai_analysis":   j.ai_analysis,
            "seen_today":    j.seen_at[:10] == datetime.now(timezone.utc).date().isoformat(),
```

**Step 4: Test manually**

```bash
python main.py --web
```

- Visit http://localhost:5000/settings — should render (even if template missing, you'll get a clear error)
- `curl -X PATCH http://localhost:5000/api/jobs/nonexistent -H "Content-Type: application/json" -d '{"status":"interested"}'` — should return 404

**Step 5: Commit**

```bash
git add src/web.py
git commit -m "feat: add settings, parse-resume, and job tracking API routes"
```

---

### Task 5: Settings Page — UI Template

**Files:**
- Create: `templates/settings.html`

**Step 1: Create templates/settings.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Settings — Job Scraper</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f0f0f; color: #e0e0e0; font-family: 'Courier New', monospace; padding: 2rem; max-width: 700px; }
    h1 { color: #7dd3fc; margin-bottom: 1.5rem; }
    h2 { color: #94a3b8; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }
    .nav { margin-bottom: 2rem; }
    .nav a { color: #7dd3fc; text-decoration: none; }
    .nav a:hover { text-decoration: underline; }
    .card { background: #161616; border: 1px solid #262626; border-radius: 6px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .form-group { margin-bottom: 1.2rem; }
    label { display: block; color: #94a3b8; font-size: 0.8rem; margin-bottom: 0.4rem; }
    input[type="text"], textarea {
      width: 100%; background: #0f0f0f; border: 1px solid #333; color: #e0e0e0;
      padding: 0.5rem 0.75rem; border-radius: 4px; font-family: inherit; font-size: 0.9rem;
    }
    input[type="text"]:focus, textarea:focus { outline: none; border-color: #7dd3fc; }
    textarea { min-height: 140px; resize: vertical; }
    input[type="file"] { color: #94a3b8; font-size: 0.85rem; }
    .btn { background: #7dd3fc; color: #0f0f0f; border: none; padding: 0.5rem 1.2rem;
           border-radius: 4px; cursor: pointer; font-family: inherit; font-weight: bold; font-size: 0.9rem; }
    .btn:hover { background: #38bdf8; }
    .btn-ghost { background: transparent; color: #94a3b8; border: 1px solid #333; }
    .btn-ghost:hover { border-color: #7dd3fc; color: #7dd3fc; }
    .hint { color: #475569; font-size: 0.78rem; margin-top: 0.3rem; }
    #parse-status { font-size: 0.82rem; margin-top: 0.6rem; min-height: 1.2rem; }
    .saved-badge { color: #4ade80; font-size: 0.82rem; margin-left: 0.75rem; display: none; }
  </style>
</head>
<body>
  <div class="nav"><a href="/">← Back to jobs</a></div>
  <h1>Profile Settings</h1>

  <div class="card">
    <h2>Import from Resume</h2>
    <p style="color:#64748b; font-size:0.85rem; margin-bottom:1rem;">
      Upload your resume PDF to auto-fill the form below. Review before saving.
    </p>
    <input type="file" id="resume-file" accept=".pdf">
    <br><br>
    <button class="btn" onclick="parseResume()">Parse Resume</button>
    <div id="parse-status"></div>
  </div>

  <form method="POST">
    <div class="card">
      <h2>Your Profile</h2>

      <div class="form-group">
        <label>Graduation Date</label>
        <input type="text" name="graduation_date" id="f-grad"
               value="{{ profile.graduation_date if profile else '' }}"
               placeholder="e.g. 2024-06">
        <div class="hint">Used to detect graduation year requirements in listings.</div>
      </div>

      <div class="form-group">
        <label>Current Location / Citizenship</label>
        <input type="text" name="location" id="f-loc"
               value="{{ profile.location if profile else '' }}"
               placeholder="e.g. Singapore, Singapore PR">
      </div>

      <div class="form-group">
        <label>Visa / Work Authorisation Status</label>
        <input type="text" name="visa_status" id="f-visa"
               value="{{ profile.visa_status if profile else '' }}"
               placeholder="e.g. student visa, needs sponsorship">
      </div>

      <div class="form-group">
        <label>Technical Skills</label>
        <input type="text" name="skills" id="f-skills"
               value="{{ profile.skills if profile else '' }}"
               placeholder="Python, Flask, React, PostgreSQL, Docker">
        <div class="hint">Comma-separated. Used to match against job requirements.</div>
      </div>

      <div class="form-group">
        <label>Projects (JSON)</label>
        <textarea name="projects" id="f-projects">{{ profile.projects if profile else '[]' }}</textarea>
        <div class="hint">Format: [{"name": "project-name", "description": "what it does, tech used"}]</div>
      </div>
    </div>

    <button type="submit" class="btn">Save Profile</button>
    <a href="/" style="color:#64748b; text-decoration:none; margin-left:1rem; font-size:0.9rem;">Cancel</a>
  </form>

  <script>
    async function parseResume() {
      const file = document.getElementById('resume-file').files[0];
      const status = document.getElementById('parse-status');
      if (!file) { status.style.color = '#f87171'; status.textContent = 'Select a PDF first.'; return; }

      status.style.color = '#94a3b8';
      status.textContent = 'Parsing resume...';

      const formData = new FormData();
      formData.append('resume', file);

      try {
        const resp = await fetch('/api/settings/parse-resume', { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.error) {
          status.style.color = '#f87171';
          status.textContent = 'Error: ' + data.error;
          return;
        }

        if (data.graduation_date) document.getElementById('f-grad').value = data.graduation_date;
        if (data.location) document.getElementById('f-loc').value = data.location;
        if (data.visa_status) document.getElementById('f-visa').value = data.visa_status;
        if (data.skills) document.getElementById('f-skills').value = data.skills;
        if (data.projects) document.getElementById('f-projects').value = JSON.stringify(data.projects, null, 2);

        status.style.color = '#4ade80';
        status.textContent = 'Parsed successfully — review the fields below and save.';
      } catch (e) {
        status.style.color = '#f87171';
        status.textContent = 'Failed to reach server.';
      }
    }
  </script>
</body>
</html>
```

**Step 2: Test manually**

```bash
python main.py --web
```

- Visit http://localhost:5000/settings
- Form should render with empty fields (or pre-filled if profile exists)
- Fill in fields manually and click Save — should redirect back and show saved values

**Step 3: Commit**

```bash
git add templates/settings.html
git commit -m "feat: add settings page UI with resume upload"
```

---

### Task 6: Integrate AI Analysis into Scraper

**Files:**
- Modify: `src/scraper.py`

**Step 1: Add AI analysis call after saving jobs in run_scrape()**

Add import at top of `scraper.py`:
```python
import json
from src.ai_analysis import analyze_job
from src.storage import get_profile, update_job_analysis
```

In `run_scrape()`, after the `new_jobs.append(job)` line and before the final `print(...)` summary, add:
```python
    # --- AI pre-screening ---
    profile = get_profile()
    if profile and new_jobs:
        print(f"[Scraper] Running AI analysis on {len(new_jobs)} new job(s)...")
        for job in new_jobs:
            analysis = analyze_job(job, profile)
            if analysis:
                update_job_analysis(job.id, json.dumps(analysis))
                disq = analysis.get("disqualifiers", [])
                flag = " ⛔ " + " · ".join(disq) if disq else ""
                print(f"  [AI] {job.title[:60]}{flag}")
    elif not profile:
        print("[Scraper] No profile set up — skipping AI analysis. Visit /settings to set up.")
```

**Step 2: Test with a manual scrape**

```bash
python main.py --now
```

Expected output includes lines like:
```
[Scraper] Running AI analysis on 3 new job(s)...
  [AI] Junior Backend Engineer at Stripe
  [AI] Software Engineer - Remote ⛔ Must be based in US
[Scraper] Done. New: 3 | ...
```

If no new jobs today, temporarily comment out the `is_known()` check to force re-analysis of one job, then revert.

**Step 3: Commit**

```bash
git add src/scraper.py
git commit -m "feat: run AI pre-screening on new jobs during scrape"
```

---

### Task 7: Update Job Cards UI

**Files:**
- Modify: `templates/index.html`

**Reference design:** `mockup_v2.html` in the project root — use this as the visual spec.

**Context:** `index.html` renders an HTML shell and fetches jobs from `/api/jobs` via JS. Jobs are rendered as table rows in JS. The controls bar gets split into two rows.

**Step 1: Read the existing index.html first**

Read `templates/index.html` to understand current structure before modifying.

**Step 2: Add "Settings" link to the header**

In the `<header>` element, add next to the existing heading:
```html
<a href="/settings" style="margin-left:auto; color:#8892a4; text-decoration:none; font-size:13px; border:1px solid #2a2d3e; padding:6px 12px; border-radius:7px;">⚙ Settings</a>
```

**Step 3: Split controls into two rows**

Replace the single `.controls` div with two rows:

**Row 1** — search, discipline, location, visa, remote, sort (same as current, just remove status from here)

**Row 2** — status pills, date pills, show-dismissed toggle:
```html
<div class="controls-row2">
  <!-- Status pills -->
  <span class="filter-label">Status</span>
  <div class="pill-group" id="status-pills">
    <button class="pill active" data-val="">All</button>
    <button class="pill" data-val="interested">Interested</button>
    <button class="pill" data-val="applied">Applied</button>
    <button class="pill" data-val="interviewing">Interviewing</button>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Date pills -->
  <span class="filter-label">Posted</span>
  <div class="pill-group" id="date-pills">
    <button class="pill active" data-val="">Any time</button>
    <button class="pill" data-val="1">Today</button>
    <button class="pill" data-val="2">2 days</button>
    <button class="pill" data-val="3">3 days</button>
    <button class="pill" data-val="7">This week</button>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Show dismissed toggle -->
  <button class="toggle-btn" id="btn-dismissed" onclick="toggleFilter('dismissed')">
    <span class="toggle-dot"></span> Show dismissed
  </button>
</div>
```

**Step 4: Update JS — pill group click handlers**

```javascript
// Generic pill group handler
document.querySelectorAll('.pill-group').forEach(group => {
  group.querySelectorAll('.pill').forEach(pill => {
    pill.addEventListener('click', () => {
      group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      loadJobs();
    });
  });
});

function getActivePill(groupId) {
  return document.querySelector(`#${groupId} .pill.active`)?.dataset.val || '';
}
```

**Step 5: Update loadJobs() params**

```javascript
const params = new URLSearchParams({
  q:          searchEl.value.trim(),
  discipline: discEl.value,
  location:   locationEl.value,
  sort:       sortEl.value,
  status:     getActivePill('status-pills'),
  days:       getActivePill('date-pills'),
  ...(filters.visa      ? { visa: '1' }      : {}),
  ...(filters.remote    ? { remote: '1' }    : {}),
  ...(filters.dismissed ? { dismissed: '1' } : {}),
});
```

**Step 6: Update card rendering JS**

Replace the existing `tbody.innerHTML = jobs.map(...)` with this updated renderer:

```javascript
// AI analysis — compact chip strip
function renderAnalysis(aiJson) {
  if (!aiJson) return `<span class="ai-empty">No analysis — <a href="/settings">set up profile</a></span>`;
  const a = typeof aiJson === 'string' ? JSON.parse(aiJson) : aiJson;
  const chips = [];
  if (a.disqualifiers?.length)  chips.push(`<span class="ai-chip disqualifier">⛔ ${a.disqualifiers[0]}</span>`);
  if (a.caution?.length)        chips.push(`<span class="ai-chip caution">⚠️ ${a.caution[0]}</span>`);
  if (a.matched_projects?.length) chips.push(`<span class="ai-chip match">✅ ${a.matched_projects.join(', ')}</span>`);
  if (a.key_requirements?.length) chips.push(`<span class="ai-chip requirements">📋 ${a.key_requirements.slice(0,3).join(' · ')}</span>`);
  return chips.join('');
}

// Status select with colour states
function renderStatusSelect(job) {
  const statuses = ['none','interested','applied','interviewing','offer','rejected','dismissed'];
  const opts = statuses.map(s =>
    `<option value="${s}" ${job.status === s ? 'selected' : ''}>${s}</option>`
  ).join('');
  const cls = { interested:'s-interested', applied:'s-applied', interviewing:'s-interview' }[job.status] || '';
  return `<select class="status-select ${cls}" onchange="updateJob('${esc(job.id)}', {status:this.value}); this.className='status-select '+({'interested':'s-interested',applied:'s-applied',interviewing:'s-interview'}[this.value]||'')">${opts}</select>`;
}

async function updateJob(jobId, data) {
  await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  // Reload if dismissed and not showing dismissed
  if (data.status === 'dismissed' && !filters.dismissed) loadJobs();
}

// Row renderer
tbody.innerHTML = jobs.map((j, i) => `
  <tr class="${j.status === 'dismissed' ? 'dismissed' : ''}">
    <td class="date-cell">${i + 1}</td>
    <td class="job-title">
      ${j.seen_today ? '<span class="new-badge">New</span> ' : ''}
      <a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
      ${j.snippet ? `<div class="job-snippet">${esc(j.snippet)}</div>` : ''}
      <div class="ai-strip">${renderAnalysis(j.ai_analysis)}</div>
    </td>
    <td><span class="tag tag-discipline">${esc(j.discipline || '—')}</span></td>
    <td>${locationTags(j)}</td>
    <td class="date-cell">${formatDate(j.published)}</td>
    <td class="tracking-cell">
      ${renderStatusSelect(j)}
      <textarea class="notes-textarea ${j.notes ? 'has-note' : ''}"
        placeholder="Add a note…"
        onblur="updateJob('${esc(job.id)}', {notes:this.value})"
      >${esc(j.notes || '')}</textarea>
    </td>
    <td><a class="link-btn" href="${esc(j.url)}" target="_blank" rel="noopener">Open ↗</a></td>
  </tr>
`).join('');
```

**Step 7: Add CSS**

Add to the `<style>` block (reference `mockup_v2.html` for exact values):
```css
/* Controls row 2 */
.controls-row2 { padding: 8px 32px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; border-bottom:1px solid var(--border); background:var(--bg); }
.filter-label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
.pill-group { display:flex; background:var(--surface); border:1px solid var(--border); border-radius:8px; overflow:hidden; }
.pill { padding:6px 13px; font-size:12px; font-weight:500; color:var(--muted); border:none; background:none; cursor:pointer; border-right:1px solid var(--border); }
.pill:last-child { border-right:none; }
.pill.active { background:#1e2a52; color:#8ba4ff; font-weight:600; }

/* AI chips */
.ai-strip { display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }
.ai-chip { display:inline-flex; align-items:center; padding:2px 8px; border-radius:4px; font-size:11px; white-space:nowrap; }
.ai-chip.disqualifier { background:#2a101080; color:#f87171; border:1px solid #4a1a1a; }
.ai-chip.caution      { background:#2a1e0080; color:#fbbf24; border:1px solid #4a3800; }
.ai-chip.match        { background:#0a2a1080; color:#4ade80; border:1px solid #1a4a28; }
.ai-chip.requirements { background:#1a1e2f80; color:#6b7a99; border:1px solid #2a3050; }
.ai-empty { color:#3a3f5c; font-style:italic; font-size:11px; }
.ai-empty a { color:var(--accent); text-decoration:none; }

/* New badge */
.new-badge { font-size:9px; font-weight:700; padding:2px 6px; border-radius:4px; background:#1e3a20; color:#4ade80; border:1px solid #2a5a30; text-transform:uppercase; letter-spacing:.05em; }

/* Tracking cell */
.tracking-cell { display:flex; flex-direction:column; gap:7px; min-width:180px; }
.status-select { width:100%; background:#12151f; border:1px solid var(--border); border-radius:6px; color:var(--muted); font-size:12px; padding:6px 24px 6px 9px; cursor:pointer; appearance:none; font-family:inherit; }
.status-select.s-interested { border-color:#f59e0b; color:#fcd34d; }
.status-select.s-applied    { border-color:#5b73f7; color:#8ba4ff; }
.status-select.s-interview  { border-color:#3ecf8e; color:#6ee7b7; }
.notes-textarea { width:100%; min-height:60px; background:#12151f; border:1px solid var(--border); border-radius:6px; color:var(--text); font-size:12px; padding:7px 9px; font-family:inherit; resize:vertical; }
.notes-textarea::placeholder { color:#3a3f5c; }
.notes-textarea.has-note { border-color:#2e3a5c; }

/* Dismissed rows */
tr.dismissed td { opacity:0.35; }
tr.dismissed .job-title a { text-decoration:line-through; }
```

**Step 8: Test manually**

```bash
python main.py --web
```

- Row 1 controls: search, discipline, location, visa, remote, sort
- Row 2 controls: status pills, date pills, show dismissed toggle
- Date pills filter by `published` date — "Today" shows only jobs posted today
- Status "dismissed" hides row by default; "Show dismissed" toggle reveals faded rows
- "New" badge appears on jobs scraped today
- AI chips show inline below snippet
- Status select and notes textarea in dedicated column — no empty space

**Step 9: Commit**

```bash
git add templates/index.html src/web.py
git commit -m "feat: two-row controls, date filter, dismissed status, new badge, AI chips"
```

---

### Task 8: Final Verification

**Step 1: Run all tests**

```bash
pytest tests/ -v
```
Expected: All PASS

**Step 2: Run full local end-to-end**

```bash
python main.py --now   # scrape + AI analysis (needs ANTHROPIC_API_KEY in .env)
python main.py --web   # open http://localhost:5000
```

Check:
- [ ] Settings page loads at `/settings`
- [ ] Resume upload parses and pre-fills form
- [ ] Profile saves and persists on refresh
- [ ] Job cards show AI analysis (or "set up profile" prompt for old jobs)
- [ ] Status dropdown updates persist on refresh
- [ ] Notes save on blur
- [ ] Status filter works in the filter bar

**Step 3: Add ANTHROPIC_API_KEY to Railway environment variables**

In the Railway dashboard, add `ANTHROPIC_API_KEY` to the environment variables for the web service.

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: job hunt assistant complete — AI pre-screening, tracking, settings"
```
