#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C C3b R3 execution-cell-runner.

Exercises `ai-stack/switchboard/execution_cell_runner.py` +
`ai-stack/switchboard/execution_cell_validator.py` per
`.agents/plans/aqos-foundation-c/C3B-R3-DESIGN-AND-AUTHORIZATION.md` §9
(frozen by `C3B-R3-FREEZE-AND-ACTIVATION.md`, owner activation
`c4aaf0117ec84f8e`). Fully offline/hermetic: builds a THROWAWAY git repo +
bare mirror under a temp dir, a test-only Ed25519 keypair (via
`execution_grant`'s test-only `sign()`), a real UDS in a temp runtime dir,
and (where the host provides one) a real delegated cgroup v2 subtree. No
network, no dependence on the live repo, no switchboard, no systemd.

Covers (design §9):
  1. valid grant + single-file-write -> GREEN; the write lands ONLY in the
     cell (the throwaway source repo is untouched); the out-of-cell
     validator confirms exactly the declared path changed.
  2. valid grant + read-validate -> GREEN (second command-vocabulary kind).
  3. --unshare-net blocks egress (direct confinement-mechanism probe, since
     R1 categorically forbids any grant from requesting a "network" effect
     at all -- there is no grant-level path to even attempt this).
  4. a syntactically-clean-but-symlink-escaping write target -> refused at
     R2 cell-create (TOCTOU-safe rebase), never a cell, never GREEN.
  5. a `..`-traversal path in the grant's own effect scope -> refused at R1
     grant verification, before any cell.
  6. bwrap unavailable (bogus BWRAP_PATH) -> confinement-unavailable DENY,
     proven never to have reached cell-create -- NEVER an unsandboxed run.
  7. epoch bump mid-run -> the tracked process tree is killed via the real
     cgroup + no GREEN (direct `_supervise()` unit test: deterministic,
     not a wall-clock race).
  8. the final epoch fence flips a would-be GREEN to RED when the epoch
     moves between command completion and publication (deterministic via
     a call-counting epoch source, not a wall-clock race).
  9. a kill that cannot PROVE removal within its budget -> Quarantined
     (direct `terminate_cgroup_tree()` unit test with a zero proof budget).
  10. non-client SO_PEERCRED peer -> dropped (real UDS, real kernel
      credential check); a same-uid peer -> accepted.
  11. a replayed grant_id -> denied.
  12. FLAG OFF -> the runner refuses to construct any cell.

Genuinely systemd-only surfaces (real socket activation, `Delegate=`-granted
cgroup control under the actual systemd unit) are marked R6-canary-deferred
below and SKIPPED with an explicit note -- never faked.

Run directly: `python3 scripts/testing/test-execution-cell-runner.py`
Exits 0 iff every non-skipped test passes; prints "N/N passed" plus any
R6-canary-deferred skip count.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
for _p in (_LIB_DIR, _SWITCHBOARD_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_grant as eg  # noqa: E402
import execution_cell_clone as ecc  # noqa: E402
import execution_cell_runner as runner  # noqa: E402
import execution_cell_validator as validator  # noqa: E402

# --------------------------------------------------------------------------
# Test harness (no external deps — matches test-execution-cell-clone.py)
# --------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []
_SKIPPED: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def skip(name: str, note: str) -> None:
    _SKIPPED.append((name, note))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    for name, note in _SKIPPED:
        print(f"[SKIP-R6-CANARY-DEFERRED] {name} — {note}")

    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed"
          f" ({len(_SKIPPED)} R6-canary-deferred skip(s))")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


# --------------------------------------------------------------------------
# Fixture helpers — throwaway git repo + bare mirror, all under one temp dir
# --------------------------------------------------------------------------

_TEMP_ROOTS: list[str] = []


def _mkdtemp(prefix: str) -> str:
    d = tempfile.mkdtemp(prefix=f"c3b-r3-{prefix}-")
    _TEMP_ROOTS.append(d)
    return d


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd, check=False, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "R3 Test", "GIT_AUTHOR_EMAIL": "r3-test@example.invalid",
             "GIT_COMMITTER_NAME": "R3 Test", "GIT_COMMITTER_EMAIL": "r3-test@example.invalid"},
    )


def _build_source_repo(with_escape_symlink: bool = False) -> tuple[str, str]:
    """`with_escape_symlink=True` bakes in a symlink escaping the repo
    entirely (`allowed_dir/escape_link` -> `/etc/passwd`) for the dedicated
    escape test ONLY — R2's `check_clone_isolation` scans the WHOLE cloned
    tree for ANY outward-pointing symlink (not just grant-declared paths),
    so every other test must build a clean repo or every cell-create would
    fail closed on this same tripwire."""
    src = _mkdtemp("source")
    assert _run_git(["init", "-q", "-b", "main"], src).returncode == 0
    os.makedirs(os.path.join(src, "allowed_dir"), exist_ok=True)
    Path(src, "allowed_dir", "writable.txt").write_text("initial content\n", encoding="utf-8")
    Path(src, "allowed_dir", "inner.txt").write_text("read-validate me\n", encoding="utf-8")
    if with_escape_symlink:
        os.symlink("/etc/passwd", os.path.join(src, "allowed_dir", "escape_link"))
    assert _run_git(["add", "-A"], src).returncode == 0
    commit = _run_git(["commit", "-q", "-m", "initial"], src)
    assert commit.returncode == 0, commit.stderr
    rev = _run_git(["rev-parse", "HEAD"], src)
    assert rev.returncode == 0, rev.stderr
    return src, rev.stdout.strip()


def _build_bare_mirror(source_repo: str) -> str:
    mirror = os.path.join(_mkdtemp("mirror-parent"), "mirror.git")
    result = subprocess.run(["git", "clone", "-q", "--mirror", source_repo, mirror],
                             check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return mirror


def _detect_delegated_cgroup_parent() -> "str | None":
    """Best-effort discovery of a REAL, writable, delegated cgroup v2
    subtree this test process can create/remove child cgroups under (e.g.
    the systemd user session's own delegated slice). Returns None if the
    host offers nothing usable — callers must SKIP (not fabricate) any
    assertion that genuinely requires kernel-verified process-tree removal
    proof."""
    uid = os.getuid()
    candidates = [
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/background.slice",
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/app.slice",
        f"/sys/fs/cgroup/aq-r3-test.slice",
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        probe = os.path.join(base, f"aq-r3-probe-{os.getpid()}")
        try:
            os.mkdir(probe)
            os.rmdir(probe)
            return base
        except OSError:
            continue
    return None


_CGROUP_PARENT = _detect_delegated_cgroup_parent()
_BWRAP_PATH = shutil.which("bwrap")
# The inner program executed INSIDE the bwrap sandbox must resolve under one
# of the sandbox's own bound paths (--ro-bind /nix/store /nix/store); a
# ~/.nix-profile symlink path (outside /nix/store, under /home which is
# never bound) would fail with execvp ENOENT inside the sandbox even though
# it works fine unsandboxed. realpath() follows the profile symlink to the
# real /nix/store derivation output.
_PYTHON_BIN = os.path.realpath(sys.executable)


# --------------------------------------------------------------------------
# Grant fixture builder — a fresh signed grant per scenario.
# --------------------------------------------------------------------------


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_signed_grant(
    private_key,
    *,
    base_revision: str,
    trusted_repo_id: str,
    effect_set: list,
    logical_paths: list,
    revocation_epoch: int = 0,
    timeout_s: int = 10,
    expires_in_minutes: int = 10,
) -> dict:
    now = datetime.now(timezone.utc)
    grant = {
        "grant_schema_version": 1,
        "grant_id": uuid.uuid4().hex + uuid.uuid4().hex,
        "lease_id": "lease-" + uuid.uuid4().hex,
        "task_id": "task-" + uuid.uuid4().hex,
        "request_id": "req-" + uuid.uuid4().hex,
        "issued_at": _rfc3339(now - timedelta(seconds=1)),
        "expires_at": _rfc3339(now + timedelta(minutes=expires_in_minutes)),
        "revocation_epoch": revocation_epoch,
        "base_revision": base_revision,
        "effect_set": effect_set,
        "exec_class": "sandbox-required",
        "trusted_repo_id": trusted_repo_id,
        "logical_paths": logical_paths,
        "resource_limits": {"timeout_s": timeout_s, "max_output_bytes": 65536, "cell_class": "small"},
    }
    return eg.sign(grant, private_key)


def _base_config(mirror: str, trusted_repo_id: str, public_key_bytes: bytes, **overrides) -> "runner.RunnerConfig":
    cell_state_root = _mkdtemp("cell-state")
    defaults = dict(
        socket_path=os.path.join(_mkdtemp("sock-dir"), "control.sock"),
        client_uid=os.getuid(),
        client_gid=None,
        public_key_bytes=public_key_bytes,
        trusted_repo_mirrors={trusted_repo_id: mirror},
        cell_state_root=cell_state_root,
        cgroup_parent=_CGROUP_PARENT or _mkdtemp("fake-cgroup-parent"),
        python_bin=_PYTHON_BIN,
        bwrap_path=_BWRAP_PATH,
        reservation_set=eg.ReplayReservationSet(),
        cell_reservation_set=eg.ReplayReservationSet(),
        epoch_source=0,
        env={"CAPABILITY_EXECUTION_CELLS": "1"},
    )
    defaults.update(overrides)
    return runner.RunnerConfig(**defaults)


# --------------------------------------------------------------------------
# 1. Valid single-file-write grant -> GREEN; write only in the cell;
#    validator confirms exactly the declared path.
# --------------------------------------------------------------------------


def test_valid_write_grant_green():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes)

    grant = _make_signed_grant(
        private_key,
        base_revision=head_oid,
        trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/writable.txt"], "mode": "write",
                      "content": "NEW CONTENT FROM CELL\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"],
    )

    decision = runner.process_grant(grant, config)
    check("write_grant_green", decision.decision == runner.DECISION_GREEN,
          f"expected green, got {decision.decision}/{decision.reason} (stage={decision.stage})")
    check("write_grant_command_kind", decision.command_kind == runner.COMMAND_SINGLE_FILE_WRITE)
    check("write_grant_tree_proven_absent", decision.tree_proven_absent is True)
    check("write_grant_diff_is_exactly_declared_path", tuple(decision.diff) == ("allowed_dir/writable.txt",),
          f"diff={decision.diff!r}")

    # The write must have landed ONLY in the (now-torn-down) cell — the
    # original throwaway source repo is untouched.
    source_content = Path(source_repo, "allowed_dir", "writable.txt").read_text(encoding="utf-8")
    check("write_grant_source_repo_untouched", source_content == "initial content\n", repr(source_content))


# --------------------------------------------------------------------------
# 2. Valid read-validate grant -> GREEN (second command-vocabulary kind).
# --------------------------------------------------------------------------


def test_valid_read_validate_grant_green():
    import hashlib

    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes)

    expected_sha = hashlib.sha256(b"read-validate me\n").hexdigest()
    grant = _make_signed_grant(
        private_key,
        base_revision=head_oid,
        trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "deterministic-validate",
            "scope": {"paths": ["allowed_dir/inner.txt"], "expected_sha256": expected_sha},
        }],
        logical_paths=["allowed_dir"],
    )

    decision = runner.process_grant(grant, config)
    check("read_validate_grant_green", decision.decision == runner.DECISION_GREEN,
          f"got {decision.decision}/{decision.reason} (stage={decision.stage})")
    check("read_validate_grant_no_diff", decision.diff == (), f"diff={decision.diff!r}")


# --------------------------------------------------------------------------
# 3. --unshare-net blocks egress (direct confinement-mechanism probe — R1
#    categorically forbids a "network" effect at the grant layer itself,
#    so there is no grant-level path that could even attempt this).
# --------------------------------------------------------------------------

_EGRESS_PROBE_SRC = (
    "import socket, sys\n"
    "try:\n"
    "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
    "    s.settimeout(2)\n"
    "    s.connect(('1.1.1.1', 80))\n"
    "    print('CONNECTED')\n"
    "except Exception as exc:\n"
    "    print('BLOCKED:' + type(exc).__name__)\n"
)


def test_unshare_net_blocks_egress():
    check("build_bwrap_argv_includes_unshare_net",
          "--unshare-net" in runner.build_bwrap_argv(_BWRAP_PATH or "/bin/true", _PYTHON_BIN, "/tmp", "/dev/null"))

    if not _BWRAP_PATH:
        skip("unshare_net_live_probe", "no bwrap binary found on this host")
        return

    argv = [
        _BWRAP_PATH, "--unshare-all", "--unshare-net", "--die-with-parent", "--new-session", "--clearenv",
        "--ro-bind", "/nix/store", "/nix/store", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--", _PYTHON_BIN, "-c", _EGRESS_PROBE_SRC,
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=10, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        check("unshare_net_live_probe_ran", False, f"probe subprocess failed to run: {exc}")
        return
    check("unshare_net_blocked_egress", "BLOCKED:" in proc.stdout, f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    check("unshare_net_never_connected", "CONNECTED" not in proc.stdout)


# --------------------------------------------------------------------------
# 4. Symlink escape target -> refused at R2 cell-create, never a cell.
# --------------------------------------------------------------------------


def test_symlink_escape_refused_at_cell_create():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo(with_escape_symlink=True)
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes)

    grant = _make_signed_grant(
        private_key,
        base_revision=head_oid,
        trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/escape_link"], "mode": "write",
                      "content": "pwned\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"],
    )

    decision = runner.process_grant(grant, config)
    check("symlink_escape_denied", decision.decision == runner.DECISION_DENIED,
          f"got {decision.decision}/{decision.reason}")
    check("symlink_escape_stage_is_cell_create", decision.stage == runner.STAGE_CELL_CREATE, decision.stage)
    # R2's `check_clone_isolation` scans the WHOLE cloned tree for ANY
    # outward-pointing symlink and runs BEFORE the per-path rebase check —
    # it catches this escape as `isolation-violation`, earlier and more
    # broadly than a declared-path-specific `path-escape` would.
    check("symlink_escape_reason", decision.reason == ecc.FAILURE_ISOLATION_VIOLATION, decision.reason)

    # /etc/passwd itself must be untouched.
    check("symlink_escape_did_not_write_host_file",
          "pwned" not in Path("/etc/passwd").read_text(encoding="utf-8", errors="replace"))


# --------------------------------------------------------------------------
# 5. `..`-traversal in the grant's own scope -> refused at R1 grant verify,
#    before any cell is ever created.
# --------------------------------------------------------------------------


def test_traversal_path_refused_at_grant_verify():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes)

    grant = _make_signed_grant(
        private_key,
        base_revision=head_oid,
        trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/../../etc/evil.txt"], "mode": "write",
                      "content": "pwned\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"],
    )

    cells_dir = os.path.join(config.cell_state_root, "cells")
    decision = runner.process_grant(grant, config)
    check("traversal_denied", decision.decision == runner.DECISION_DENIED,
          f"got {decision.decision}/{decision.reason}")
    check("traversal_stage_is_grant_verify", decision.stage == runner.STAGE_GRANT_VERIFY, decision.stage)
    check("traversal_reason_is_path_invalid", decision.reason == eg.DENY_PATH_INVALID, decision.reason)
    check("traversal_never_created_a_cell", not os.path.isdir(cells_dir) or not os.listdir(cells_dir))


# --------------------------------------------------------------------------
# 6. bwrap unavailable -> confinement-unavailable DENY; NEVER unsandboxed.
# --------------------------------------------------------------------------


def test_bwrap_unavailable_never_unsandboxed():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes, bwrap_path="/nonexistent/bwrap-binary-xyz")

    grant = _make_signed_grant(
        private_key,
        base_revision=head_oid,
        trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/writable.txt"], "mode": "write",
                      "content": "should-never-land\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"],
    )

    cells_dir = os.path.join(config.cell_state_root, "cells")
    decision = runner.process_grant(grant, config)
    check("bwrap_missing_denied", decision.decision == runner.DECISION_DENIED,
          f"got {decision.decision}/{decision.reason}")
    check("bwrap_missing_reason", decision.reason == runner.REASON_CONFINEMENT_UNAVAILABLE, decision.reason)
    check("bwrap_missing_stage_is_preflight", decision.stage == runner.STAGE_CONFINE_PREFLIGHT, decision.stage)
    # Proof of "never unsandboxed": no cell was ever constructed (preflight
    # runs BEFORE ecc.create_cell in the pipeline), and the source content
    # is untouched.
    check("bwrap_missing_never_created_a_cell", not os.path.isdir(cells_dir) or not os.listdir(cells_dir))
    content = Path(source_repo, "allowed_dir", "writable.txt").read_text(encoding="utf-8")
    check("bwrap_missing_source_untouched", content == "initial content\n", repr(content))


# --------------------------------------------------------------------------
# 7. Epoch bump mid-run -> tree killed via real cgroup, no GREEN.
#    Direct `_supervise()` unit test — deterministic (epoch flipped by a
#    background thread partway through a real, longer-running child), not
#    a fragile end-to-end wall-clock race against a near-instant command.
# --------------------------------------------------------------------------


def test_epoch_bump_mid_run_kills_tree():
    if _CGROUP_PARENT is None:
        skip("epoch_bump_mid_run_kills_tree", "no delegated cgroup v2 subtree available on this host")
        return

    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(
        mirror, "test-repo", public_key_bytes,
        poll_interval_s=0.1, heartbeat_deadline_s=1.0,
    )

    grant = _make_signed_grant(
        private_key, base_revision=head_oid, trusted_repo_id="test-repo",
        effect_set=[{"effect": "read", "scope": {"paths": ["allowed_dir/inner.txt"], "mode": "read"}}],
        logical_paths=["allowed_dir"], revocation_epoch=100, timeout_s=30,
    )
    now = datetime.now(timezone.utc)
    verified = eg.verify_grant(grant, public_key_bytes, now, 0, eg.ReplayReservationSet())
    check("epoch_bump_fixture_grant_verifies", isinstance(verified, eg.VerifiedGrant),
          f"got {verified!r}")
    if not isinstance(verified, eg.VerifiedGrant):
        return

    cgroup_path = runner.create_cgroup(_CGROUP_PARENT, f"epoch-bump-{uuid.uuid4().hex[:12]}")
    check("epoch_bump_cgroup_created", cgroup_path is not None)
    if cgroup_path is None:
        return

    proc = subprocess.Popen(["sleep", "5"], start_new_session=True)
    runner.add_pid_to_cgroup(cgroup_path, proc.pid)

    class _EpochHolder:
        def __init__(self):
            self.value = 0

        def __call__(self):
            return self.value

    holder = _EpochHolder()
    supervise_config = runner.RunnerConfig(
        socket_path="", client_uid=None, client_gid=None, public_key_bytes=public_key_bytes,
        trusted_repo_mirrors={}, cell_state_root=config.cell_state_root, cgroup_parent=_CGROUP_PARENT,
        python_bin=_PYTHON_BIN, bwrap_path=_BWRAP_PATH, poll_interval_s=0.1, heartbeat_deadline_s=1.0,
        sigterm_grace_s=0.5, kill_proof_budget_s=4.5, epoch_source=holder,
    )

    import threading
    result_box = {}

    def _run_supervise():
        result_box["result"] = runner._supervise(proc, cgroup_path, verified, supervise_config)

    thread = threading.Thread(target=_run_supervise)
    thread.start()
    time.sleep(0.4)  # let a couple of 0.1s ticks pass at the *valid* epoch
    holder.value = 101  # bump past revocation_epoch=100 -> next tick denies
    thread.join(timeout=15)

    check("epoch_bump_supervise_returned", "result" in result_box, "supervise() did not return within timeout")
    if "result" not in result_box:
        try:
            proc.kill()
        except OSError:
            pass
        return

    outcome, trigger, cgroup_kill_used, proven = result_box["result"]
    check("epoch_bump_outcome_terminated", outcome == "terminated", outcome)
    check("epoch_bump_trigger_is_epoch_bump", trigger == "epoch-bump", trigger)
    check("epoch_bump_tree_proven_absent", proven is True, f"proven={proven}")

    # Reap before asserting death: `cgroup.procs` reporting empty (what
    # `proven` certifies) and the parent's own zombie-reap via waitpid can
    # be a beat apart under load — `.wait()` blocks until the exit status is
    # actually collected, which is the honest way to assert "actually dead"
    # from THIS process's point of view (poll() alone right after join()
    # could still race a not-yet-delivered SIGCHLD).
    try:
        proc.wait(timeout=2)
    except Exception:
        pass
    check("epoch_bump_process_actually_dead", proc.poll() is not None)


# --------------------------------------------------------------------------
# 8. Final epoch fence flips a would-be GREEN to RED. Deterministic via a
#    call-counting epoch source (not a wall-clock race against a
#    near-instant single-file-write command).
# --------------------------------------------------------------------------


class _CountingEpoch:
    """Returns `before` for the first `flip_after` calls, then `after`."""

    def __init__(self, flip_after: int, before: int, after: int):
        self.calls = 0
        self.flip_after = flip_after
        self.before = before
        self.after = after

    def __call__(self):
        self.calls += 1
        return self.before if self.calls <= self.flip_after else self.after


def test_final_epoch_fence_flips_green_to_red():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)

    grant = _make_signed_grant(
        private_key, base_revision=head_oid, trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/writable.txt"], "mode": "write",
                      "content": "fence test\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"], revocation_epoch=100,
    )

    # First, learn the exact call count for a run where the epoch never
    # moves (deterministic baseline — avoids guessing the pipeline's
    # internal resolve_current_epoch call count).
    counter_probe = _CountingEpoch(flip_after=10_000, before=0, after=0)
    config_probe = _base_config(mirror, "test-repo", public_key_bytes, epoch_source=counter_probe)
    baseline = runner.process_grant(grant, config_probe)
    check("fence_baseline_green", baseline.decision == runner.DECISION_GREEN,
          f"got {baseline.decision}/{baseline.reason} (stage={baseline.stage}) — cannot proceed to fence-flip test")
    if baseline.decision != runner.DECISION_GREEN:
        return
    total_calls = counter_probe.calls
    check("fence_baseline_calls_at_least_one", total_calls >= 1, total_calls)

    # Second run: flip epoch to STALE exactly on the LAST resolve call
    # (design: the final fence re-reads the epoch immediately before
    # publishing GREEN — that is always the last call in the pipeline).
    grant2 = _make_signed_grant(
        private_key, base_revision=head_oid, trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/writable.txt"], "mode": "write",
                      "content": "fence test 2\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"], revocation_epoch=100,
    )
    counter = _CountingEpoch(flip_after=total_calls - 1, before=0, after=101)
    config2 = _base_config(mirror, "test-repo", public_key_bytes, epoch_source=counter)
    decision = runner.process_grant(grant2, config2)

    check("fence_flip_not_green", decision.decision != runner.DECISION_GREEN,
          f"expected fence to flip GREEN->RED, got {decision.decision}/{decision.reason}")
    check("fence_flip_reason", decision.reason == runner.REASON_FINAL_FENCE_FAILED, decision.reason)
    check("fence_flip_stage", decision.stage == runner.STAGE_FINAL_FENCE, decision.stage)


# --------------------------------------------------------------------------
# 9. Kill that cannot prove removal within budget -> Quarantined. Direct
#    `terminate_cgroup_tree()` unit test with a zero proof budget — a real
#    process, real cgroup, real SIGTERM/SIGKILL, but no time at all to
#    observe the (genuinely imminent) removal.
# --------------------------------------------------------------------------


def test_kill_cannot_prove_removal_quarantines():
    if _CGROUP_PARENT is None:
        skip("kill_cannot_prove_removal_quarantines", "no delegated cgroup v2 subtree available on this host")
        return

    cgroup_path = runner.create_cgroup(_CGROUP_PARENT, f"proof-budget-{uuid.uuid4().hex[:12]}")
    check("proof_budget_cgroup_created", cgroup_path is not None)
    if cgroup_path is None:
        return

    proc = subprocess.Popen(["sleep", "5"], start_new_session=True)
    runner.add_pid_to_cgroup(cgroup_path, proc.pid)

    proven, _kill_used = runner.terminate_cgroup_tree(cgroup_path, sigterm_grace_s=0.05, kill_proof_budget_s=0.0)
    check("proof_budget_exhausted_not_proven", proven is False, f"proven={proven}")

    # Hygiene + honesty check: with a REAL budget afterward, the (already
    # signalled) tree IS actually reclaimable — this is a tight-budget
    # limitation being tested, not a real kill failure.
    proven_retry, _ = runner.terminate_cgroup_tree(cgroup_path, sigterm_grace_s=0.2, kill_proof_budget_s=4.5)
    check("proof_budget_retry_with_real_budget_proves_absent", proven_retry is True, f"proven_retry={proven_retry}")
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 10. Non-client SO_PEERCRED peer -> dropped; same-uid peer -> accepted.
#     Real UDS, real kernel credential check.
# --------------------------------------------------------------------------


def test_peer_authentication_real_uds():
    import threading

    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)

    # -- non-client peer: client_uid/gid deliberately do not match us --
    config_rejecting = _base_config(
        mirror, "test-repo", public_key_bytes,
        client_uid=999999, client_gid=999999,
        env={"CAPABILITY_EXECUTION_CELLS": "0"},
    )
    stop_event = threading.Event()
    server_thread = threading.Thread(target=runner.serve_forever, args=(config_rejecting, stop_event), daemon=True)
    server_thread.start()
    time.sleep(0.3)
    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(3)
        conn.connect(config_rejecting.socket_path)
        conn.sendall(b'{"probe": true}')
        # The server closes the connection WITHOUT ever reading (peer
        # rejected before any recv) — with unread data still in the
        # kernel's receive buffer, closing the socket is free to surface as
        # either a clean EOF (b"") or ECONNRESET on our next read. Both are
        # honest manifestations of "dropped, no response" — never an
        # error-oracle response with content.
        try:
            data = conn.recv(4096)
        except (ConnectionResetError, BrokenPipeError):
            data = b""
        check("non_client_peer_dropped_no_response", data == b"", f"got unexpected response: {data!r}")
        conn.close()
    finally:
        stop_event.set()
        server_thread.join(timeout=3)

    # -- authorized (same-uid) peer: gets a real typed response --
    config_accepting = _base_config(
        mirror, "test-repo", public_key_bytes,
        client_uid=os.getuid(), client_gid=None,
        env={"CAPABILITY_EXECUTION_CELLS": "0"},
    )
    stop_event2 = threading.Event()
    server_thread2 = threading.Thread(target=runner.serve_forever, args=(config_accepting, stop_event2), daemon=True)
    server_thread2.start()
    time.sleep(0.3)
    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(3)
        conn.connect(config_accepting.socket_path)
        conn.sendall(json.dumps({"probe": True}).encode("utf-8"))
        conn.shutdown(socket.SHUT_WR)
        data = conn.recv(4096)
        check("client_peer_gets_response", len(data) > 0, "expected a typed JSON response, got nothing")
        if data:
            payload = json.loads(data.decode("utf-8"))
            check("client_peer_response_is_flag_off_denial",
                  payload.get("decision") == runner.DECISION_DENIED and payload.get("reason") == runner.REASON_FLAG_OFF,
                  f"payload={payload!r}")
        conn.close()
    finally:
        stop_event2.set()
        server_thread2.join(timeout=3)


# --------------------------------------------------------------------------
# 11. Replayed grant_id -> denied.
# --------------------------------------------------------------------------


def test_replayed_grant_denied():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes)

    grant = _make_signed_grant(
        private_key, base_revision=head_oid, trusted_repo_id="test-repo",
        effect_set=[{"effect": "read", "scope": {"paths": ["allowed_dir/inner.txt"], "mode": "read"}}],
        logical_paths=["allowed_dir"],
    )

    first = runner.process_grant(grant, config)
    check("replay_first_call_not_replay_denied", first.reason != eg.DENY_REPLAYED,
          f"first call already denied as replay: {first.reason}")

    second = runner.process_grant(grant, config)
    check("replay_second_call_denied", second.decision == runner.DECISION_DENIED, second.decision)
    check("replay_second_call_reason", second.reason == eg.DENY_REPLAYED, second.reason)
    check("replay_second_call_stage", second.stage == runner.STAGE_GRANT_VERIFY, second.stage)


# --------------------------------------------------------------------------
# 12. FLAG OFF -> the runner refuses to construct any cell.
# --------------------------------------------------------------------------


def test_flag_off_refuses_cell():
    private_key, public_key_bytes = eg.generate_keypair()
    source_repo, head_oid = _build_source_repo()
    mirror = _build_bare_mirror(source_repo)
    config = _base_config(mirror, "test-repo", public_key_bytes, env={"CAPABILITY_EXECUTION_CELLS": "0"})

    grant = _make_signed_grant(
        private_key, base_revision=head_oid, trusted_repo_id="test-repo",
        effect_set=[{
            "effect": "write",
            "scope": {"paths": ["allowed_dir/writable.txt"], "mode": "write",
                      "content": "should never run\n", "encoding": "utf-8"},
        }],
        logical_paths=["allowed_dir"],
    )

    cells_dir = os.path.join(config.cell_state_root, "cells")
    decision = runner.process_grant(grant, config)
    check("flag_off_denied", decision.decision == runner.DECISION_DENIED, decision.decision)
    check("flag_off_reason", decision.reason == runner.REASON_FLAG_OFF, decision.reason)
    check("flag_off_stage_is_flag", decision.stage == runner.STAGE_FLAG, decision.stage)
    check("flag_off_grant_never_verified", decision.grant_digest is None, decision.grant_digest)
    check("flag_off_never_created_a_cell", not os.path.isdir(cells_dir) or not os.listdir(cells_dir))
    content = Path(source_repo, "allowed_dir", "writable.txt").read_text(encoding="utf-8")
    check("flag_off_source_untouched", content == "initial content\n", repr(content))

    # Also default (no env override at all): default OFF.
    check("flag_default_is_off", runner.execution_cells_enabled({}) is False)


# --------------------------------------------------------------------------
# R6-canary-deferred: genuinely systemd-only surfaces this offline harness
# cannot exercise (real socket activation, `Delegate=`-granted cgroup
# control under the actual deployed unit). Recorded as explicit skips —
# never faked.
# --------------------------------------------------------------------------


def note_r6_canary_deferred_surfaces():
    skip("systemd_socket_activation", "requires the deployed aq-execution-cell-runner.socket unit under systemd — R6 canary")
    skip("systemd_cgroup_delegate_true", "requires Delegate=true under the real systemd service manager, not a user-session cgroup — R6 canary")


def main() -> None:
    tests = [
        test_valid_write_grant_green,
        test_valid_read_validate_grant_green,
        test_unshare_net_blocks_egress,
        test_symlink_escape_refused_at_cell_create,
        test_traversal_path_refused_at_grant_verify,
        test_bwrap_unavailable_never_unsandboxed,
        test_epoch_bump_mid_run_kills_tree,
        test_final_epoch_fence_flips_green_to_red,
        test_kill_cannot_prove_removal_quarantines,
        test_peer_authentication_real_uds,
        test_replayed_grant_denied,
        test_flag_off_refuses_cell,
    ]
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 — a test crashing is itself a FAIL, not a harness crash
            check(test.__name__, False, f"test raised {type(exc).__name__}: {exc}")

    note_r6_canary_deferred_surfaces()

    for d in _TEMP_ROOTS:
        shutil.rmtree(d, ignore_errors=True)

    _report_and_exit()


if __name__ == "__main__":
    main()
