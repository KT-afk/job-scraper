## 1. Visa Negation Detection

- [x] 1.1 Add `VISA_NEGATIONS` list to `src/config.py` after `VISA_KEYWORDS` (13 phrases covering "not eligible", "no sponsorship", "does not sponsor", "do not sponsor", "unable to sponsor", "cannot sponsor", "not able to sponsor", "not sponsoring", "without sponsorship", "sponsorship is not available", "not provide sponsorship", "ineligible for sponsorship", "visa sponsorship is not offered")
- [x] 1.2 Import `VISA_NEGATIONS` in `src/scraper.py` alongside existing config imports
- [x] 1.3 Update `_detect_visa()` to check negation phrases before positive keywords — return `False` if any negation matches, keeping `location_searched` early-return intact
- [x] 1.4 Write tests in `tests/test_scraper_filters.py`: negation suppresses positive, positive-only returns True, location_searched overrides negation, no keywords returns False, "do not sponsor" variant, "ineligible" variant

## 2. Written-Out Year Exclusion

- [x] 2.1 Update `_build_exclude_keywords()` in `src/config.py` to generate `"{Y} or more years"`, `"minimum {Y} years"`, `"at least {Y} years"` for Y in range(TARGET_MAX_YEARS+1, 16) alongside existing numeric forms
- [x] 2.2 Write tests verifying written-out phrases appear in `EXCLUDE_KEYWORDS`, numeric phrases still present, and phrases for years ≤ TARGET_MAX_YEARS are absent

## 3. Filter List Extensions

- [x] 3.1 Add to `EXCLUDE_DOMAINS` in `src/config.py`: `"rubyonremote.com"`, `"jobstreet.com.sg"`, `"remoterocketship.com"`, `"workatastartup.com"`
- [x] 3.2 Add to `EXCLUDE_ROLE_KEYWORDS` in `src/config.py`: `"accounting"`, `"bookkeeping"`, `"payroll"`, `"finance manager"`
- [x] 3.3 Add to `EXCLUDE_TITLE_PATTERNS` in `src/config.py`: `"remote jobs"`, `" developer jobs"`, `" engineer jobs"`, `"remote jobs 2026"`
- [x] 3.4 Write tests verifying all new entries are present in their respective lists

## 4. Snippet Markdown Stripping

- [x] 4.1 Add `_strip_markdown(text: str) -> str` helper to `src/scraper.py` using `re.sub` to strip ATX headers (`#{1,6} `), bold (`**text**`), and italic (`*text*`)
- [x] 4.2 Apply `_strip_markdown()` to `result.get("text", "")` when building `JobPosting.snippet` in `run_scrape()`
- [x] 4.3 Write tests for `_strip_markdown`: H1/H2 header stripping, bold stripping, plain text passthrough

## 5. Verification

- [x] 5.1 Run full test suite (`.venv/bin/pytest -v`) — all existing 30 tests plus new tests must pass
- [ ] 5.2 Commit all changes with descriptive message
