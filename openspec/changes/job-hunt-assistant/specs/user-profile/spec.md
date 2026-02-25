## ADDED Requirements

### Requirement: User profile storage
The system SHALL maintain a single-row user profile in the database containing the user's graduation date, current location, visa/work authorisation status, technical skills, and a JSON array of personal projects.

#### Scenario: Profile does not exist on first use
- **WHEN** no profile has been saved
- **THEN** `get_profile()` SHALL return `None`

#### Scenario: Save and retrieve a profile
- **WHEN** a `UserProfile` is saved via `save_profile()`
- **THEN** `get_profile()` SHALL return the profile with all fields intact

#### Scenario: Saving a profile overwrites any existing profile
- **WHEN** `save_profile()` is called when a profile already exists
- **THEN** the existing profile SHALL be replaced with the new values

### Requirement: Settings page
The system SHALL expose a web page at `/settings` that renders a form pre-filled with the current profile (if one exists) and allows the user to save changes.

#### Scenario: GET /settings with no existing profile
- **WHEN** the user visits `/settings` and no profile is saved
- **THEN** the page SHALL render with all form fields empty

#### Scenario: GET /settings with existing profile
- **WHEN** the user visits `/settings` and a profile exists
- **THEN** the page SHALL render with form fields pre-filled from the saved profile

#### Scenario: POST /settings saves profile and redirects
- **WHEN** the user submits the settings form
- **THEN** the system SHALL save the profile and redirect to `/settings`

### Requirement: Resume PDF parsing
The system SHALL expose a `POST /api/settings/parse-resume` endpoint that accepts a PDF file upload and returns extracted profile fields as JSON.

#### Scenario: Valid PDF upload
- **WHEN** a PDF file is uploaded to `/api/settings/parse-resume`
- **THEN** the system SHALL return JSON with keys: `graduation_date`, `location`, `visa_status`, `skills`, `projects`

#### Scenario: No file in request
- **WHEN** the endpoint is called with no file attached
- **THEN** the system SHALL return HTTP 400 with `{"error": "No file uploaded"}`

#### Scenario: Parsing failure
- **WHEN** the AI call fails or returns unparseable output
- **THEN** the system SHALL return HTTP 500 with `{"error": "Failed to parse resume"}`
