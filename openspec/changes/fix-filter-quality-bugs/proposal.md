## Why

The job scraper's filter and enrichment layer has 6 data-quality bugs that cause false positives (jobs incorrectly tagged as visa-sponsored), missed exclusions (senior/non-SWE roles slipping through), and polluted display data (raw markdown in snippets). These degrade the usefulness of the tool's daily output before any new features are built on top.

## What Changes

- `_detect_visa()` checks negation phrases ("not eligible for sponsorship") before positive keywords, preventing false-positive visa tags
- `_build_exclude_keywords()` generates written-out year patterns ("3 or more years", "minimum 3 years", "at least 3 years") in addition to the existing "3+ years" numeric forms
- `EXCLUDE_DOMAINS` gains 4 missing aggregator domains: `rubyonremote.com`, `jobstreet.com.sg`, `remoterocketship.com`, `workatastartup.com`
- `EXCLUDE_ROLE_KEYWORDS` gains non-SWE terms: `accounting`, `bookkeeping`, `payroll`, `finance manager`
- `EXCLUDE_TITLE_PATTERNS` gains aggregator-style title patterns: `"remote jobs"`, `" developer jobs"`, `" engineer jobs"`, `"remote jobs 2026"`
- A new `_strip_markdown()` helper strips `#` headers, `**bold**`, and `*italic*` from Exa page text before it is stored as a snippet

## Capabilities

### New Capabilities

- `visa-negation-detection`: Detects when job text explicitly negates visa sponsorship and suppresses false-positive tagging
- `written-out-year-exclusion`: Extends the experience filter to catch written-out year phrases alongside numeric ones
- `snippet-markdown-stripping`: Cleans raw Exa page markdown before storing job snippets

### Modified Capabilities

None — no existing spec files exist; all filter lists are implementation details, not spec-level contracts.

## Impact

- `src/config.py`: `VISA_NEGATIONS` list added; `_build_exclude_keywords()` updated; `EXCLUDE_DOMAINS`, `EXCLUDE_ROLE_KEYWORDS`, `EXCLUDE_TITLE_PATTERNS` extended
- `src/scraper.py`: `_detect_visa()` logic updated; `_strip_markdown()` helper added and applied to snippet field
- `tests/test_scraper_filters.py`: New test file covering all changed logic
- No DB schema changes, no API changes, no dependency changes
