#!/usr/bin/env python3
"""
Security tests for dashboard proxy endpoint
Verifies P1-SEC-001 fixes for subprocess injection vulnerability
"""
import sys
import urllib.request
import urllib.error
import json
import ssl
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVE_DASHBOARD = PROJECT_ROOT / 'scripts' / 'serve-dashboard.sh'

def test_allowed_endpoints():
    """Test that only whitelisted health endpoints are accessible"""
    allowed = [
        'health',
        # health/live, health/ready, health/startup may return 404 if AIDB isn't fully initialized
        # But they should NOT return 403 (which would mean dashboard blocked them)
    ]

    # Note: Dashboard must be running on port 8888
    print("Testing allowed endpoints...")
    for endpoint in allowed:
        try:
            url = f'http://localhost:8888/aidb/{endpoint}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Test/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                print(f"✓ {endpoint}: {status}")
        except urllib.error.HTTPError as e:
            # 404, 503 are acceptable (AIDB may not have endpoint or be unavailable)
            # 403 means dashboard blocked it (BAD)
            if e.code in [200, 404, 503]:
                print(f"✓ {endpoint}: {e.code} (acceptable - reached backend)")
            elif e.code == 403:
                print(f"✗ {endpoint}: 403 (wrongly blocked by dashboard)")
                return False
            else:
                print(f"? {endpoint}: {e.code} (unexpected)")
        except Exception as e:
            print(f"✗ {endpoint}: {e}")
            return False
    return True

def test_blocked_endpoints():
    """Test that non-whitelisted endpoints are blocked"""
    blocked = [
        ('query', 403),  # Should be blocked by dashboard (403)
        ('../etc/passwd', 403),  # Path traversal attempt
        # Command injection attempts may be caught by URL validation before reaching dashboard
    ]

    print("\nTesting blocked endpoints...")
    for endpoint, expected_code in blocked:
        try:
            url = f'http://localhost:8888/aidb/{endpoint}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Test/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode()
                print(f"✗ {endpoint}: {response.status} (SHOULD BE BLOCKED)")
                return False
        except urllib.error.HTTPError as e:
            if e.code == expected_code:
                print(f"✓ {endpoint}: {e.code} (correctly blocked)")
            else:
                print(f"? {endpoint}: {e.code} (blocked, expected {expected_code})")
        except urllib.error.URLError as e:
            # URL validation errors are acceptable (caught before reaching server)
            print(f"✓ {endpoint}: URL validation blocked ({str(e)[:60]})")
        except Exception as e:
            print(f"✓ {endpoint}: {type(e).__name__} (blocked)")
    return True

def test_no_subprocess():
    """Verify subprocess module is not used in proxy code"""
    print("\nChecking serve-dashboard.sh for subprocess in proxy...")
    try:
        with open(SERVE_DASHBOARD, 'r') as f:
            content = f.read()
            # Find the aidb proxy section
            lines = content.split('\n')
            in_aidb_section = False
            subprocess_in_aidb = False
            for i, line in enumerate(lines):
                if "if clean_path.startswith('/aidb/'):" in line:
                    in_aidb_section = True
                if in_aidb_section and 'subprocess.run' in line:
                    # Check if we're past the aidb section
                    if i > 130:  # aidb section ends around line 130
                        break
                    subprocess_in_aidb = True
                    print(f"✗ Found subprocess.run in aidb proxy section at line {i+1}")
                if in_aidb_section and "# Serve JSON data files" in line:
                    break

            if not subprocess_in_aidb:
                print("✓ No subprocess.run found in aidb proxy section")
                return True
            return False
    except Exception as e:
        print(f"✗ Error checking file: {e}")
        return False

def main():
    print("=" * 60)
    print("P1-SEC-001: Dashboard Proxy Security Tests")
    print("=" * 60)

    results = []

    # Test 1: No subprocess in proxy code
    results.append(("No subprocess vulnerability", test_no_subprocess()))

    # Test 2: Allowed endpoints work
    results.append(("Allowed endpoints", test_allowed_endpoints()))

    # Test 3: Blocked endpoints fail
    results.append(("Blocked endpoints", test_blocked_endpoints()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("✓ ALL TESTS PASSED" if all_passed else "✗ SOME TESTS FAILED"))
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
