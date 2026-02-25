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
