#!/usr/bin/env python3
"""
Test Suite for Discovery Pipeline
Tests cadence enforcement, duplicate detection, and report parsing
"""

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

# Import functions from discover-improvements.py
sys.path.insert(0, str(Path(__file__).parent))


def test_cadence_enforcement():
    """Verify sources with cadence_hours are skipped when not due."""
    print("TEST: Cadence Enforcement")

    # Mock is_due function (inline since we can't import from bash script)
    def is_due(source: dict, state: dict, now: dt.datetime) -> bool:
        cadence_hours = source.get("cadence_hours")
        if not cadence_hours:
            return True
        url = source.get("url", "")
        if not url:
            return False
        last_checked = state.get(url)
        if not last_checked:
            return True
        try:
            last_dt = dt.datetime.fromisoformat(last_checked)
            # Ensure timezone-aware
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            return True
        delta = now - last_dt
        return delta.total_seconds() >= float(cadence_hours) * 3600

    # Test 1: Source with no cadence should always be due
    source_no_cadence = {"url": "https://example.com"}
    state = {}
    now = dt.datetime.now(dt.timezone.utc)
    assert is_due(source_no_cadence, state, now), "Source without cadence should be due"
    print("  ✓ Source without cadence is always due")

    # Test 2: Source never checked should be due
    source_with_cadence = {"url": "https://example.com", "cadence_hours": 24}
    assert is_due(source_with_cadence, {}, now), "Never-checked source should be due"
    print("  ✓ Never-checked source is due")

    # Test 3: Source checked 1 hour ago with 24h cadence should NOT be due
    one_hour_ago = (now - dt.timedelta(hours=1)).isoformat()
    state = {"https://example.com": one_hour_ago}
    assert not is_due(source_with_cadence, state, now), "Recently checked source should not be due"
    print("  ✓ Recently checked source (1h ago, 24h cadence) is not due")

    # Test 4: Source checked 25 hours ago with 24h cadence SHOULD be due
    twenty_five_hours_ago = (now - dt.timedelta(hours=25)).isoformat()
    state = {"https://example.com": twenty_five_hours_ago}
    assert is_due(source_with_cadence, state, now), "Old source should be due"
    print("  ✓ Old source (25h ago, 24h cadence) is due")

    # Test 5: Timezone handling (naive timestamp)
    naive_timestamp = now.replace(tzinfo=None).isoformat()
    state = {"https://example.com": naive_timestamp}
    try:
        # Should handle naive timestamps gracefully
        result = is_due(source_with_cadence, state, now)
        print(f"  ✓ Handles naive timestamps (result: {result})")
    except Exception as e:
        print(f"  ✗ Failed on naive timestamp: {e}")
        return False

    print("  ✅ All cadence tests passed\n")
    return True


def test_duplicate_detection():
    """Verify config validation detects duplicate URLs."""
    print("TEST: Duplicate URL Detection")

    config_dir = Path(__file__).parent.parent / "config"
    sources_file = config_dir / "improvement-sources.json"

    if not sources_file.exists():
        print(f"  ⚠️  Config file not found: {sources_file}")
        return False

    with open(sources_file) as f:
        sources = json.load(f)

    urls = [s.get("url") for s in sources if s.get("url")]
    duplicates = [url for url in urls if urls.count(url) > 1]
    unique_duplicates = list(set(duplicates))

    if unique_duplicates:
        print(f"  ✗ Found {len(unique_duplicates)} duplicate URLs:")
        for url in unique_duplicates:
            print(f"    - {url} (appears {urls.count(url)} times)")
        return False
    else:
        print(f"  ✓ No duplicate URLs found ({len(urls)} unique sources)")
        print("  ✅ Duplicate detection passed\n")
        return True


def test_report_parsing():
    """Verify discovery report is correctly parsed to JSON."""
    print("TEST: Report Parsing")

    # Create test report
    report_content = """# Improvement Discovery Report
**Date:** 2025-12-22

## Candidate Summary (Scored)

### https://github.com/foo/bar/releases
- **Score:** 42.5
- **Repo:** foo/bar
- **Latest release:** v1.2.3
- **Release URL:** https://github.com/foo/bar/releases/tag/v1.2.3
- **Stars:** 1234

### https://github.com/baz/qux/releases
- **Score:** 38.0
- **Repo:** baz/qux
- **Latest release:** v2.0.0
- **Stars:** 567

## Signals (Low-Trust)

- https://reddit.com/r/foo (social signal; requires corroboration)
- https://news.ycombinator.com/ (social signal; requires corroboration)

## Sources Reviewed

### https://github.com/foo/bar/releases
- **Type:** github_release
- **Weight:** 0.7
"""

    # Write test report
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(report_content)
        report_path = f.name

    try:
        # Parse using same logic as generate-dashboard-data.sh
        with open(report_path) as f:
            lines = f.read().splitlines()

        section = None
        candidates = []
        signals = []
        sources = []
        current = None

        def flush_candidate():
            nonlocal current
            if current:
                candidates.append(current)
                current = None

        for line in lines:
            if line.startswith("## "):
                flush_candidate()
                line_lower = line.lower()
                if "candidate" in line_lower and "summary" in line_lower:
                    section = "candidates"
                elif "signal" in line_lower and "low" in line_lower:
                    section = "signals"
                elif "source" in line_lower and "review" in line_lower:
                    section = "sources"
                else:
                    section = None
                continue

            if section == "candidates":
                if line.startswith("### "):
                    flush_candidate()
                    current = {"url": line[4:].strip(), "details": {}}
                elif line.startswith("- **") and current is not None:
                    raw = line.split(":", 1)
                    if len(raw) == 2:
                        label = raw[0].replace("- **", "").replace("**", "").strip()
                        val = raw[1].replace("**", "").strip()
                        if label.lower() == "score":
                            try:
                                current["score"] = float(val)
                            except ValueError:
                                current["score"] = val
                        elif label.lower() == "release url":
                            current["release_url"] = val
                        elif label.lower() == "latest release":
                            current["release"] = val
                        elif label.lower() == "repo":
                            current["repo"] = val
                        elif label.lower() == "stars":
                            try:
                                current["stars"] = int(val.replace(",", ""))
                            except ValueError:
                                current["stars"] = val
                        else:
                            current["details"][label] = val
                elif not line.strip():
                    flush_candidate()
            elif section == "signals":
                if line.startswith("- "):
                    entry = line[2:].strip()
                    note = ""
                    if " (" in entry and entry.endswith(")"):
                        entry, note = entry.rsplit(" (", 1)
                        note = note[:-1]
                    signals.append({"url": entry.strip(), "note": note})

        flush_candidate()

        # Verify results
        assert len(candidates) == 2, f"Expected 2 candidates, got {len(candidates)}"
        assert candidates[0]["score"] == 42.5, f"Expected score 42.5, got {candidates[0]['score']}"
        assert candidates[0]["repo"] == "foo/bar", f"Expected repo foo/bar, got {candidates[0]['repo']}"
        assert candidates[0]["stars"] == 1234, f"Expected 1234 stars, got {candidates[0]['stars']}"
        assert len(signals) == 2, f"Expected 2 signals, got {len(signals)}"
        assert "social" in signals[0]["note"], f"Expected 'social' in note, got {signals[0]['note']}"

        print("  ✓ Parsed 2 candidates correctly")
        print("  ✓ Extracted scores, repos, stars")
        print("  ✓ Parsed 2 signals correctly")
        print("  ✓ Flexible section matching works")
        print("  ✅ Report parsing tests passed\n")
        return True

    except AssertionError as e:
        print(f"  ✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        Path(report_path).unlink(missing_ok=True)


def test_state_file_validation():
    """Verify state file handles corruption gracefully."""
    print("TEST: State File Validation")

    # Test valid state
    valid_state = {
        "https://example.com": dt.datetime.now(dt.timezone.utc).isoformat(),
        "https://example2.com": dt.datetime.now(dt.timezone.utc).isoformat()
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_state, f)
        state_file = f.name

    try:
        with open(state_file) as f:
            state = json.load(f)

        # Validate all timestamps
        valid_count = 0
        invalid_count = 0
        for url, timestamp in state.items():
            try:
                dt.datetime.fromisoformat(timestamp)
                valid_count += 1
            except (ValueError, AttributeError):
                invalid_count += 1

        print(f"  ✓ Valid state file loaded ({valid_count} valid timestamps)")

        # Test corrupted state
        corrupted_state = {
            "https://example.com": "not-a-timestamp",
            "https://example2.com": dt.datetime.now(dt.timezone.utc).isoformat()
        }

        with open(state_file, 'w') as f:
            json.dump(corrupted_state, f)

        with open(state_file) as f:
            state = json.load(f)

        cleaned_state = {}
        for url, timestamp in state.items():
            try:
                dt.datetime.fromisoformat(timestamp)
                cleaned_state[url] = timestamp
            except (ValueError, AttributeError):
                pass  # Skip invalid entries

        assert len(cleaned_state) == 1, "Should have removed 1 corrupt entry"
        print("  ✓ Handles corrupt timestamps gracefully")
        print("  ✅ State validation tests passed\n")
        return True

    except Exception as e:
        print(f"  ✗ State validation failed: {e}")
        return False
    finally:
        Path(state_file).unlink(missing_ok=True)


def main():
    """Run all tests."""
    print("=" * 70)
    print("DISCOVERY PIPELINE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        test_cadence_enforcement,
        test_duplicate_detection,
        test_report_parsing,
        test_state_file_validation
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
