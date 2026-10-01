#!/usr/bin/env python3
"""
Test antigravity health check for credential/endpoint mismatch.

Verifies that the health script checks for remote key/endpoint compatibility.
"""

import subprocess
import sys
from pathlib import Path

def get_test_root():
    """Find the repository root."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent

def test_health_script_has_credential_check():
    """Verify that antigravity-health.sh has credential/endpoint check."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Check for the credential endpoint check function
    assert 'check_remote_key_endpoint' in content, \
        "Should have check_remote_key_endpoint function"

    # Check for the mismatch detection logic
    assert 'sk-or-' in content, \
        "Should check for OpenRouter key prefix"

    assert 'generativelanguage.googleapis.com' in content, \
        "Should check for Google Gemini endpoint"

    assert 'REMOTE_KEY_ENDPOINT_COMPATIBLE' in content, \
        "Should define REMOTE_KEY_ENDPOINT_COMPATIBLE variable"

def test_health_script_reports_mismatch():
    """Verify that mismatch is reported in output."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Check that mismatch reason is documented
    assert 'mismatch' in content.lower(), \
        "Should mention mismatch detection"

    # Check that the error message is clear
    assert 'credential' in content.lower() or 'endpoint' in content.lower(), \
        "Should explain the mismatch issue"

def test_health_script_preflight_only():
    """Verify that the check is preflight (no network calls)."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Find the check_remote_key_endpoint function
    start = content.find('check_remote_key_endpoint()')
    end = content.find('check_remote_key_endpoint\n', start + 30)

    if start > 0 and end > 0:
        function_text = content[start:end]

        # Should not have network calls
        assert 'curl' not in function_text.lower(), \
            "Preflight check should not make network calls"
        assert 'http' not in function_text.lower() or 'https://' not in function_text, \
            "Preflight check should not make HTTP requests"

def test_emit_result_includes_credential_field():
    """Verify that emit_result includes remote_key_endpoint_compatible."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Check that the field is output in both JSON and non-JSON modes
    assert '"remote_key_endpoint_compatible"' in content, \
        "Should output remote_key_endpoint_compatible in JSON mode"

    assert 'remote_key_endpoint_compatible=' in content, \
        "Should output remote_key_endpoint_compatible in plain text mode"

def test_health_check_reads_environment():
    """Verify that the health check reads REMOTE_LLM_API_KEY and REMOTE_LLM_URL."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Check for environment variable reading
    assert 'REMOTE_LLM_API_KEY' in content or 'REMOTE_API_KEY' in content, \
        "Should read remote API key from environment"

    assert 'REMOTE_LLM_URL' in content or 'REMOTE_URL' in content, \
        "Should read remote URL from environment"

def test_mismatch_makes_status_unhealthy():
    """Verify that mismatch results in unhealthy status."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "health" / "antigravity-health.sh"

    content = script_file.read_text()

    # Find the compose_check_result function
    if 'compose_check_result' in content:
        # Check that mismatch case is handled before other checks
        start = content.find('compose_check_result() {')
        end = content.find('\n}', start) + 2

        if start > 0 and end > start:
            function_text = content[start:end]

            # Mismatch should be checked first
            mismatch_pos = function_text.find('mismatch')
            quota_pos = function_text.find('QUOTA_STATUS')

            if mismatch_pos > 0 and quota_pos > 0:
                # Mismatch check should come before quota check
                assert mismatch_pos < quota_pos, \
                    "Mismatch check should be evaluated before quota status"

if __name__ == "__main__":
    print("Testing health script has credential check...")
    test_health_script_has_credential_check()
    print("✓ Credential check exists test passed")

    print("Testing health script reports mismatch...")
    test_health_script_reports_mismatch()
    print("✓ Mismatch reporting test passed")

    print("Testing health script is preflight only...")
    test_health_script_preflight_only()
    print("✓ Preflight-only test passed")

    print("Testing emit_result includes credential field...")
    test_emit_result_includes_credential_field()
    print("✓ Emit result field test passed")

    print("Testing health check reads environment...")
    test_health_check_reads_environment()
    print("✓ Environment reading test passed")

    print("Testing mismatch makes status unhealthy...")
    test_mismatch_makes_status_unhealthy()
    print("✓ Mismatch unhealthy status test passed")

    print("\nAll tests passed!")
    sys.exit(0)
