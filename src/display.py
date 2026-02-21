"""
display.py
----------
Rich-powered CLI display for job results.

Functions
---------
print_jobs(jobs)   - Render a list of JobPosting objects as a formatted table.
print_summary(n)   - Print a one-line summary after the scrape.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich import box

from src.storage import JobPosting

console = Console()


def print_jobs(jobs: list[JobPosting]) -> None:
    """
    Print a Rich table of job postings to the terminal.

    Columns:
        #       - row number
        Role    - the role category we searched for
        Title   - page/posting title (truncated to 50 chars)
        Location- location tag from our search
        Published - date the posting was published (if known)
        URL     - full link (clickable in most terminals)
    """
    if not jobs:
        console.print("\n[yellow]No new jobs found for today.[/yellow]\n")
        return

    table = Table(
        box=box.ROUNDED,
        title=f"[bold green]Daily Job Digest — {len(jobs)} new posting(s)[/bold green]",
        show_lines=True,
        highlight=True,
        expand=False,
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Role", style="cyan", max_width=20)
    table.add_column("Title", style="bold white", max_width=45)
    table.add_column("Loc", style="magenta", max_width=16)
    table.add_column("Published", style="yellow", max_width=12)
    table.add_column("URL", style="blue underline", max_width=60)

    for idx, job in enumerate(jobs, start=1):
        # Shorten title if it's very long
        title = job.title if len(job.title) <= 50 else job.title[:47] + "..."

        # Clean up published date: strip time portion if present
        published = (job.published or "unknown")[:10]

        table.add_row(
            str(idx),
            job.role,
            title,
            job.location,
            published,
            job.url,
        )

    console.print()
    console.print(table)
    console.print()


def print_summary(new_count: int) -> None:
    """Print a brief one-line summary after a scrape run."""
    if new_count == 0:
        console.print("[dim]Scrape complete. No new postings.[/dim]")
    else:
        console.print(
            f"[bold green]Scrape complete.[/bold green] "
            f"[white]{new_count} new job(s) added to the database.[/white]"
        )
