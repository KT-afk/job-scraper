## ADDED Requirements

### Requirement: Per-job AI analysis
The system SHALL analyze each new job posting against the saved user profile using an AI model and store the result as a JSON string on the job row.

#### Scenario: Analysis runs when profile exists and new jobs are found
- **WHEN** a scrape run completes and new jobs are saved AND a user profile exists
- **THEN** the system SHALL call `analyze_job(job, profile)` for each new job and persist the result via `update_job_analysis()`

#### Scenario: Analysis skipped when no profile exists
- **WHEN** a scrape run completes and no user profile is set up
- **THEN** the system SHALL skip AI analysis and print a notice to set up a profile

#### Scenario: Analysis failure does not break scrape
- **WHEN** the AI API call fails for a job
- **THEN** `analyze_job()` SHALL return `None` and the job SHALL remain saved with `ai_analysis = NULL`

### Requirement: Analysis result structure
The `analyze_job()` function SHALL return a dict with exactly these keys: `disqualifiers` (hard blockers), `caution` (soft concerns), `matched_projects` (user's relevant projects), `key_requirements` (3–5 bullet points of what the role needs).

#### Scenario: Well-formed API response
- **WHEN** the AI returns valid JSON matching the schema
- **THEN** `analyze_job()` SHALL return a dict with all four keys present

#### Scenario: Malformed or error API response
- **WHEN** the AI returns invalid JSON or the API raises an exception
- **THEN** `analyze_job()` SHALL return `None`

### Requirement: AI analysis displayed in web UI
The web UI SHALL display the AI analysis for each job inline below the job title, using visually distinct chips for each category.

#### Scenario: Job has analysis
- **WHEN** a job card is rendered and `ai_analysis` is non-null
- **THEN** the card SHALL show chips for disqualifiers (red), cautions (amber), matched projects (green), and key requirements (grey)

#### Scenario: Job has no analysis
- **WHEN** a job card is rendered and `ai_analysis` is null
- **THEN** the card SHALL show a prompt linking to `/settings`
