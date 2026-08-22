#!/usr/bin/env python3
"""Hermetic protected-branch review-disposition hook contract."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".githooks/commit-msg"
SUBJECT_TOKEN = "__STAGED_SUBJECT_SHA256__"


def staged_subject(repo: Path) -> str:
    patch = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--"],
        cwd=repo, check=True, capture_output=True,
    ).stdout
    return hashlib.sha256(patch).hexdigest()


def run(message: str, *, deletion_only: bool = False, one_line: bool = False) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        subprocess.run(["git", "config", "user.name", "hook-test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "hook-test@example.invalid"], cwd=repo, check=True)
        shutil.copy2(HOOK, repo / "commit-msg")
        if deletion_only:
            victim = repo / "victim"
            victim.write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "add", "victim"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
            victim.unlink()
            subprocess.run(["git", "add", "-u"], cwd=repo, check=True)
        else:
            (repo / "one").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "one"], cwd=repo, check=True)
            if not one_line:
                (repo / "two").write_text("two\n", encoding="utf-8")
                subprocess.run(["git", "add", "two"], cwd=repo, check=True)
        msg = repo / "MESSAGE"
        msg.write_text(message.replace(SUBJECT_TOKEN, staged_subject(repo)), encoding="utf-8")
        return subprocess.run(
            ["bash", str(repo / "commit-msg"), str(msg)],
            cwd=repo, text=True, capture_output=True,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
        )


def accepted() -> str:
    return (
        "feat: accepted slice\n\n"
        "Review-Disposition: ACCEPTED\n"
        "Independent-Review: PASS\n"
        f"Reviewed-subject-sha256: {SUBJECT_TOKEN}\n"
        "Reviewed-by: independent-agent\n"
    )


assert run(accepted()).returncode == 0
assert run(accepted() + "\nRoot cause: earlier provisional integration was unsafe.\n").returncode == 0
assert run(accepted().replace(SUBJECT_TOKEN, "a" * 64)).returncode != 0
assert run("feat: no evidence\n", one_line=True).returncode != 0
assert run("chore: deleted material\n", deletion_only=True).returncode != 0
assert run(accepted(), one_line=True).returncode == 0
assert run(accepted().replace("PASS", "CONCERNS")).returncode != 0
assert run("feat: blocked\n\nReview-Disposition: ACTIVATION_BLOCKED\n").returncode != 0
assert run("feat: rejected\n\nReview-Disposition: REJECTED\n").returncode != 0
followup = (
    "feat: forward-safe slice\n\n"
    "Review-Disposition: IMPLEMENTED_FOLLOWUP_REQUIRED\n"
    "Independent-Review: PASS\n"
    f"Reviewed-subject-sha256: {SUBJECT_TOKEN}\n"
    "Reviewed-by: independent-agent\n"
    "Safe-At-Rest: true\n"
    "Activation-Authority: false\n"
    "Next-Slice: bounded-repair\n"
)
assert run(followup).returncode == 0
assert run(followup.replace("Independent-Review: PASS\n", "")).returncode != 0
assert run(followup.replace(SUBJECT_TOKEN, "b" * 64)).returncode != 0
assert run(followup.replace("Activation-Authority: false", "Activation-Authority: true")).returncode != 0
assert run(accepted().replace("accepted slice", "provisional slice")).returncode != 0
assert run(accepted() + "Integration-State: provisional\n").returncode != 0
print("PASS: protected-branch review disposition hook")
