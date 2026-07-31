"""Execution Cell Adapter — Foundation C, C3b R5 (default-OFF, enforcement-tier).

Implements ONLY the guarded switchboard adapter authorized by
`.agents/plans/aqos-foundation-c/C3B-R5-DESIGN-AND-AUTHORIZATION.md` §2-§4,
frozen by `C3B-R5-FREEZE-AND-ACTIVATION.md` and released for build by owner
activation event `ffd469a6` (`activation.grant`). That activation authorizes
ONLY this ceiling, flag DEFAULT-OFF:

  - mint an R1 execution grant from a C2-admitted request's classification
    (base_revision, effect_set, exec_class, logical_paths, resource_limits,
    a fresh grant_id, the current revocation_epoch, a bounded deadline);
  - Ed25519-SIGN it with the PRODUCTION private key loaded from
    `/run/secrets/aq-grant-signing-key` (SOPS-decrypted; NEVER a tracked
    file, NEVER hardcoded). This module is the PRODUCTION signer —
    `scripts/ai/lib/execution_grant.py::sign()` is TEST-ONLY (see that
    module's docstring) and is never called here; only its pure
    canonicalization helpers (`canonical_payload`/`compute_grant_digest`)
    are reused, exactly as any other consumer of that pure library;
  - submit the signed grant to the R3 runner over its UDS control socket
    and consume its typed GREEN/RED/QUARANTINED/DENIED result;
  - project a low-cardinality, secret-free receipt to PULSE/audit (stderr,
    matching the `capability-lease-gate-decision`/
    `execution-cell-runner-decision` precedent) and, additively, a C5
    `workspace` taxonomy span shadow-emit (flag `CAPABILITY_SPAN_TRUTH`,
    unchanged contract — this module does NOT modify `span_taxonomy.py`).

Key-unavailable (`/run/secrets/aq-grant-signing-key` absent/unreadable/
wrong-length) => NO grant is minted => deny (authority-degrade posture,
never an unsigned or fallback grant). Any adapter/runner error anywhere in
this pipeline => deny-closed (the effect does not happen) — this module
NEVER raises to its caller.

Scope discipline (design §1, §6): this is a SHADOW attach point only. The
switchboard call site (`ai-stack/switchboard/switchboard.py`) invokes this
module strictly AFTER a tool's real, already-admitted (C2) execution has
already produced its real result — this module's typed result is recorded
for validation/observability, it NEVER replaces, gates, delays, or
retroactively undoes that real result. Making the runner's result
authoritative for real effects (routing real traffic through the cell) is
a SEPARATE, later, owner-activated R6 canary — never this slice. This
module also never itself constructs a cell, runs bwrap, or creates a
namespace — that stays the R3 runner's sole job.

The flag is `CAPABILITY_CELL_ADAPTER`, default OFF ("0"), DISTINCT from the
R3 runner's own `CAPABILITY_EXECUTION_CELLS` flag (defense in depth,
Q-R5-1). While OFF, `cell_adapter_enabled()` is False and `submit_to_cell()`
returns an immediate `denied`/`adapter-disabled` result without importing
`cryptography`, touching the filesystem, or opening a socket — "nothing
runs". The switchboard's own call site additionally short-circuits on this
same flag BEFORE ever importing this module at all (mirrors
`_admit_tool_call`'s lazy import of `capability_lease_gate`), so flag-OFF
is byte-for-byte parity with pre-R5 switchboard behavior.

This module consumes, and NEVER reimplements or modifies:
  - `scripts/ai/lib/execution_grant.py` (R1) — `canonical_payload`,
    `compute_grant_digest` (pure canonicalization; production-safe), plus
    `verify_signature`/`verify_grant` (used only by this module's own
    tests, to round-trip what was signed here).
  - `ai-stack/switchboard/execution_cell_runner.py` (R3) — consumed only as
    a UDS peer over its documented request/response protocol (raw JSON
    grant in, `receipt_of()`-shaped JSON out); this module never imports or
    calls into the runner's internals directly.
  - `ai-stack/switchboard/capability_lease_gate.py` (C2) —
    `resolve_current_epoch`, the ONE authoritative epoch source (matching
    the runner's own dependency). `current_epoch is None` always denies
    (never a skipped staleness check, never a locally-guessed epoch).
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[1]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import execution_grant as eg  # noqa: E402 — pure canonicalization helpers only
import capability_lease_gate as clg  # noqa: E402 — resolve_current_epoch (frozen dependency)

# ---------------------------------------------------------------------------
# The default-OFF flag (design §2/§6; `config/env-contract.yaml`). DISTINCT
# from the R3 runner's own `CAPABILITY_EXECUTION_CELLS` (Q-R5-1).
# ---------------------------------------------------------------------------

FLAG_ENV = "CAPABILITY_CELL_ADAPTER"


def cell_adapter_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """True iff the adapter is authorized to mint/sign/submit a grant at
    all. Default OFF: an absent/unrecognized value is OFF, never ON
    (deny-closed on the flag itself, matching every other flag in this
    harness)."""
    source = env if env is not None else os.environ
    return source.get(FLAG_ENV, "0") == "1"


# ---------------------------------------------------------------------------
# Typed result vocabulary — mirrors the R3 runner's DECISION_* vocabulary
# for the four outcomes that can flow back over the wire, plus adapter-only
# denial reasons for everything that stops BEFORE a request ever reaches
# the runner (flag off, not cell-required, key unavailable, epoch/base-
# revision unresolvable, runner unreachable, malformed runner response).
# ---------------------------------------------------------------------------

DECISION_GREEN = "green"
DECISION_RED = "red"
DECISION_QUARANTINED = "quarantined"
DECISION_DENIED = "denied"

_RUNNER_DECISIONS = frozenset({DECISION_GREEN, DECISION_RED, DECISION_QUARANTINED, DECISION_DENIED})

REASON_ADAPTER_DISABLED = "adapter-disabled"
REASON_NOT_CELL_REQUIRED = "not-cell-required"
REASON_SIGNING_KEY_UNAVAILABLE = "signing-key-unavailable"
REASON_EPOCH_UNRESOLVABLE = "epoch-unresolvable"
REASON_BASE_REVISION_UNRESOLVABLE = "base-revision-unresolvable"
REASON_RUNNER_UNREACHABLE = "runner-unreachable"
REASON_RUNNER_RESPONSE_MALFORMED = "runner-response-malformed"
REASON_ADAPTER_INTERNAL_ERROR = "adapter-internal-error"


@dataclass(frozen=True)
class AdapterResult:
    """A terminal, typed outcome. `runner_decision` (when present) is the
    raw schema-conformant receipt the runner returned — kept only for a
    caller in this same process; the PROJECTED receipt (`_project_receipt`)
    is always the narrow, low-cardinality subset, never this whole dict."""

    decision: str
    reason: str
    receipt_id: Optional[str] = None
    grant_digest: Optional[str] = None
    runner_decision: Optional[dict] = None


# ---------------------------------------------------------------------------
# Minimal cell-required classification vocabulary (Q-R5-3: the minimal R1/R3
# vocabulary only — single-file-write / read-validate; everything else stays
# non-cell, unaffected by this adapter). Pure, no I/O, never raises.
# ---------------------------------------------------------------------------

CELL_REQUIRED_TOOLS: frozenset[str] = frozenset({"write_file"})

_UNSAFE_PATH_MARKER_CHARS = ("\\",)


def _path_syntactically_safe(path: str) -> bool:
    """Cheap, conservative pre-screen (defense in depth only — R1's own
    `classify_paths` is the authoritative gate at grant-verify time
    regardless). Rejects absolute paths, traversal, and the backslash
    escape marker; anything else is left to R1."""
    if not isinstance(path, str) or not path:
        return False
    if path.startswith("/"):
        return False
    if any(marker in path for marker in _UNSAFE_PATH_MARKER_CHARS):
        return False
    if ".." in path.split("/"):
        return False
    return True


def classify_cell_required_effect(tool_name: str, arguments: Any) -> Optional[dict]:
    """Design §2/§3 + Q-R5-3. Returns a pure classification
    `{"effect_set", "exec_class", "logical_paths"}` (the shape §3 says the
    grant's effect_set/exec_class/logical_paths are drawn from), or `None`
    when `tool_name`/`arguments` do not match the minimal closed vocabulary
    this first cut supports — the tool then simply executes via the normal,
    unaffected in-process path (this adapter is never involved). Never
    raises.

    First-cut vocabulary: ONLY `write_file` (mapping to R1's `write` effect
    / R3's `single-file-write` command) with a syntactically-safe, relative
    `file_path` and string `content`. `read-validate` is NOT wired to any
    currently-dispatchable first-party tool (no tool call surface supplies
    an `expected_sha256`) and is deliberately left unclassified here —
    adding it is a later, separately-reviewed slice, matching R0's
    incremental-vocabulary discipline."""
    try:
        if tool_name not in CELL_REQUIRED_TOOLS:
            return None
        if not isinstance(arguments, dict):
            return None
        if tool_name == "write_file":
            file_path = arguments.get("file_path")
            content = arguments.get("content")
            encoding = arguments.get("encoding", "utf-8")
            if not isinstance(file_path, str) or not _path_syntactically_safe(file_path):
                return None
            if not isinstance(content, str):
                return None
            if not isinstance(encoding, str) or not encoding:
                encoding = "utf-8"
            return {
                "effect_set": [
                    {
                        "effect": "write",
                        "scope": {"mode": "write", "paths": [file_path], "content": content, "encoding": encoding},
                    }
                ],
                "exec_class": "sandbox-required",
                "logical_paths": [file_path],
            }
        return None
    except Exception:  # noqa: BLE001 — total fail-closed: never classify on error
        return None


# ---------------------------------------------------------------------------
# Key loading (design §3 — the sharp edge). Deny-closed: any absent/
# unreadable/malformed/wrong-length key file yields None (never a partial,
# guessed, or fallback key). NO key is ever hardcoded here.
# ---------------------------------------------------------------------------

DEFAULT_SIGNING_KEY_PATH = "/run/secrets/aq-grant-signing-key"
_ED25519_RAW_SEED_LEN = 32


def load_signing_key(path: Optional[str] = None) -> Optional[Ed25519PrivateKey]:
    """Load the PRODUCTION Ed25519 PRIVATE signing key from a SOPS-decrypted
    `/run/secrets/...` path (never a tracked file, never an env literal).
    SOPS yaml stores STRING values only — a raw 32-byte Ed25519 seed is not
    valid UTF-8 and cannot round-trip through a SOPS yaml string, so the
    decrypted file holds a HEX-encoded seed instead (64 hex chars, one
    trailing newline tolerated and stripped), matching the R3 runner's own
    pre-existing `AQ_EXECUTION_CELL_RUNNER_PUBLIC_KEY_HEX` convention.
    Nothing beyond that trailing-newline strip is guessed or padded.
    Returns None (deny-closed) on ANY failure: missing file, unreadable,
    non-hex text, a decoded length != 32 bytes, or anything `cryptography`
    itself rejects as an Ed25519 seed. Never raises."""
    target = path or DEFAULT_SIGNING_KEY_PATH
    try:
        with open(target, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    except UnicodeDecodeError:
        return None
    try:
        stripped = text.strip()
        raw = bytes.fromhex(stripped)
        if len(raw) != _ED25519_RAW_SEED_LEN:
            return None
        return Ed25519PrivateKey.from_private_bytes(raw)
    except Exception:  # noqa: BLE001 — malformed key material -> deny, never raise
        return None


# ---------------------------------------------------------------------------
# Grant minting + PRODUCTION signing (design §3). Distinct from
# `execution_grant.sign()` (TEST-ONLY) — this is the real signer, reusing
# ONLY R1's pure canonicalization helpers, never its test-only signer.
# ---------------------------------------------------------------------------


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_grant_base(
    *,
    base_revision: str,
    trusted_repo_id: str,
    effect_set: list,
    exec_class: str,
    logical_paths: list,
    revocation_epoch: int,
    resource_limits: Mapping[str, Any],
    deadline_s: float,
    now: Optional[datetime] = None,
) -> dict:
    """Build every REQUIRED_GRANT_FIELDS field except `grant_digest`/
    `signature` (design §3: base_revision, effect_set/scopes, exec_class,
    logical_paths, resource_limits, a fresh unique grant_id,
    revocation_epoch, a bounded expiry). `grant_id` uses two concatenated
    uuid4 hex strings (64 hex chars) — well above R1's
    `MIN_GRANT_ID_LEN` collision-resistance floor."""
    moment = now or datetime.now(timezone.utc)
    return {
        "grant_schema_version": 1,
        "grant_id": uuid.uuid4().hex + uuid.uuid4().hex,
        "lease_id": f"cell-adapter::{uuid.uuid4().hex}",
        "task_id": f"cell-adapter-task::{uuid.uuid4().hex}",
        "request_id": f"cell-adapter-req::{uuid.uuid4().hex}",
        "issued_at": _rfc3339(moment),
        "expires_at": _rfc3339(moment + timedelta(seconds=max(1.0, float(deadline_s)))),
        "revocation_epoch": int(revocation_epoch),
        "base_revision": base_revision,
        "effect_set": effect_set,
        "exec_class": exec_class,
        "trusted_repo_id": trusted_repo_id,
        "logical_paths": logical_paths,
        "resource_limits": dict(resource_limits),
    }


def sign_grant_production(grant_base: dict, private_key: Ed25519PrivateKey) -> dict:
    """The PRODUCTION signer (R5). `execution_grant.sign()` is TEST-ONLY
    (see that module's docstring: "Production code never calls this") — this
    function is what actually signs a real grant, using ONLY R1's pure
    `compute_grant_digest`/`canonical_payload` (canonicalization, not
    signing) plus `cryptography`'s `Ed25519PrivateKey.sign()` directly.
    Never called with anything but a genuinely SOPS-loaded production key
    (see `load_signing_key`)."""
    base = {k: v for k, v in grant_base.items() if k not in ("grant_digest", "signature")}
    digest = eg.compute_grant_digest(base)
    with_digest = {**base, "grant_digest": digest}
    payload = eg.canonical_payload(with_digest)
    signature = private_key.sign(payload)
    return {**with_digest, "signature": signature.hex()}


# ---------------------------------------------------------------------------
# UDS client (design §2 — transport only, exactly the R3 runner's own
# protocol: send the raw JSON grant, shutdown the write side so the
# runner's `_recv_all` sees EOF, then read the JSON response until the
# runner closes). Deny-closed on any socket error: returns None, never
# raises.
# ---------------------------------------------------------------------------


def _uds_round_trip(payload_bytes: bytes, socket_path: str, timeout_s: float) -> Optional[bytes]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(max(0.1, float(timeout_s)))
        sock.connect(socket_path)
        sock.sendall(payload_bytes)
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except (OSError, socket.timeout):
        return None
    finally:
        try:
            sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Receipt projection (design §4) — low-cardinality, secret-free. Reuses the
# existing stderr audit-line pattern (`capability-lease-gate-decision`,
# matched by `execution-cell-runner-decision`) plus the existing C5
# `workspace` taxonomy span (flag `CAPABILITY_SPAN_TRUTH`, UNCHANGED
# contract — this module does not add attrs or kinds to `span_taxonomy.py`).
# ---------------------------------------------------------------------------


def adapter_receipt_record(result: AdapterResult) -> dict:
    """The schema-conformant record
    (`config/schemas/execution-cell-adapter-receipt.schema.json`) — NEVER
    carries a grant's raw fields, logical paths, file content, or prompts;
    only enum-ish decision/reason strings and the two correlation
    identifiers (mirrors the R3 runner's own receipt precedent)."""
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_id": result.receipt_id,
        "grant_digest": result.grant_digest,
        "decision": result.decision,
        "reason": result.reason,
    }


def _emit_adapter_span_shadow(result: AdapterResult) -> None:
    """C5 (non-enforcement observability, additive): flag-gated `workspace`
    span shadow-emit, mirroring the R3 runner's own
    `_emit_workspace_span_shadow` shape exactly (same kind, same required
    attrs) so this module never needs to touch `span_taxonomy.py`. Flag
    default OFF (`CAPABILITY_SPAN_TRUTH`) => returns before any
    import/emit. `base_oid` is always `None` here — the adapter's own
    UDS-transported receipt never carries it (it is deliberately excluded
    from the runner's wire-schema); presence of the key (not its value) is
    what `span_taxonomy` requires. A `denied` result (no cell was ever
    constructed for this request) emits no span, mirroring the runner's own
    `_workspace_event_for(None)` semantics. Never raises."""
    if os.environ.get("CAPABILITY_SPAN_TRUTH", "0") != "1":
        return
    event = {
        DECISION_GREEN: "snapshot",
        DECISION_RED: "rollback",
        DECISION_QUARANTINED: "quarantine",
    }.get(result.decision)
    if event is None:
        return
    try:
        import span_taxonomy as _st

        _st.emit_taxonomy_span(
            "workspace",
            agent="execution_cell_adapter",
            attrs={
                "event": event,
                "cell_id": result.receipt_id,
                "base_oid": None,
                "grant_digest": result.grant_digest,
            },
        )
    except Exception:  # noqa: BLE001 — telemetry must never break the caller
        pass


def _project_receipt(result: AdapterResult, config: "AdapterConfig") -> None:
    try:
        record = adapter_receipt_record(result)
        if config.receipt_sink is not None:
            config.receipt_sink(record)
        else:
            sys.stderr.write("execution-cell-adapter-receipt " + json.dumps(record, sort_keys=True) + "\n")
            sys.stderr.flush()
    except Exception:  # noqa: BLE001 — telemetry must never break the caller
        pass
    _emit_adapter_span_shadow(result)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterConfig:
    signing_key_path: str = DEFAULT_SIGNING_KEY_PATH
    runner_socket_path: str = "/run/aq-execution-cell-runner/control.sock"
    trusted_repo_id: str = "primary"
    epoch_source: Any = None
    base_revision_resolver: Optional[Callable[[], Optional[str]]] = None
    request_timeout_s: float = 10.0
    deadline_s: float = 60.0
    resource_limits: Mapping[str, Any] = field(
        default_factory=lambda: {"timeout_s": 30, "max_output_bytes": 65536, "cell_class": "small"}
    )
    env: Optional[Mapping[str, str]] = None
    receipt_sink: Optional[Callable[[dict], None]] = None


_HEX_OID_RE = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64})$")


def resolve_base_revision_git_head(repo_root: Optional[str] = None) -> Optional[str]:
    """Design §3: `base_revision = current trusted OID`. Shells `git
    rev-parse HEAD` in `repo_root` (default the harness repo root). Returns
    None (deny-closed) on any failure or a non-hex-OID result — never a
    guessed/partial revision."""
    try:
        root = repo_root or str(_REPO_ROOT)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        oid = result.stdout.strip()
        return oid if _HEX_OID_RE.match(oid) else None
    except Exception:  # noqa: BLE001 — total fail-closed
        return None


def build_adapter_config_from_env(env: Optional[Mapping[str, str]] = None) -> AdapterConfig:
    source = env if env is not None else os.environ
    resource_limits = {
        "timeout_s": int(source.get("AQ_EXECUTION_CELL_ADAPTER_TIMEOUT_S", "30")),
        "max_output_bytes": int(source.get("AQ_EXECUTION_CELL_ADAPTER_MAX_OUTPUT_BYTES", "65536")),
        "cell_class": source.get("AQ_EXECUTION_CELL_ADAPTER_CELL_CLASS", "small"),
    }
    return AdapterConfig(
        signing_key_path=source.get("AQ_GRANT_SIGNING_KEY_PATH", DEFAULT_SIGNING_KEY_PATH),
        runner_socket_path=source.get(
            "AQ_EXECUTION_CELL_RUNNER_SOCKET_PATH", "/run/aq-execution-cell-runner/control.sock"
        ),
        trusted_repo_id=source.get("AQ_EXECUTION_CELL_ADAPTER_TRUSTED_REPO_ID", "primary"),
        epoch_source=None,
        base_revision_resolver=resolve_base_revision_git_head,
        request_timeout_s=float(source.get("AQ_EXECUTION_CELL_ADAPTER_REQUEST_TIMEOUT_S", "10")),
        deadline_s=float(source.get("AQ_EXECUTION_CELL_ADAPTER_DEADLINE_S", "60")),
        resource_limits=resource_limits,
        env=source,
        receipt_sink=None,
    )


# ---------------------------------------------------------------------------
# The entry point (design §2/§3/§4) — mint -> sign -> submit -> receipt.
# NEVER raises to its caller; deny-closed at every step.
# ---------------------------------------------------------------------------


def submit_to_cell(tool_name: str, arguments: Any, config: AdapterConfig) -> AdapterResult:
    """The whole guarded pipeline for one already-C2-admitted tool call.
    See the module docstring's "Scope discipline" note: this is a SHADOW
    call — its result is recorded for observability/validation, it never
    gates or replaces the tool's own already-produced real result. Never
    raises."""
    try:
        if not cell_adapter_enabled(config.env):
            return AdapterResult(DECISION_DENIED, REASON_ADAPTER_DISABLED)

        classification = classify_cell_required_effect(tool_name, arguments)
        if classification is None:
            return AdapterResult(DECISION_DENIED, REASON_NOT_CELL_REQUIRED)

        private_key = load_signing_key(config.signing_key_path)
        if private_key is None:
            result = AdapterResult(DECISION_DENIED, REASON_SIGNING_KEY_UNAVAILABLE)
            _project_receipt(result, config)
            return result

        current_epoch = clg.resolve_current_epoch(config.epoch_source)
        if current_epoch is None:
            result = AdapterResult(DECISION_DENIED, REASON_EPOCH_UNRESOLVABLE)
            _project_receipt(result, config)
            return result

        base_revision = config.base_revision_resolver() if callable(config.base_revision_resolver) else None
        if not isinstance(base_revision, str) or not base_revision:
            result = AdapterResult(DECISION_DENIED, REASON_BASE_REVISION_UNRESOLVABLE)
            _project_receipt(result, config)
            return result

        grant_base = build_grant_base(
            base_revision=base_revision,
            trusted_repo_id=config.trusted_repo_id,
            effect_set=classification["effect_set"],
            exec_class=classification["exec_class"],
            logical_paths=classification["logical_paths"],
            revocation_epoch=current_epoch,
            resource_limits=config.resource_limits,
            deadline_s=config.deadline_s,
        )
        signed_grant = sign_grant_production(grant_base, private_key)
        grant_digest = signed_grant.get("grant_digest")

        payload_bytes = json.dumps(signed_grant).encode("utf-8")
        raw_response = _uds_round_trip(payload_bytes, config.runner_socket_path, config.request_timeout_s)
        if raw_response is None:
            result = AdapterResult(DECISION_DENIED, REASON_RUNNER_UNREACHABLE, grant_digest=grant_digest)
            _project_receipt(result, config)
            return result

        try:
            receipt = json.loads(raw_response.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            result = AdapterResult(DECISION_DENIED, REASON_RUNNER_RESPONSE_MALFORMED, grant_digest=grant_digest)
            _project_receipt(result, config)
            return result

        if not isinstance(receipt, dict) or receipt.get("decision") not in _RUNNER_DECISIONS:
            result = AdapterResult(DECISION_DENIED, REASON_RUNNER_RESPONSE_MALFORMED, grant_digest=grant_digest)
            _project_receipt(result, config)
            return result

        result = AdapterResult(
            decision=str(receipt.get("decision")),
            reason=str(receipt.get("reason") or ""),
            receipt_id=receipt.get("receipt_id"),
            grant_digest=receipt.get("grant_digest") or grant_digest,
            runner_decision=receipt,
        )
        _project_receipt(result, config)
        return result
    except Exception as exc:  # noqa: BLE001 — total fail-closed, NEVER raise to the caller
        result = AdapterResult(DECISION_DENIED, f"{REASON_ADAPTER_INTERNAL_ERROR}:{type(exc).__name__}")
        try:
            _project_receipt(result, config)
        except Exception:
            pass
        return result


def submit_to_cell_default(tool_name: str, arguments: Any) -> AdapterResult:
    """Convenience wrapper: build an `AdapterConfig` from the process
    environment and call `submit_to_cell`. This is the sole surface
    `switchboard.py`'s guarded shadow call site invokes, keeping that
    edit to a single lazy-import + single-call attach point."""
    config = build_adapter_config_from_env()
    return submit_to_cell(tool_name, arguments, config)
