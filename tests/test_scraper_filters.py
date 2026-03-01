"""
tests/test_scraper_filters.py
------------------------------
Tests for scraper helper functions: _detect_visa, _strip_markdown,
_exceeds_experience_limit, _is_excluded, _is_junk, and config list contents.
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


# ---------------------------------------------------------------------------
# EXCLUDE_KEYWORDS content checks (seniority + location keywords remain)
# ---------------------------------------------------------------------------

from src.config import EXCLUDE_KEYWORDS


def test_seniority_keywords_present():
    assert "Senior" in EXCLUDE_KEYWORDS
    assert "Staff Engineer" in EXCLUDE_KEYWORDS
    assert "Engineering Manager" in EXCLUDE_KEYWORDS


def test_location_keywords_present():
    assert "India" in EXCLUDE_KEYWORDS
    assert "Bangalore" in EXCLUDE_KEYWORDS


def test_written_out_within_target_not_excluded():
    # TARGET_MAX_YEARS is 2 — "2 or more years" is NOT a flat keyword
    # (it's handled by the regex in _exceeds_experience_limit instead).
    assert "2 or more years" not in EXCLUDE_KEYWORDS
    assert "minimum 2 years" not in EXCLUDE_KEYWORDS


# ---------------------------------------------------------------------------
# Filter list extensions
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
# _strip_markdown
# ---------------------------------------------------------------------------

from src.scraper import _strip_markdown


def test_strip_markdown_removes_h2_header():
    assert (
        _strip_markdown("## About Us\nWe build things.") == "About Us\nWe build things."
    )


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
# _exceeds_experience_limit — the new regex-based experience filter
# ---------------------------------------------------------------------------

from src.scraper import _exceeds_experience_limit


def test_numeric_plus_over_limit():
    assert _exceeds_experience_limit("requires 3+ years of experience") is True


def test_numeric_plus_at_limit():
    # 2+ years — lower bound is 2, which equals TARGET_MAX_YEARS → allowed
    assert _exceeds_experience_limit("2+ years of experience required") is False


def test_numeric_range_over_limit():
    # "1-3 years" — lower bound is 1, allowed
    assert _exceeds_experience_limit("1-3 years experience") is False


def test_numeric_range_lower_bound_over_limit():
    # "3-5 years" — lower bound is 3 > TARGET_MAX_YEARS → excluded
    assert _exceeds_experience_limit("3-5 years of experience") is True


def test_written_out_word_over_limit():
    assert _exceeds_experience_limit("minimum three years of experience") is True


def test_written_out_word_at_limit():
    assert _exceeds_experience_limit("two years of experience preferred") is False


def test_minimum_prefix_over_limit():
    assert _exceeds_experience_limit("minimum 4 years relevant experience") is True


def test_at_least_prefix_over_limit():
    assert _exceeds_experience_limit("at least 3 years of work experience") is True


def test_company_history_not_excluded():
    # "our 10 years of experience" describes the company, not a requirement
    assert (
        _exceeds_experience_limit("with our 10 years of experience in fintech") is False
    )


def test_we_have_not_excluded():
    assert (
        _exceeds_experience_limit("we have 5 years of experience building platforms")
        is False
    )


def test_no_experience_mention_not_excluded():
    assert _exceeds_experience_limit("join our team and grow your career") is False


def test_or_more_pattern_over_limit():
    assert _exceeds_experience_limit("5 or more years experience") is True


# ---------------------------------------------------------------------------
# _is_excluded and _is_junk functional tests
# ---------------------------------------------------------------------------

from src.scraper import _is_excluded, _is_junk


def test_written_out_phrase_triggers_is_excluded():
    result = {"title": "", "text": "Requires minimum 3 years of experience in Python."}
    assert _is_excluded(result) is True


def test_numeric_range_over_limit_triggers_is_excluded():
    result = {"title": "", "text": "Looking for 3-5 years of backend experience."}
    assert _is_excluded(result) is True


def test_acceptable_experience_not_excluded():
    result = {
        "title": "Junior Backend Engineer",
        "text": "0-2 years of experience welcome. Fresh grads encouraged.",
    }
    assert _is_excluded(result) is False


def test_finance_role_keyword_triggers_is_excluded():
    result = {"title": "Senior Accounting Manager", "text": ""}
    assert _is_excluded(result) is True


def test_aggregator_title_triggers_is_junk():
    result = {
        "url": "https://example.com/page",
        "title": "Remote Jobs 2025",
        "text": "",
    }
    assert _is_junk(result) is True


def test_closed_job_triggers_is_junk():
    result = {
        "url": "https://somejob.com/backend-engineer",
        "title": "Backend Engineer",
        "text": "This job is no longer accepting applicants. Please browse other openings.",
    }
    assert _is_junk(result) is True


# ---------------------------------------------------------------------------
# Non-SWE role exclusion tests — roles slipping through filters
# ---------------------------------------------------------------------------


def test_beginner_qa_tester_is_excluded():
    result = {"title": "Beginner QA Tester", "text": ""}
    assert _is_excluded(result) is True


def test_associate_support_engineer_is_excluded():
    result = {"title": "Associate Support Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_accounts_receivable_associate_is_excluded():
    result = {"title": "Accounts Receivable Associate", "text": ""}
    assert _is_excluded(result) is True


def test_associate_manager_payments_sales_is_excluded():
    result = {"title": "Associate Manager Payments Sales", "text": ""}
    assert _is_excluded(result) is True


def test_software_engineer_not_excluded():
    """Ensure legitimate SWE roles are not accidentally excluded."""
    result = {"title": "Software Engineer", "text": ""}
    assert _is_excluded(result) is False


# ---------------------------------------------------------------------------
# Edge case: role keywords in snippet must NOT exclude legitimate SWE roles
# ---------------------------------------------------------------------------


def test_swe_job_with_quality_assurance_in_snippet_not_excluded():
    """A junior SWE role whose description mentions QA processes should pass."""
    result = {
        "title": "Junior Backend Engineer",
        "text": "You will work closely with our quality assurance and test engineering teams.",
    }
    assert _is_excluded(result) is False


def test_swe_job_at_fintech_with_financial_services_in_snippet_not_excluded():
    """SWE role at a fintech company that mentions 'financial services' in description."""
    result = {
        "title": "Software Engineer",
        "text": "We build infrastructure for financial services and accounting software.",
    }
    assert _is_excluded(result) is False


def test_swe_job_with_support_engineers_in_snippet_not_excluded():
    """'Support engineers' mentioned as teammates should not exclude a SWE role."""
    result = {
        "title": "Junior Software Engineer",
        "text": "You will collaborate with our support engineering and senior engineers.",
    }
    assert _is_excluded(result) is False


def test_swe_job_with_senior_teammates_in_snippet_not_excluded():
    """Junior role describing senior teammates should not be excluded."""
    result = {
        "title": "Junior Backend Engineer",
        "text": "You will be mentored by Senior Engineers and Staff Developers.",
    }
    assert _is_excluded(result) is False


def test_quality_assurance_engineer_title_is_excluded():
    """QA Engineer in the title IS a non-SWE role and should be excluded."""
    result = {"title": "Quality Assurance Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_associate_product_manager_is_excluded():
    result = {"title": "Associate Product Manager", "text": ""}
    assert _is_excluded(result) is True


def test_data_analyst_associate_is_excluded():
    result = {"title": "Data Analyst Associate", "text": ""}
    assert _is_excluded(result) is True


def test_ux_designer_is_excluded():
    result = {"title": "UX Designer", "text": ""}
    assert _is_excluded(result) is True


# ---------------------------------------------------------------------------
# Edge case: experience regex should not fire on equity vesting / company age
# ---------------------------------------------------------------------------

from src.scraper import _exceeds_experience_limit


def test_vesting_schedule_not_excluded():
    """Equity vesting mention should not trigger the experience filter."""
    assert _exceeds_experience_limit("4 year vesting schedule with 1 year cliff") is False


def test_founded_years_not_excluded():
    """Company founding date should not trigger the experience filter."""
    assert _exceeds_experience_limit("founded 15 years ago in singapore") is False


def test_established_company_not_excluded():
    assert _exceeds_experience_limit("an established 10 years company in fintech") is False


# ---------------------------------------------------------------------------
# Edge case: ATS junior signal "grad" catches EOL titles
# ---------------------------------------------------------------------------

from src.ats_client import _is_junior


def test_is_junior_software_engineer_grad():
    """'Software Engineer Grad' (grad at end of string) must be caught."""
    assert _is_junior("Software Engineer Grad") is True


def test_is_junior_grad_software_engineer():
    assert _is_junior("Grad Software Engineer") is True


def test_is_junior_swe_new_grad():
    assert _is_junior("SWE New Grad") is True


def test_is_junior_intern_at_end():
    assert _is_junior("Software Engineer Intern") is True


def test_is_junior_internship():
    assert _is_junior("Backend Engineering Internship") is True


def test_is_junior_internal_not_matched():
    """'internal' should NOT be caught as a junior signal."""
    assert _is_junior("Manager, Software Engineering - Internal Tools") is False


def test_is_junior_international_not_matched():
    """'international' should NOT be caught as a junior signal."""
    assert _is_junior("International Tax Manager") is False


def test_is_junior_internal_auditor_not_matched():
    assert _is_junior("Internal Auditor, Luxembourg") is False


# ---------------------------------------------------------------------------
# Edge case: seniority gaps — Principal/Staff/Lead/Director without explicit
# pairing (e.g. "Principal SRE" not just "Principal Engineer")
# ---------------------------------------------------------------------------


def test_principal_sre_is_excluded():
    result = {"title": "Principal Site Reliability Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_staff_backend_engineer_is_excluded():
    result = {"title": "Staff Backend Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_lead_backend_engineer_is_excluded():
    result = {"title": "Lead Backend Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_director_role_is_excluded():
    result = {"title": "Director, International Financial Reporting", "text": ""}
    assert _is_excluded(result) is True


# ---------------------------------------------------------------------------
# Edge case: additional non-SWE roles
# ---------------------------------------------------------------------------


def test_technical_writer_is_excluded():
    result = {"title": "Technical Writer - No Experience", "text": ""}
    assert _is_excluded(result) is True


def test_mechanical_engineer_is_excluded():
    result = {"title": "Graduate Mechanical Engineer", "text": ""}
    assert _is_excluded(result) is True


def test_solutions_consultant_is_excluded():
    result = {"title": "Associate Solutions Consultant", "text": ""}
    assert _is_excluded(result) is True


def test_recruiting_associate_is_excluded():
    result = {"title": "Recruiting Associate (Tel Aviv, Israel)", "text": ""}
    assert _is_excluded(result) is True


def test_internal_auditor_is_excluded():
    result = {"title": "Internal Auditor, Luxembourg", "text": ""}
    assert _is_excluded(result) is True
