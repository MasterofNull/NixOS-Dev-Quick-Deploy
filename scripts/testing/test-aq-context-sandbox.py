#!/usr/bin/env python3
"""Regression checks for aq-context-sandbox."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "scripts" / "ai" / "aq-context-sandbox"


def run_sandbox(payload: str, artifact_dir: Path) -> dict:
    env = os.environ.copy()
    env["SWB_CONTEXT_ARTIFACT_DIR"] = str(artifact_dir)
    proc = subprocess.run(
        ["python3", str(CMD), "--json", "--label", "Playwright Snapshot", "--kind", "snapshot", "--summary-chars", "80"],
        input=payload,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
        env=env,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    large_payload = "line one\n" + ("raw browser snapshot token " * 200)
    with tempfile.TemporaryDirectory(prefix="aq-context-sandbox-") as tmp:
        artifact_dir = Path(tmp)
        result = run_sandbox(large_payload, artifact_dir)
        artifact_path = Path(result["artifact_path"])
        assert result["status"] == "stored"
        assert result["kind"] == "snapshot"
        assert result["bytes"] == len(large_payload.encode("utf-8"))
        assert len(result["summary"]) <= 80
        assert "usage" in result and "do not paste" in result["usage"]
        assert artifact_path.exists()
        assert artifact_path.parent == artifact_dir
        assert artifact_path.read_text(encoding="utf-8") == large_payload
    print("PASS: aq-context-sandbox stores raw payloads behind compact artifact envelopes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
