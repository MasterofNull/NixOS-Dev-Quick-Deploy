"""Execution Cell Runner — Foundation C, C3b R3 (default-OFF, enforcement-tier).

Implements ONLY the runner authorized by
`.agents/plans/aqos-foundation-c/C3B-R3-DESIGN-AND-AUTHORIZATION.md` §3-§9,
frozen by `C3B-R3-FREEZE-AND-ACTIVATION.md` and released for build by owner
activation event `c4aaf0117ec84f8e` (`activation.grant`). That activation
authorizes ONLY this ceiling, flag DEFAULT-OFF:

  - a socket-activated UDS server, `SO_PEERCRED`-gated, transport-only;
  - the request protocol: verify a signed grant (R1, PUBLIC key only) ->
    create a self-contained cell (R2) -> bwrap-confine the grant's derived
    command inside it -> cgroup-tracked supervise + kill + final epoch
    fence -> out-of-cell validate (`execution_cell_validator.py`) -> typed
    GREEN/RED/QUARANTINED/DENIED result;
  - NO switchboard adoption (R5), NO network profile (C4), NO live traffic,
    NO auto-merge, and — explicitly — NO unsandboxed / in-process /
    direct-exec fallback of any kind (the aider
    `AI_AIDER_SANDBOX_FALLBACK_UNSAFE` pattern is deliberately absent: if
    bwrap is missing, userns is unavailable, or cell construction fails,
    the ONLY outcome is a typed `confinement-unavailable` denial).

This module consumes, and NEVER reimplements or modifies:
  - `scripts/ai/lib/execution_grant.py` (R1) — `verify_grant`, the Ed25519
    PUBLIC-key-only verifier. The runner never holds a private key; a
    compromised runner cannot forge a grant (R1 SF-1).
  - `scripts/ai/lib/execution_cell_clone.py` (R2) — `create_cell`,
    `teardown_cell`, `reconcile`, `rebase_logical_path`.
  - `ai-stack/switchboard/capability_lease_gate.py` — `resolve_current_epoch`,
    the ONE authoritative epoch source (design §6). `current_epoch is None`
    always denies (never a skipped staleness check).

The FLAG is `CAPABILITY_EXECUTION_CELLS`, default OFF ("0"). While OFF, the
runner NEVER constructs a cell — every request is denied at the very first
step of `process_grant`, before grant verification, before touching R1/R2,
before any disk I/O — "nothing runs" (design §8, `env-contract.yaml`).

The runner NEVER raises to its socket caller: every code path in the
request-handling chain is wrapped and converted to a typed denial (design
§3/§4: "fail-closed"). Every emitted decision/receipt record is typed and
low-cardinality (no grants, no paths, no prompts, no high-cardinality IDs
beyond the two correlation identifiers `receipt_id`/`grant_digest`, matching
the precedent set by `capability-lease-gate-decision.schema.json`'s
`lease_id` field) — see
`config/schemas/execution-cell-runner-decision.schema.json`.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[1]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import execution_grant as eg  # noqa: E402
import execution_cell_clone as ecc  # noqa: E402
import execution_cell_validator as validator  # noqa: E402
import capability_lease_gate as clg  # noqa: E402

# ---------------------------------------------------------------------------
# The default-OFF flag (design §8; `config/env-contract.yaml`).
# ---------------------------------------------------------------------------

FLAG_ENV = "CAPABILITY_EXECUTION_CELLS"


def execution_cells_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """True iff the runner is authorized to construct a cell at all. Default
    OFF: an absent/unrecognized value is treated as OFF, never as ON
    (deny-closed on the flag itself, matching every other check in this
    module)."""
    source = env if env is not None else os.environ
    return source.get(FLAG_ENV, "0") == "1"


# ---------------------------------------------------------------------------
# Typed decision vocabulary (design §4/§9/§10 — GREEN / RED / QUARANTINED /
# DENIED). DENIED covers every pre-cell-execution stop (flag off, peer
# rejected, grant denied, command-descriptor unsupported, cell-create
# failed, confinement unavailable). RED covers a cell that ran but whose
# result is not trustworthy (supervision trigger, validator RED, final-fence
# failure, malformed self-report). QUARANTINED is reserved for the one case
# §6 names explicitly: the runner cannot PROVE the tracked process tree is
# gone — never GREEN, never a false finite-redelivery claim.
# ---------------------------------------------------------------------------

DECISION_GREEN = "green"
DECISION_RED = "red"
DECISION_QUARANTINED = "quarantined"
DECISION_DENIED = "denied"

REASON_FLAG_OFF = "flag-off"
REASON_PEER_REJECTED = "peer-rejected"
REASON_REQUEST_MALFORMED = "request-malformed"
REASON_CONFINEMENT_UNAVAILABLE = "confinement-unavailable"
REASON_COMMAND_UNSUPPORTED = "command-descriptor-unsupported"
REASON_UNKNOWN_TRUSTED_REPO = "unknown-trusted-repo"
REASON_TREE_NOT_PROVEN_ABSENT = "tree-not-proven-absent"
REASON_MALFORMED_RESULT = "malformed-cell-result"
REASON_COMMAND_FAILED = "command-failed"
REASON_FINAL_FENCE_FAILED = "final-epoch-fence-failed"
REASON_RUNNER_INTERNAL_ERROR = "runner-internal-error"
REASON_RUNNER_BUSY = "runner-busy"
REASON_OK = "ok"

STAGE_FLAG = "flag"
STAGE_PEER = "peer"
STAGE_REQUEST = "request"
STAGE_GRANT_VERIFY = "grant-verify"
STAGE_COMMAND_DERIVE = "command-derive"
STAGE_CONFINE_PREFLIGHT = "confine-preflight"
STAGE_CELL_CREATE = "cell-create"
STAGE_CONFINE_RUN = "confine-run"
STAGE_SUPERVISE = "supervise"
STAGE_VALIDATE = "validate"
STAGE_FINAL_FENCE = "final-fence"


@dataclass(frozen=True)
class Decision:
    """A terminal, typed outcome. `diff` is populated ONLY on GREEN — the
    retained changed-path list for a LATER, separate orchestrator review
    (design §4.5/§10-7: no auto-merge, ever). It is deliberately excluded
    from the low-cardinality receipt schema (paths are high-cardinality);
    it exists only on the in-process return value for a caller in this same
    process (R3 has no live wiring — R5)."""

    decision: str
    reason: str
    stage: str
    receipt_id: str
    grant_digest: Optional[str] = None
    degraded: bool = False
    command_kind: Optional[str] = None
    duration_ms: int = 0
    cgroup_kill_used: bool = False
    tree_proven_absent: Optional[bool] = None
    diff: tuple = ()


def receipt_of(decision: Decision) -> dict:
    """Low-cardinality decision/receipt record matching
    `config/schemas/execution-cell-runner-decision.schema.json`. NEVER
    includes grants, logical paths, prompts, or file content — only enum
    reason/stage codes, booleans, small ints, and the two correlation IDs
    (mirrors `capability-lease-gate-decision.schema.json`'s `lease_id`
    precedent)."""
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_id": decision.receipt_id,
        "grant_digest": decision.grant_digest,
        "decision": decision.decision,
        "reason": decision.reason,
        "stage": decision.stage,
        "degraded": decision.degraded,
        "command_kind": decision.command_kind,
        "duration_ms": decision.duration_ms,
        "cgroup_kill_used": decision.cgroup_kill_used,
        "tree_proven_absent": decision.tree_proven_absent,
    }


# ---------------------------------------------------------------------------
# Command-descriptor vocabulary (Q-R3-4, recommended-and-endorsed answer):
# noop / read-validate / single-file-write — the smallest enforceable first
# cell. Derived ENTIRELY from the verified grant's own classified effects
# (never from arbitrary caller text — there is no field anywhere in this
# module that accepts free-form shell/command text).
# ---------------------------------------------------------------------------

COMMAND_NOOP = "noop"
COMMAND_READ_VALIDATE = "read-validate"
COMMAND_SINGLE_FILE_WRITE = "single-file-write"


@dataclass(frozen=True)
class CommandDescriptor:
    kind: str
    logical_path: Optional[str] = None
    content: Optional[str] = None
    encoding: str = "utf-8"
    expected_sha256: Optional[str] = None


def derive_command_descriptor(verified_grant: "eg.VerifiedGrant") -> Union[CommandDescriptor, eg.Denial]:
    """Design §5/§9 + Q-R3-4. Maps the grant's classified effect SET (never
    its raw, unclassified JSON) to exactly one of the three closed command
    kinds. Any effect combination outside this closed set is a typed
    `command-descriptor-unsupported` denial — conservative, matching R1's
    own `classification-ambiguous` posture. Never raises."""
    try:
        effects = verified_grant.classification.effects
        kinds = tuple(sorted({e.effect for e in effects}))

        if kinds == ("read",) and len(effects) == 1:
            return CommandDescriptor(kind=COMMAND_NOOP)

        if kinds == ("deterministic-validate",) and len(effects) == 1:
            scope = effects[0].scope
            paths = scope.get("paths")
            expected = scope.get("expected_sha256")
            if not isinstance(paths, list) or len(paths) != 1 or not isinstance(paths[0], str) or not paths[0]:
                return eg.Denial(REASON_COMMAND_UNSUPPORTED, "read-validate requires exactly one scope path")
            if not isinstance(expected, str) or not expected:
                return eg.Denial(REASON_COMMAND_UNSUPPORTED, "read-validate requires scope.expected_sha256")
            return CommandDescriptor(kind=COMMAND_READ_VALIDATE, logical_path=paths[0], expected_sha256=expected)

        if kinds == ("write",) and len(effects) == 1:
            scope = effects[0].scope
            paths = scope.get("paths")
            content = scope.get("content")
            encoding = scope.get("encoding", "utf-8")
            if not isinstance(paths, list) or len(paths) != 1 or not isinstance(paths[0], str) or not paths[0]:
                return eg.Denial(REASON_COMMAND_UNSUPPORTED, "single-file-write requires exactly one scope path")
            if not isinstance(content, str):
                return eg.Denial(REASON_COMMAND_UNSUPPORTED, "single-file-write requires scope.content: str")
            if not isinstance(encoding, str) or not encoding:
                encoding = "utf-8"
            return CommandDescriptor(
                kind=COMMAND_SINGLE_FILE_WRITE, logical_path=paths[0], content=content, encoding=encoding
            )

        return eg.Denial(REASON_COMMAND_UNSUPPORTED, f"unsupported effect combination for R3: {kinds!r}")
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return eg.Denial(REASON_COMMAND_UNSUPPORTED, f"internal command-derive error: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# The cell worker — a FIXED, closed constant executed inside bwrap. Its only
# dynamic input is a small descriptor JSON the runner itself writes (never
# caller-supplied text, never a shell string); this constant is identical
# across every request.
# ---------------------------------------------------------------------------

_WORKER_SRC = r"""
import hashlib, json, os, sys

def main():
    with open("/run/cell-descriptor.json", "r", encoding="utf-8") as fh:
        descriptor = json.load(fh)
    kind = descriptor.get("kind")
    result = {"kind": kind, "ok": False}
    try:
        logical_path = descriptor.get("logical_path")
        if logical_path is not None:
            if logical_path.startswith("/") or ".." in logical_path.split("/"):
                result["error"] = "path-rejected"
                raise ValueError("path-rejected")
            target = os.path.join("/cell", logical_path)
        else:
            target = None

        if kind == "noop":
            result["ok"] = True
        elif kind == "read-validate":
            with open(target, "rb") as fh2:
                data = fh2.read()
            digest = hashlib.sha256(data).hexdigest()
            result["sha256"] = digest
            result["ok"] = (digest == descriptor.get("expected_sha256"))
        elif kind == "single-file-write":
            content = descriptor.get("content", "")
            encoding = descriptor.get("encoding") or "utf-8"
            with open(target, "w", encoding=encoding) as fh2:
                fh2.write(content)
            result["ok"] = True
        else:
            result["error"] = "unknown-kind"
    except Exception as exc:
        result["ok"] = False
        result.setdefault("error", f"{type(exc).__name__}: {exc}")
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    sys.exit(0 if result.get("ok") else 1)

if __name__ == "__main__":
    main()
"""

_ENV_ALLOWLIST = {"HOME": "/tmp", "LANG": "C.UTF-8", "PATH": "/nonexistent"}


def resolve_bwrap_path(configured: Optional[str] = None) -> Optional[str]:
    """Design §5: `BWRAP_PATH` from env/PATH. Returns None (never raises,
    never guesses) if no usable bwrap binary can be found — the caller
    converts that to a typed `confinement-unavailable` denial."""
    candidate = configured or os.environ.get("BWRAP_PATH")
    if candidate:
        return candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None
    return shutil.which("bwrap")


def confinement_preflight(bwrap_path: Optional[str], python_bin: str) -> Optional[str]:
    """A cheap, real self-test of the deny-closed baseline (bwrap present +
    can actually construct a userns + minimal mounts). Returns None if OK,
    else a reason string. Never raises. This is the ONLY gate between "grant
    verified" and "cell construction begins" — its failure is the sole
    trigger for `confinement-unavailable`, and there is no path around it."""
    if not bwrap_path:
        return "bwrap-missing"
    if not python_bin or not os.path.isfile(python_bin):
        return "python-bin-missing"
    try:
        proc = subprocess.run(
            [
                bwrap_path,
                "--unshare-all", "--unshare-net",
                "--die-with-parent", "--new-session", "--clearenv",
                "--ro-bind", "/nix/store", "/nix/store",
                "--proc", "/proc",
                "--dev", "/dev",
                "--tmpfs", "/tmp",
                "--",
                python_bin, "-c", "pass",
            ],
            check=False, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "userns-unavailable"
    return None if proc.returncode == 0 else "userns-unavailable"


def build_bwrap_argv(bwrap_path: str, python_bin: str, cell_root: str, descriptor_file: str) -> list:
    """Design §5 — deny-closed baseline, derived ONLY from runner-owned
    inputs (bwrap/python binary paths resolved by this process, the R2
    `CellReady.cell_root`, and the runner's own descriptor file). No live
    repo/.git, no host home, no device/secret/mount beyond this fixed set,
    no ambient capabilities. Exactly ONE writable bind = the cell root."""
    argv = [
        bwrap_path,
        "--unshare-all", "--unshare-net",
        "--die-with-parent", "--new-session",
        "--clearenv",
    ]
    for key, value in _ENV_ALLOWLIST.items():
        argv += ["--setenv", key, value]
    argv += [
        "--ro-bind", "/nix/store", "/nix/store",
        "--ro-bind", descriptor_file, "/run/cell-descriptor.json",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--bind", cell_root, "/cell",
        "--chdir", "/cell",
        "--",
        python_bin, "-c", _WORKER_SRC,
    ]
    return argv


# ---------------------------------------------------------------------------
# cgroup v2 tracking + whole-tree kill/prove (design §6, folds R0 finding #7)
# ---------------------------------------------------------------------------


def create_cgroup(cgroup_parent: str, cell_id: str) -> Optional[str]:
    path = os.path.join(cgroup_parent, f"aq-cell-{cell_id}")
    try:
        os.makedirs(path, mode=0o700, exist_ok=False)
        return path
    except OSError:
        return None


def read_cgroup_pids(cgroup_path: str) -> list:
    try:
        with open(os.path.join(cgroup_path, "cgroup.procs"), "r", encoding="utf-8") as fh:
            return [int(line.strip()) for line in fh if line.strip()]
    except (OSError, ValueError):
        return []


def add_pid_to_cgroup(cgroup_path: str, pid: int) -> bool:
    try:
        with open(os.path.join(cgroup_path, "cgroup.procs"), "w", encoding="utf-8") as fh:
            fh.write(str(pid))
        return True
    except OSError:
        return False


def terminate_cgroup_tree(cgroup_path: str, sigterm_grace_s: float, kill_proof_budget_s: float) -> tuple:
    """Design §6 exact sequence: cgroup-scoped SIGTERM (enumerate
    `cgroup.procs`, signal each), wait <= `sigterm_grace_s`, then
    `cgroup.kill` (SIGKILL of the WHOLE tree, handles grandchildren the
    runner never directly tracked), wait up to `kill_proof_budget_s` to
    PROVE the tree is gone. Returns `(proven_absent, cgroup_kill_used)`.
    Never raises — every filesystem op here is best-effort and
    exception-guarded; an unproven tree is the caller's QUARANTINED
    trigger, never a raised error."""
    cgroup_kill_used = False
    try:
        for pid in read_cgroup_pids(cgroup_path):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        deadline = time.monotonic() + sigterm_grace_s
        while time.monotonic() < deadline:
            if not read_cgroup_pids(cgroup_path):
                break
            time.sleep(0.05)

        if read_cgroup_pids(cgroup_path):
            cgroup_kill_used = True
            try:
                with open(os.path.join(cgroup_path, "cgroup.kill"), "w", encoding="utf-8") as fh:
                    fh.write("1")
            except OSError:
                for pid in read_cgroup_pids(cgroup_path):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass

        proof_deadline = time.monotonic() + kill_proof_budget_s
        proven = False
        while time.monotonic() < proof_deadline:
            if not read_cgroup_pids(cgroup_path):
                proven = True
                break
            time.sleep(0.1)

        if proven:
            try:
                os.rmdir(cgroup_path)
            except OSError:
                # Directory removal failing after `cgroup.procs` is verified
                # empty still counts as "the tracked PROCESS TREE is proven
                # absent" (the only thing design §6 requires proof of); a
                # leftover empty cgroup directory is a `reconcile()`-class
                # sweep concern, not a false-GREEN safety concern.
                pass
        return proven, cgroup_kill_used
    except Exception:  # noqa: BLE001 — total fail-closed: never proven on error
        return False, cgroup_kill_used


def _cleanup_cgroup_dir(cgroup_path: Optional[str]) -> None:
    if not cgroup_path:
        return
    try:
        if not read_cgroup_pids(cgroup_path):
            os.rmdir(cgroup_path)
    except OSError:
        pass


def _proc_starttime(pid: int) -> Optional[int]:
    """Field 22 of `/proc/<pid>/stat` (starttime, in clock ticks since
    boot) — the process-identity binding component of the runner-generated
    heartbeat (design §6: `{grant_digest, receipt_id, pid, proc_starttime,
    cgroup_path}`). A changed starttime under the SAME pid means the kernel
    recycled the pid to an unrelated process — treated as a supervision
    trigger, never silently re-trusted."""
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as fh:
            data = fh.read()
        after_comm = data.rsplit(")", 1)[-1].split()
        return int(after_comm[19])
    except (OSError, ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# SO_PEERCRED authentication (design §3/§10-2 — UDS is transport-only)
# ---------------------------------------------------------------------------

_UCRED_FMT = "3i"  # struct ucred { pid_t pid; uid_t uid; gid_t gid; }


def get_peer_credentials(conn: "socket.socket") -> Optional[tuple]:
    """`sock.getsockopt(SOL_SOCKET, SO_PEERCRED, ...)` -> `(pid, uid, gid)`,
    or None on any failure (never raises). The UDS conveys no authority of
    its own — this kernel-verified identity is the ENTIRE authentication
    boundary before a byte of the request is even parsed."""
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(_UCRED_FMT))
        pid, uid, gid = struct.unpack(_UCRED_FMT, raw)
        return pid, uid, gid
    except (OSError, struct.error):
        return None


def peer_authorized(creds: Optional[tuple], client_uid: Optional[int], client_gid: Optional[int]) -> bool:
    if creds is None:
        return False
    _pid, uid, gid = creds
    if client_uid is not None and uid == client_uid:
        return True
    if client_gid is not None and gid == client_gid:
        return True
    return False


# ---------------------------------------------------------------------------
# Runner configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunnerConfig:
    socket_path: str
    client_uid: Optional[int]
    client_gid: Optional[int]
    public_key_bytes: bytes
    trusted_repo_mirrors: Mapping[str, str]
    cell_state_root: str
    cgroup_parent: str
    python_bin: str
    bwrap_path: Optional[str] = None
    validator_work_root: Optional[str] = None
    max_concurrent_cells: int = 1
    request_timeout_s: float = 30.0
    poll_interval_s: float = 0.25
    heartbeat_deadline_s: float = 1.0
    sigterm_grace_s: float = 0.5
    kill_proof_budget_s: float = 4.5
    epoch_source: Any = None
    reservation_set: Any = None
    cell_reservation_set: Any = None
    now_fn: Callable[[], datetime] = field(default_factory=lambda: (lambda: datetime.now(timezone.utc)))
    env: Optional[Mapping[str, str]] = None
    receipt_sink: Optional[Callable[[dict], None]] = None

    def resolved_bwrap_path(self) -> Optional[str]:
        return resolve_bwrap_path(self.bwrap_path)

    def resolved_validator_work_root(self) -> str:
        return self.validator_work_root or os.path.join(self.cell_state_root, "validator-work")


# ---------------------------------------------------------------------------
# The request pipeline (design §4) — grant verify -> command derive ->
# confinement preflight -> R2 create_cell -> bwrap-confine run -> supervise
# -> validate -> final epoch fence -> typed Decision. NEVER raises.
# ---------------------------------------------------------------------------


def process_grant(raw_grant: Any, config: RunnerConfig) -> Decision:
    receipt_id = uuid.uuid4().hex
    start_t = time.monotonic()
    try:
        if not execution_cells_enabled(config.env):
            return Decision(DECISION_DENIED, REASON_FLAG_OFF, STAGE_FLAG, receipt_id)

        now = config.now_fn()
        current_epoch = clg.resolve_current_epoch(config.epoch_source)
        verified = eg.verify_grant(raw_grant, config.public_key_bytes, now, current_epoch, config.reservation_set)
        if isinstance(verified, eg.Denial):
            return Decision(DECISION_DENIED, verified.reason, STAGE_GRANT_VERIFY, receipt_id)

        grant_digest = verified.grant_digest

        command = derive_command_descriptor(verified)
        if isinstance(command, eg.Denial):
            return Decision(DECISION_DENIED, command.reason, STAGE_COMMAND_DERIVE, receipt_id, grant_digest=grant_digest)

        mirror_path = config.trusted_repo_mirrors.get(verified.trusted_repo_id)
        if not mirror_path:
            return Decision(DECISION_DENIED, REASON_UNKNOWN_TRUSTED_REPO, STAGE_CELL_CREATE, receipt_id, grant_digest=grant_digest)

        bwrap_path = config.resolved_bwrap_path()
        preflight = confinement_preflight(bwrap_path, config.python_bin)
        if preflight is not None:
            return Decision(
                DECISION_DENIED, REASON_CONFINEMENT_UNAVAILABLE, STAGE_CONFINE_PREFLIGHT, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind,
            )

        cell_reservation = config.cell_reservation_set if config.cell_reservation_set is not None else config.reservation_set
        cell_result = ecc.create_cell(
            verified,
            bare_mirror_path=mirror_path,
            cell_state_root=config.cell_state_root,
            now=now,
            current_epoch=current_epoch,
            reservation_set=cell_reservation,
        )
        if isinstance(cell_result, ecc.TypedFailure):
            return Decision(
                DECISION_DENIED, cell_result.code, STAGE_CELL_CREATE, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind,
            )

        cell = cell_result
        try:
            return _confine_run_validate(cell, command, verified, grant_digest, receipt_id, bwrap_path, config, start_t)
        finally:
            # R3 never retains a live cell past this single request — the
            # GREEN diff is retained as DATA (Decision.diff), never as a
            # lingering writable working tree (design §4.5: no auto-merge,
            # ever; a retained cell is not itself an authority to merge).
            ecc.teardown_cell(cell)
    except Exception as exc:  # noqa: BLE001 — total fail-closed, NEVER raise to the caller
        # Reason carries only the exception CLASS name (low-cardinality,
        # bounded set) — never str(exc), which could embed a path/content
        # fragment and violate the "no high-cardinality detail" receipt
        # contract.
        return Decision(
            DECISION_DENIED, f"{REASON_RUNNER_INTERNAL_ERROR}:{type(exc).__name__}", STAGE_GRANT_VERIFY, receipt_id
        )


def _parse_worker_result(stdout: bytes) -> Optional[dict]:
    try:
        payload = json.loads(stdout.decode("utf-8"))
        if not isinstance(payload, dict) or "ok" not in payload:
            return None
        return payload
    except (ValueError, UnicodeDecodeError):
        return None


def _confine_run_validate(
    cell: "ecc.CellReady",
    command: CommandDescriptor,
    verified: "eg.VerifiedGrant",
    grant_digest: str,
    receipt_id: str,
    bwrap_path: Optional[str],
    config: RunnerConfig,
    start_t: float,
) -> Decision:
    def _elapsed_ms() -> int:
        return int((time.monotonic() - start_t) * 1000)

    # TOCTOU-safe re-resolution immediately before use (CellReady docstring,
    # R2): the informational `resolved_paths` map from cell-creation time is
    # NEVER trusted as a substitute for a fresh check right here.
    if command.logical_path is not None:
        rebased = ecc.rebase_logical_path(cell.cell_root, command.logical_path, verified.path_plan.allowlist)
        if isinstance(rebased, ecc.PathEscape):
            return Decision(
                DECISION_RED, "path-escape-at-run", STAGE_CONFINE_RUN, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, duration_ms=_elapsed_ms(),
            )
        os.close(rebased)

    descriptor = {
        "kind": command.kind,
        "logical_path": command.logical_path,
        "content": command.content,
        "encoding": command.encoding,
        "expected_sha256": command.expected_sha256,
    }

    os.makedirs(config.cell_state_root, mode=0o700, exist_ok=True)
    descriptor_fd, descriptor_path = tempfile.mkstemp(prefix="aq-cell-descriptor-", dir=config.cell_state_root)
    cgroup_path: Optional[str] = None
    try:
        with os.fdopen(descriptor_fd, "w", encoding="utf-8") as fh:
            json.dump(descriptor, fh)
        os.chmod(descriptor_path, 0o400)

        if not bwrap_path:
            return Decision(
                DECISION_DENIED, REASON_CONFINEMENT_UNAVAILABLE, STAGE_CONFINE_RUN, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, duration_ms=_elapsed_ms(),
            )

        argv = build_bwrap_argv(bwrap_path, config.python_bin, cell.cell_root, descriptor_path)

        cgroup_path = create_cgroup(config.cgroup_parent, receipt_id)
        if cgroup_path is None:
            return Decision(
                DECISION_QUARANTINED, "cgroup-unavailable", STAGE_CONFINE_RUN, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, duration_ms=_elapsed_ms(),
            )

        try:
            popen = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError:
            return Decision(
                DECISION_DENIED, REASON_CONFINEMENT_UNAVAILABLE, STAGE_CONFINE_RUN, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, duration_ms=_elapsed_ms(),
            )
        add_pid_to_cgroup(cgroup_path, popen.pid)

        outcome, trigger, cgroup_kill_used, proven = _supervise(popen, cgroup_path, verified, config)

        try:
            stdout, _stderr = popen.communicate(timeout=1.0)
        except Exception:
            stdout = b""
            try:
                popen.kill()
            except OSError:
                pass

        if not proven:
            return Decision(
                DECISION_QUARANTINED, REASON_TREE_NOT_PROVEN_ABSENT, STAGE_SUPERVISE, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, cgroup_kill_used=cgroup_kill_used,
                tree_proven_absent=False, duration_ms=_elapsed_ms(),
            )

        if outcome == "terminated":
            return Decision(
                DECISION_RED, trigger or "supervision-terminal-trigger", STAGE_SUPERVISE, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, cgroup_kill_used=cgroup_kill_used,
                tree_proven_absent=True, duration_ms=_elapsed_ms(),
            )

        self_report = _parse_worker_result(stdout)
        if self_report is None:
            return Decision(
                DECISION_RED, REASON_MALFORMED_RESULT, STAGE_SUPERVISE, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, cgroup_kill_used=cgroup_kill_used,
                tree_proven_absent=True, duration_ms=_elapsed_ms(),
            )
        if popen.returncode != 0 or not self_report.get("ok"):
            return Decision(
                DECISION_RED, REASON_COMMAND_FAILED, STAGE_SUPERVISE, receipt_id,
                grant_digest=grant_digest, command_kind=command.kind, cgroup_kill_used=cgroup_kill_used,
                tree_proven_absent=True, duration_ms=_elapsed_ms(),
            )
    finally:
        _cleanup_cgroup_dir(cgroup_path)
        try:
            os.remove(descriptor_path)
        except OSError:
            pass

    # ---- out-of-cell validation (design §7) — the cell's own self-report
    # above is evidence only; GREEN is decided here. ----
    declared = (command.logical_path,) if command.logical_path else ()
    validator_config = validator.ValidatorConfig(
        bare_mirror_path=config.trusted_repo_mirrors[verified.trusted_repo_id],
        bwrap_path=bwrap_path,
        python_bin=config.python_bin,
        work_root=config.resolved_validator_work_root(),
    )
    validation = validator.validate(
        grant_digest=grant_digest,
        base_oid=cell.base_oid,
        cell_root=cell.cell_root,
        declared_output_paths=declared,
        config=validator_config,
    )
    if validation.verdict != validator.VERDICT_GREEN:
        return Decision(
            DECISION_RED, f"validator:{validation.reason}", STAGE_VALIDATE, receipt_id,
            grant_digest=grant_digest, command_kind=command.kind,
            tree_proven_absent=True, duration_ms=_elapsed_ms(),
        )

    # ---- FINAL EPOCH FENCE (design §6) — re-read the authoritative epoch
    # AND re-check freshness immediately before publishing GREEN. Any
    # failure here flips a would-be GREEN to RED. ----
    final_epoch = clg.resolve_current_epoch(config.epoch_source)
    raw = dict(verified.raw)
    fence_epoch_ok = eg.verify_epoch(raw, final_epoch) == eg.VERIFY_OK
    fence_fresh_ok = eg.verify_freshness(raw, config.now_fn()) == eg.VERIFY_OK
    if not (fence_epoch_ok and fence_fresh_ok):
        return Decision(
            DECISION_RED, REASON_FINAL_FENCE_FAILED, STAGE_FINAL_FENCE, receipt_id,
            grant_digest=grant_digest, command_kind=command.kind,
            tree_proven_absent=True, duration_ms=_elapsed_ms(),
        )

    return Decision(
        DECISION_GREEN, REASON_OK, STAGE_FINAL_FENCE, receipt_id,
        grant_digest=grant_digest, command_kind=command.kind,
        tree_proven_absent=True, duration_ms=_elapsed_ms(), diff=validation.changed_paths,
    )


def _supervise(popen: "subprocess.Popen", cgroup_path: str, verified: "eg.VerifiedGrant", config: RunnerConfig) -> tuple:
    """Design §6: poll epoch + liveness every `poll_interval_s` (250 ms);
    the runner IS the sole heartbeat source (never trusts a caller
    heartbeat) bound to `{grant_digest, receipt_id, pid, proc_starttime,
    cgroup_path}` with a `heartbeat_deadline_s` (1 s) local deadline —
    modeled here as: if the supervisor's OWN tick cadence stalls past that
    deadline, that is itself treated as a heartbeat-miss (the runner cannot
    vouch for liveness it did not itself observe on schedule). Terminal
    triggers: timeout, heartbeat-miss, epoch-bump, pid-recycle (peer/receipt
    mismatch), crash. Returns
    `(outcome in {"completed","terminated"}, trigger_or_None,
    cgroup_kill_used, tree_proven_absent)`."""
    timeout_s = verified.resource_limits.get("timeout_s") or config.request_timeout_s
    try:
        timeout_s = float(timeout_s)
    except (TypeError, ValueError):
        timeout_s = config.request_timeout_s

    start = time.monotonic()
    proc_start = _proc_starttime(popen.pid)
    last_tick = time.monotonic()
    trigger: Optional[str] = None

    while True:
        time.sleep(config.poll_interval_s)
        now_tick = time.monotonic()
        tick_gap = now_tick - last_tick
        last_tick = now_tick

        if tick_gap > max(config.heartbeat_deadline_s, config.poll_interval_s * 4):
            trigger = "heartbeat-miss"
            break

        exit_code = popen.poll()
        if exit_code is not None:
            break

        if now_tick - start > timeout_s:
            trigger = "timeout"
            break

        current_epoch = clg.resolve_current_epoch(config.epoch_source)
        if eg.verify_epoch(dict(verified.raw), current_epoch) != eg.VERIFY_OK:
            trigger = "epoch-bump"
            break

        current_starttime = _proc_starttime(popen.pid)
        if proc_start is not None and current_starttime != proc_start:
            trigger = "peer-receipt-mismatch"
            break

    if trigger is not None:
        proven, cgroup_kill_used = terminate_cgroup_tree(cgroup_path, config.sigterm_grace_s, config.kill_proof_budget_s)
        return "terminated", trigger, cgroup_kill_used, proven

    proven, cgroup_kill_used = terminate_cgroup_tree(cgroup_path, config.sigterm_grace_s, config.kill_proof_budget_s)
    return "completed", None, cgroup_kill_used, proven


# ---------------------------------------------------------------------------
# UDS server (design §3) — SO_PEERCRED-gated, transport-only, bounded
# concurrency. NEVER raises to the socket caller.
# ---------------------------------------------------------------------------


def _recv_all(conn: "socket.socket", max_bytes: int) -> bytes:
    chunks = []
    total = 0
    conn.settimeout(10.0)
    try:
        while total < max_bytes:
            chunk = conn.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except (OSError, socket.timeout):
        pass
    return b"".join(chunks)


def _send_json(conn: "socket.socket", payload: dict) -> None:
    try:
        conn.sendall(json.dumps(payload).encode("utf-8"))
    except OSError:
        pass


def _emit_receipt(decision: Decision, config: RunnerConfig) -> None:
    try:
        record = receipt_of(decision)
        if config.receipt_sink is not None:
            config.receipt_sink(record)
    except Exception:  # noqa: BLE001 — telemetry must never break the response path
        pass


def _handle_connection(conn: "socket.socket", config: RunnerConfig, semaphore: "threading.BoundedSemaphore") -> None:
    acquired = False
    try:
        creds = get_peer_credentials(conn)
        if not peer_authorized(creds, config.client_uid, config.client_gid):
            # No error oracle: the connection is simply closed, no response
            # at all — a non-client peer learns nothing about why.
            return

        raw = _recv_all(conn, max_bytes=1 << 20)

        acquired = semaphore.acquire(blocking=False)
        if not acquired:
            _send_json(conn, {"decision": DECISION_DENIED, "reason": REASON_RUNNER_BUSY, "receipt_id": uuid.uuid4().hex})
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            decision = Decision(DECISION_DENIED, REASON_REQUEST_MALFORMED, STAGE_REQUEST, uuid.uuid4().hex)
            _send_json(conn, receipt_of(decision))
            _emit_receipt(decision, config)
            return

        decision = process_grant(payload, config)
        _send_json(conn, receipt_of(decision))
        _emit_receipt(decision, config)
    except Exception:  # noqa: BLE001 — NEVER raise to the socket caller
        try:
            _send_json(conn, {"decision": DECISION_DENIED, "reason": REASON_RUNNER_INTERNAL_ERROR})
        except Exception:
            pass
    finally:
        if acquired:
            semaphore.release()
        try:
            conn.close()
        except OSError:
            pass


def serve_forever(config: RunnerConfig, stop_event: Optional["threading.Event"] = None) -> None:
    """The socket-activated runner's accept loop. Design §8: systemd owns
    socket creation/mode/ownership in production (`systemd.sockets.
    aq-execution-cell-runner`); this function also binds its own socket
    directly for offline testing without systemd socket activation."""
    if os.path.exists(config.socket_path):
        try:
            os.unlink(config.socket_path)
        except OSError:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(config.socket_path)
        os.chmod(config.socket_path, 0o660)
        server.listen(16)
        server.settimeout(0.5)
        semaphore = threading.BoundedSemaphore(max(1, config.max_concurrent_cells))
        while stop_event is None or not stop_event.is_set():
            try:
                conn, _addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=_handle_connection, args=(conn, config, semaphore), daemon=True).start()
    finally:
        try:
            server.close()
        except OSError:
            pass
        try:
            os.unlink(config.socket_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# main() — production entry point for the systemd unit. R3 ships NO live
# wiring (no switchboard adoption, no trusted_repo_mirrors provisioning
# beyond what an operator explicitly configures) — this exists so the Nix
# ExecStart has a valid target; `enable=true` is a separate R6 owner act.
# ---------------------------------------------------------------------------


def build_config_from_env(env: Optional[Mapping[str, str]] = None) -> RunnerConfig:
    source = env if env is not None else os.environ
    public_key_hex = source.get("AQ_EXECUTION_CELL_RUNNER_PUBLIC_KEY_HEX", "")
    try:
        public_key_bytes = bytes.fromhex(public_key_hex) if public_key_hex else b""
    except ValueError:
        public_key_bytes = b""

    mirrors: dict = {}
    mirrors_raw = source.get("AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS", "")
    if mirrors_raw:
        try:
            parsed = json.loads(mirrors_raw)
            if isinstance(parsed, dict):
                mirrors = {str(k): str(v) for k, v in parsed.items()}
        except (ValueError, TypeError):
            mirrors = {}

    state_root = source.get("AQ_EXECUTION_CELL_RUNNER_STATE_ROOT", "/var/lib/aq-execution-cell-runner")
    return RunnerConfig(
        socket_path=source.get("AQ_EXECUTION_CELL_RUNNER_SOCKET_PATH", "/run/aq-execution-cell-runner/control.sock"),
        client_uid=int(source["AQ_EXECUTION_CELL_RUNNER_CLIENT_UID"]) if source.get("AQ_EXECUTION_CELL_RUNNER_CLIENT_UID") else None,
        client_gid=int(source["AQ_EXECUTION_CELL_RUNNER_CLIENT_GID"]) if source.get("AQ_EXECUTION_CELL_RUNNER_CLIENT_GID") else None,
        public_key_bytes=public_key_bytes,
        trusted_repo_mirrors=mirrors,
        cell_state_root=os.path.join(state_root, "cells"),
        cgroup_parent=source.get("AQ_EXECUTION_CELL_RUNNER_CGROUP_PARENT", "/sys/fs/cgroup/aq-execution-cell-runner.slice"),
        python_bin=source.get("AQ_EXECUTION_CELL_RUNNER_PYTHON_BIN", sys.executable),
        bwrap_path=source.get("BWRAP_PATH"),
        max_concurrent_cells=int(source.get("AQ_EXECUTION_CELL_RUNNER_MAX_CONCURRENT_CELLS", "1")),
        request_timeout_s=float(source.get("AQ_EXECUTION_CELL_RUNNER_REQUEST_TIMEOUT_SECONDS", "30")),
        env=source,
    )


def main() -> int:
    config = build_config_from_env()
    if not execution_cells_enabled(config.env):
        # Default-OFF gate at the process level too: still listens (systemd
        # socket-activation contract) but every request is denied inside
        # process_grant before anything is constructed. We do not exit
        # early here, since a healthy-but-inert service is the correct
        # default-OFF posture (observable, not crash-looping).
        pass
    serve_forever(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
