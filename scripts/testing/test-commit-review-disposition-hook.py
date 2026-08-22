#!/usr/bin/env python3
"""Hermetic protected-branch review-disposition hook contract."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".githooks/commit-msg"
SUBJECT = "a" * 64


def run(message: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        shutil.copy2(HOOK, repo / "commit-msg")
        (repo / "one").write_text("one\n", encoding="utf-8")
        (repo / "two").write_text("two\n", encoding="utf-8")
        subprocess.run(["git", "add", "one", "two"], cwd=repo, check=True)
        msg = repo / "MESSAGE"
        msg.write_text(message, encoding="utf-8")
        return subprocess.run(
            ["bash", str(repo / "commit-msg"), str(msg)],
            cwd=repo,
            text=True,
            capture_output=True,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
        )


def accepted() -> str:
    return (
        "feat: accepted slice\n\n"
        "Review-Disposition: ACCEPTED\n"
        "Independent-Review: PASS\n"
        f"Reviewed-subject-sha256: {SUBJECT}\n"
        "Reviewed-by: independent-agent\n"
    )


assert run(accepted()).returncode == 0
assert run(accepted() + "\nRoot cause: earlier provisional integration was unsafe.\n").returncode == 0
assert run("feat: no evidence\n").returncode != 0
assert run(accepted().replace("PASS", "CONCERNS")).returncode != 0
assert run(accepted().replace(SUBJECT, "ABC")).returncode != 0
assert run("feat: blocked\n\nReview-Disposition: ACTIVATION_BLOCKED\n").returncode != 0
assert run("feat: rejected\n\nReview-Disposition: REJECTED\n").returncode != 0
assert run(
    "feat: forward-safe slice\n\n"
    "Review-Disposition: IMPLEMENTED_FOLLOWUP_REQUIRED\n"
    "Safe-At-Rest: true\n"
    "Activation-Authority: false\n"
    "Next-Slice: bounded-repair\n"
).returncode == 0
assert run(
    "feat: forward-unsafe slice\n\n"
    "Review-Disposition: IMPLEMENTED_FOLLOWUP_REQUIRED\n"
    "Safe-At-Rest: true\n"
    "Activation-Authority: true\n"
    "Next-Slice: later\n"
).returncode != 0
assert run(accepted().replace("accepted slice", "provisional slice")).returncode != 0
assert run(accepted() + "Integration-State: provisional\n").returncode != 0
print("PASS: protected-branch review disposition hook")
