"""
Unit tests for AUTH-S3 (peer identity, SO_PEERPIDFD, cgroup classification, aq_http client).
"""

import os
from pathlib import Path
import socket
import pytest

from shared.peer_identity import (
    self_test_peer_pidfd,
    read_cgroup_for_pid,
    classify_cgroup,
    resolve_peer_identity,
)
from shared.aq_http import AqHttpClient


def test_so_peerpidfd_self_test():
    """Verify raw SO_PEERPIDFD (constant 77) works on current kernel."""
    assert self_test_peer_pidfd() is True


def test_read_cgroup_for_pid_self():
    """Verify reading own cgroup yields valid non-empty string."""
    cg = read_cgroup_for_pid(os.getpid())
    assert isinstance(cg, str)
    assert len(cg) > 0
    assert cg.startswith("/")


def test_classify_cgroup_rules():
    """Verify Section 2.2 cgroup classification rules."""
    owner_uid = 1000
    units_policy = {
        "/system.slice/ai-switchboard.service": {"class": "service:switchboard"},
        "/system.slice/command-center-dashboard-api.service": {"class": "service:dashboard"},
    }

    # Rule 1: Exact match in units table
    cls, reason = classify_cgroup("/system.slice/ai-switchboard.service", 1000, owner_uid, units_policy)
    assert cls == "service:switchboard"
    assert reason is None

    # Rule 2: User slice owner vs non-owner
    cls, reason = classify_cgroup("/user.slice/user-1000.slice/session-1.scope", 1000, owner_uid, units_policy)
    assert cls == "owner-agent"
    assert reason is None

    cls, reason = classify_cgroup("/user.slice/user-1001.slice/session-2.scope", 1001, owner_uid, units_policy)
    assert cls == "unknown"
    assert reason == "user_slice_untrusted_uid"

    # Rule 3: Unlisted system slice
    cls, reason = classify_cgroup("/system.slice/custom-cron.service", 1000, owner_uid, units_policy)
    assert cls == "owner-agent"
    assert reason == "unlisted_unit"

    cls, reason = classify_cgroup("/system.slice/custom-cron.service", 1001, owner_uid, units_policy)
    assert cls == "unknown"
    assert reason == "unlisted_system_unit_untrusted_uid"


def test_resolve_peer_identity_socketpair():
    """Verify resolve_peer_identity on connected socketpair."""
    s1, s2 = socket.socketpair(socket.AF_UNIX)
    try:
        identity = resolve_peer_identity(s1, owner_uid=os.getuid())
        assert identity.verified is True
        assert identity.pid == os.getpid()
        assert identity.uid == os.getuid()
        assert identity.client_class in ("owner-agent", "unknown")
    finally:
        s1.close()
        s2.close()


@pytest.mark.asyncio
async def test_aq_http_client_instantiation():
    """Verify aq_http client helper instantiates correctly."""
    client = AqHttpClient(uds_path="/tmp/nonexistent.sock")
    assert client.uds_path == "/tmp/nonexistent.sock"
    await client.aclose()
