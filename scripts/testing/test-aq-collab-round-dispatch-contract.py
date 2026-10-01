#!/usr/bin/env python3
"""aq-collab-round must record real task ids and never silently lose a lane.

Regression (2026-10-01, round tiered-auto-update-prd-20261001): codex was sent
`--mode edit --shared` (refused by delegate-to-codex), the last stdout line
("Output file: ...") was recorded as its task id, and local's shim was killed
by a 30s run() timeout before launching. Round sat DISPATCHED with 0 lanes live.
"""
import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("aq_collab_round", str(REPO / "scripts/ai/aq-collab-round"))
spec = importlib.util.spec_from_loader("aq_collab_round", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)


def _cp(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def test_parse_task_id_ignores_trailing_lines():
    out = ("[delegate-to-codex] Delegating task: codex-20261001-084150-gvj9qx\n"
           "[delegate-to-codex] Mode:            edit\n"
           "[delegate-to-codex] Output file:     /x/codex-20261001-084150-gvj9qx.log\n")
    assert mod._parse_task_id(out) == "codex-20261001-084150-gvj9qx"
    assert mod._parse_task_id("[delegate-to-codex] Output file: /x.log\n") == ""


def test_codex_dispatched_isolated_not_shared(tmp_path):
    pf = tmp_path / "p.txt"; pf.write_text("x")
    with mock.patch.object(mod.subprocess, "run", return_value=_cp("[d] Delegating task: codex-1\n")) as run:
        assert mod._dispatch_process("codex", pf, 60) == "codex-1"
    cmd = run.call_args.args[0]
    assert "--shared" not in cmd and "--mode" in cmd


def test_refused_launch_is_reported_not_recorded(tmp_path):
    pf = tmp_path / "p.txt"; pf.write_text("x")
    refused = _cp("[d] Delegating task: codex-2\n", "ERROR: shared editing is not authorized", rc=1)
    with mock.patch.object(mod.subprocess, "run", return_value=refused):
        r = mod._dispatch_process("codex", pf, 60)
    assert r.startswith("error:rc=1:") and "not authorized" in r


def test_launch_budget_exceeds_preflight_gates(tmp_path):
    pf = tmp_path / "p.txt"; pf.write_text("x")
    with mock.patch.object(mod.subprocess, "run", return_value=_cp("[d] Delegating task: local-3\n")) as run:
        assert mod._dispatch_process("local", pf, 60) == "local-3"
    assert run.call_args.kwargs["timeout"] >= 120
    with mock.patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
        assert mod._dispatch_process("local", pf, 60) == "error:launch-timeout"


def test_uncommitted_task_inputs_detected(tmp_path):
    # Committed file -> clean; untracked file -> flagged; nonexistent path -> ignored.
    repo = tmp_path / "r"; (repo / "docs").mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    run("init", "-q"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
    (repo / "docs/committed.md").write_text("a"); run("add", "."); run("commit", "-qm", "x")
    (repo / "docs/new-prd.md").write_text("b")
    with mock.patch.object(mod, "REPO", repo):
        task = "Read docs/committed.md, docs/new-prd.md and nix/missing.nix (bounded reads)."
        assert mod._uncommitted_task_inputs(task) == ["docs/new-prd.md"]
        (repo / "docs/committed.md").write_text("changed")
        assert mod._uncommitted_task_inputs(task) == ["docs/committed.md", "docs/new-prd.md"]


if __name__ == "__main__":
    import tempfile
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                if fn.__code__.co_argcount:
                    with tempfile.TemporaryDirectory() as d:
                        fn(Path(d))
                else:
                    fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if fails else 0)
