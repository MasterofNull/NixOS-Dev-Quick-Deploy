#!/usr/bin/env python3
"""Tests for scripts/ai/aq-review-request with stubbed git, gh and dispatchers.

Never dispatches a real Codex/local task: DELEGATE_TO_* point at a recording stub.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = REPO_ROOT / "scripts" / "ai" / "aq-review-request"
HEAD = "abcdef0123456789abcdef0123456789abcdef01"

GH_STUB = f"""#!/usr/bin/env bash
echo '{json.dumps({"headRefOid": HEAD, "title": "feat: demo", "body": "Author-lane: local-qwen"})}'
"""
GIT_STUB = """#!/usr/bin/env bash
case "$1" in
  fetch) exit 0 ;;
  merge-base) echo basebase000 ;;
  diff) if [[ "$2" == "--stat" ]]; then echo " f.py | 3 +++"; else cat "$DIFF_FILE"; fi ;;
esac
"""
DISPATCH_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$RECORD_FILE"
echo "task-id: stub-123"
"""


def setup(tmp, diff_text):
    for name, body in (("gh", GH_STUB), ("git", GIT_STUB), ("disp", DISPATCH_STUB)):
        p = tmp / name
        p.write_text(body)
        p.chmod(0o755)
    (tmp / "diff.txt").write_text(diff_text)
    (tmp / "out").mkdir()
    return {
        "GH_BIN": str(tmp / "gh"), "GIT_BIN": str(tmp / "git"),
        "DELEGATE_TO_CODEX": str(tmp / "disp"), "DELEGATE_TO_LOCAL": str(tmp / "disp"),
        "DELEGATE_OUTPUTS_DIR": str(tmp / "out"), "DIFF_FILE": str(tmp / "diff.txt"),
        "RECORD_FILE": str(tmp / "record.txt"),
    }


def run(args, env):
    e = os.environ.copy()
    e.update(env)
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, env=e)


def prompt_of(tmp):
    files = list((tmp / "out").glob("review-prompt-pr7-*.md"))
    assert len(files) == 1, files
    assert files[0].name == f"review-prompt-pr7-{HEAD[:12]}.md", files[0].name
    return files[0].read_text()


def test_dry_run_prompt():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        env = setup(t, "+ASSERT_MARKER_LINE\n")
        r = run(["--pr", "7", "--lane", "codex", "--focus", "check locking", "--dry-run"], env)
        assert r.returncode == 0, r.stderr
        p = prompt_of(t)
        for needle in (HEAD, "+ASSERT_MARKER_LINE", "author lane: local-qwen", "check locking",
                       f"Reviewed-head-sha: {HEAD}", "Review-Disposition: PASS_WITH_FOLLOWUPS",
                       "READ-ONLY", "f.py | 3 +++", "feat: demo"):
            assert needle in p, needle
        assert "truncated" not in p
        assert not (t / "record.txt").exists(), "dry-run must not dispatch"
        assert "--role review" in r.stdout


def test_truncation():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        env = setup(t, "+" + "x" * 5000 + "\n")
        r = run(["--pr", "7", "--lane", "codex", "--max-diff-bytes", "100", "--dry-run"], env)
        assert r.returncode == 0, r.stderr
        p = prompt_of(t)
        assert "diff truncated to 100" in p and "f.py | 3 +++" in p
        assert "x" * 200 not in p


def test_codex_args():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        env = setup(t, "+a\n")
        r = run(["--pr", "7", "--lane", "codex"], env)
        assert r.returncode == 0, r.stderr
        argv = (t / "record.txt").read_text().split("\n")
        assert argv[:6] == ["--role", "review", "--effort", "medium", "--mode", "safe"], argv
        assert "--prompt-file" in argv
        assert "stub-123" in r.stdout


def test_local_args():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        env = setup(t, "+a\n")
        r = run(["--pr", "7", "--lane", "local"], env)
        assert r.returncode == 0, r.stderr
        argv = (t / "record.txt").read_text().split("\n")
        assert argv[:4] == ["--mode", "direct", "--role", "reviewer"], argv


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS: {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL: {fn.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
