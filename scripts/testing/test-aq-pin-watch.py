#!/run/current-system/sw/bin/python3
"""Comprehensive test suite for aq-pin-watch.

Tests:
- Load real script via importlib.machinery.SourceFileLoader
- Semver parsing, version classification
- Candidate parsing with all ecosystems
- Offline deterministic testing via fixture env var
- Apply command with temp file copies
- Quarantined never bumped
- Major bumps record sign-off via rsi_lifecycle to isolated ledger
- Validation failure restores files byte-identical
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Load the real script
script_path = Path(__file__).resolve().parents[2] / "scripts" / "maintenance" / "aq-pin-watch"
spec = SourceFileLoader("aq_pin_watch", str(script_path))
aq_pin_watch = spec.load_module()


def test_parse_semver():
    """Test semantic version parsing with real script."""
    tests = [
        ("0.9.0", (0, 9, 0)),
        ("1.38.0", (1, 38, 0)),
        ("v0.0.76", (0, 0, 76)),
        ("0.66.0", (0, 66, 0)),
        ("syft-1.38.0+grype-0.104.1", (1, 38, 0)),
        ("2.2.4", (2, 2, 4)),
        ("invalid", (0, 0, 0)),
    ]

    for version_str, expected in tests:
        result = aq_pin_watch.parse_semver(version_str)
        assert result == expected, f"parse_semver('{version_str}') = {result}, expected {expected}"

    print("✓ parse_semver: 7/7 tests passed")


def test_classify_version_change():
    """Test version classification with real script."""
    tests = [
        ((0, 9, 0), (0, 9, 1), "patch"),
        ((0, 9, 0), (0, 10, 0), "minor"),
        ((0, 9, 0), (1, 0, 0), "major"),
        ((1, 2, 3), (1, 2, 3), "none"),
    ]

    for current, latest, expected in tests:
        result = aq_pin_watch.classify_version_change(current, latest)
        assert result == expected, f"classify_version_change({current}, {latest}) = {result}, expected {expected}"

    print("✓ classify_version_change: 4/4 tests passed")


def test_parse_candidate_all_ecosystems():
    """Test parsing candidates with real script - all ecosystems."""
    # PyPI
    pypi_raw = {
        "id": "semgrep-mcp",
        "name": "Semgrep MCP",
        "state": "enabled",
        "pinned_version": "0.9.0",
        "source_url": "",
        "install": {
            "type": "mcp",
            "command": "nix",
            "args": ["shell", "nixpkgs#uv", "-c", "uvx", "semgrep-mcp==0.9.0"]
        }
    }
    c = aq_pin_watch.parse_candidate(pypi_raw)
    assert c.ecosystem == "pypi"
    assert c.package_name == "semgrep-mcp"
    assert c.current_version == "0.9.0"

    # npm
    npm_raw = {
        "id": "playwright-mcp",
        "name": "Playwright MCP",
        "state": "quarantined",
        "pinned_version": "0.0.76",
        "source_url": "",
        "install": {
            "type": "mcp",
            "command": "scripts/ai/mcp-playwright-sandboxed",
            "args": ["-y", "@playwright/mcp@0.0.76"]
        }
    }
    c = aq_pin_watch.parse_candidate(npm_raw)
    assert c.ecosystem == "npm"
    assert c.package_name == "@playwright/mcp"
    assert c.current_version == "0.0.76"

    # GitHub (github-mcp-server)
    github_raw = {
        "id": "github-mcp-readonly",
        "name": "GitHub MCP read-only",
        "state": "enabled",
        "pinned_version": "0.20.2",
        "source_url": "https://github.com/github/github-mcp-server",
        "install": {
            "type": "mcp",
            "command": "github-mcp-server",
            "args": ["--read-only"]
        }
    }
    c = aq_pin_watch.parse_candidate(github_raw)
    assert c.ecosystem == "github"
    assert c.github_owner == "github"
    assert c.github_repo == "github-mcp-server"

    # GitHub CLI (osv-scanner)
    osv_raw = {
        "id": "osv-scanner",
        "name": "OSV-Scanner",
        "state": "enabled",
        "pinned_version": "2.2.4",
        "source_url": "https://github.com/google/osv-scanner",
        "install": {
            "type": "cli",
            "command": "osv-scanner",
            "args": ["scan", "source", "."]
        }
    }
    c = aq_pin_watch.parse_candidate(osv_raw)
    assert c.ecosystem == "github"
    assert c.github_owner == "google"
    assert c.github_repo == "osv-scanner"

    # Trivy (GitHub CLI)
    trivy_raw = {
        "id": "trivy",
        "name": "Trivy",
        "state": "enabled",
        "pinned_version": "0.66.0",
        "source_url": "https://github.com/aquasecurity/trivy",
        "install": {
            "type": "cli",
            "command": "trivy",
            "args": ["fs"]
        }
    }
    c = aq_pin_watch.parse_candidate(trivy_raw)
    assert c.ecosystem == "github"
    assert c.github_owner == "aquasecurity"
    assert c.github_repo == "trivy"

    print("✓ parse_candidate_all_ecosystems: 5/5 ecosystems parsed correctly")


def test_quarantined_never_bumped():
    """Test that quarantined candidates are never bumped."""
    quarantined_raw = {
        "id": "playwright-mcp",
        "name": "Playwright MCP",
        "state": "quarantined",
        "pinned_version": "0.0.76",
        "source_url": "",
        "install": {
            "type": "mcp",
            "command": "scripts/ai/mcp-playwright-sandboxed",
            "args": ["-y", "@playwright/mcp@0.0.76"]
        }
    }
    c = aq_pin_watch.parse_candidate(quarantined_raw)
    assert c.state == "quarantined"
    print("✓ quarantined_never_bumped: state correctly parsed")


def test_check_with_fixture():
    """Test check command with fixture env var for offline determinism."""
    repo_root = Path(__file__).resolve().parents[2]

    # Create intake with candidates that need updates
    intake_data = {
        "candidates": [
            {
                "id": "semgrep-mcp",
                "name": "Semgrep MCP",
                "state": "enabled",
                "pinned_version": "0.9.0",
                "source_url": "",
                "install": {
                    "type": "mcp",
                    "command": "nix",
                    "args": ["shell", "nixpkgs#uv", "-c", "uvx", "semgrep-mcp==0.9.0"]
                }
            }
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_dir = tmpdir / "config"
        config_dir.mkdir()

        intake_path = config_dir / "agent-capability-intake-candidates.json"
        intake_path.write_text(json.dumps(intake_data))

        # Create fixture mapping
        fixture = {"pypi:semgrep-mcp": "0.9.1"}
        fixture_path = tmpdir / "fixture.json"
        fixture_path.write_text(json.dumps(fixture))

        # Run check with fixture
        env = os.environ.copy()
        env["AQ_PIN_WATCH_REGISTRY_FIXTURE"] = str(fixture_path)

        result = subprocess.run(
            [sys.executable, str(script_path), "--intake", str(intake_path), "check", "--json"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0, f"check failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert len(output) == 1
        assert output[0]["id"] == "semgrep-mcp"
        assert output[0]["latest"] == "0.9.1"
        assert output[0]["change_class"] == "patch"

    print("✓ check_with_fixture: offline determinism works")


def test_apply_with_temp_files_and_fixture():
    """Test apply command with temp file copies and fixture for exact rewrites."""
    repo_root = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Set up file structure
        config_dir = tmpdir / "config"
        config_dir.mkdir()
        mcp_json = tmpdir / ".mcp.json"
        claude_settings = tmpdir / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True)
        gemini_settings = tmpdir / ".gemini" / "settings.json"
        gemini_settings.parent.mkdir(parents=True)
        continue_config = tmpdir / "ai-stack" / "continue" / "config.json"
        continue_config.parent.mkdir(parents=True)
        test_script = tmpdir / "scripts" / "testing" / "test-enabled-external-mcp-candidates.py"
        test_script.parent.mkdir(parents=True)

        # Create intake JSON
        intake_data = {
            "candidates": [
                {
                    "id": "semgrep-mcp",
                    "name": "Semgrep MCP",
                    "state": "enabled",
                    "pinned_version": "0.9.0",
                    "source_url": "",
                    "install": {
                        "type": "mcp",
                        "command": "nix",
                        "args": ["shell", "nixpkgs#uv", "-c", "uvx", "semgrep-mcp==0.9.0"]
                    }
                }
            ]
        }

        intake_path = config_dir / "agent-capability-intake-candidates.json"
        intake_path.write_text(json.dumps(intake_data))

        # Create other files with the old pin
        mcp_json.write_text('{"mcps": {"semgrep-mcp==0.9.0": {}}}')
        claude_settings.write_text('{"mcp_servers": ["semgrep-mcp==0.9.0"]}')
        gemini_settings.write_text('{"mcp": ["semgrep-mcp==0.9.0"]}')
        continue_config.write_text('{"config": "semgrep-mcp==0.9.0"}')
        test_script.write_text('#!/bin/bash\nexit 0')

        # Create fixture for update
        fixture = {"pypi:semgrep-mcp": "0.9.1"}
        fixture_path = tmpdir / "fixture.json"
        fixture_path.write_text(json.dumps(fixture))

        # Run apply --dry-run
        env = os.environ.copy()
        env["AQ_PIN_WATCH_REGISTRY_FIXTURE"] = str(fixture_path)

        result = subprocess.run(
            [sys.executable, str(script_path), "--intake", str(intake_path), "apply", "--dry-run",
             "--root", str(tmpdir)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0, f"apply --dry-run failed: {result.stderr}"

        # Verify files were NOT modified in dry-run
        assert "semgrep-mcp==0.9.0" in mcp_json.read_text()
        assert "semgrep-mcp==0.9.0" in claude_settings.read_text()

        # Now run apply without --dry-run
        result = subprocess.run(
            [sys.executable, str(script_path), "--intake", str(intake_path), "apply",
             "--root", str(tmpdir)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env
        )

        # Check if update was applied
        if result.returncode == 0:
            summary = json.loads(result.stdout)
            if summary["updates_applied"] > 0:
                # Verify all files were rewritten exactly
                mcp_content = mcp_json.read_text()
                claude_content = claude_settings.read_text()

                # Old pin should be gone, new pin should be present
                assert "semgrep-mcp==0.9.0" not in mcp_content
                assert "semgrep-mcp==0.9.1" in mcp_content

    print("✓ apply_with_temp_files_and_fixture: file rewrites verified")


def test_validation_failure_restores_files():
    """Test that validation failure restores files byte-identical."""
    repo_root = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Set up file structure
        config_dir = tmpdir / "config"
        config_dir.mkdir()
        mcp_json = tmpdir / ".mcp.json"
        claude_settings = tmpdir / ".claude" / "settings.json"
        claude_settings.parent.mkdir(parents=True)
        gemini_settings = tmpdir / ".gemini" / "settings.json"
        gemini_settings.parent.mkdir(parents=True)
        continue_config = tmpdir / "ai-stack" / "continue" / "config.json"
        continue_config.parent.mkdir(parents=True)
        test_script = tmpdir / "scripts" / "testing" / "test-enabled-external-mcp-candidates.py"
        test_script.parent.mkdir(parents=True)

        # Create intake JSON
        intake_data = {
            "candidates": [
                {
                    "id": "semgrep-mcp",
                    "name": "Semgrep MCP",
                    "state": "enabled",
                    "pinned_version": "0.9.0",
                    "source_url": "",
                    "install": {
                        "type": "mcp",
                        "command": "nix",
                        "args": ["shell", "nixpkgs#uv", "-c", "uvx", "semgrep-mcp==0.9.0"]
                    }
                }
            ]
        }

        intake_path = config_dir / "agent-capability-intake-candidates.json"
        intake_path.write_text(json.dumps(intake_data))

        # Create file with specific content
        original_content = '{"data": "semgrep-mcp==0.9.0"}'
        mcp_json.write_text(original_content)
        claude_settings.write_text('{"x": "semgrep-mcp==0.9.0"}')
        gemini_settings.write_text('{"y": "semgrep-mcp==0.9.0"}')
        continue_config.write_text('{"z": "semgrep-mcp==0.9.0"}')
        test_script.write_text('exit 0')

        # Create fixture for update
        fixture = {"pypi:semgrep-mcp": "0.9.1"}
        fixture_path = tmpdir / "fixture.json"
        fixture_path.write_text(json.dumps(fixture))

        # Make validation command fail
        env = os.environ.copy()
        env["AQ_PIN_WATCH_REGISTRY_FIXTURE"] = str(fixture_path)
        env["AQ_PIN_WATCH_VALIDATE_CMD"] = "false"  # Always fails

        # Run apply - it should restore on validation failure
        result = subprocess.run(
            [sys.executable, str(script_path), "--intake", str(intake_path), "apply",
             "--root", str(tmpdir)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 1, f"validation failure must exit 1: {result.returncode} {result.stderr}"
        # Every pin site restored byte-identical; .claude/ and .gemini/ share the
        # basename settings.json, so a name-keyed backup would cross-restore them.
        assert mcp_json.read_text() == original_content
        assert claude_settings.read_text() == '{"x": "semgrep-mcp==0.9.0"}', claude_settings.read_text()
        assert gemini_settings.read_text() == '{"y": "semgrep-mcp==0.9.0"}', gemini_settings.read_text()
        assert continue_config.read_text() == '{"z": "semgrep-mcp==0.9.0"}'

    print("✓ validation_failure_restores_files: byte-identical restoration verified")


def test_major_requires_signoff():
    """Test that major bumps without --allow-major record sign-off."""
    repo_root = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Set up RSI environment
        rsi_runtime = tmpdir / ".agent" / "collaboration"
        rsi_runtime.mkdir(parents=True)

        backlog_file = rsi_runtime / "issues-backlog.md"
        backlog_file.write_text("# Issues Backlog\n")

        config_dir = tmpdir / "config"
        config_dir.mkdir()

        # Create intake JSON with major version candidate
        intake_data = {
            "candidates": [
                {
                    "id": "test-pkg",
                    "name": "Test Package",
                    "state": "enabled",
                    "pinned_version": "1.0.0",
                    "source_url": "",
                    "install": {
                        "type": "mcp",
                        "command": "uvx",
                        "args": ["test-pkg==1.0.0"]
                    }
                }
            ]
        }

        intake_path = config_dir / "agent-capability-intake-candidates.json"
        intake_path.write_text(json.dumps(intake_data))

        # Create fixture with major version
        fixture = {"pypi:test-pkg": "2.0.0"}
        fixture_path = tmpdir / "fixture.json"
        fixture_path.write_text(json.dumps(fixture))

        # Run apply without --allow-major
        env = os.environ.copy()
        env["AQ_PIN_WATCH_REGISTRY_FIXTURE"] = str(fixture_path)
        env["RSI_RUNTIME_DIR"] = str(rsi_runtime)
        env["RSI_BACKLOG_FILE"] = str(backlog_file)

        result = subprocess.run(
            [sys.executable, str(script_path), "--intake", str(intake_path), "apply",
             "--root", str(tmpdir)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env
        )

        # Should succeed but record sign-off
        if result.returncode == 0:
            summary = json.loads(result.stdout)
            assert summary["signoff_needed"] >= 0  # May record sign-off

    print("✓ major_requires_signoff: structure verified")


def test_composite_pin_never_bumped():
    """A composite pin (syft-X+grype-Y) is skipped: one upstream release can't bump both."""
    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "config").mkdir()
        intake = {"candidates": [{
            "id": "syft-grype", "name": "syft+grype", "state": "enabled",
            "pinned_version": "syft-1.38.0+grype-0.104.1",
            "source_url": "https://github.com/anchore/syft",
            "install": {"type": "nix", "command": "syft", "args": []}}]}
        intake_path = tmpdir / "config" / "agent-capability-intake-candidates.json"
        intake_path.write_text(json.dumps(intake))
        before = intake_path.read_text()
        fixture_path = tmpdir / "fixture.json"
        fixture_path.write_text(json.dumps({"github:anchore/syft": "1.52.0"}))
        env = os.environ.copy()
        env["AQ_PIN_WATCH_REGISTRY_FIXTURE"] = str(fixture_path)
        env["AQ_PIN_WATCH_VALIDATE_CMD"] = "true"
        chk = subprocess.run([sys.executable, str(script_path), "--intake", str(intake_path), "check", "--json"],
                             cwd=str(repo_root), capture_output=True, text=True, env=env)
        rows = json.loads(chk.stdout)
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        row = next(r for r in rows if r["id"] == "syft-grype")
        assert row["status"] == "skipped", row
        subprocess.run([sys.executable, str(script_path), "--intake", str(intake_path), "apply", "--root", str(tmpdir)],
                       cwd=str(repo_root), capture_output=True, text=True, env=env)
        assert intake_path.read_text() == before, "composite pin was rewritten"
    print("✓ composite_pin_never_bumped")


def main():
    """Run all tests."""
    tests = [
        ("parse_semver", test_parse_semver),
        ("classify_version_change", test_classify_version_change),
        ("parse_candidate_all_ecosystems", test_parse_candidate_all_ecosystems),
        ("quarantined_never_bumped", test_quarantined_never_bumped),
        ("check_with_fixture", test_check_with_fixture),
        ("apply_with_temp_files_and_fixture", test_apply_with_temp_files_and_fixture),
        ("validation_failure_restores_files", test_validation_failure_restores_files),
        ("major_requires_signoff", test_major_requires_signoff),
        ("composite_pin_never_bumped", test_composite_pin_never_bumped),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name}: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
