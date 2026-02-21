"""
notify.py
---------
Telegram notification for the daily job digest.

Setup (one-time):
1. Message @BotFather on Telegram → /newbot → copy the token.
2. Start a chat with your new bot (send it /start).
3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id.
4. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to your .env file.

Usage:
    from src.notify import send_digest
    send_digest(new_jobs)
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage import JobPosting

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


# Telegram message length limit (4096 chars); we stay under it.
_MAX_MSG_LEN = 4000


def _send_message(text: str) -> None:
    """Send a single message via the Telegram Bot API (no third-party deps)."""
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


def _format_job(job: "JobPosting", idx: int) -> str:
    """Format a single job posting as a Telegram HTML snippet."""
    date = (job.published or "")[:10] or "unknown date"

    tags: list[str] = []
    tags.append(f"#{job.discipline}" if job.discipline else "#Job")
    if job.visa_sponsored:
        tags.append("#VisaSponsored")
    if job.remote_ok:
        tags.append("#Remote")
    if job.location.lower() == "singapore":
        tags.append("#Singapore")

    tag_str = "  ".join(tags)

    return (
        f"{idx}. <b><a href=\"{job.url}\">{job.title}</a></b>\n"
        f"   {tag_str}\n"
        f"   {date}"
    )


def send_digest(jobs: "list[JobPosting]") -> None:
    """
    Send a Telegram message summarising the new jobs found in this run.
    Long digests are split into multiple messages to stay under the 4096-char limit.
    """
    if not jobs:
        _send_message("No new early-career jobs found today.")
        return

    header = (
        f"<b>Job Digest — {len(jobs)} new posting{'s' if len(jobs) != 1 else ''}</b>\n"
        f"{'─' * 30}\n"
    )

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

    print(f"[Notify] Sending {len(chunks)} Telegram message(s)...")
    for chunk in chunks:
        _send_message(chunk)
    print("[Notify] Done.")
