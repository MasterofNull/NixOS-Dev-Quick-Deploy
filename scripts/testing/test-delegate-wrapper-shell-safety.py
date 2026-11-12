#!/usr/bin/env python3
"""Regression: delegate-to-codex / delegate-to-gemini background launch is shell-safe.

Root cause (backlog generated-background-shell-loses-errors-and-reparses-prompts):
the background branch interpolated the raw prompt into a double-quoted `bash -c` string
(shell re-parsed prompt text) and ended `> /dev/null 2>&1 &` (launch errors lost); registry
rewrites used a non-transactional inline `open(rf, 'w')` heredoc.

Each case runs the real wrapper from a throwaway copy of scripts/ai (so its registry and
outputs are isolated) against a stub provider binary.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))
from task_registry import TaskRegistry  # noqa: E402

TRUE = shutil.which("true") or "true"
NASTY_PROMPT = (
    "line1 $(touch PWNED_SUBST) `touch PWNED_TICK` \"dq\" 'sq' ; touch PWNED_SEMI\n"
    "line2 \\n ${HOME} $HOME && touch PWNED_AND\n"
    "tail with 'quote\" and EOF\nPYEOF\n"
)

STUB = """#!/usr/bin/env python3
import json, os, sys
out = os.environ.get("STUB_ARGV_OUT")
if out:
    with open(out, "w") as fh:
        json.dump(sys.argv[1:], fh)
if os.environ.get("STUB_FAIL"):
    sys.stderr.write("boom-launch-error\\n")
    sys.exit(3)
print("stub-ok " * 100)
"""


def make_sandbox() -> Path:
    root = Path(tempfile.mkdtemp(prefix="delegate-shell-safety-"))
    shutil.copytree(
        REPO_ROOT / "scripts" / "ai",
        root / "scripts" / "ai",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        symlinks=True,
    )
    (root / "config").mkdir()
    # Egress gate fails closed without its config.
    shutil.copy2(REPO_ROOT / "config" / "remote-lane-egress.json", root / "config" / "remote-lane-egress.json")
    (root / ".agents" / "delegation" / "outputs").mkdir(parents=True)
    stub = root / "stub-provider"
    stub.write_text(STUB)
    stub.chmod(0o755)
    return root


def registry_rows(root: Path) -> list[dict]:
    path = root / ".agents" / "delegation" / "registry.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def wait_terminal(root: Path, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = registry_rows(root)
        if rows and rows[-1].get("status") not in ("running", None):
            return rows[-1]
        time.sleep(0.2)
    logs = {p.name: p.read_text()[-600:] for p in (root / ".agents" / "delegation" / "outputs").glob("*.log")}
    raise AssertionError(f"task never left running: {registry_rows(root)} logs={logs}")


def _fixture_env(root: Path, **extra: str) -> dict:
    """Ambient env with the wrappers' state dir pinned to the fixture (the group runner sets AQ_DELEGATION_DIR elsewhere)."""
    return {**os.environ, "AQ_DELEGATION_DIR": str(root / ".agents" / "delegation"), **extra}


def run_wrapper(provider: str, root: Path, fail: bool, extra: tuple = ()) -> tuple[subprocess.CompletedProcess, Path]:
    env = _fixture_env(root)
    argv_out = root / "argv.json"
    env.update(
        {
            "STUB_ARGV_OUT": str(argv_out),
            "HYBRID_COORDINATOR_URL": "http://127.0.0.1:9",
            "A2A_BUDGET_BYPASS": "1",
            "DELEGATE_CODEX_IGNORE_COOLDOWN": "1",
        }
    )
    env.pop("STUB_FAIL", None)
    if fail:
        env["STUB_FAIL"] = "1"
    stub = str(root / "stub-provider")
    if provider == "codex":
        env["CODEX_BIN"] = stub
        args = ["--prompt", NASTY_PROMPT, "--shared", "--mode", "safe", *extra]
    else:
        env["GEMINI_BIN"] = stub
        args = ["--prompt", NASTY_PROMPT]
    proc = subprocess.run(
        [str(root / "scripts" / "ai" / f"delegate-to-{provider}")] + args,
        cwd=root, env=env, capture_output=True, text=True, timeout=60,
    )
    return proc, argv_out


def run_gemini(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = _fixture_env(root)
    env.update(
        {
            "STUB_ARGV_OUT": str(root / "argv.json"),
            "GEMINI_BIN": str(root / "stub-provider"),
            "HYBRID_COORDINATOR_URL": "http://127.0.0.1:9",
            "A2A_BUDGET_BYPASS": "1",
        }
    )
    env.pop("STUB_FAIL", None)
    return subprocess.run(
        [str(root / "scripts" / "ai" / "delegate-to-gemini")] + args,
        cwd=root, env=env, capture_output=True, text=True, timeout=60,
    )


def check_gemini_mode_mapping() -> None:
    for wrapper_mode, cli_mode in (("yolo", "auto"), ("auto_edit", "accept-edits"), ("plan", "plan")):
        root = make_sandbox()
        try:
            proc = run_gemini(root, ["--prompt", "hi", "--mode", wrapper_mode])
            assert proc.returncode == 0, f"{wrapper_mode}: rc={proc.returncode} {proc.stderr}"
            wait_terminal(root)
            argv = json.loads((root / "argv.json").read_text())
            assert argv[argv.index("--mode") + 1] == cli_mode, f"{wrapper_mode}: argv={argv!r}"
            assert "--approval-mode" not in argv, f"{wrapper_mode}: obsolete option passed: {argv!r}"
        finally:
            shutil.rmtree(root, ignore_errors=True)
    print("PASS gemini: yolo->auto, auto_edit->accept-edits, plan->plan, no --approval-mode")


def check_gemini_noise_only_output() -> None:
    """All-filtered output (e.g. 429 quota noise) must count as 0 meaningful bytes, not a bash arithmetic error."""
    root = make_sandbox()
    try:
        proc = run_gemini(root, ["--prompt", "hi"])
        assert proc.returncode == 0, proc.stderr
        row = wait_terminal(root)
        (root / row["output_file"]).write_text("Warning: quota\nAttempt 1 failed. retrying with backoff\n")
        env = _fixture_env(root, GEMINI_BIN=str(root / "stub-provider"))
        chk = subprocess.run(
            [str(root / "scripts" / "ai" / "delegate-to-gemini"), "--check", row["id"]],
            cwd=root, env=env, capture_output=True, text=True, timeout=60,
        )
        assert chk.returncode == 0, f"rc={chk.returncode} {chk.stderr}"
        assert "syntax error" not in chk.stderr and "integer expression" not in chk.stderr, chk.stderr
        assert "0B meaningful content" in chk.stderr, chk.stderr
        print("PASS gemini: noise-only output reported as 0 meaningful bytes, no arithmetic error")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_gemini_wait_nonzero_exit() -> None:
    """--wait with a failing provider must reach the failure handling, not die on set -e at the tee pipeline."""
    root = make_sandbox()
    try:
        env = _fixture_env(root)
        env.update(STUB_FAIL="1", STUB_ARGV_OUT=str(root / "argv.json"), GEMINI_BIN=str(root / "stub-provider"),
                   HYBRID_COORDINATOR_URL="http://127.0.0.1:9", A2A_BUDGET_BYPASS="1")
        proc = subprocess.run(
            [str(root / "scripts" / "ai" / "delegate-to-gemini"), "--prompt", "hi", "--wait"],
            cwd=root, env=env, capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr
        assert proc.returncode == 3, f"rc={proc.returncode} {out}"
        assert "failed (exit 3" in out, out
        row = registry_rows(root)[-1]
        assert row["status"] == "failed", row
        assert "boom-launch-error" in (root / row["output_file"]).read_text()
        print("PASS gemini: --wait non-zero exit reaches failure handling, status failed, stderr in log")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_gemini_oversize_prompt() -> None:
    root = make_sandbox()
    try:
        # Via file: the same limit would block passing this much text to the wrapper itself as argv.
        big = root / "big-prompt.txt"
        big.write_text("x" * 131072)
        proc = run_gemini(root, ["--prompt-file", str(big)])
        assert proc.returncode != 0, proc.stdout
        assert "too large" in proc.stderr and "131071" in proc.stderr, proc.stderr
        assert not (root / "argv.json").exists(), "stub was invoked despite oversize prompt"
        print("PASS gemini: oversize prompt rejected with clear error, provider never invoked")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_provider(provider: str) -> None:
    # 1. prompt reaches the provider byte-identical; nothing executes
    root = make_sandbox()
    try:
        proc, argv_out = run_wrapper(provider, root, fail=False)
        assert proc.returncode == 0, f"{provider}: rc={proc.returncode} {proc.stderr}"
        row = wait_terminal(root)
        assert row["status"] == "done", f"{provider}: {row}"
        argv = json.loads(argv_out.read_text())
        full_prompt = argv[argv.index("-p") + 1] if provider == "gemini" else argv[-1]
        assert full_prompt.endswith(NASTY_PROMPT), f"{provider}: prompt mangled: {full_prompt[-200:]!r}"
        for marker in root.rglob("PWNED*"):
            raise AssertionError(f"{provider}: prompt text was executed: {marker}")
        assert not list(Path.cwd().glob("PWNED*"))
        assert isinstance(row.get("pid"), int), f"{provider}: pid not recorded: {row}"
        print(f"PASS {provider}: nasty prompt byte-identical, nothing executed")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 2. failing provider launch leaves its error in the task log
    root = make_sandbox()
    try:
        proc, _ = run_wrapper(provider, root, fail=True)
        assert proc.returncode == 0, f"{provider}: rc={proc.returncode} {proc.stderr}"
        row = wait_terminal(root)
        assert row["status"] == "failed", f"{provider}: {row}"
        log = (root / row["output_file"]).read_text()
        assert "boom-launch-error" in log, f"{provider}: error lost, log={log!r}"
        print(f"PASS {provider}: failing launch error preserved in task log")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_worker_launch_error_logged() -> None:
    """A worker that cannot even start (bad cd dir) must log, not vanish."""
    root = make_sandbox()
    try:
        out = root / "out.log"
        worker = root / "scripts" / "ai" / "lib" / "codex-background-worker.sh"
        reg = root / ".agents" / "delegation" / "registry.jsonl"
        TaskRegistry(reg.parent).append("t1", "d", "out.log", "x", "r")
        subprocess.run(
            ["bash", str(worker), str(out), TRUE, "http://127.0.0.1:9", str(reg), "t1",
             "safe", "p", TRUE, "", "", str(root / "no-such-dir"), "--", TRUE],
            check=False, timeout=30,
        )
        assert "no-such-dir" in out.read_text(), out.read_text()
        assert registry_rows(root)[0]["status"] == "failed", (registry_rows(root), out.read_text())
        print("PASS codex worker: bad launch dir error preserved, status failed")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_registry_transactional() -> None:
    root = Path(tempfile.mkdtemp(prefix="delegate-registry-"))
    try:
        reg = TaskRegistry(root)
        n = 40
        for i in range(n):
            reg.append_row_atomic({"id": f"t{i}", "status": "running", "description": "x" * 6000})
        stop = threading.Event()
        bad: list[str] = []

        def reader() -> None:
            while not stop.is_set():
                text = reg.registry_file.read_text()
                lines = [ln for ln in text.split("\n") if ln]
                try:
                    parsed = [json.loads(ln) for ln in lines]
                except json.JSONDecodeError as exc:
                    bad.append(f"truncated/partial read: {exc}")
                    return
                if len(parsed) != n or not text.endswith("\n"):
                    bad.append(f"row count {len(parsed)} != {n}")
                    return

        t = threading.Thread(target=reader)
        t.start()
        for rnd in range(30):
            for i in range(0, n, 5):
                reg.update_fields_atomic(f"t{i}", {"status": "done", "pid": rnd})
        stop.set()
        t.join()
        assert not bad, bad
        rows = [json.loads(x) for x in reg.registry_file.read_text().splitlines() if x]
        assert rows[0]["status"] == "done" and rows[1]["status"] == "running"

        # CLI helper goes through the same path and keeps unparseable legacy lines
        with open(reg.registry_file, "a") as fh:
            fh.write("not-json-legacy-line\n")
        cli = REPO_ROOT / "scripts" / "ai" / "lib" / "registry-update.py"
        subprocess.run([sys.executable, str(cli), "set", str(reg.registry_file), "t1", "pid", "77"], check=True)
        text = reg.registry_file.read_text()
        assert "not-json-legacy-line" in text
        assert [json.loads(x) for x in text.splitlines() if x.startswith("{")][1]["pid"] == 77
        print("PASS registry: transactional writers, no truncation under concurrent reader")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_codex_context_profiles() -> None:
    """Every codex context profile (explicit full, explicit lean, auto on a short prompt) delivers the prompt intact."""
    for label, extra in (("full", ("--context-profile", "full")), ("lean", ("--context-profile", "lean")), ("auto", ())):
        root = make_sandbox()
        try:
            proc, argv_out = run_wrapper("codex", root, fail=False, extra=extra)
            assert proc.returncode == 0, f"codex/{label}: rc={proc.returncode} {proc.stderr}"
            row = wait_terminal(root)
            assert row["status"] == "done", f"codex/{label}: {row}"
            delivered = json.loads(argv_out.read_text())[-1]
            assert delivered.endswith(NASTY_PROMPT), f"codex/{label}: prompt mangled: {delivered[-200:]!r}"
            assert delivered.count(NASTY_PROMPT) == 1, f"codex/{label}: prompt duplicated"
            assert not list(root.rglob("PWNED*")), f"codex/{label}: prompt text was executed"
            assert not list(Path.cwd().glob("PWNED*"))
            print(f"PASS codex/{label}: prompt byte-identical (trailing newline kept), nothing executed")
        finally:
            shutil.rmtree(root, ignore_errors=True)


def check_wrappers_use_transactional_path() -> None:
    for w in sorted((REPO_ROOT / "scripts" / "ai" / "lib").glob("*-background-worker.sh")):
        subprocess.run(["bash", "-n", str(w)], check=True)
    for name in ("delegate-to-codex", "delegate-to-gemini", "delegate-to-claude"):
        text = (REPO_ROOT / "scripts" / "ai" / name).read_text()
        assert "open(rf, 'w')" not in text and 'open(registry_file, "w")' not in text, name
        assert "> /dev/null 2>&1 &" not in text, f"{name}: background launch still discards errors"
        assert "bash -c \"" not in text, f"{name}: still builds a bash -c string"
    print("PASS wrappers: no inline registry rewrite / bash -c / discarded launch stderr")


def main() -> int:
    check_registry_transactional()
    check_wrappers_use_transactional_path()
    check_worker_launch_error_logged()
    check_provider("codex")
    check_codex_context_profiles()
    check_provider("gemini")
    check_gemini_mode_mapping()
    check_gemini_noise_only_output()
    check_gemini_oversize_prompt()
    check_gemini_wait_nonzero_exit()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
