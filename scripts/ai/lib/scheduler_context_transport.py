"""Local authenticated UDS transport for the C2 scheduler-context issuer — Foundation C,
C2-SCI subslice B1 (self-contained, INERT; mirrors `lease_signing_authority.serve()`).

Carries the switchboard-caller <-> issuer request/response for
`scheduler_context_issuer.mint_scheduler_context()`. This module is transport-only: it
authenticates nothing on its own authority. Per the C2-SCI design (rev2/rev3/rev4), the
switchboard client runs as `cfg.primaryUser` — indistinguishable at the peer level from
any other owner-uid process — so `SO_PEERCRED` here is READ AND LOGGED as
defense-in-depth ONLY, never as authority. The actual gate on minting is the
independently-verified Ed25519-signed lease inside `mint_scheduler_context` itself; a
peer that passes every check below still mints nothing without a lease it cannot forge.

Not exercised live in this subslice — nothing imports or enables this today (B2 wires
the confined `aq-c2-scheduler-context-issuer` service + Nix unit around `serve()`).
`__main__` requires the same env-driven socket path convention as
`lease_signing_authority.py` so the two services compose the same way once B2 lands.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import sys
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------
# Bounds — mirrors lease_signing_authority.serve()'s frame/timeout discipline.
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

_UCRED_FMT = "3i"  # struct ucred { pid_t pid; uid_t uid; gid_t gid; }


def _deny(reason: str, detail: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "detail": detail}


# --------------------------------------------------------------------------
# SO_PEERCRED — defense-in-depth only (see module docstring). Mirrors
# `execution_cell_runner.get_peer_credentials` exactly (same struct format).
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
# issuer's ledger/private key/allowlist). Ambiguity/oversize/timeout always
# yield a typed deny frame back to the peer; one bad connection never
# crashes the loop (matches `lease_signing_authority.serve()`).
# --------------------------------------------------------------------------


def serve(
    socket_path: str,
    handler: Callable[[dict[str, Any], Optional[tuple[int, int, int]]], dict[str, Any]],
    client_group_env: str = "AQ_SCHEDULER_CONTEXT_CLIENT_GROUP",
) -> None:  # pragma: no cover — exercised live only once B2 enables the unit
    """Minimal confined UDS server. `handler(request_dict, peer_creds) ->
    response_dict` is supplied by the caller (B2's service wrapper), which
    owns the private key / ledger / allowlist this module never touches.
    `peer_creds` is passed through for LOGGING only — `handler` must not
    treat it as authority (see module docstring)."""
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
                f"[c2-sci-transport] WARN: could not chgrp socket to client group "
                f"{_client_group!r} ({exc}); socket stays issuer-only (clients fail-closed)",
                file=sys.stderr,
                flush=True,
            )
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        try:
            conn.settimeout(RECV_TIMEOUT_S)
            peer_creds = get_peer_credentials(conn)  # log-only, see module docstring
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
# Client — fail-closed helper for the (future, B3) switchboard-side caller.
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


if __name__ == "__main__":  # pragma: no cover — no default handler; B2 supplies one
    print(
        "scheduler_context_transport: library module, no standalone entrypoint in B1 "
        "(B2 wires a handler bound to the issuer's ledger/key/allowlist)",
        file=sys.stderr,
    )
    sys.exit(1)
