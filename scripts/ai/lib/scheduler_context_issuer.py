"""C2 scheduler-lease-context issuer — Foundation C, C2-SCI subslice B1 (self-contained, INERT).

Sole issuer of the signed `aq.scheduler-lease-context/1` handoff that C6's scheduler
revocation gate consumes downstream (later, not-yet-wired subslices B2/B3). This module
is a pure library: it opens no socket, reads no `/run/secrets`, and is imported by
nothing today — B2 adds the confined service + Nix unit, B3 wires
`capability_lease_gate.py` (outbound client) and `dispatch.py` (authenticated ingress).
See `.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`
(rev4, binding-review PASS) §2-§4 and the FREEZE doc's B1 scope.

Trust model (rev2/rev3, unchanged in rev4 — the central fact this file exists to
enforce): authority is the PRESENTED, INDEPENDENTLY-VERIFIED Ed25519-signed C2
capability lease, never the caller, never `SO_PEERCRED` (defense-in-depth only, see
`scheduler_context_transport.py`), and never any caller-supplied `correlation` field.
`mint_scheduler_context()` below:

  1. VERIFY the presented lease via `capability_lease.verify_authoritative` — the sole
     ALA entrypoint (Ed25519, scheme-pinned, no HMAC/dev-key fallback). Not authentically
     signed by an active key => deny, mint nothing.
  2. OBLIG-1 (design §3 mandate 2): independently reject an authentically-signed lease
     that is expired or epoch-stale. `verify_authoritative` proves provenance, not
     current validity — both checks are mandatory on top of it.
  3. RE-DERIVE the admission tuple (`lease_id`, `grant_digest`, `trust_tier`,
     `policy_revision`, `action_class`) from the lease's OWN signed fields only. Never
     from caller input. `correlation = {task_id, principal, dispatch_mode}` is
     correlation-only dispatch metadata (design §4/Q-R3-1) — carried into the context
     verbatim but never a source of authority; only those three keys are ever read from
     it, so stuffing extra keys (e.g. a spoofed `trust_tier`) into `correlation` has no
     effect on the minted context.
  4. SINGLE-USE ledger (design §3 mandate 3): keyed on `{lease_id, grant_digest}` — one
     scheduler-context per lease, not per task. A second mint attempt for the same key is
     a replay and denies, even under a different `task_id`.
  5. Build + Ed25519-sign the closed `aq.scheduler-lease-context/1` document (field list
     per `C6-P0-TRUST-ANCHORS-DESIGN-20260801.md` §"Domain-separated issuer", plus
     `sig_scheme`/`trust_tier` per this slice's build instructions), with
     `expires_at = min(lease.expires_at, now + context_ttl_cap_seconds)` (design mandate
     4 — a context can never outlive its lease) and `revocation_epoch = current_epoch`
     (the authority-resolved epoch already checked in step 2, NOT the lease's own
     `revocation_epoch` — that field only gates step 2; the context's own revocation
     tracking is deliberately pinned to the authority epoch so later epoch bumps apply
     to it independent of which epoch the lease happened to be minted under).

Fail-CLOSED everywhere: an unverifiable/expired/stale/malformed lease, a replay, a
ledger fault, or an unavailable/invalid signer key all deny and mint NOTHING. There is
no environment fallback and no unsigned path.

`current_epoch` (mirrors `execution_grant.py`'s convention): this is a PURE core
function and does not resolve the authoritative epoch itself. The caller (the B2
service wrapper, not built in this subslice) is responsible for resolving it from the
same authoritative source `lease_signing_authority._resolve_epoch()` uses — never from
an untrusted request field.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import capability_lease as cl  # noqa: E402  (sibling in scripts/ai/lib; self-contained, no local deps)

# --------------------------------------------------------------------------
# Constants — closed context schema (C6-P0-TRUST-ANCHORS-DESIGN-20260801.md
# §"Domain-separated issuer": the signed document is closed; `audience` is
# EXACTLY `aq-f2.5-slot-queue`, never caller-supplied).
# --------------------------------------------------------------------------

CONTEXT_SCHEMA = "aq.scheduler-lease-context/1"
CONTEXT_SCHEMA_VERSION = 1
AUDIENCE = "aq-f2.5-slot-queue"

REQUIRED_CORRELATION_FIELDS = ("task_id", "principal", "dispatch_mode")

# --------------------------------------------------------------------------
# Typed, fail-closed deny vocabulary — every reason below is safe to log
# (never security-bearing detail beyond the deny category, mirroring
# `capability_lease.AuthoritativeVerdict`/`execution_grant.Denial`).
# --------------------------------------------------------------------------

MINT_OK = "ok"

DENY_LEASE_UNVERIFIED = "lease-unverified"
DENY_LEASE_EXPIRED = "lease-expired"
DENY_LEASE_EPOCH_MISMATCH = "lease-epoch-mismatch"
DENY_LEASE_FIELDS_MALFORMED = "lease-fields-malformed"
DENY_CORRELATION_MALFORMED = "correlation-malformed"
DENY_REPLAY = "replay-lease-already-consumed"
DENY_LEDGER_UNAVAILABLE = "ledger-unavailable"
DENY_SIGNER_UNAVAILABLE = "signer-unavailable"
DENY_KEY_ID_MISSING = "issuer-key-id-missing"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --------------------------------------------------------------------------
# Single-use ledger — B1 seam (design §3 mandate 3)
# --------------------------------------------------------------------------


class SingleUseLedger(Protocol):
    """Duck-typed contract every ledger implementation (in-memory here, a
    durable file-backed store closing the B2.5 seam) must satisfy:
    `check_and_record` is an ATOMIC check-and-record — it returns True iff
    `key` had never been recorded before (and records it in the same
    call), else False. On a well-formed `(lease_id, grant_digest)` string
    tuple the ONLY thing that raises is a genuine storage fault (disk
    full, permission denied, ledger dir gone) — that is deliberately
    ALLOWED to propagate: the caller (`mint_scheduler_context`) treats any
    raised exception as ledger-unavailable and denies (fail-closed, never
    fail-open). `DurableSingleUseLedger` below documents exactly which
    conditions raise vs. return False."""

    def check_and_record(self, key: tuple[str, str]) -> bool: ...


class InMemorySingleUseLedger:
    """B1 reference ledger: a per-process `set`. NOT durable across process
    restarts or multiple issuer workers — closed for the confined service
    by `DurableSingleUseLedger` below (B2.5); this in-memory form remains
    the default for tests / any caller that does not pass a ledger dir.
    Never raises."""

    def __init__(self) -> None:
        self._used: set[tuple[str, str]] = set()

    def check_and_record(self, key: tuple[str, str]) -> bool:
        if key in self._used:
            return False
        self._used.add(key)
        return True


class DurableSingleUseLedger:
    """B2.5 durable ledger — Foundation C, C2-SCI subslice B2.5. Closes the
    fail-open-across-restarts gap `InMemorySingleUseLedger` documents: a
    service restart must NOT forget which `{lease_id, grant_digest}` pairs
    were already consumed, or a previously-used lease could mint a SECOND
    context.

    On-disk shape: one empty(-ish) marker file per consumed key, named
    `sha256("{lease_id}\\x00{grant_digest}").hexdigest()` under
    `ledger_dir` — a filesystem-safe digest of the tuple (lease_id/
    grant_digest are opaque strings, not path-safe by construction).

    ATOMICITY (the whole point of this class): the check-and-record is
    `os.open(path, O_CREAT | O_EXCL, ...)` — a single kernel syscall that
    is the atomic test-and-set primitive itself. `O_EXCL` guarantees the
    kernel fails the call with `EEXIST` if the path already exists,
    checked and created in one indivisible operation; there is no
    "check, then separately create" window a second racing caller could
    land in. This holds across THREADS in one process, across MULTIPLE
    PROCESSES on the same host, and (unlike an in-process lock) survives
    a restart, because the state the race is decided against is the
    filesystem itself, not process memory. Exactly one of two simultaneous
    `check_and_record` calls for the identical key can ever observe
    "I created it" (-> True); the other deterministically observes
    `FileExistsError` (-> False). No external lock/DB dependency needed.

    DURABILITY: the marker file's bytes and its directory entry are both
    `fsync`'d before `check_and_record` returns True, so a consumed key
    survives a crash immediately after the mint that consumed it (mirrors
    `execution_cell_clone._fsync_write_json` / `qa_evidence_store
    ._atomic_write`'s file+directory fsync discipline elsewhere in this
    codebase). A NEW `DurableSingleUseLedger` instance pointed at the SAME
    `ledger_dir` (i.e. after a process restart) sees every previously
    recorded key as already-used — that is the restart simulation this
    class exists to pass.

    FAIL-CLOSED: `EEXIST` (key already used) is the only condition that
    returns `False` from a well-formed call. Any OTHER `OSError` while
    creating/writing/fsyncing the marker (permission denied, disk full,
    `ledger_dir` missing/unwritable) is NOT swallowed — it propagates out
    of `check_and_record`, and `mint_scheduler_context`'s
    `except Exception: DENY_LEDGER_UNAVAILABLE` turns that into a deny.
    A ledger that cannot prove a key was never used must never say "go
    ahead" — raising, not guessing `True`, is the safe direction. NOTE: if
    the marker file itself is created (`O_CREAT|O_EXCL` succeeds) but a
    LATER step (write/fsync) then raises, the key is still durably marked
    used (the create already happened) even though this call denies the
    mint — a strict, deliberate over-denial on a genuine I/O fault, not a
    security gap; see the operator reset path below.

    OBSERVABILITY / INTERVENABILITY (O2 seam): `stats()` returns
    best-effort in-process counters (`recorded`, `replays`) for dashboard
    wiring. Operator reset path (the intervenability control for a
    transient-signer-burn recovery, e.g. a legitimate re-issuance after an
    operator manually revoked+re-signed a lease under the SAME
    `{lease_id, grant_digest}`): delete the one marker file for that key —
    `rm <ledger_dir>/<sha256("{lease_id}\\x00{grant_digest}")>` — which
    clears exactly that lease's single-use slot and nothing else. No code
    change or restart required."""

    def __init__(self, ledger_dir: str) -> None:
        self._dir = ledger_dir
        os.makedirs(self._dir, mode=0o700, exist_ok=True)
        self._recorded = 0
        self._replays = 0

    def _key_path(self, key: tuple[str, str]) -> str:
        lease_id, grant_digest = key
        digest = hashlib.sha256(f"{lease_id}\x00{grant_digest}".encode("utf-8")).hexdigest()
        return os.path.join(self._dir, digest)

    def check_and_record(self, key: tuple[str, str]) -> bool:
        path = self._key_path(key)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            self._replays += 1
            return False
        # Any other OSError here (permission denied, ENOSPC, ledger_dir
        # gone, ...) is a genuine storage fault -> deliberately NOT caught;
        # propagates to the caller as fail-closed (see class docstring).
        try:
            payload = json.dumps(
                {"lease_id": key[0], "grant_digest": key[1], "recorded_at": _iso(datetime.now(timezone.utc))},
                sort_keys=True,
            ).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        dir_fd = os.open(self._dir, os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        self._recorded += 1
        return True

    def stats(self) -> dict[str, int]:
        """Best-effort in-process counters for dashboard/O2 wiring — NOT
        a durable audit trail (that is the marker files themselves); a
        restart resets these to zero even though the ledger's actual
        deny/allow decisions remain fully durable and correct."""
        return {"recorded": self._recorded, "replays": self._replays}


# --------------------------------------------------------------------------
# Result — typed for both success and deny (never bare None on either path;
# a deliberate refinement of the sketch `-> dict|None` signature into a
# fully typed contract, mirroring `AuthoritativeVerdict`/`Denial` elsewhere
# in this codebase so callers branch on `result["ok"]`/`result["reason"]`
# without an isinstance check).
# --------------------------------------------------------------------------


def _deny(reason: str, detail: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "detail": detail, "context": None}


def _derive_action_class(lease_data: Mapping[str, Any]) -> Optional[str]:
    """`action_class` FROM `permissions.actions` (design §4) — never a
    caller-selected value. A lease with exactly one action (the common
    first-party/shadow-issuance shape, e.g. `lease_signing_authority.py`'s
    `actions = [tool]`) yields `action_class == that action`; a multi-action
    lease yields a stable, deterministic composite (sorted, `+`-joined) so
    distinct action sets never collide. Returns None (=> malformed) if
    `permissions.actions` is missing, empty, or not a list of non-empty
    strings."""
    perms = lease_data.get("permissions")
    if not isinstance(perms, dict):
        return None
    actions = perms.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    if not all(isinstance(a, str) and a for a in actions):
        return None
    uniq = sorted(set(actions))
    return uniq[0] if len(uniq) == 1 else "+".join(uniq)


def _extract_admission_fields(lease_data: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """Re-derive `{lease_id, grant_digest, trust_tier, policy_revision,
    action_class}` from the lease's OWN signed fields only. Returns None
    (=> `DENY_LEASE_FIELDS_MALFORMED`) if any field is absent or the wrong
    type — this issuer never invents `grant_digest`/`policy_revision`; a
    lease that does not carry them (as its own signed top-level fields) is
    treated as malformed for scheduler-context purposes, never
    silently substituted."""
    lease_id = lease_data.get("lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        return None

    grant_digest = lease_data.get("grant_digest")
    if not isinstance(grant_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", grant_digest):
        return None

    trust_tier = lease_data.get("trust_tier")
    if not isinstance(trust_tier, int) or isinstance(trust_tier, bool):
        return None

    policy_revision = lease_data.get("policy_revision")
    if not isinstance(policy_revision, int) or isinstance(policy_revision, bool) or policy_revision < 1:
        return None

    action_class = _derive_action_class(lease_data)
    if action_class is None:
        return None

    return {
        "lease_id": lease_id,
        "grant_digest": grant_digest,
        "trust_tier": trust_tier,
        "policy_revision": policy_revision,
        "action_class": action_class,
    }


def _extract_correlation_fields(correlation: Any) -> Optional[dict[str, str]]:
    """Correlation-ONLY (design §4/Q-R3-1): reads EXACTLY
    `{task_id, principal, dispatch_mode}` from `correlation` and nothing
    else — any additional caller-supplied key (e.g. an attempted
    `trust_tier`/`action_class` override) is structurally ignored, never
    read. Returns None (=> `DENY_CORRELATION_MALFORMED`) if `correlation`
    is not a mapping or any of the three required keys is missing / not a
    non-empty string."""
    if not isinstance(correlation, Mapping):
        return None
    out: dict[str, str] = {}
    for field in REQUIRED_CORRELATION_FIELDS:
        value = correlation.get(field)
        if not isinstance(value, str) or not value:
            return None
        out[field] = value
    return out


def mint_scheduler_context(
    presented_lease: Mapping[str, Any],
    keys_json_dict: Any,
    current_epoch: int,
    correlation: Any,
    private_key_bytes: Optional[bytes],
    key_id: str,
    context_ttl_cap_seconds: int,
    ledger: SingleUseLedger,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Verify -> OBLIG-1 -> re-derive -> ledger -> sign. Returns
    `{"ok": True, "reason": MINT_OK, "context": {...signed...}, "detail": ""}`
    on success, or `{"ok": False, "reason": DENY_*, "detail": ..., "context": None}`
    on any deny. NEVER raises; NEVER mints on any deny path."""
    try:
        # 1) Verify the PRESENTED lease is authentically signed by an active
        #    key — the sole trust root. Trust is the signed lease, never the
        #    caller (see module docstring).
        verdict = cl.verify_authoritative(presented_lease, keys_json_dict)
        if not verdict.ok:
            return _deny(DENY_LEASE_UNVERIFIED, verdict.reason)

        try:
            lease_data = dict(presented_lease)
        except (TypeError, ValueError):
            return _deny(DENY_LEASE_FIELDS_MALFORMED, "presented_lease not a mapping")

        # 2) OBLIG-1 — authentically signed != currently valid. Independently
        #    reject expired or any epoch mismatch (past OR future).
        if cl.is_expired(lease_data, now=now):
            return _deny(DENY_LEASE_EXPIRED)
        lease_epoch = lease_data.get("revocation_epoch")
        if isinstance(current_epoch, bool) or not isinstance(current_epoch, int) or current_epoch < 0:
            return _deny(DENY_LEASE_FIELDS_MALFORMED, "current_epoch invalid")
        if isinstance(lease_epoch, bool) or not isinstance(lease_epoch, int) or lease_epoch < 0:
            return _deny(DENY_LEASE_FIELDS_MALFORMED, "lease epoch invalid")
        if lease_epoch != current_epoch:
            return _deny(DENY_LEASE_EPOCH_MISMATCH)

        # 3) Re-derive the admission tuple from the lease's OWN signed
        #    fields only — never from caller input.
        admission = _extract_admission_fields(lease_data)
        if admission is None:
            return _deny(DENY_LEASE_FIELDS_MALFORMED)

        correlation_fields = _extract_correlation_fields(correlation)
        if correlation_fields is None:
            return _deny(DENY_CORRELATION_MALFORMED)

        if not isinstance(key_id, str) or not key_id:
            return _deny(DENY_KEY_ID_MISSING)

        # 4) Single-use ledger — one scheduler-context per lease, keyed on
        #    {lease_id, grant_digest}, NOT per task (design §3 mandate 3).
        ledger_key = (admission["lease_id"], admission["grant_digest"])
        try:
            first_use = ledger.check_and_record(ledger_key)
        except Exception:  # noqa: BLE001 — a faulting ledger fails CLOSED, never open
            return _deny(DENY_LEDGER_UNAVAILABLE)
        if not first_use:
            return _deny(DENY_REPLAY)

        # 5) Signer availability (fail-closed; no env fallback, no
        #    unsigned path).
        if not private_key_bytes or not isinstance(private_key_bytes, (bytes, bytearray)):
            return _deny(DENY_SIGNER_UNAVAILABLE)

        moment = now or datetime.now(timezone.utc)
        issued_at = _iso(moment)
        lease_expires_at = _parse_iso(lease_data["expires_at"])
        cap_expires_at = moment + timedelta(seconds=max(0, int(context_ttl_cap_seconds)))
        expires_at_dt = min(lease_expires_at, cap_expires_at)

        context: dict[str, Any] = {
            "schema": CONTEXT_SCHEMA,
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "context_id": f"sched-ctx::{admission['lease_id']}::{admission['grant_digest']}",
            "lease_id": admission["lease_id"],
            "grant_digest": admission["grant_digest"],
            "task_id": correlation_fields["task_id"],
            "audience": AUDIENCE,
            "principal": correlation_fields["principal"],
            "dispatch_mode": correlation_fields["dispatch_mode"],
            "action_class": admission["action_class"],
            "trust_tier": admission["trust_tier"],
            "policy_revision": admission["policy_revision"],
            "issued_at": issued_at,
            "expires_at": _iso(expires_at_dt),
            "revocation_epoch": int(current_epoch),
            "issuer_key_id": key_id,
            "sig_scheme": cl.SIG_SCHEME_ED25519,
            "signature": "",
        }
        try:
            context["signature"] = cl.sign_ed25519(context, bytes(private_key_bytes))
        except Exception:  # noqa: BLE001 — malformed/invalid key material fails CLOSED
            return _deny(DENY_SIGNER_UNAVAILABLE)

        return {"ok": True, "reason": MINT_OK, "detail": "", "context": context}
    except Exception as exc:  # noqa: BLE001 — total function, never raises into the caller
        return _deny(DENY_LEASE_FIELDS_MALFORMED, f"unhandled:{exc.__class__.__name__}")


def verify_scheduler_context(context: Mapping[str, Any], signer_keys_json: Any) -> "cl.AuthoritativeVerdict":
    """Verify a minted context's own Ed25519 signature against the
    context-signer allowlist (`config/aqos/c6-scheduler-signer-keys.json`
    shape — a SEPARATE key family from the lease-signer allowlist per
    design §2). Reuses `capability_lease.verify_authoritative`'s
    scheme-pinned check: the context's `sig_scheme` field must be
    `"ed25519"` and `issuer_key_id` must resolve to an `active` key in
    `signer_keys_json`. Convenience wrapper for tests/B2+; not itself a
    trust boundary (verify_authoritative is)."""
    return cl.verify_authoritative(context, signer_keys_json)
