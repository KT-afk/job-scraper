## ADDED Requirements

### Requirement: Per-job application status
Each job posting SHALL have a `status` field with one of these values: `none`, `interested`, `applied`, `interviewing`, `offer`, `rejected`, `dismissed`. The default SHALL be `none`.

#### Scenario: New job has default status
- **WHEN** a job is saved during a scrape
- **THEN** its `status` SHALL be `"none"`

#### Scenario: Status update persists
- **WHEN** `update_job_tracking(job_id, status="applied")` is called
- **THEN** subsequent reads of that job SHALL return `status == "applied"`

#### Scenario: Update for unknown job ID returns False
- **WHEN** `update_job_tracking()` is called with a job ID not in the database
- **THEN** the function SHALL return `False`

### Requirement: Per-job notes
Each job posting SHALL have a `notes` field for freeform text. The default SHALL be an empty string.

#### Scenario: Notes update persists
- **WHEN** `update_job_tracking(job_id, notes="finish project first")` is called
- **THEN** subsequent reads of that job SHALL return the saved notes

### Requirement: PATCH /api/jobs/<id> endpoint
The system SHALL expose a `PATCH /api/jobs/<id>` endpoint that accepts `status` and/or `notes` in the JSON body and persists the update.

#### Scenario: Valid PATCH updates the job
- **WHEN** `PATCH /api/jobs/<id>` is called with `{"status": "interested"}`
- **THEN** the system SHALL return HTTP 200 with `{"ok": true}` and the job status SHALL be updated

#### Scenario: PATCH for unknown job returns 404
- **WHEN** `PATCH /api/jobs/<nonexistent>` is called
- **THEN** the system SHALL return HTTP 404

### Requirement: Status and dismissed filters in web UI
The web UI SHALL allow filtering jobs by status and toggling visibility of dismissed jobs.

#### Scenario: Status pill filters results
- **WHEN** the user selects the "Applied" status pill
- **THEN** only jobs with `status == "applied"` SHALL be shown

#### Scenario: Dismissed jobs hidden by default
- **WHEN** the job board loads
- **THEN** jobs with `status == "dismissed"` SHALL NOT be shown

#### Scenario: Show dismissed toggle reveals dismissed jobs
- **WHEN** the user activates the "Show dismissed" toggle
- **THEN** dismissed jobs SHALL appear with reduced visual prominence (faded / strikethrough)

### Requirement: Date range filter in web UI
The web UI SHALL allow filtering jobs by published date using preset pills (Today, 2 days, 3 days, This week, Any time).

#### Scenario: Date pill filters by published date
- **WHEN** the user selects "Today"
- **THEN** only jobs with `published` date matching today SHALL be shown
