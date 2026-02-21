"""
notify.py
---------
Telegram notification for the daily job digest.

Setup (one-time):
1. Message @BotFather on Telegram → /newbot → copy the token.
2. Start a chat with your new bot (send it /start).
3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id.
4. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to your .env file.
5. Optionally set WEB_URL to your hosted job board URL.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage import JobPosting

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEB_URL

# Telegram hard limit is 4096 chars; stay comfortably under it.
_MAX_MSG_LEN = 3800


def _send_message(text: str) -> None:
    """Send one message via the Telegram Bot API (stdlib only, no extra deps)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Notify] Telegram credentials not set — skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                print(f"[Notify] Telegram returned HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001
        print(f"[Notify] Failed to send Telegram message: {exc}")


def _resolve_date(job: "JobPosting") -> str:
    """
    Return the best available date string for a job.

    Priority:
      1. published  — the date the posting was published (from Exa)
      2. seen_at    — the date WE first saw it (always present)

    Always returns a YYYY-MM-DD string, never "unknown".
    """
    if job.published:
        return job.published[:10]
    # seen_at is an ISO timestamp like "2026-02-21T08:03:22.123456+00:00"
    return job.seen_at[:10] + " (scraped)"


def _format_job(job: "JobPosting", idx: int) -> str:
    """
    Format one job as a readable Telegram HTML block.

    Example output:
        3. Junior Backend Engineer at Stripe
           📅 2026-02-21
           🏷 Backend · Singapore · Visa Sponsor
           🔗 https://stripe.com/jobs/...
    """
    date = _resolve_date(job)

    # Build label list
    labels: list[str] = []
    if job.discipline:
        labels.append(job.discipline)

    loc = job.location.lower()
    if loc == "singapore":
        labels.append("Singapore")
    elif loc == "remote":
        labels.append("Remote")
    elif "visa" in loc:
        pass  # covered by visa_sponsored flag below

    if job.visa_sponsored:
        labels.append("Visa Sponsor")
    if job.remote_ok and loc != "remote":
        labels.append("Remote OK")

    label_str = " · ".join(labels) if labels else "—"

    return (
        f"{idx}. <b><a href=\"{job.url}\">{job.title}</a></b>\n"
        f"   \U0001f4c5 {date}\n"
        f"   \U0001f3f7 {label_str}"
    )


def send_digest(jobs: "list[JobPosting]") -> None:
    """
    Send a Telegram digest of new jobs.
    Splits into multiple messages if the list is long.
    Appends a link to the web UI if WEB_URL is configured.
    """
    today = datetime.now(timezone.utc).strftime("%A, %d %b %Y")  # e.g. "Friday, 21 Feb 2026"

    if not jobs:
        _send_message(
            f"\U0001f4cb <b>Job Digest — {today}</b>\n\n"
            "No new early-career jobs found today. Check again tomorrow."
        )
        return

    header = (
        f"\U0001f4cb <b>Job Digest — {today}</b>\n"
        f"<b>{len(jobs)} new posting{'s' if len(jobs) != 1 else ''} found</b>\n"
        f"{'─' * 32}\n\n"
    )

    # Footer shown on the last chunk only
    footer_parts: list[str] = []
    if WEB_URL:
        footer_parts.append(f"\n\U0001f310 <a href=\"{WEB_URL}\">View full job board</a>")
    footer = "".join(footer_parts)

    # Split into chunks that fit within Telegram's limit
    chunks: list[str] = []
    current = header

    for idx, job in enumerate(jobs, start=1):
        entry = _format_job(job, idx) + "\n\n"
        if len(current) + len(entry) > _MAX_MSG_LEN:
            chunks.append(current.rstrip())
            current = entry
        else:
            current += entry

    if current.strip():
        chunks.append(current.rstrip())

    # Append footer to the last chunk
    if footer and chunks:
        last = chunks[-1]
        if len(last) + len(footer) <= _MAX_MSG_LEN:
            chunks[-1] = last + footer
        else:
            chunks.append(footer.strip())

    print(f"[Notify] Sending {len(chunks)} Telegram message(s)...")
    for chunk in chunks:
        _send_message(chunk)
    print("[Notify] Done.")
