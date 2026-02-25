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
