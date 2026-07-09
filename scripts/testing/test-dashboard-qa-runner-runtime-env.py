#!/usr/bin/env python3
"""Regression test for dashboard-confined aq-qa runtime paths."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

from api.services import qa_runner  # noqa: E402


class _Proc:
    returncode = 0

    async def communicate(self):
        payload = {"phase": "0", "tests": [], "passed": 0, "failed": 0, "skipped": 0}
        return json.dumps(payload).encode(), b""

    def kill(self):
        raise AssertionError("process should not be killed")


async def _main() -> int:
    captured: dict[str, object] = {}
    original_create = qa_runner.asyncio.create_subprocess_exec
    original_data_dir = os.environ.get("DASHBOARD_DATA_DIR")

    async def fake_create(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env")
        return _Proc()

    try:
        with tempfile.TemporaryDirectory(prefix="dashboard-qa-runner-env-") as tmp:
            os.environ["DASHBOARD_DATA_DIR"] = tmp
            qa_runner.asyncio.create_subprocess_exec = fake_create
            data = await qa_runner._execute_phase("0", timeout_s=5, cwd=ROOT)
            assert data["phase"] == "0"

            env = captured["env"]
            assert isinstance(env, dict)
            expected_tmp = Path(tmp) / "qa-runner-tmp"
            expected_pycache = Path(tmp) / "qa-runner-pycache"
            expected_cargo = Path(tmp) / "qa-runner-cargo-target"
            for name in ("TMPDIR", "TEMP", "TMP"):
                assert env.get(name) == str(expected_tmp), f"{name} should use dashboard writable tmp"
            assert env.get("PYTHONPYCACHEPREFIX") == str(expected_pycache)
            assert env.get("CARGO_TARGET_DIR") == str(expected_cargo)
            assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
            assert env.get("AQ_QA_DASHBOARD_SAFE") == "1"
            for path in (expected_tmp, expected_pycache, expected_cargo):
                assert path.is_dir(), f"{path} should be created before aq-qa starts"
    finally:
        qa_runner.asyncio.create_subprocess_exec = original_create
        if original_data_dir is None:
            os.environ.pop("DASHBOARD_DATA_DIR", None)
        else:
            os.environ["DASHBOARD_DATA_DIR"] = original_data_dir

    print("PASS: dashboard qa runner redirects temp/cache writes into dashboard data dir")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
