#!/usr/bin/env python3
"""FT-7 tests: check-lane-hook-parity PASS/GAP on fixture repos."""
import os
import subprocess
import tempfile
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "governance/tier0.d/check-lane-hook-parity.sh"
LANES = ["codex", "local", "claude", "antigravity"]

def build(root: Path, hooks=True, bypass=False):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".githooks").mkdir()
    pc = root / ".githooks/pre-commit"
    pc.write_text("#!/bin/sh\nexit 0\n"); pc.chmod(0o755)
    if hooks:
        subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", ".githooks"], check=True)
    ai = root / "scripts/ai"; (ai / "lib").mkdir(parents=True)
    (ai / "lib/worktree-isolation.sh").write_text("git commit -q -m x\n")
    for lane in LANES:
        body = "#!/bin/sh\n"
        if lane in ("codex", "local"):
            body += "source lib/worktree-isolation.sh\n"
        if lane == "antigravity":
            body += "# blocked_unsupported_ide_worktree_isolation\n"
        if bypass and lane == "local":
            body += "git commit --no-verify -m x\n"
        (ai / f"delegate-to-{lane}").write_text(body)

def run(root):
    env = dict(os.environ, LANE_PARITY_ROOT=str(root))
    p = subprocess.run(["bash", str(CHECK), "--pre-commit"], env=env, capture_output=True, text=True)
    assert p.returncode == 0, "must never block"
    return p.stdout

with tempfile.TemporaryDirectory() as d:
    a = Path(d) / "ok"; build(a); out = run(a)
    assert "GAP" not in out and "every lane reaches the same commit gate at integration" in out, out
    b = Path(d) / "nohooks"; build(b, hooks=False); out = run(b)
    assert "GAP: repo root core.hooksPath" in out, out
    c = Path(d) / "bypass"; build(c, bypass=True); out = run(c)
    assert "GAP: lane local" in out and "lane codex: dispatch" in out, out
print("PASS")
