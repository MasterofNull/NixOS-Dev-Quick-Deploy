"""Phase 132: Domain-role eligibility enforcement tests.

Validates that validate_role_eligibility() blocks restricted
provider/role combinations and passes everything else through.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.domain_router import validate_role_eligibility, classify_domain


def test_security_reviewer_gemini_blocked():
    ok, reason = validate_role_eligibility("security", "reviewer", "gemini-orchestrator")
    assert not ok, "Gemini must be blocked as security reviewer"
    assert "gemini" in reason.lower() or "security" in reason.lower()


def test_security_reviewer_claude_allowed():
    ok, _ = validate_role_eligibility("security", "reviewer", "claude-reasoning")
    assert ok, "Claude must be allowed as security reviewer"


def test_security_reviewer_local_allowed():
    ok, _ = validate_role_eligibility("security", "reviewer", "local-agent")
    assert ok, "Local profile must be allowed as security reviewer"


def test_security_implementer_gemini_allowed():
    ok, _ = validate_role_eligibility("security", "implementer", "gemini-orchestrator")
    assert ok, "Gemini as implementer in security is allowed"


def test_nonsecurity_domain_no_restriction():
    ok, _ = validate_role_eligibility("python", "reviewer", "gemini-orchestrator")
    assert ok, "No restriction in python domain"


def test_empty_fields_pass():
    ok, _ = validate_role_eligibility("", "reviewer", "gemini-orchestrator")
    assert ok, "Empty domain is always eligible"
    ok, _ = validate_role_eligibility("security", "", "gemini-orchestrator")
    assert ok, "Empty role is always eligible"


def test_classify_domain_security():
    domain = classify_domain("Review this authentication token handling for CVE exposure")
    assert domain == "security", f"Expected 'security', got '{domain}'"


def test_classify_domain_general_fallback():
    domain = classify_domain("What is the capital of France?")
    assert domain == "general"


if __name__ == "__main__":
    tests = [
        test_security_reviewer_gemini_blocked,
        test_security_reviewer_claude_allowed,
        test_security_reviewer_local_allowed,
        test_security_implementer_gemini_allowed,
        test_nonsecurity_domain_no_restriction,
        test_empty_fields_pass,
        test_classify_domain_security,
        test_classify_domain_general_fallback,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
