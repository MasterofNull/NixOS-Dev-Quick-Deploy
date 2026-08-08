#!/usr/bin/env python3
"""Confined asymmetric first-party lease signing authority (Foundation C — ALA rev4).

The SOLE minter of Ed25519-signed first-party capability leases. It holds the Ed25519
PRIVATE key (via `/run/secrets`, readable only by the dedicated `aq-lease-signing-authority`
principal — the owner-uid switchboard cannot read it). Verifiers hold only the public key
(`config/aqos/lease-signer-keys.json`) → verify != forge.

Trust model (rev4 mandate 2', reviewer-confirmed oracle-closed): the caller (the owner-uid
switchboard gate) is PURE TRANSPORT. It never supplies a signable payload. This authority reads
the tool manifest + resolves the epoch ITSELF and MINTS every field — matching
`capability_lease_gate.issue_first_party_leases()` semantics exactly, plus authority-clock
temporals — so a compromised owner-uid gate cannot influence any field of a signed lease. It sets
`sig_scheme="ed25519"` + `issuer_key_id` (both signed) and signs with
`capability_lease.sign_ed25519`. First-party leases have no per-caller selector: the set is minted
from the manifest, so the caller supplies nothing at all.

Default-OFF: nothing calls this unless `CAPABILITY_ASYMMETRIC_LEASE=1` AND the
`aq-lease-signing-authority` service is enabled (both further, separate owner acts).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import capability_lease as cl  # noqa: E402  (sibling in scripts/ai/lib; self-contained, no local deps)
import revocation_epoch as re_lib  # noqa: E402

# Must match capability_lease_gate.py's first-party constants EXACTLY (parity is
# asserted in test-lease-signing-authority.py against the gate's own output).
FIRST_PARTY_SOURCE = "first-party-manifest"
FIRST_PARTY_LEASE_TTL = timedelta(hours=24)

# The authority reads the manifest + epoch DIRECTLY from the same source files the gate uses —
# it does not import the heavy capability_lease_gate module, keeping the confined-service bundle
# minimal (lease_signing_authority.py + capability_lease.py only; WR-3 lesson).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))  # scripts/ai/lib -> repo
DEFAULT_MANIFEST_PATH = os.environ.get("AQ_LEASE_SIGNING_MANIFEST_PATH", "").strip() or os.path.join(
    _REPO_ROOT, "config", "first-party-tools.json"
)

SIGNER_KEY_PATH_ENV = "AQ_LEASE_SIGNING_KEY_PATH"
SIGNER_KEY_ID_ENV = "AQ_LEASE_SIGNING_KEY_ID"

DENY_UNKNOWN_TOOL = "unknown-tool"
DENY_SIGNER_UNAVAILABLE = "signer-unavailable"
DENY_MANIFEST_UNUSABLE = "manifest-unusable"
DENY_EPOCH_AUTHORITY_UNAVAILABLE = "epoch-authority-unavailable"
POLICY_DIGEST_DOMAIN = b"aq.first-party-policy-binding/1"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(key)): _nfc(item) for key, item in value.items()}
    return value


def _canonical_policy_bytes(projection: Mapping[str, Any]) -> bytes:
    """Exact policy-binding JSON: NFC, sorted, compact UTF-8 and no NaN."""
    return json.dumps(
        _nfc(dict(projection)), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _policy_projection(tool: str, lease: Mapping[str, Any], policy_revision: int) -> dict[str, Any]:
    return {
        "tool": tool,
        "policy_revision": policy_revision,
        "source": lease["source"],
        "owner": lease["owner"],
        "issued_to": lease["issued_to"],
        "cost_class": lease["cost_class"],
        "parent_lease_id": lease["parent_lease_id"],
        "permissions": lease["permissions"],
        "input_schema": lease["input_schema"],
        "output_schema": lease["output_schema"],
        "trust_tier": lease["trust_tier"],
        "zero_trust_behavior": lease["zero_trust_behavior"],
    }


def policy_grant_digest(tool: str, lease: Mapping[str, Any], policy_revision: int) -> str:
    """Domain-separated SHA-256 policy identity, excluding time/key/lease identity."""
    if isinstance(policy_revision, bool) or not isinstance(policy_revision, int) or policy_revision < 1:
        raise ValueError("policy_revision_invalid")
    return hashlib.sha256(POLICY_DIGEST_DOMAIN + b"\x00" + _canonical_policy_bytes(
        _policy_projection(tool, lease, policy_revision)
    )).hexdigest()


def _build_first_party_lease_unsigned(
    tool: str, entry: dict, issued_at: str, expires_at: str, current_epoch: int, key_id: str, policy_revision: int
) -> dict:
    """The exact first-party lease dict from
    `capability_lease_gate.issue_first_party_leases()` PLUS the two required signed
    ed25519 fields (`sig_scheme`, `issuer_key_id`). `signature` is empty; the caller signs."""
    actions = list(entry.get("actions") or [tool])
    lease = {
        "lease_id": f"first-party::{tool}::{issued_at}",
        "version": 1,
        "source": FIRST_PARTY_SOURCE,
        "owner": FIRST_PARTY_SOURCE,
        "issued_to": "switchboard-local-tool-executor",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "permissions": {
            "actions": actions,
            "resources": list(entry.get("resources") or []),
            "constraints": {
                **{k: v for k, v in (entry.get("constraints") or {}).items()},
                "risk": {
                    "write_capable": bool(entry.get("write_capable", False)),
                    "network_capable": bool(entry.get("network_capable", False)),
                    "exec_capable": bool(entry.get("exec_capable", False)),
                    "trust_tier": int(entry.get("trust_tier", 0)),
                },
            },
        },
        "input_schema": {},
        "output_schema": {},
        "trust_tier": int(entry.get("trust_tier", 0)),
        "zero_trust_behavior": str(entry.get("zero_trust_behavior", "none")),
        "cost_class": "first-party",
        "parent_lease_id": None,
        "revocation_epoch": int(current_epoch),
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "issuer_key_id": key_id,
        "signature": "",
    }
    lease["policy_revision"] = policy_revision
    lease["grant_digest"] = policy_grant_digest(tool, lease, policy_revision)
    return lease


def mint_first_party_leases(
    manifest: dict,
    epoch: int,
    private_key_bytes: bytes,
    key_id: str,
    policy_revision: int,
    now: Optional[datetime] = None,
) -> dict:
    """Mint the full first-party lease set from the MANIFEST (never a caller payload),
    Ed25519-signed. Authority-clock temporals. Returns `{tool: signed_lease}`. Pure core —
    the service wrapper supplies `private_key_bytes`/`key_id`/`epoch`; the gate supplies nothing."""
    if not manifest or isinstance(policy_revision, bool) or not isinstance(policy_revision, int) or policy_revision < 1:
        return {}
    moment = now or datetime.now(timezone.utc)
    issued_at = _iso(moment)
    expires_at = _iso(moment + FIRST_PARTY_LEASE_TTL)
    leases: dict[str, dict] = {}
    for tool, entry in manifest.items():
        lease = _build_first_party_lease_unsigned(tool, entry, issued_at, expires_at, epoch, key_id, policy_revision)
        lease["signature"] = cl.sign_ed25519(lease, private_key_bytes)
        leases[tool] = lease
    return leases


def _read_private_key() -> Optional[bytes]:
    """Read the Ed25519 private key (raw 32 bytes, hex or raw) from the confined
    `/run/secrets` path. Returns None (→ signer-unavailable, fail-closed) if unreadable/empty."""
    path = os.environ.get(SIGNER_KEY_PATH_ENV, "").strip()
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            data = fh.read().strip()
        if not data:
            return None
        # accept 64-hex or raw 32 bytes
        try:
            return bytes.fromhex(data.decode("ascii").strip())
        except (ValueError, UnicodeDecodeError):
            return data if len(data) == 32 else None
    except OSError:
        return None


# --- service wrapper (default-OFF; the aq-lease-signing-authority.nix unit runs this) ---
# The UDS server is intentionally minimal: it authenticates the peer (SO_PEERCRED, done in
# the nix socket unit's group + here), reads NOTHING authority-bearing from the request (the
# authority reads the manifest + epoch itself), mints, and returns the signed lease set. It is
# not exercised while default-OFF; the tested contract is mint_first_party_leases() above.
def _resolve_epoch() -> int:
    """Resolve only through the confined epoch authority; callers must deny on failure."""
    return re_lib.resolve_current_epoch()


def _load_manifest() -> tuple[Optional[dict], Optional[int]]:
    """Read the first-party tool manifest directly, mirroring the gate's `_load_manifest`
    transform: the file is `{..., "tools": [ {"tool": ..., ...}, ... ]}` and this returns
    `{tool: entry}`. Fail-CLOSED to {} on missing/bad JSON, a non-list `tools`, a non-dict or
    tool-less entry, or a duplicate tool (same as the gate)."""
    try:
        with open(DEFAULT_MANIFEST_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None, None
    revision = raw.get("version") if isinstance(raw, dict) else None
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        return None, None
    entries = raw.get("tools") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return None, None
    out: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return None, None
        tool = entry.get("tool")
        if not isinstance(tool, str) or not tool or tool in out:
            return None, None
        out[tool] = entry
    return out, revision


def serve_once_stub() -> str:
    """Health self-check: 'ready' iff the signing key is readable, else the typed
    signer-unavailable deny. Used by `__main__ --check` and slice-3 health-spider."""
    return "ready" if _read_private_key() is not None else DENY_SIGNER_UNAVAILABLE


def handle_request(request_bytes: bytes) -> dict:
    """Pure request handler (unit-testable): the request carries NO authority-bearing data.
    The authority reads the manifest + resolves the epoch + reads its own key, mints, and returns
    `{"leases": {...}}` or a typed `{"error": ...}`. Fail-closed on a missing key."""
    key = _read_private_key()
    if key is None:
        return {"error": DENY_SIGNER_UNAVAILABLE}
    key_id = os.environ.get(SIGNER_KEY_ID_ENV, "lease-signer").strip() or "lease-signer"
    manifest, revision = _load_manifest()
    if manifest is None or revision is None:
        return {"error": DENY_MANIFEST_UNUSABLE}
    try:
        epoch = _resolve_epoch()
    except re_lib.EpochAuthorityError:
        return {"error": DENY_EPOCH_AUTHORITY_UNAVAILABLE}
    leases = mint_first_party_leases(manifest, epoch, key, key_id, revision)
    return {"leases": leases}


def serve(socket_path: str) -> None:  # pragma: no cover — exercised live only when the unit is enabled
    """Minimal confined UDS server. The nix unit runs this as the dedicated
    `aq-lease-signing-authority` principal with a group-restricted 0660 socket (peer access is the
    primary control; SO_PEERCRED is logged as defense-in-depth). The authority NEVER trusts caller
    input (handle_request ignores the request body), so even an unexpected peer only obtains the
    manifest-authorized lease set — the property the ALA review confirmed closes the oracle."""
    import json
    import socket
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    os.chmod(socket_path, 0o660)
    # Client access: the switchboard runs as the human primaryUser (NOT this dedicated authority
    # user), so a socket left in the authority's own group is unreachable by it. Hand the socket to
    # a shared client group (both the authority and the switchboard user are members) at 0660 — the
    # SAME model the execution-cell-runner uses. This widens ONLY connect access, never key access
    # (the Ed25519 private key stays 0400 user-only); and per handle_request the authority never
    # trusts caller input, so an unexpected group peer still obtains only the manifest lease set.
    # chgrp requires this process to be a member of the target group (wired in the nix unit); on
    # failure we stay deny-closed (socket keeps the authority-only group -> clients can't connect)
    # and log loudly rather than crash-loop or widen.
    _client_group = os.environ.get("AQ_LEASE_SIGNING_CLIENT_GROUP", "").strip()
    if _client_group:
        import grp
        try:
            os.chown(socket_path, -1, grp.getgrnam(_client_group).gr_gid)
            os.chmod(socket_path, 0o660)
        except (KeyError, PermissionError, OSError) as exc:
            print(
                f"[ala] WARN: could not chgrp socket to client group {_client_group!r} "
                f"({exc}); socket stays authority-only (clients will fail-closed)",
                file=sys.stderr,
                flush=True,
            )
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        try:
            conn.settimeout(5.0)
            buf = b""
            while b"\n" not in buf and len(buf) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
            resp = handle_request(buf)
            conn.sendall((json.dumps(resp, sort_keys=True) + "\n").encode("utf-8"))
        except Exception:  # noqa: BLE001 — never crash the server on one bad connection
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print(serve_once_stub())
    else:
        _sp = os.environ.get("AQ_LEASE_SIGNING_SOCKET_PATH", "").strip()
        if not _sp:
            print(DENY_SIGNER_UNAVAILABLE)
            sys.exit(1)
        serve(_sp)
