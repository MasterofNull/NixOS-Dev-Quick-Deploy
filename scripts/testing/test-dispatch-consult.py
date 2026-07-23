#!/usr/bin/env python3
"""
Tests for scripts/ai/lib/dispatch_consult.py — the shared aq-role-route /
aq-slice-claim consult library, and (resolution B) its CLI seam used by the
non-frozen scripts/ai/delegate-to-local shim.

DESIGN SSOT: .agents/plans/agent-agnostic-factory/DISPATCH-INTEGRATION-DESIGN.md
  (see "## Amendment: resolution B" — dispatch.py stays frozen/untouched
  under the L2B golden-source manifest; the consult wiring lives in the
  delegate-to-local shim via this module's CLI instead.)

Covers the design's 6 original library acceptance test cases plus the
resolution-B CLI cases:
  1. Happy path: route returns the requested lane + claim acquires -> ok, token set.
  2. Substitution: route returns a different lane -> ok with routed_lane/reason
     surfaced, but the claim is still acquired under the REQUESTED lane (never
     silently applied).
  3. Blocked: claim already-held -> blocked, current owner surfaced, NO release
     of someone else's claim.
  4. Fail-open (load-bearing): broken tool path -> ok, degraded=True. Negative
     control: the same broken-tool condition WOULD block without the fail-open
     branch (proven via the internal _fail_open=False toggle, not by
     re-implementing the logic in the test).
  5. Context manager releases on normal exit AND on exception.
  6. Read-only dispatch.py subcommands never reach dispatch_task -> never
     consult, AND dispatch.py itself carries NO consult wiring (frozen/pinned
     under the L2B manifest — resolution B keeps the seam out of this file).
  7. CLI `consult` subcommand: happy path -> JSON to stdout, exit 0.
  8. CLI `consult` subcommand: blocked -> "blocked":true JSON, exit 3.
  9. CLI `release` subcommand: prints JSON, exit 0.
  10. CLI fail-open: an internal exception (patched-in raise) still prints
      ok=True/degraded=True JSON and exits 0 — the CLI itself can never block
      a caller's dispatch because of its own failure.

All fake tools are tiny standalone python scripts invoked via `sys.executable
<path> <args>`, exactly how dispatch_consult.py invokes the real tools — no
shell=True anywhere, matching the library's own contract. The CLI tests in
turn invoke dispatch_consult.py itself as a subprocess (`sys.executable
dispatch_consult.py consult ...`), pointed at the same kind of stub tool
binaries via its test-only --role-route-bin/--slice-claim-bin flags, so they
exercise the real argv/stdout/exit-code contract instead of calling library
functions directly.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ai" / "lib"
DISPATCH_CONSULT_PY = LIB / "dispatch_consult.py"
sys.path.insert(0, str(LIB))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_module(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: dispatch_consult.py defines a @dataclass
    # (ConsultResult) directly in-module, and dataclasses' own type
    # resolution does `sys.modules.get(cls.__module__).__dict__` — that
    # lookup fails with a bare AttributeError unless the module is already
    # registered under its own name before exec_module() runs.
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def _write_stub(path: Path, body: str) -> Path:
    """Write a tiny fake tool script that prints JSON to stdout. Invoked as
    `sys.executable <path> <args>` (never relies on the shebang/exec bit,
    matching how dispatch_consult._run_tool calls real tools) but chmod +x
    anyway so a stray direct-exec probe would also work."""
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _role_route_stub(tmp: Path, *, chosen: str, reason: str = "cheapest eligible", ok: bool = True) -> Path:
    body = f"""
import json, sys
payload = {{
    "ok": {ok!r},
    "role": "implementer",
    "subject": sys.argv[2] if len(sys.argv) > 2 else "unknown",
    "chosen_agent": {chosen!r} if {ok!r} else None,
    "reason": {reason!r},
    "alternates": [],
    "excluded": [],
}}
print(json.dumps(payload))
"""
    return _write_stub(tmp / "fake-role-route.py", body)


def _slice_claim_stub_recording(
    tmp: Path,
    *,
    acquire_response: dict,
    name: str = "fake-slice-claim.py",
) -> tuple[Path, Path]:
    """A claim-tool stub that always answers `acquire_response` to `acquire`
    and always succeeds on `release`, logging every invocation's argv (minus
    --json) to a sibling `calls.log` (one JSON line per call) so tests can
    assert exactly what was/wasn't called."""
    log_name = f"{name}.calls.log"
    acquire_json = json.dumps(acquire_response)
    body = f"""
import json, sys
from pathlib import Path
LOG = Path(__file__).with_name({log_name!r})
with LOG.open("a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
cmd = sys.argv[1]
if cmd == "acquire":
    print({acquire_json!r})
elif cmd == "release":
    print(json.dumps({{"ok": True, "reason": "released", "slice_id": sys.argv[2], "owner": "local"}}))
else:
    print(json.dumps({{"ok": False, "reason": "unsupported-cmd"}}))
"""
    stub = _write_stub(tmp / name, body)
    log = tmp / log_name
    return stub, log


def _read_calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── test 1: happy path ──────────────────────────────────────────────────────

def test_happy_path_ok_and_token_set():
    dispatch_consult = _load_module("dispatch_consult_t1", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "SUBJ", "owner": "local"}
        )

        result = dispatch_consult.consult_before_dispatch(
            "SUBJ", "implementer", "local", "deadbeef",
            role_route_bin=route_bin, slice_claim_bin=claim_bin,
        )

        assert_true(result.ok, f"expected ok=True, got {result.as_dict()}")
        assert_true(not result.blocked, "happy path must not be blocked")
        assert_true(not result.degraded, "happy path must not be degraded")
        assert_true(result.claim_token == "SUBJ", "claim_token must be the subject id")
        assert_true(result.routed_lane == "local", f"expected routed_lane=local, got {result.routed_lane}")
        assert_true(not result.substituted, "happy path (same lane) must not report substitution")

        calls = _read_calls(log)
        assert_true(len(calls) == 1 and calls[0][0] == "acquire", f"expected exactly one acquire call, got {calls}")
        print("PASS  happy path: ok=True, claim_token set, routed_lane matches requested")


# ── test 2: substitution surfaced, not silently applied ─────────────────────

def test_substitution_surfaced_claim_stays_on_requested_lane():
    dispatch_consult = _load_module("dispatch_consult_t2", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Router says "codex" would be the choice; caller requested "local".
        route_bin = _role_route_stub(tmp_path, chosen="codex", reason="local flagged-down; substituted codex")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "SUBJ2", "owner": "local"}
        )

        result = dispatch_consult.consult_before_dispatch(
            "SUBJ2", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=claim_bin,
        )

        assert_true(result.ok, f"substitution must still be ok=True (advisory only), got {result.as_dict()}")
        assert_true(result.substituted, "substitution must be flagged True")
        assert_true(result.routed_lane == "codex", f"routed_lane must surface router's choice, got {result.routed_lane}")
        assert_true(result.requested_lane == "local", "requested_lane must be preserved unchanged")
        assert_true(result.reason and "codex" in result.reason, "reason must mention the substitution")

        # The critical assertion: the claim itself must NOT have been silently
        # redirected to the routed lane — it stays under the caller's own
        # (requested) identity.
        assert_true(result.claim_owner == "local", f"claim must stay owned by requested lane, got {result.claim_owner}")
        calls = _read_calls(log)
        assert_true(calls[0][0] == "acquire" and "--owner" in calls[0] and "local" in calls[0],
                    f"acquire call must use owner=local (requested), got {calls[0]}")
        print("PASS  substitution surfaced (routed_lane=codex) without silently redirecting the claim owner")


# ── test 3: blocked, no release of someone else's claim ─────────────────────

def test_blocked_already_held_no_release_of_others_claim():
    dispatch_consult = _load_module("dispatch_consult_t3", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path,
            acquire_response={
                "ok": False, "reason": "already-held", "slice_id": "SUBJ3",
                "current_owner": "codex-other-session", "current_head": "cafebabe",
            },
        )

        # Use the context manager (not the bare function) so the "no release"
        # guarantee on blocked is exercised end to end.
        with dispatch_consult.dispatch_consult(
            "SUBJ3", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=claim_bin,
        ) as result:
            assert_true(result.blocked, f"already-held must block, got {result.as_dict()}")
            assert_true(result.ok is False, "blocked result must have ok=False")
            assert_true(result.current_owner == "codex-other-session",
                        f"current_owner must be surfaced, got {result.current_owner}")

        calls = _read_calls(log)
        assert_true(len(calls) == 1 and calls[0][0] == "acquire",
                    f"expected exactly one acquire call and NO release, got {calls}")
        print("PASS  blocked (already-held) surfaces current owner and never calls release")


# ── test 4: fail-open (load-bearing) + negative control ─────────────────────

def test_fail_open_degrades_and_negative_control_proves_it_is_load_bearing():
    dispatch_consult = _load_module("dispatch_consult_t4", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")  # route tool healthy
        broken_claim_bin = tmp_path / "does-not-exist.py"  # claim tool: missing binary

        # Production behavior: fail-open, degraded, dispatch proceeds.
        degraded_result = dispatch_consult.consult_before_dispatch(
            "SUBJ4", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=broken_claim_bin,
        )
        assert_true(degraded_result.ok, f"missing claim tool must fail OPEN (ok=True), got {degraded_result.as_dict()}")
        assert_true(degraded_result.degraded, "missing claim tool must set degraded=True")
        assert_true(not degraded_result.blocked, "fail-open must never block")
        assert_true(degraded_result.reason and "claim-degraded" in degraded_result.reason,
                    f"reason should explain the degrade, got {degraded_result.reason}")

        # Negative control: SAME broken-tool condition, only _fail_open flipped
        # to False. If this did NOT flip to blocked, the fail-open branch above
        # would be provably vacuous (dead code that never changes behavior).
        no_fail_open_result = dispatch_consult.consult_before_dispatch(
            "SUBJ4", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=broken_claim_bin,
            _fail_open=False,
        )
        assert_true(no_fail_open_result.blocked,
                    f"negative control: without fail-open the same condition must block, got {no_fail_open_result.as_dict()}")
        assert_true(no_fail_open_result.ok is False, "negative control must have ok=False")
        assert_true(
            no_fail_open_result.reason and no_fail_open_result.reason.startswith("no-fail-open-would-block:"),
            f"negative-control reason must show what fail-open suppressed, got {no_fail_open_result.reason}",
        )
        print("PASS  fail-open degrades on missing tool; negative control confirms the branch is load-bearing")


def test_fail_open_also_covers_unparseable_and_timeout():
    """Broaden test 4's coverage: unparseable output and a hard timeout must
    also degrade, not raise or block."""
    dispatch_consult = _load_module("dispatch_consult_t4b", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")

        garbage_claim_bin = _write_stub(tmp_path / "garbage-claim.py", "print('not json at all')\n")
        result = dispatch_consult.consult_before_dispatch(
            "SUBJ4B", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=garbage_claim_bin,
        )
        assert_true(result.ok and result.degraded and not result.blocked,
                    f"unparseable claim output must degrade, got {result.as_dict()}")

        slow_claim_bin = _write_stub(tmp_path / "slow-claim.py", "import time\ntime.sleep(5)\n")
        result2 = dispatch_consult.consult_before_dispatch(
            "SUBJ4C", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=slow_claim_bin,
            timeout=0.2,
        )
        assert_true(result2.ok and result2.degraded and not result2.blocked,
                    f"claim timeout must degrade, got {result2.as_dict()}")
        print("PASS  fail-open also covers unparseable output and subprocess timeout")


# ── test 5: context manager releases on normal exit AND on exception ────────

def test_context_manager_releases_on_normal_exit():
    dispatch_consult = _load_module("dispatch_consult_t5a", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "SUBJ5A", "owner": "local"}
        )

        with dispatch_consult.dispatch_consult(
            "SUBJ5A", "implementer", "local", None,
            role_route_bin=route_bin, slice_claim_bin=claim_bin,
        ) as result:
            assert_true(result.ok and not result.blocked, "setup: acquire must succeed for this test")

        calls = _read_calls(log)
        cmds = [c[0] for c in calls]
        assert_true(cmds == ["acquire", "release"], f"expected acquire then release on normal exit, got {cmds}")
        print("PASS  context manager releases on normal exit")


def test_context_manager_releases_on_exception():
    dispatch_consult = _load_module("dispatch_consult_t5b", LIB / "dispatch_consult.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "SUBJ5B", "owner": "local"}
        )

        raised = False
        try:
            with dispatch_consult.dispatch_consult(
                "SUBJ5B", "implementer", "local", None,
                role_route_bin=route_bin, slice_claim_bin=claim_bin,
            ) as result:
                assert_true(result.ok and not result.blocked, "setup: acquire must succeed for this test")
                raise RuntimeError("boom-inside-with-block")
        except RuntimeError as exc:
            raised = "boom-inside-with-block" in str(exc)

        assert_true(raised, "exception must propagate out of the context manager, not be swallowed")
        calls = _read_calls(log)
        cmds = [c[0] for c in calls]
        assert_true(cmds == ["acquire", "release"], f"expected acquire then release even on exception, got {cmds}")
        print("PASS  context manager releases on exception (and does not swallow it)")


# ── test 6: read-only dispatch.py subcommands never consult ─────────────────

def test_readonly_subcommands_never_reach_dispatch_task():
    """Static + behavioral: list/status/check/monitor/repair-status/repair-stale
    must never call dispatch_task() (the only place a consult could fire),
    proven by patching dispatch_task with a spy that raises if invoked, then
    actually running main() for each read-only subcommand against a real
    (empty) temp delegation dir.

    Resolution B (see module docstring): dispatch.py is pinned by the L2B
    frozen-source manifest and carries NO consult wiring at all — the seam
    lives in the delegate-to-local shim via this module's CLI instead. So the
    static half of this test asserts the ABSENCE of any consult reference in
    dispatch.py (proving the frozen file stayed frozen), not the presence of
    gating logic that used to live there under the old (reverted) approach.
    """
    dispatch_mod = _load_module("dispatch_for_readonly_consult_test", LIB / "dispatch.py")

    called = []

    def _spy(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("dispatch_task must not be called for a read-only subcommand")

    dispatch_mod.dispatch_task = _spy

    with tempfile.TemporaryDirectory() as tmp:
        delegation_dir = Path(tmp) / "delegation"
        delegation_dir.mkdir(parents=True)
        (delegation_dir / "registry.jsonl").write_text("", encoding="utf-8")

        subcommands = [
            ["list", "--delegation-dir", str(delegation_dir)],
            ["monitor", "--delegation-dir", str(delegation_dir)],
            ["status", "nonexistent-task", "--delegation-dir", str(delegation_dir)],
            ["check", "nonexistent-task", "--delegation-dir", str(delegation_dir)],
            ["repair-status", "nonexistent-task", "--delegation-dir", str(delegation_dir)],
            ["repair-stale", "--delegation-dir", str(delegation_dir)],
        ]

        old_argv = sys.argv
        try:
            for argv in subcommands:
                sys.argv = ["dispatch.py", *argv]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    dispatch_mod.main()
        finally:
            sys.argv = old_argv

    assert_true(len(called) == 0, f"dispatch_task was called for a read-only subcommand: {called}")

    # Frozen-file guarantee: dispatch.py must carry no reference to the
    # consult layer at all (not even a dormant import) — resolution B moved
    # the whole seam out to the shim so this file's sha256 stays pinned.
    src = (LIB / "dispatch.py").read_text(encoding="utf-8")
    assert_true("dispatch_consult" not in src,
                "dispatch.py must remain frozen: no dispatch_consult reference (resolution B moved "
                "the consult seam to the delegate-to-local shim, not dispatch.py)")
    print("PASS  read-only dispatch.py subcommands never reach dispatch_task; dispatch.py stays consult-free (frozen)")


# ── tests 7-10: resolution B CLI seam (subprocess, real argv/stdout/exit) ───

def _run_cli(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DISPATCH_CONSULT_PY), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def test_cli_consult_happy_path_json_and_exit_zero():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "CLI-SUBJ", "owner": "local"}
        )

        proc = _run_cli([
            "consult", "--subject", "CLI-SUBJ", "--role", "implementer", "--lane", "local",
            "--head", "deadbeef",
            "--role-route-bin", str(route_bin), "--slice-claim-bin", str(claim_bin),
        ])

        assert_true(proc.returncode == 0, f"happy-path consult must exit 0, got {proc.returncode} stderr={proc.stderr}")
        payload = json.loads(proc.stdout)
        assert_true(payload["ok"] is True and payload["blocked"] is False,
                    f"expected ok=True/blocked=False, got {payload}")
        assert_true(payload["claim_token"] == "CLI-SUBJ", f"expected claim_token=CLI-SUBJ, got {payload}")
        calls = _read_calls(log)
        assert_true(len(calls) == 1 and calls[0][0] == "acquire", f"expected exactly one acquire call, got {calls}")
        print("PASS  CLI consult happy path: JSON to stdout, exit 0")


def test_cli_consult_blocked_json_and_nonzero_exit():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        route_bin = _role_route_stub(tmp_path, chosen="local")
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path,
            acquire_response={
                "ok": False, "reason": "already-held", "slice_id": "CLI-SUBJ-BLK",
                "current_owner": "codex-other-session", "current_head": "cafebabe",
            },
        )

        proc = _run_cli([
            "consult", "--subject", "CLI-SUBJ-BLK", "--role", "implementer", "--lane", "local",
            "--role-route-bin", str(route_bin), "--slice-claim-bin", str(claim_bin),
        ])

        assert_true(proc.returncode != 0, f"blocked consult must exit non-zero, got {proc.returncode}")
        payload = json.loads(proc.stdout)
        assert_true(payload["blocked"] is True, f"expected blocked=True, got {payload}")
        assert_true(payload["current_owner"] == "codex-other-session",
                    f"expected current_owner surfaced, got {payload}")
        calls = _read_calls(log)
        assert_true(len(calls) == 1 and calls[0][0] == "acquire",
                    f"blocked path must not release someone else's claim, got {calls}")
        print("PASS  CLI consult blocked: blocked=true JSON, non-zero exit, no release")


def test_cli_release_prints_json_and_exits_zero():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        claim_bin, log = _slice_claim_stub_recording(
            tmp_path, acquire_response={"ok": True, "reason": "acquired", "slice_id": "CLI-REL", "owner": "local"}
        )

        proc = _run_cli([
            "release", "--subject", "CLI-REL", "--owner", "local",
            "--slice-claim-bin", str(claim_bin),
        ])

        assert_true(proc.returncode == 0, f"release must always exit 0, got {proc.returncode} stderr={proc.stderr}")
        payload = json.loads(proc.stdout)
        assert_true(payload["ok"] is True, f"expected release ok=True, got {payload}")
        calls = _read_calls(log)
        assert_true(len(calls) == 1 and calls[0][0] == "release", f"expected exactly one release call, got {calls}")
        print("PASS  CLI release: JSON to stdout, exit 0")


def test_cli_fail_open_on_broken_tools_exit_zero_degraded():
    """The CLI-level fail-open guarantee: pointing BOTH tool paths at
    nonexistent binaries must still print ok=True/degraded=True and exit 0 —
    the CLI subprocess itself must never be able to block a caller's
    dispatch, matching the library's own fail-open contract one layer up."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        missing_route = tmp_path / "does-not-exist-route.py"
        missing_claim = tmp_path / "does-not-exist-claim.py"

        proc = _run_cli([
            "consult", "--subject", "CLI-DEGRADED", "--role", "implementer", "--lane", "local",
            "--role-route-bin", str(missing_route), "--slice-claim-bin", str(missing_claim),
        ])

        assert_true(proc.returncode == 0, f"fail-open must exit 0, got {proc.returncode} stderr={proc.stderr}")
        payload = json.loads(proc.stdout)
        assert_true(payload["ok"] is True and payload["degraded"] is True and payload["blocked"] is False,
                    f"expected ok=True/degraded=True/blocked=False on missing tools, got {payload}")
        print("PASS  CLI fail-open: missing tool binaries -> ok=True/degraded=True, exit 0")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_happy_path_ok_and_token_set,
        test_substitution_surfaced_claim_stays_on_requested_lane,
        test_blocked_already_held_no_release_of_others_claim,
        test_fail_open_degrades_and_negative_control_proves_it_is_load_bearing,
        test_fail_open_also_covers_unparseable_and_timeout,
        test_context_manager_releases_on_normal_exit,
        test_context_manager_releases_on_exception,
        test_readonly_subcommands_never_reach_dispatch_task,
        test_cli_consult_happy_path_json_and_exit_zero,
        test_cli_consult_blocked_json_and_nonzero_exit,
        test_cli_release_prints_json_and_exits_zero,
        test_cli_fail_open_on_broken_tools_exit_zero_degraded,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
