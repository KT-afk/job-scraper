## Context

The job scraper fetches results from the Exa search API and filters them through a chain of helpers in `src/scraper.py` and data lists in `src/config.py`. Six bugs cause bad data to reach the database and web UI:

1. `_detect_visa()` has no negation check — jobs saying "not eligible for sponsorship" get tagged as visa-sponsored
2. `_build_exclude_keywords()` only generates numeric year patterns ("3+ years") — written-out forms slip through
3. Four aggregator domains are missing from `EXCLUDE_DOMAINS`
4. Finance/accounting role keywords are missing from `EXCLUDE_ROLE_KEYWORDS`
5. Two aggregator title patterns are missing from `EXCLUDE_TITLE_PATTERNS`
6. Exa page text contains raw markdown (`##`, `**bold**`) that is stored verbatim in the snippet field

All bugs are isolated to two files with no DB or API impact.

## Goals / Non-Goals

**Goals:**
- Fix all 6 filter quality bugs in `src/config.py` and `src/scraper.py`
- Each fix covered by at least one failing-then-passing test
- No regressions in existing 30 passing tests

**Non-Goals:**
- Rebuilding the filter architecture
- Adding new filter dimensions beyond the 6 identified bugs
- Changes to the DB schema, web UI, or notification system

## Decisions

**Decision: Check negations before positives in `_detect_visa()`**
A separate `VISA_NEGATIONS` list in `config.py` is checked first. If any negation phrase matches, return `False` immediately without checking positive keywords. Alternative: regex with negative lookbehind — rejected because it couples the negation patterns to specific keyword positions, making the list harder to maintain.

**Decision: `location_searched="visa sponsorship"` short-circuits all text checks**
If the Exa query was explicitly for visa-sponsoring jobs, the result is always tagged `True` regardless of text content. This preserves existing intent: jobs returned by that query are presumed visa-friendly at the query level.

**Decision: Written-out year patterns generated at build time in `_build_exclude_keywords()`**
Same function, same `TARGET_MAX_YEARS` upper bound, same range (3–15). No separate constant — keeps the single source of truth for the year threshold.

**Decision: `_strip_markdown()` applied to snippet only, not title**
Titles from Exa are already plain text. Only the `text` field (page body) contains markdown. Applying strip to title would be a no-op and add noise.

## Risks / Trade-offs

- **Negation false negatives**: A job could say "We do not provide sponsorship but we will sponsor exceptional candidates" — the negation phrase matches first and suppresses the positive. Mitigation: negation list is conservative (exact phrases only, not partial matches); the trade-off (fewer false positives) is acceptable for a personal tool.
- **Markdown stripping edge cases**: `re.sub` patterns for bold/italic may mangle code snippets in job descriptions (e.g., `*args`). Mitigation: italic stripping uses non-greedy match with word-boundary awareness; impact is cosmetic only.
- **Domain list maintenance**: `EXCLUDE_DOMAINS` is a static list that will grow stale. No mitigation in scope — accepted as a known limitation of the approach.
