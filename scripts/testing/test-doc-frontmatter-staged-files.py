#!/usr/bin/env python3
"""Regression coverage for Phase 93.9 doc-frontmatter staged-file scoped validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts" / "governance" / "check-doc-frontmatter.py"
REGISTRY = ROOT / "config" / "validation-check-registry.json"
RUNNER = ROOT / "scripts" / "governance" / "run-focused-ci-checks.sh"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _yaml_parser_available() -> bool:
    """Mirror check-doc-frontmatter's parser gate: PyYAML or yq. On this host's
    intentionally-minimal gate python neither may be present, in which case the
    checker cannot load its schema and degrades to a graceful skip."""
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        pass
    import shutil
    return shutil.which("yq") is not None


def test_registry_has_pass_staged_files() -> None:
    doc = json.loads(REGISTRY.read_text())
    doc_fm_check = next(
        (c for c in doc.get("checks", []) if c["id"] == "doc-frontmatter"),
        None,
    )
    assert_true(doc_fm_check is not None, "doc-frontmatter check present in registry")
    assert_true(
        doc_fm_check.get("pass_staged_files") is True,
        "doc-frontmatter check has pass_staged_files=true",
    )


def test_check_script_valid_frontmatter() -> None:
    valid_md = """\
---
doc_type: prd
id: test-prd
title: Test PRD
status: active
owner: test-agent
phase: "Phase 93"
priority: medium
---

# Test PRD body
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=str(ROOT)
    ) as fh:
        fh.write(valid_md)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert_true(
            result.returncode == 0,
            f"valid frontmatter should pass; stderr: {result.stderr}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_check_script_invalid_doc_type_fails() -> None:
    invalid_md = """\
---
doc_type: invalid_nonexistent_type
id: bad-doc
title: Bad Doc
status: active
owner: test-agent
---

# Body
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=str(ROOT)
    ) as fh:
        fh.write(invalid_md)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if not _yaml_parser_available():
            # No YAML parser => the checker cannot parse frontmatter or load the
            # schema, so it degrades to a graceful skip (exit 0). Invalid doc_types
            # are only catchable when a parser is present (CI). Assert the skip is
            # clean and honest rather than a silent pass.
            assert_true(
                result.returncode == 0 and "SKIP" in result.stdout,
                f"no-parser env should skip gracefully; got rc={result.returncode} "
                f"stdout={result.stdout}",
            )
            return
        assert_true(
            result.returncode != 0,
            f"invalid doc_type should fail; stdout: {result.stdout}",
        )
        assert_true(
            tmp_path in result.stdout or Path(tmp_path).name in result.stdout,
            f"failure output should include file path; got: {result.stdout}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_check_script_no_frontmatter_exempt() -> None:
    no_fm_md = "# Legacy Document\n\nNo frontmatter here.\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=str(ROOT)
    ) as fh:
        fh.write(no_fm_md)
        tmp_path = fh.name

    try:
        result = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert_true(
            result.returncode == 0,
            f"legacy doc without frontmatter should be exempt; stderr: {result.stderr}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_runner_pass_staged_files_flag_supported() -> None:
    """Runner should not error on pass_staged_files field in registry."""
    # Create a minimal registry with pass_staged_files
    minimal_registry = {
        "checks": [
            {
                "id": "test-pass-staged",
                "description": "test pass_staged_files support",
                "trigger_paths": [".agents/plans/"],
                "command": [sys.executable, "-c", "import sys; print('OK')"],
                "pass_staged_files": True,
                "enabled": True,
                "timeout_seconds": 10,
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path = Path(tmpdir) / "test-registry.json"
        reg_path.write_text(json.dumps(minimal_registry))
        env = {
            **os.environ,
            "REGISTRY": str(reg_path),
            "MODE": "--pre-commit",
        }
        result = subprocess.run(
            ["bash", str(RUNNER), "--pre-commit"],
            capture_output=True,
            text=True,
            env=env,
        )
        # Should exit 0 (no staged files matching trigger → skip, not error)
        assert_true(
            result.returncode == 0,
            f"runner with pass_staged_files should not error; stderr: {result.stderr}",
        )


if __name__ == "__main__":
    tests = [
        ("registry has pass_staged_files", test_registry_has_pass_staged_files),
        ("valid frontmatter passes", test_check_script_valid_frontmatter),
        ("invalid doc_type fails with file path", test_check_script_invalid_doc_type_fails),
        ("legacy doc without frontmatter exempt", test_check_script_no_frontmatter_exempt),
        ("runner supports pass_staged_files flag", test_runner_pass_staged_files_flag_supported),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
