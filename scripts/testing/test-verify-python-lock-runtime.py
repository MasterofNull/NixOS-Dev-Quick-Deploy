#!/usr/bin/env python3
"""Regression tests for Python lock integrity verification."""

from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "security" / "verify-python-lock-runtime.py"


class VerifyPythonLockRuntimeTests(unittest.TestCase):
    def _run_verify(self, requirements_text: str, lock_text: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            requirements = tmp / "requirements.txt"
            lockfile = tmp / "requirements.lock"
            requirements.write_text(textwrap.dedent(requirements_text).strip() + "\n", encoding="utf-8")
            lockfile.write_text(textwrap.dedent(lock_text).strip() + "\n", encoding="utf-8")
            return subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--service",
                    "test-service",
                    "--requirements",
                    str(requirements),
                    "--lock",
                    str(lockfile),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_accepts_uvicorn_standard_when_lock_has_base_distribution(self) -> None:
        result = self._run_verify(
            """
            uvicorn[standard]==0.38.0
            """,
            """
            uvicorn==0.38.0 \\
                --hash=sha256:testhash
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["event"], "dependency_lock_verified")

    def test_accepts_known_extra_alias_packages(self) -> None:
        result = self._run_verify(
            """
            psycopg[binary,pool]==3.2.13  # async postgres
            redis[hiredis]==7.1.0
            """,
            """
            psycopg-binary==3.2.13 \\
                --hash=sha256:testhash1
            psycopg-pool==3.3.0 \\
                --hash=sha256:testhash2
            redis==7.1.0 \\
                --hash=sha256:testhash3
            hiredis==3.3.0 \\
                --hash=sha256:testhash4
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["validated_packages"], 2)

    def test_reports_truly_missing_top_level_dependency(self) -> None:
        result = self._run_verify(
            """
            httpx>=0.24.0
            """,
            """
            aiohttp==3.13.3 \\
                --hash=sha256:testhash
            """,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["event"], "dependency_hash_mismatch")
        self.assertEqual(payload["missing_from_lock"], ["httpx>=0.24.0"])


if __name__ == "__main__":
    unittest.main()
