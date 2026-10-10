#!/usr/bin/env python3
"""aq-commit-agent --draft-message: deterministic draft from the staged diff, read-only."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-commit-agent"


def run(repo: Path, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), "--draft-message"], cwd=repo, capture_output=True,
                          text=True, env={**os.environ, "AQ_USAGE_TELEMETRY": "0", **(env or {})})


def git(repo: Path, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@t")
        git(repo, "config", "user.name", "t")
        r = run(repo)
        assert r.returncode == 2 and "nothing staged" in r.stderr, (r.returncode, r.stderr)

        (repo / "scripts/ai/lib").mkdir(parents=True)
        (repo / "scripts/ai/lib/new_tool.py").write_text("x = 1\n")
        git(repo, "add", "-A")
        r = run(repo, {"AQ_AGENT_NAME": "Claude Test"})
        assert r.returncode == 0, r.stderr
        head = r.stdout.splitlines()[0]
        assert head.startswith("feat(ai): "), head
        assert "- scripts/ai/lib/: A new_tool.py" in r.stdout
        assert "Root cause:" in r.stdout and "Co-Authored-By: Claude Test <noreply@anthropic.com>" in r.stdout
        before = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, capture_output=True, text=True).stdout
        git(repo, "commit", "-qm", "base")

        (repo / "tests").mkdir()
        for i in range(17):
            (repo / "tests" / f"t{i}.py").write_text("pass\n")
        git(repo, "add", "-A")
        r = run(repo)
        assert r.stdout.startswith("test(tests): ") or r.stdout.startswith("test("), r.stdout.splitlines()[0]
        assert "+2 more" in r.stdout and "<agent>" in r.stdout
        assert before.strip() == "scripts/ai/lib/new_tool.py"  # draft did not alter the index
    print("PASS: aq-commit-agent --draft-message (type/scope, grouping, truncation, trailer, nothing-staged, read-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
