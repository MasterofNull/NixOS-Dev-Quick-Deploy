#!/usr/bin/env python3
"""Antigravity worktree-bound implementer lane: dispatch, wake argv, completion validation.

Uses temp git repos and a fake `antigravity` binary on PATH; never touches the real IDE or inbox.
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELEGATE = ROOT / "scripts" / "ai" / "delegate-to-antigravity"
INBOX_SCRIPT = ROOT / "scripts" / "ai" / "aq-antigravity-inbox"
os.environ.pop("AQ_DELEGATION_DIR", None)
os.environ["AQ_ANTIGRAVITY_WINDOW_SETTLE_S"] = "0"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(mod)
    return mod


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def make_repo(td: Path):
    origin = td / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    repo = td / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    (repo / "tracked.txt").write_text("base\n")
    (repo / ".agent/collaboration").mkdir(parents=True)
    (repo / ".agent/collaboration/PULSE.log").write_text("p\n")
    (repo / ".agent/memory").mkdir(parents=True)
    (repo / ".agent/memory/issues-backlog.md").write_text("b\n")
    (repo / ".agent/collaboration/rsi-incidents.json").write_text("[]\n")
    (repo / ".agent/collaboration/AGENT-CATCHUP-QUEUE.md").write_text("q\n")
    (repo / "premod.txt").write_text("pre\n")
    (repo / ".gitignore").write_text(".agents/delegation/\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    return repo


def make_delegate(repo: Path):
    mod = load("dta_" + repo.name, DELEGATE)
    mod._REPO = repo
    mod._DELEGATION_DIR = repo / ".agents" / "delegation"
    mod._OUTPUTS_DIR = mod._DELEGATION_DIR / "outputs"
    mod._REGISTRY = mod._DELEGATION_DIR / "registry.jsonl"
    mod._ensure_dirs()
    return mod


def make_inbox(repo: Path):
    mod = load("inb_" + repo.name, INBOX_SCRIPT)
    mod.REPO = repo
    mod.INBOX = repo / ".agent" / "collaboration" / "antigravity-inbox"
    mod.STATE = mod.INBOX / ".lane-state.json"
    return mod


def fake_antigravity(td: Path) -> Path:
    bindir = td / "bin"
    bindir.mkdir()
    log = td / "argv.log"
    exe = bindir / "antigravity"
    exe.write_text(
        "#!/usr/bin/env python3\nimport json,sys\n"
        f"open({str(log)!r},'a').write(json.dumps(sys.argv[1:])+'\\n')\n"
    )
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"
    return log


def calls(log: Path):
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def simulate_ide_completion(inbox, repo, tid):
    out = repo / ".agents" / "delegation" / "outputs" / f"{tid}.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("implemented the change and ran checks; summary details here.\n")
    assert inbox.main(["claim", f"{tid}.md", "--actor", "ide-watch", "--json"]) == 0
    assert inbox.main(["complete", f".claimed-{tid}", "--output",
                       f".agents/delegation/outputs/{tid}.log", "--json"]) == 0


def dispatch(mod, repo, tid, role="implementer"):
    log = mod._OUTPUTS_DIR / f"{tid}.log"
    status, _, _ = mod._run_inbox(tid, "add feature", role, timeout=1, log_path=log)
    assert status == "timeout", status  # no IDE in test: dispatch itself must not exit/blocked
    return repo / ".agent/collaboration/antigravity-inbox" / f"{tid}.md"


def main():
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        argv_log = fake_antigravity(td)
        repo = make_repo(td)
        mod = make_delegate(repo)
        inbox = make_inbox(repo)

        # 1. dispatch: editing role is no longer blocked; worktree + headers + fingerprint.
        tid = "antigravity-20261010-120000-imp001"
        task = dispatch(mod, repo, tid)
        wt = repo / ".agents/delegation/worktrees" / tid
        assert wt.is_dir() and git(wt, "branch", "--show-current").strip() == f"delegate/{tid}"
        text = task.read_text()
        assert f"Workspace: {wt}" in text and f"Branch: delegate/{tid}" in text, text
        assert "IMPLEMENTER CONTRACT" in text and "Do not push" in text and "delivery-workflow.summary.md" in text
        side = json.loads((mod._OUTPUTS_DIR / f"{tid}.workspace.json").read_text())
        assert side["workspace"] == str(wt) and side["main_fingerprint"].startswith(git(repo, "rev-parse", "HEAD").strip())
        assert git(repo, "rev-parse", f"refs/delegate-base/{tid}").strip() == side["base"]
        print("PASS: dispatch creates worktree, headers, contract, fingerprint")

        # 2. wake: workspace path -> --new-window then chat --reuse-window.
        assert inbox.main(["wake", f"{tid}.md", "--actor", "owner-manual", "--json"]) == 0
        c = calls(argv_log)
        assert len(c) == 2, c
        assert c[0] == ["--new-window", str(wt)], c[0]
        assert c[1][:5] == ["chat", "--reuse-window", "--mode", "agent", c[1][4]] and c[1][0] == "chat"
        assert str(wt) in c[1][-1] and f"{tid}.md" in c[1][-1]
        # The window is the worktree; inbox paths must point at the main repo, not resolve inside it.
        assert f"{repo}/scripts/ai/aq-antigravity-inbox claim" in c[1][-1], c[1][-1]
        assert f"{inbox.INBOX}/.claimed-{tid}" in c[1][-1], c[1][-1]
        rec = [r for r in inbox._load(tid)["records"] if r["type"] == "wake_attempt"][-1]
        assert rec["wake_path"] == "workspace-bound" and rec["method"] == "cli-nudge-ok"
        # advisory task: original single argv, unchanged.
        argv_log.write_text("")
        adv = inbox.INBOX / "adv1.md"
        adv.write_text("Role: reviewer\nOutput: .agents/plans/adv1/antigravity.md\n")
        assert inbox.main(["wake", "adv1.md", "--actor", "owner-manual", "--json"]) == 0
        c = calls(argv_log)
        assert c == [list(inbox.WAKE_ARGV[1:])], c
        # editing role without a valid Workspace header stays blocked.
        bad = inbox.INBOX / "bad1.md"
        bad.write_text("Role: implementer\nOutput: .agents/plans/bad1/antigravity.md\n")
        assert inbox.main(["wake", "bad1.md", "--actor", "owner-manual", "--json"]) == 1
        bad.write_text(f"Role: implementer\nWorkspace: {repo}\nBranch: delegate/x\nOutput: .agents/plans/bad1/antigravity.md\n")
        assert inbox.main(["wake", "bad1.md", "--actor", "owner-manual", "--json"]) == 1
        print("PASS: wake argv for workspace and advisory tasks; spoofed workspace blocked")

        # 3a. completion rejected when a tracked main-checkout file changed (even with worktree change).
        (wt / "feature.txt").write_text("new\n")
        (repo / "tracked.txt").write_text("edited in main\n")
        simulate_ide_completion(inbox, repo, tid)
        ok, reason = mod._validate_inbox_completion(tid)
        assert not ok and "main checkout" in reason, (ok, reason)
        # append-only logs are ignored; restoring tracked file makes it acceptable.
        (repo / "tracked.txt").write_text("base\n")
        (repo / ".agent/collaboration/PULSE.log").write_text("p\nappended\n")
        (repo / ".agent/memory/issues-backlog.md").write_text("b\nappended\n")
        ok, reason = mod._validate_inbox_completion(tid)
        assert ok, reason
        patch = mod._OUTPUTS_DIR / f"{tid}.patch"
        assert patch.exists() and "feature.txt" in patch.read_text() and "+new" in patch.read_text()
        assert wt.is_dir() and git(repo, "rev-parse", f"delegate/{tid}").strip()  # retained, not merged
        assert git(repo, "rev-parse", "HEAD").strip() == side["main_fingerprint"].split(":")[0]
        print("PASS: main-checkout drift rejected, append-only logs ignored, patch handed back")

        # 3b. no worktree changes -> rejected.
        git(repo, "checkout", "-q", "--", ".")
        tid2 = "antigravity-20261010-120000-imp002"
        dispatch(mod, repo, tid2)
        simulate_ide_completion(inbox, repo, tid2)
        ok, reason = mod._validate_inbox_completion(tid2)
        assert not ok and "no changes" in reason, (ok, reason)
        assert not (mod._OUTPUTS_DIR / f"{tid2}.patch").exists()
        print("PASS: unchanged worktree rejected")

        # 3c. changes committed on the task branch (clean tree) still count.
        tid3 = "antigravity-20261010-120000-imp003"
        dispatch(mod, repo, tid3)
        wt3 = repo / ".agents/delegation/worktrees" / tid3
        (wt3 / "c.txt").write_text("c\n")
        git(wt3, "add", "-A")
        git(wt3, "-c", "user.email=a@b.c", "-c", "user.name=a", "commit", "-q", "-m", "c")
        simulate_ide_completion(inbox, repo, tid3)
        ok, reason = mod._validate_inbox_completion(tid3)
        assert ok and "c.txt" in (mod._OUTPUTS_DIR / f"{tid3}.patch").read_text(), reason
        print("PASS: committed-on-branch changes accepted")

        # 3d. owner pulls merged work during a long task (HEAD fast-forwards to origin/main): accepted.
        tid5 = "antigravity-20261010-120000-imp005"
        dispatch(mod, repo, tid5)
        (repo / ".agents/delegation/worktrees" / tid5 / "d.txt").write_text("d\n")
        other = td / "other"
        subprocess.run(["git", "clone", "-q", str(td / "origin.git"), str(other)], check=True)
        (other / "merged.txt").write_text("merged pr\n")
        git(other, "add", "-A")
        git(other, "-c", "user.email=a@b.c", "-c", "user.name=a", "commit", "-q", "-m", "merged")
        git(other, "push", "-q", "origin", "main")
        git(repo, "pull", "-q", "--ff-only", "origin", "main")
        simulate_ide_completion(inbox, repo, tid5)
        ok, reason = mod._validate_inbox_completion(tid5)
        assert ok, reason
        # a commit made directly in the main checkout (not on origin/main) is still drift.
        tid6 = "antigravity-20261010-120000-imp006"
        dispatch(mod, repo, tid6)
        (repo / ".agents/delegation/worktrees" / tid6 / "e.txt").write_text("e\n")
        (repo / "tracked.txt").write_text("committed in main by the agent\n")
        git(repo, "-c", "user.email=a@b.c", "-c", "user.name=a", "commit", "-q", "-am", "local")
        simulate_ide_completion(inbox, repo, tid6)
        ok, reason = mod._validate_inbox_completion(tid6)
        assert not ok and "not on origin/main" in reason, (ok, reason)
        print("PASS: fast-forward pull accepted; local main-checkout commit rejected")

        # 3e. fingerprint = SET OF PATHS: staging churn + runtime ledgers are not drift; a new path is.
        (repo / "premod.txt").write_text("pre-modified before dispatch\n")
        git(repo, "add", "premod.txt")  # staged (M ) at dispatch
        tid7 = "antigravity-20261010-120000-imp007"
        dispatch(mod, repo, tid7)
        (repo / ".agents/delegation/worktrees" / tid7 / "f.txt").write_text("f\n")
        git(repo, "reset", "-q", "premod.txt")  # orchestrator unstages (' M')
        (repo / ".agent/collaboration/rsi-incidents.json").write_text('[{"x":1}]\n')
        (repo / ".agent/collaboration/AGENT-CATCHUP-QUEUE.md").write_text("q\nmore\n")
        simulate_ide_completion(inbox, repo, tid7)
        ok, reason = mod._validate_inbox_completion(tid7)
        assert ok, reason
        tid8 = "antigravity-20261010-120000-imp008"
        dispatch(mod, repo, tid8)
        (repo / ".agents/delegation/worktrees" / tid8 / "g.txt").write_text("g\n")
        (repo / ".gitignore").write_text(".agents/delegation/\n# edited\n")
        simulate_ide_completion(inbox, repo, tid8)
        ok, reason = mod._validate_inbox_completion(tid8)
        assert not ok and "main checkout" in reason, (ok, reason)
        git(repo, "checkout", "-q", "--", ".gitignore")
        print("PASS: path-set fingerprint ignores staging churn and runtime ledgers")

        # 3f. ALREADY PRESENT no-op accepted with distinct outcome; plain no-change still rejected.
        assert "ALREADY PRESENT:" in mod._IMPLEMENTER_CONTRACT and "origin/main" in mod._IMPLEMENTER_CONTRACT
        tid9 = "antigravity-20261010-120000-imp009"
        dispatch(mod, repo, tid9)
        assert "ALREADY PRESENT:" in (repo / ".agent/collaboration/antigravity-inbox" / f"{tid9}.md").read_text()
        simulate_ide_completion(inbox, repo, tid9)
        out9 = mod._OUTPUTS_DIR / f"{tid9}.log"
        ok, reason = mod._validate_inbox_completion(tid9)
        assert not ok and "no changes" in reason, (ok, reason)
        tid10 = "antigravity-20261010-120000-imp010"
        dispatch(mod, repo, tid10)
        out10 = mod._OUTPUTS_DIR / f"{tid10}.log"
        out10.write_text("ALREADY PRESENT: commit abcd1234 on origin/main already does this\n")
        assert inbox.main(["claim", f"{tid10}.md", "--actor", "ide-watch", "--json"]) == 0
        assert inbox.main(["complete", f".claimed-{tid10}", "--output",
                           f".agents/delegation/outputs/{tid10}.log", "--json"]) == 0
        ok, reason = mod._validate_inbox_completion(tid10)
        assert ok and reason.startswith("already-present"), (ok, reason)
        assert not (mod._OUTPUTS_DIR / f"{tid10}.patch").exists()
        print("PASS: ALREADY PRESENT contract + no-op acceptance")

        # 2b. wake dedupe: one window per task within the window; concurrent wakes too.
        argv_log.write_text("")
        tidw = "antigravity-20261010-120000-wak011"
        dispatch(mod, repo, tidw)
        os.environ.pop("AQ_ANTIGRAVITY_WAKE_DEDUPE_S", None)
        assert inbox.main(["wake", f"{tidw}.md", "--actor", "auto-delegate", "--json"]) == 0
        assert inbox.main(["wake", f"{tidw}.md", "--actor", "owner-manual", "--json"]) == 0
        c = calls(argv_log)
        assert sum(1 for x in c if x and x[0] == "--new-window") == 1, c
        last = [r for r in inbox._load(tidw)["records"] if r["type"] == "wake_attempt"][-1]
        assert last["method"] == "skipped-recent-wake", last
        os.environ["AQ_ANTIGRAVITY_WAKE_DEDUPE_S"] = "0"
        assert inbox.main(["wake", f"{tidw}.md", "--actor", "owner-manual", "--json"]) == 0
        assert sum(1 for x in calls(argv_log) if x and x[0] == "--new-window") == 2
        os.environ.pop("AQ_ANTIGRAVITY_WAKE_DEDUPE_S", None)
        argv_log.write_text("")
        tidc = "antigravity-20261010-120000-wak012"
        dispatch(mod, repo, tidc)
        rcs = []
        ths = [threading.Thread(target=lambda a=a: rcs.append(inbox.main(["wake", f"{tidc}.md", "--actor", a, "--json"])))
               for a in ("auto-delegate", "owner-manual", "owner-manual")]
        [x.start() for x in ths]
        [x.join() for x in ths]
        assert rcs == [0, 0, 0], rcs
        assert sum(1 for x in calls(argv_log) if x and x[0] == "--new-window") == 1, calls(argv_log)
        print("PASS: wake dedupe (sequential, expired window, concurrent)")

        # 4. advisory role dispatch: no worktree, no Workspace header.
        tid4 = "antigravity-20261010-120000-adv004"
        task4 = dispatch(mod, repo, tid4, role="reviewer")
        assert "Workspace:" not in task4.read_text()
        assert not (repo / ".agents/delegation/worktrees" / tid4).exists()
        print("PASS: advisory dispatch unchanged")

    with tempfile.TemporaryDirectory() as t:
        # 5. non-git repo: editing dispatch refused fail-closed, nothing created.
        repo = Path(t)
        mod = make_delegate(repo)
        try:
            mod._run_inbox("antigravity-20261010-120000-nog005", "x", "implementer", 1,
                           mod._OUTPUTS_DIR / "x.log")
        except SystemExit as exc:
            assert "blocked_unsupported_ide_worktree_isolation" in str(exc)
        else:
            raise AssertionError("expected refusal without a git repo")
        assert not (repo / ".agent").exists()
        print("PASS: no-worktree dispatch refused")
    print("PASS: antigravity implementer lane")


if __name__ == "__main__":
    main()
