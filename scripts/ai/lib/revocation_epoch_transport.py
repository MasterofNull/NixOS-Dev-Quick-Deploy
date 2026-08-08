"""Local confined UDS transport for the C6 revocation-epoch authority — Foundation C,
C6-B2 (self-contained, INERT; mirrors `scheduler_context_transport.py` / `lease_signing_authority.py`).

Carries the owner-CLI (`aq-epoch-bump`, C6-B1) <-> authority request/response for
`revocation_epoch.apply_bump()`. This module is transport-only: it authenticates nothing on its
own authority. Per the design (`C6-DESIGN-AND-AUTHORIZATION.md` §2.1), the control UDS is mode
0660, group-restricted, and additionally validates `SO_PEERCRED` — but transport membership
(socket group membership, the connecting peer's uid/gid) is READ AND LOGGED as defense-in-depth
ONLY, NEVER treated as authority. The actual gate on advancing the epoch is the
independently-verified Ed25519-signed `aq.revocation-epoch-bump/1` document inside
`apply_bump` itself: a peer that passes every transport check below still advances nothing
without a bump an active owner key actually signed.

Unlike the C2-SCI issuer and the ALA, this authority holds NO private signing key anywhere —
owners sign a bump OFFLINE with their own tooling (`revocation_epoch.sign_bump` is explicitly
documented as "FOR OFFLINE OWNER-SIGNING TOOLING AND TEST FIXTURES ONLY"; nothing in this
process ever calls it). This service only VERIFIES a presented signed document against the
tracked, public `config/aqos/c6-owner-public-keys.json` allowlist and, on a valid first-use
bump matching the durable current epoch, performs the ONE sanctioned mutation
(`revocation_epoch.apply_bump`'s atomic +1). `build_env_handler()` below constructs the
request handler entirely from the `AQ_REVOCATION_EPOCH_*` env vars the Nix unit
(`revocation-epoch-authority.nix`) sets; `__main__` binds it to `serve()`. Still default-OFF and
unexercised until that unit is enabled.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import sys
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------
# Bounds — mirrors scheduler_context_transport.py / lease_signing_authority.py's
# frame/timeout discipline.
# --------------------------------------------------------------------------

MAX_REQUEST_BYTES = 65536
MAX_RESPONSE_BYTES = 65536
RECV_TIMEOUT_S = 5.0

DENY_OVERSIZE = "request-oversize"
DENY_TIMEOUT = "request-timeout"
DENY_EMPTY = "request-empty"
DENY_MALFORMED_JSON = "request-malformed-json"
DENY_MALFORMED_RESPONSE = "response-malformed"
DENY_CONNECT_FAILED = "connect-failed"
DENY_MALFORMED_BUMP = "request-malformed-bump"
DENY_OWNER_KEYS_UNAVAILABLE = "owner-keys-unavailable"
DENY_LEDGER_INIT_FAILED = "ledger-init-failed"

_UCRED_FMT = "3i"  # struct ucred { pid_t pid; uid_t uid; gid_t gid; }


def _deny(reason: str, detail: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "detail": detail, "receipt": None}


# --------------------------------------------------------------------------
# SO_PEERCRED — defense-in-depth only (see module docstring). Mirrors
# `scheduler_context_transport.get_peer_credentials` / `execution_cell_runner
# .get_peer_credentials` exactly (same struct format).
# --------------------------------------------------------------------------


def get_peer_credentials(conn: "socket.socket") -> Optional[tuple[int, int, int]]:
    """`(pid, uid, gid)` via `SO_PEERCRED`, or None on any failure. Never
    raises. NOT the authority — logged only; see module docstring."""
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(_UCRED_FMT))
        pid, uid, gid = struct.unpack(_UCRED_FMT, raw)
        return pid, uid, gid
    except (OSError, struct.error):
        return None


# --------------------------------------------------------------------------
# Frame I/O — one immutable JSON object per line, bounded, never blocks
# forever, never crashes the caller on a bad peer.
# --------------------------------------------------------------------------


def read_frame(conn: "socket.socket", max_bytes: int = MAX_REQUEST_BYTES) -> dict[str, Any]:
    """Read one newline-terminated JSON frame from `conn`. Returns the
    decoded dict wrapped as `{"ok": True, "frame": {...}}`, or a typed deny
    dict (`DENY_OVERSIZE`/`DENY_TIMEOUT`/`DENY_EMPTY`/`DENY_MALFORMED_JSON`)
    — never raises past this function."""
    buf = b""
    try:
        while b"\n" not in buf:
            if len(buf) >= max_bytes:
                return _deny(DENY_OVERSIZE)
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        return _deny(DENY_TIMEOUT)
    except OSError as exc:
        return _deny(DENY_CONNECT_FAILED, str(exc))

    if len(buf) > max_bytes:
        return _deny(DENY_OVERSIZE)
    line = buf.split(b"\n", 1)[0].strip()
    if not line:
        return _deny(DENY_EMPTY)
    try:
        decoded = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _deny(DENY_MALFORMED_JSON)
    if not isinstance(decoded, dict):
        return _deny(DENY_MALFORMED_JSON)
    return {"ok": True, "frame": decoded}


# --------------------------------------------------------------------------
# Server — generic loop; the caller supplies the handler (closes over the
# authority's epoch path/ledger/owner-key allowlist — never a private key,
# this authority holds none). Ambiguity/oversize/timeout always yield a
# typed deny frame back to the peer; one bad connection never crashes the
# loop (matches `scheduler_context_transport.serve` / `lease_signing_authority.serve`).
# --------------------------------------------------------------------------


def serve(
    socket_path: str,
    handler: Callable[[dict[str, Any], Optional[tuple[int, int, int]]], dict[str, Any]],
    client_group_env: str = "AQ_REVOCATION_EPOCH_CLIENT_GROUP",
) -> None:  # pragma: no cover — exercised live only once the unit is enabled
    """Minimal confined UDS server. `handler(request_dict, peer_creds) ->
    response_dict` is supplied by the caller (this module's service wrapper
    below), which owns the epoch path / replay ledger / owner-key allowlist
    this generic transport never touches directly. `peer_creds` is passed
    through for LOGGING only — `handler` must not treat it as authority (see
    module docstring)."""
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    os.chmod(socket_path, 0o660)
    _client_group = os.environ.get(client_group_env, "").strip()
    if _client_group:
        import grp
        try:
            os.chown(socket_path, -1, grp.getgrnam(_client_group).gr_gid)
            os.chmod(socket_path, 0o660)
        except (KeyError, PermissionError, OSError) as exc:
            print(
                f"[revocation-epoch-authority-transport] WARN: could not chgrp socket to "
                f"client group {_client_group!r} ({exc}); socket stays authority-only "
                f"(clients fail-closed)",
                file=sys.stderr,
                flush=True,
            )
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        try:
            conn.settimeout(RECV_TIMEOUT_S)
            peer_creds = get_peer_credentials(conn)  # log-only, see module docstring
            if peer_creds is not None:
                print(
                    f"[revocation-epoch-authority-transport] peer pid={peer_creds[0]} "
                    f"uid={peer_creds[1]} gid={peer_creds[2]} (defense-in-depth log only, "
                    f"not authority)",
                    file=sys.stderr,
                    flush=True,
                )
            framed = read_frame(conn)
            if not framed.get("ok"):
                response = framed
            else:
                try:
                    response = handler(framed["frame"], peer_creds)
                except Exception as exc:  # noqa: BLE001 — a faulting handler denies, never crashes
                    response = _deny("handler-error", exc.__class__.__name__)
            payload = (json.dumps(response, sort_keys=True) + "\n").encode("utf-8")
            conn.sendall(payload[:MAX_RESPONSE_BYTES])
        except Exception:  # noqa: BLE001 — never crash the server on one bad connection
            pass
        finally:
            conn.close()


# --------------------------------------------------------------------------
# Client — fail-closed helper for the (C6-B1-shipped) `aq-epoch-bump` CLI.
# --------------------------------------------------------------------------


def send_request(socket_path: str, request: dict[str, Any], timeout: float = RECV_TIMEOUT_S) -> dict[str, Any]:
    """Connect, send one JSON frame, read one JSON frame back. Returns the
    decoded response dict on success, or a typed deny dict
    (`DENY_CONNECT_FAILED`/`DENY_TIMEOUT`/`DENY_MALFORMED_RESPONSE`) — never
    raises into the caller."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_path)
    except OSError as exc:
        return _deny(DENY_CONNECT_FAILED, str(exc))
    try:
        payload = (json.dumps(request, sort_keys=True) + "\n").encode("utf-8")
        sock.sendall(payload)
        framed = read_frame(sock, max_bytes=MAX_RESPONSE_BYTES)
        if not framed.get("ok"):
            return framed
        return framed["frame"]
    except socket.timeout:
        return _deny(DENY_TIMEOUT)
    except OSError as exc:
        return _deny(DENY_CONNECT_FAILED, str(exc))
    finally:
        try:
            sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------
# B2 service wiring — env-driven handler binding revocation_epoch.apply_bump() to
# this transport's serve(). Only imported when run as __main__ (the confined
# aq-revocation-epoch-authority unit); everything above stays import-light for any
# caller that only needs read_frame/send_request/get_peer_credentials (tests, the
# aq-epoch-bump CLI) and never pays for the cryptography import.
# --------------------------------------------------------------------------


def _load_json_file(path: str) -> Any:
    """Best-effort JSON load; None on any failure. The caller treats None as
    owner-keys-allowlist-unavailable (fail-closed), never a bespoke
    fallback. Read fresh PER REQUEST (never cached) so a key revocation in
    `config/aqos/c6-owner-public-keys.json` takes effect without a service
    restart — mirrors `scheduler_context_transport._load_json_file`."""
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def build_env_handler() -> Callable[[dict[str, Any], Optional[tuple[int, int, int]]], dict[str, Any]]:
    """Construct the request handler `serve()` needs, entirely from the
    `AQ_REVOCATION_EPOCH_*` env vars the Nix unit sets. Imports `revocation_epoch`
    lazily (only when run as `__main__`) so this module's non-service uses (tests
    exercising read_frame/send_request only) never pay for the cryptography import.

    The durable replay ledger (`revocation_epoch.DurableReplayLedger`) is
    constructed ONCE, pointed at `AQ_REVOCATION_EPOCH_LEDGER_DIR` (always set by
    the Nix unit, under `StateDirectory`) — durable and atomic
    (`O_CREAT|O_EXCL`) across process restarts by construction (it is the
    filesystem, not process memory; see the class docstring in
    `revocation_epoch.py`). There is no in-memory fallback here: unlike the
    C2-SCI issuer's ledger (which has a deliberate non-durable dev/test mode),
    a revocation-epoch replay ledger MUST be durable in every configuration
    this transport ever serves live, so `AQ_REVOCATION_EPOCH_LEDGER_DIR` is
    required — its absence fails the service at startup rather than silently
    downgrading to an in-process ledger that forgets consumed requests on
    restart (that would be a fail-open replay surface on a fleet kill-switch).

    The request must present exactly `{"bump": {...}}`; the handler never
    trusts any other top-level field (mirrors `mint_scheduler_context`'s own
    re-derivation discipline in the C2-SCI transport)."""
    import revocation_epoch as re_lib  # noqa: E402  (lazy; sibling in scripts/ai/lib)

    owner_keys_path = os.environ.get("AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH", "").strip()
    epoch_path = os.environ.get("AQ_REVOCATION_EPOCH_EPOCH_PATH", "").strip()
    ledger_dir = os.environ.get("AQ_REVOCATION_EPOCH_LEDGER_DIR", "").strip()
    if not ledger_dir:
        raise RuntimeError(
            "AQ_REVOCATION_EPOCH_LEDGER_DIR is required — a revocation-epoch replay "
            "ledger must always be durable (StateDirectory-backed), never in-memory"
        )
    ledger = re_lib.DurableReplayLedger(ledger_dir)

    def handler(request: dict[str, Any], _peer_creds: Optional[tuple[int, int, int]]) -> dict[str, Any]:
        bump_doc = request.get("bump")
        if not isinstance(bump_doc, dict):
            return _deny(DENY_MALFORMED_BUMP)
        owner_keys_json = _load_json_file(owner_keys_path)
        if owner_keys_json is None:
            return _deny(DENY_OWNER_KEYS_UNAVAILABLE)
        return re_lib.apply_bump(bump_doc, epoch_path, ledger, owner_keys_json)

    return handler


if __name__ == "__main__":  # pragma: no cover — exercised live only once the unit is enabled
    _sp = os.environ.get("AQ_REVOCATION_EPOCH_SOCKET_PATH", "").strip()
    if not _sp:
        print(
            "revocation_epoch_transport: AQ_REVOCATION_EPOCH_SOCKET_PATH not set",
            file=sys.stderr,
        )
        sys.exit(1)
    serve(_sp, build_env_handler())
