## ADDED Requirements

### Requirement: Visa negation suppresses false-positive tagging
The system SHALL check a list of negation phrases against the job title and text before checking positive visa keywords. If any negation phrase is found, the job SHALL be tagged `visa_sponsored = False` regardless of whether positive keywords also appear.

#### Scenario: Negation phrase present with positive keyword
- **WHEN** job text contains "not eligible for sponsorship" AND "visa sponsorship"
- **THEN** `_detect_visa()` returns `False`

#### Scenario: Positive keyword with no negation
- **WHEN** job text contains "we sponsor visa" and no negation phrases
- **THEN** `_detect_visa()` returns `True`

#### Scenario: location_searched is visa sponsorship
- **WHEN** the result's `location_searched` field contains "visa"
- **THEN** `_detect_visa()` returns `True` regardless of negation phrases in text

#### Scenario: No visa keywords or negations
- **WHEN** job text contains no visa keywords and no negation phrases
- **THEN** `_detect_visa()` returns `False`

### Requirement: VISA_NEGATIONS list is exported from config
The system SHALL define `VISA_NEGATIONS: list[str]` in `src/config.py`, covering at minimum: "not eligible", "no sponsorship", "does not sponsor", "do not sponsor", "unable to sponsor", "cannot sponsor", "not able to sponsor", "not sponsoring", "without sponsorship", "sponsorship is not available", "not provide sponsorship", "ineligible for sponsorship", "visa sponsorship is not offered".

#### Scenario: Negation list is importable
- **WHEN** `from src.config import VISA_NEGATIONS` is called
- **THEN** it returns a non-empty list of strings

### Requirement: Filter data lists are extended with missing entries
The system SHALL include the following entries that were previously missing:

**EXCLUDE_DOMAINS**: `rubyonremote.com`, `jobstreet.com.sg`, `remoterocketship.com`, `workatastartup.com`

**EXCLUDE_ROLE_KEYWORDS**: `accounting`, `bookkeeping`, `payroll`, `finance manager`

**EXCLUDE_TITLE_PATTERNS**: `remote jobs`, ` developer jobs`, ` engineer jobs`, `remote jobs 2026`

#### Scenario: Missing domain is in EXCLUDE_DOMAINS
- **WHEN** `EXCLUDE_DOMAINS` is imported from `src.config`
- **THEN** it contains `"rubyonremote.com"`, `"jobstreet.com.sg"`, `"remoterocketship.com"`, `"workatastartup.com"`

#### Scenario: Finance role keyword triggers exclusion
- **WHEN** a result title contains "accounting"
- **THEN** `_is_excluded()` returns `True`

#### Scenario: Aggregator title pattern triggers junk filter
- **WHEN** a result title contains "remote jobs"
- **THEN** `_is_junk()` returns `True`
