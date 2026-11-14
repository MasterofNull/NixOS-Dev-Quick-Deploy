#!/usr/bin/env python3
"""tier0.d/check-plan-paths: staged plans may only cite existing repo paths unless the line says NEW."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "governance" / "tier0.d" / "check-plan-paths.py"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")


def run(files):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=ENV)
        (root / "scripts").mkdir()
        (root / "scripts/real.py").write_text("x\n")
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=ENV)
        r = subprocess.run([sys.executable, str(GATE), "--pre-commit"], cwd=root, capture_output=True, text=True, env=ENV)
        return r.returncode, r.stdout + r.stderr


def test_missing_path_fails_with_file_and_line():
    rc, out = run({".agents/plans/p/PLAN.md": "ok `scripts/real.py`\nuse `scripts/ghost.sh` here\n"})
    assert rc == 1 and "PLAN.md:2" in out and "scripts/ghost.sh" in out and "real.py" not in out, out


def test_new_marker_and_existing_paths_pass():
    rc, out = run({".agents/plans/p/PLAN.md": "add `scripts/ghost.sh` (new)\nadd `docs/x.md` NEW\nuse `scripts/real.py:12`\n"})
    assert rc == 0, out


def test_project_prd_is_in_scope_and_other_markdown_is_not():
    rc, out = run({".agent/PROJECT-X-PRD.md": "see `nix/modules/ghost.nix`\n"})
    assert rc == 1, out
    rc, out = run({"docs/other.md": "see `nix/modules/ghost.nix`\n"})
    assert rc == 0, out


def test_globs_urls_placeholders_and_plain_words_are_ignored():
    rc, out = run({".agents/plans/p/PLAN.md":
                   "`scripts/*.py` `https://x.io/a/b.md` `<dir>/file.py` `and/or` `/abs/path.txt` `scripts/$VAR/x.sh`\n"})
    assert rc == 0, out


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if fails else 0)
