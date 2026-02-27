"""
Phase 12.3.2 — Tool audit log sidecar.

Listens on a Unix domain socket (supports systemd socket activation).
MCP service processes write JSON audit entries to the socket; this daemon
appends them to the audit log file. Because the sidecar owns the log file
and MCP services have no direct filesystem access to it, a compromised
MCP process cannot tamper with the audit trail.

Activation:
    # systemd socket activation (production)
    systemd socket unit sets LISTEN_PID / LISTEN_FDS before exec.
    # Standalone dev mode (fallback)
    AUDIT_SOCKET_PATH=/run/ai-audit-sidecar.sock python3 audit_sidecar.py

Protocol: each client sends one UTF-8 JSON object per line, then closes.
The sidecar validates JSON parse-ability before writing to the log.
"""

import asyncio
import json
import logging
import os
import socket
from pathlib import Path

LOG_PATH = Path(os.getenv("TOOL_AUDIT_LOG_PATH", "/var/log/ai-audit-sidecar/tool-audit.jsonl"))
SOCKET_PATH = os.getenv("AUDIT_SOCKET_PATH", "/run/ai-audit-sidecar.sock")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("audit-sidecar")

# Asyncio write lock — all clients share the single event loop; protect the fd.
_write_lock: asyncio.Lock


async def _handle_client(reader: asyncio.StreamReader, _writer: asyncio.StreamWriter) -> None:
    """Receive newline-delimited JSON lines and append them to the audit log."""
    try:
        async for raw in reader:
            line = raw.strip()
            if not line:
                continue
            try:
                json.loads(line)  # validate before persisting
            except json.JSONDecodeError:
                logger.warning("invalid_json_skipped length=%d", len(line))
                continue
            async with _write_lock:
                await asyncio.to_thread(_append_line, line.decode("utf-8", errors="replace"))
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        _writer.close()


def _append_line(line: str) -> None:
    """Synchronous append — called in a thread pool to avoid blocking the loop."""
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _get_systemd_socket() -> "socket.socket | None":
    """Return the pre-opened FD from systemd socket activation, or None."""
    try:
        listen_pid = int(os.getenv("LISTEN_PID", "0"))
        listen_fds = int(os.getenv("LISTEN_FDS", "0"))
    except ValueError:
        return None
    if listen_pid != os.getpid() or listen_fds < 1:
        return None
    fd = 3  # SD_LISTEN_FDS_START
    sock = socket.socket(fileno=fd)
    sock.setblocking(False)
    return sock


async def _main() -> None:
    global _write_lock
    _write_lock = asyncio.Lock()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    sd_sock = _get_systemd_socket()
    if sd_sock is not None:
        server = await asyncio.start_unix_server(_handle_client, sock=sd_sock)
        logger.info("listening via systemd socket activation fd=3")
    else:
        # Dev/standalone mode: create socket ourselves.
        sock_path = Path(SOCKET_PATH)
        sock_path.parent.mkdir(parents=True, exist_ok=True)
        sock_path.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(_handle_client, path=SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        logger.info("listening on %s (dev mode)", SOCKET_PATH)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
