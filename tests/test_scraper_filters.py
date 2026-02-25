"""
tests/test_scraper_filters.py
------------------------------
Tests for scraper helper functions: _detect_visa, _strip_markdown,
and config list contents (EXCLUDE_KEYWORDS, EXCLUDE_DOMAINS, etc.).
"""

from src.scraper import _detect_visa


def test_visa_negation_not_eligible_returns_false():
    result = {
        "location_searched": "Singapore",
        "title": "Full Stack Developer at First Horizon Bank",
        "text": "Position not eligible for visa sponsorship. Great benefits.",
    }
    assert _detect_visa(result) is False


def test_visa_positive_keyword_returns_true():
    result = {
        "location_searched": "Singapore",
        "title": "Junior Backend Engineer",
        "text": "We sponsor visa for qualified candidates.",
    }
    assert _detect_visa(result) is True


def test_visa_location_searched_overrides_negation():
    """location_searched='visa sponsorship' should always return True, even if text has negation."""
    result = {
        "location_searched": "visa sponsorship",
        "title": "Any Job",
        "text": "Position not eligible for visa sponsorship.",
    }
    assert _detect_visa(result) is True


def test_visa_no_keywords_returns_false():
    result = {
        "location_searched": "Singapore",
        "title": "Junior Engineer",
        "text": "Great place to work. Competitive salary.",
    }
    assert _detect_visa(result) is False


def test_visa_negation_do_not_sponsor_returns_false():
    result = {
        "location_searched": "Singapore",
        "title": "Junior Engineer",
        "text": "We do not sponsor visa sponsorship applications for this role.",
    }
    assert _detect_visa(result) is False


def test_visa_negation_ineligible_returns_false():
    result = {
        "location_searched": "Singapore",
        "title": "Software Developer",
        "text": "Applicants must be ineligible for sponsorship. We will sponsor only permanent residents.",
    }
    assert _detect_visa(result) is False


from src.config import EXCLUDE_KEYWORDS


def test_written_out_years_excluded():
    assert "3 or more years" in EXCLUDE_KEYWORDS
    assert "minimum 5 years" in EXCLUDE_KEYWORDS
    assert "at least 4 years" in EXCLUDE_KEYWORDS


def test_numeric_years_still_excluded():
    assert "3+ years" in EXCLUDE_KEYWORDS
    assert "10+ years" in EXCLUDE_KEYWORDS


def test_written_out_max_boundary():
    assert "15 or more years" in EXCLUDE_KEYWORDS
    assert "minimum 15 years" in EXCLUDE_KEYWORDS


def test_written_out_within_target_not_excluded():
    # TARGET_MAX_YEARS is 2, so "2 or more years" must NOT be in the list
    assert "2 or more years" not in EXCLUDE_KEYWORDS
    assert "minimum 2 years" not in EXCLUDE_KEYWORDS


# ---------------------------------------------------------------------------
# Filter list extensions (Task 3)
# ---------------------------------------------------------------------------

from src.config import EXCLUDE_DOMAINS, EXCLUDE_ROLE_KEYWORDS, EXCLUDE_TITLE_PATTERNS


def test_missing_domains_present():
    assert "rubyonremote.com" in EXCLUDE_DOMAINS
    assert "jobstreet.com.sg" in EXCLUDE_DOMAINS
    assert "remoterocketship.com" in EXCLUDE_DOMAINS
    assert "workatastartup.com" in EXCLUDE_DOMAINS


def test_non_swe_role_keywords_present():
    for kw in ["accounting", "bookkeeping", "payroll", "finance manager"]:
        assert kw in EXCLUDE_ROLE_KEYWORDS


def test_aggregator_title_patterns_present():
    for pat in ["remote jobs", " developer jobs", " engineer jobs", "remote jobs 2026"]:
        assert pat in EXCLUDE_TITLE_PATTERNS


# ---------------------------------------------------------------------------
# _strip_markdown (Task 4)
# ---------------------------------------------------------------------------

from src.scraper import _strip_markdown


def test_strip_markdown_removes_h2_header():
    assert _strip_markdown("## About Us\nWe build things.") == "About Us\nWe build things."


def test_strip_markdown_removes_h1_header():
    assert _strip_markdown("# Title\nBody text") == "Title\nBody text"


def test_strip_markdown_removes_bold():
    assert _strip_markdown("**Requirements:** Python") == "Requirements: Python"


def test_strip_markdown_passthrough_plain_text():
    text = "We are looking for a junior engineer."
    assert _strip_markdown(text) == text


def test_strip_markdown_removes_italic():
    assert _strip_markdown("*important* detail") == "important detail"


# ---------------------------------------------------------------------------
# Functional filter tests (calling _is_excluded / _is_junk directly)
# ---------------------------------------------------------------------------

from src.scraper import _is_excluded, _is_junk


def test_written_out_phrase_triggers_is_excluded():
    """Written-out year phrase in text must cause _is_excluded to return True."""
    result = {"title": "", "text": "Requires minimum 3 years of experience in Python."}
    assert _is_excluded(result) is True


def test_finance_role_keyword_triggers_is_excluded():
    """A title containing a finance role keyword must cause _is_excluded to return True."""
    result = {"title": "Senior Accounting Manager", "text": ""}
    assert _is_excluded(result) is True


def test_aggregator_title_triggers_is_junk():
    """A title containing an aggregator title pattern must cause _is_junk to return True."""
    result = {"url": "https://example.com/page", "title": "Remote Jobs 2025"}
    assert _is_junk(result) is True
