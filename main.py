"""
main.py
-------
Entry point for the job scraper.

Usage
-----
    python main.py --now      # Scrape immediately, notify via Telegram, exit
    python main.py --web      # Launch the web UI at http://127.0.0.1:5000
    python main.py --list     # Print all jobs in the database, exit
    python main.py --today    # Print today's jobs, exit
    python main.py --help     # Show this help text, exit
    python main.py            # Start the daily scheduler (08:00 UTC)
"""

from __future__ import annotations

import sys


def _print_help() -> None:
    print(__doc__)


def _do_scrape() -> None:
    """Run one full scrape cycle, display results, and send Telegram digest."""
    from src.display import print_jobs, print_summary
    from src.notify import send_digest
    from src.scraper import run_scrape

    new_jobs = run_scrape()
    print_jobs(new_jobs)
    print_summary(len(new_jobs))
    send_digest(new_jobs)


def main() -> None:
    from src.storage import init_db

    # Ensure the database and tables exist before anything else.
    init_db()

    args = sys.argv[1:]

    # ------------------------------------------------------------------ #
    # --help : show usage
    # ------------------------------------------------------------------ #
    if "--help" in args or "-h" in args:
        _print_help()
        return

    # ------------------------------------------------------------------ #
    # --web  :  launch the Flask job board
    # ------------------------------------------------------------------ #
    if "--web" in args:
        from src.web import run as run_web
        run_web(debug="--debug" in args)
        return

    # ------------------------------------------------------------------ #
    # --now  :  run once immediately, notify, exit
    # ------------------------------------------------------------------ #
    if "--now" in args:
        print("Running a one-off scrape...\n")
        _do_scrape()
        return

    # ------------------------------------------------------------------ #
    # --list :  show everything in the database, exit
    # ------------------------------------------------------------------ #
    if "--list" in args:
        from src.display import print_jobs
        from src.storage import get_all_jobs

        jobs = get_all_jobs()
        if not jobs:
            print("No jobs in database yet. Run with --now to fetch some.")
        else:
            print_jobs(jobs)
            print(f"Total: {len(jobs)} job(s) in database.")
        return

    # ------------------------------------------------------------------ #
    # --today : show only today's new postings, exit
    # ------------------------------------------------------------------ #
    if "--today" in args:
        from src.display import print_jobs
        from src.storage import get_todays_jobs

        jobs = get_todays_jobs()
        print_jobs(jobs)
        return

    # ------------------------------------------------------------------ #
    # Default: start the daily scheduler
    # ------------------------------------------------------------------ #
    from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
    from src.config import SCHEDULE_HOUR, SCHEDULE_MINUTE

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _do_scrape,
        trigger="cron",
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        id="daily_scrape",
    )

    print(
        f"Scheduler started. "
        f"Next scrape at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC daily."
    )
    print("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
