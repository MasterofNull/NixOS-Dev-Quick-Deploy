#!/usr/bin/env python3
"""delegate-to-codex context profiles: lean is smaller than full, keeps all 11 constraints, is chosen
automatically for review/short safe prompts, and leaves codex's AGENTS.md auto-load on (canon parity, Rule 16); full is unchanged.
Uses --print-prompt and a fake codex binary; never calls the real codex."""
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WRAP = str(REPO / "scripts/ai/delegate-to-codex")


def prompt_for(*args, text="ping"):
    r = subprocess.run(["bash", WRAP, "--prompt", text, "--print-prompt", *args], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    m = re.search(r"profile=(\w+) injected_bytes=(\d+) est_tokens=(\d+)", r.stderr)
    assert m, r.stderr
    return r.stdout, m.group(1), int(m.group(2))


def test_explicit_profiles_and_size():
    full, pf, bf = prompt_for("--context-profile", "full")
    lean, pl, bl = prompt_for("--context-profile", "lean")
    assert (pf, pl) == ("full", "lean")
    assert bl < bf * 0.6, (bl, bf)
    for body in (full, lean):
        for n in range(1, 12):
            assert re.search(rf"^{n}\. [A-Z]", body, re.M), f"constraint {n} missing"
        assert "Scope & Stop Discipline" in body and "Commit Format" in body
        assert "DELEGATE MODE (headless)" in body
        assert body.rstrip("\n").endswith("ping")
    assert "AppArmor Rules" in full and "AppArmor Rules" not in lean
    assert "config/local-agent-grounding.md" in lean


def test_auto_selection():
    assert prompt_for("--role", "review")[1] == "lean"
    assert prompt_for()[1] == "lean"  # short safe-mode prompt
    assert prompt_for("--mode", "edit")[1] == "full"
    assert prompt_for(text="x" * 700)[1] == "full"
    assert prompt_for("--role", "review", text="x" * 700)[1] == "lean"
    assert prompt_for("--role", "implement", "--mode", "edit", "--context-profile", "lean")[1] == "lean"


def test_invalid_profile_rejected():
    r = subprocess.run(["bash", WRAP, "--prompt", "p", "--print-prompt", "--context-profile", "nope"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "Invalid --context-profile" in r.stderr + r.stdout


def test_lean_keeps_agents_md_autoload():
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "codex"
        fake.write_text('#!/bin/sh\nfor a in "$@"; do printf "ARG:%s\\n" "$a" | head -1; done\n')
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        env = {**os.environ, "CODEX_BIN": str(fake), "AQ_DELEGATION_DIR": td, "DELEGATE_CODEX_IGNORE_COOLDOWN": "1"}
        (Path(td) / "outputs").mkdir()

        def run(*extra):
            r = subprocess.run(["bash", WRAP, "--shared", "--wait", "--prompt", "ping", *extra],
                               env=env, capture_output=True, text=True, timeout=120)
            return r.stdout + r.stderr
        lean = run("--role", "review")
        full = run("--context-profile", "full")
        assert "ARG:exec" in lean and "project_doc_max_bytes" not in lean, lean[-600:]
        assert "project_doc_max_bytes" not in full, full[-600:]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {exc!r}")
    sys.exit(1 if fails else 0)
