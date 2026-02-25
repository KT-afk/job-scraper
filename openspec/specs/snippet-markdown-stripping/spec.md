## ADDED Requirements

### Requirement: Markdown is stripped from job snippets before storage
The system SHALL strip common markdown formatting from Exa page text before storing it as a job snippet. A `_strip_markdown(text: str) -> str` helper SHALL be added to `src/scraper.py` and applied to the `text` field when building `JobPosting.snippet`.

Formatting to strip:
- ATX headers (`# H1`, `## H2`, up to `###### H6`) — remove the leading `#` characters and space, keeping the heading text
- Bold (`**text**`) — remove the `**` markers, keeping the inner text
- Italic (`*text*`) — remove the `*` markers, keeping the inner text

#### Scenario: Header markers are stripped
- **WHEN** `_strip_markdown("## About Us\nWe build things.")` is called
- **THEN** it returns `"About Us\nWe build things."`

#### Scenario: Bold markers are stripped
- **WHEN** `_strip_markdown("**Requirements:** Python")` is called
- **THEN** it returns `"Requirements: Python"`

#### Scenario: Plain text is unchanged
- **WHEN** `_strip_markdown("We are looking for a junior engineer.")` is called
- **THEN** it returns `"We are looking for a junior engineer."`

#### Scenario: H1 header markers are stripped
- **WHEN** `_strip_markdown("# Title\nBody text")` is called
- **THEN** it returns `"Title\nBody text"`
