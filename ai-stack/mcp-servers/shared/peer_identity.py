"""
Hardened UDS peer identity resolution (AUTH-S3).

Resolves caller identity from AF_UNIX sockets using SO_PEERCRED, raw SO_PEERPIDFD (77),
and cgroup verification against procfs.
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import signal
import socket
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Raw Linux constant for SO_PEERPIDFD (constant 77 on Linux SOL_SOCKET)
_SO_PEERPIDFD = getattr(socket, "SO_PEERPIDFD", 77)


@dataclass(frozen=True)
class PeerIdentity:
    pid: int
    uid: int
    gid: int
    cgroup: str
    client_class: str
    verified: bool
    reason: Optional[str] = None


def self_test_peer_pidfd() -> bool:
    """Startup self-test verifying raw SO_PEERPIDFD works on this kernel."""
    try:
        s1, s2 = socket.socketpair(socket.AF_UNIX)
        try:
            raw = s1.getsockopt(socket.SOL_SOCKET, _SO_PEERPIDFD)
            return raw > 0
        finally:
            s1.close()
            s2.close()
    except Exception as e:
        logger.warning("SO_PEERPIDFD self-test failed: %s", e)
        return False


def read_cgroup_for_pid(pid: int) -> str:
    """Read the unified cgroup v2 path (0::/...) for a pid from procfs."""
    cgroup_path = Path(f"/proc/{pid}/cgroup")
    if not cgroup_path.exists():
        return ""
    try:
        for line in cgroup_path.read_text().splitlines():
            # cgroup v2 single hierarchy entry: 0::<path>
            parts = line.strip().split("::", 1)
            if len(parts) == 2 and parts[0] == "0":
                return parts[1]
            # fallback for cgroup v1 or older lines
            if line.startswith("0:"):
                subparts = line.split(":")
                if len(subparts) >= 3:
                    return subparts[2]
    except (OSError, PermissionError):
        pass
    return ""


def classify_cgroup(
    cgroup_path: str,
    uid: int,
    owner_uid: int,
    units_policy: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str]]:
    """
    Classify a peer according to Section 2.2 rules:
    1. Exact match in units_policy
    2. /user.slice/ -> owner-agent if uid == owner_uid else unknown
    3. Other /system.slice/ not listed -> owner-agent with unlisted_unit if uid == owner_uid else unknown
    4. uid != owner_uid on agent.sock is unknown unless explicitly mapped
    """
    if units_policy is None:
        units_policy = {}

    # Rule 1: Exact match in units table
    if cgroup_path in units_policy:
        unit_info = units_policy[cgroup_path]
        return unit_info.get("class", "unknown"), None

    # Rule 2: Path beginning /user.slice/
    if cgroup_path.startswith("/user.slice/"):
        if uid == owner_uid:
            return "owner-agent", None
        return "unknown", "user_slice_untrusted_uid"

    # Rule 3: Other path under /system.slice/
    if cgroup_path.startswith("/system.slice/"):
        if uid == owner_uid:
            return "owner-agent", "unlisted_unit"
        return "unknown", "unlisted_system_unit_untrusted_uid"

    # Rule 4: Fallback
    if uid == owner_uid:
        return "owner-agent", "unlisted_cgroup_owner"
    return "unknown", "uid_mismatch"


def resolve_peer_identity(
    sock: socket.socket,
    owner_uid: Optional[int] = None,
    units_policy: Optional[Dict[str, Any]] = None,
) -> PeerIdentity:
    """
    Resolve peer identity from an accepted AF_UNIX socket.
    Fails closed to class 'unknown' if any validation fails.
    """
    if owner_uid is None:
        owner_uid = os.getuid()

    # Step 1: SO_PEERCRED -> (pid, uid, gid)
    try:
        import struct
        creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", creds)
    except Exception as e:
        logger.error("SO_PEERCRED failed: %s", e)
        return PeerIdentity(pid=0, uid=-1, gid=-1, cgroup="", client_class="unknown", verified=False, reason="peercred_failed")

    # Step 2: raw SO_PEERPIDFD (77) -> pidfd
    pidfd = -1
    try:
        pidfd = sock.getsockopt(socket.SOL_SOCKET, _SO_PEERPIDFD)
    except Exception as e:
        logger.warning("SO_PEERPIDFD failed: %s", e)
        return PeerIdentity(pid=pid, uid=uid, gid=gid, cgroup="", client_class="unknown", verified=False, reason="peerpidfd_unsupported")

    try:
        # Step 3: Verify pidfd matches pid via /proc/self/fdinfo/<pidfd>
        # In container or user namespace, Pid is host PID, NSpid lists namespace PIDs (e.g. NSpid:\t4126474\t36)
        fdinfo_path = Path(f"/proc/self/fdinfo/{pidfd}")
        matching_pids: List[int] = []
        if fdinfo_path.exists():
            for line in fdinfo_path.read_text().splitlines():
                if line.startswith("Pid:"):
                    matching_pids.append(int(line.split(":", 1)[1].strip()))
                elif line.startswith("NSpid:"):
                    for p in line.split(":", 1)[1].strip().split():
                        try:
                            matching_pids.append(int(p))
                        except ValueError:
                            pass
        if matching_pids and pid not in matching_pids:
            return PeerIdentity(pid=pid, uid=uid, gid=gid, cgroup="", client_class="unknown", verified=False, reason="pidfd_mismatch")

        # Read cgroup before liveness check
        cgroup = read_cgroup_for_pid(pid)
        if not cgroup:
            # Process may already have terminated or procfs unreadable
            return PeerIdentity(pid=pid, uid=uid, gid=gid, cgroup="", client_class="unknown", verified=False, reason="peer_gone")

        # Liveness check via pidfd_send_signal(pidfd, 0)
        try:
            signal.pidfd_send_signal(pidfd, 0)
        except OSError:
            # Process terminated during inspection
            return PeerIdentity(pid=pid, uid=uid, gid=gid, cgroup=cgroup, client_class="unknown", verified=False, reason="peer_gone")

        # Classify
        client_class, reason = classify_cgroup(cgroup, uid, owner_uid, units_policy)
        return PeerIdentity(
            pid=pid,
            uid=uid,
            gid=gid,
            cgroup=cgroup,
            client_class=client_class,
            verified=True,
            reason=reason,
        )
    finally:
        if pidfd >= 0:
            try:
                os.close(pidfd)
            except OSError:
                pass
