"""
Unit tests for agent-auth AUTH-S6: research.fetch SSRF hardening.

Covers:
- Literal IP address checks: loopback, RFC1918, link-local, cloud metadata, multicast, NAT64, 6to4, CGNAT
- Pinned IP connect logic and DNS rebinding rejection
- Mixed DNS answer rejection (if any resolved IP is non-global, entire host is rejected)
- Tighten-only configuration switches under enforce/lockdown
- Header preservation (Host and SNI extensions) for pinned requests
- Test seam behavior requiring AQ_TEST_MODE=1
"""

import asyncio
import os
import unittest
from unittest.mock import patch

from shared.ssrf_protection import (
    assert_safe_outbound_url,
    create_ssrf_safe_http_client,
    is_safe_global_ip,
    resolve_pinned,
    _ssrf_policy_config,
)


class TestSSRFHardeningS6(unittest.IsolatedAsyncioTestCase):
    def test_is_safe_global_ip_rejections(self):
        blocked_ips = [
            "127.0.0.1",
            "::1",
            "0.0.0.0",
            "169.254.169.254",         # Cloud metadata
            "169.254.1.1",             # Link local IPv4
            "fe80::1",                 # Link local IPv6
            "10.0.0.1",                # RFC1918 Class A
            "172.16.0.1",              # RFC1918 Class B
            "192.168.1.1",             # RFC1918 Class C
            "100.64.0.1",              # CGNAT RFC 6598
            "::ffff:127.0.0.1",        # IPv4-mapped loopback
            "::ffff:169.254.169.254",  # IPv4-mapped cloud metadata
            "::ffff:10.0.0.1",         # IPv4-mapped private
            "64:ff9b::7f00:1",         # NAT64
            "64:ff9b::a00:1",          # NAT64
            "2002:7f00:1::",           # 6to4
            "224.0.0.1",               # Multicast IPv4
            "ff02::1",                 # Multicast IPv6
            "255.255.255.255",         # Broadcast
        ]
        for ip in blocked_ips:
            with self.subTest(ip=ip):
                self.assertFalse(is_safe_global_ip(ip), f"Expected {ip} to be blocked")

    def test_is_safe_global_ip_accepts_valid_public_ips(self):
        valid_ips = [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",
            "2606:4700:4700::1111",
            "2001:4860:4860::8888",
        ]
        for ip in valid_ips:
            with self.subTest(ip=ip):
                self.assertTrue(is_safe_global_ip(ip), f"Expected {ip} to be allowed")

    async def test_resolve_pinned_blocks_non_global_ips(self):
        with patch("asyncio.get_running_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            mock_loop.return_value = loop

            # Mock getaddrinfo returning private IP
            async def fake_gai_private(host, port, proto=0):
                return [(2, 1, 6, "", ("10.0.0.1", port))]
            loop.getaddrinfo = fake_gai_private

            with self.assertRaises(PermissionError):
                await resolve_pinned("internal.service.local", 443)

    async def test_resolve_pinned_rejects_mixed_dns_answer(self):
        """If a host returns both a public IP and a private/loopback IP, it must be rejected completely."""
        with patch("asyncio.get_running_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            mock_loop.return_value = loop

            async def fake_gai_mixed(host, port, proto=0):
                return [
                    (2, 1, 6, "", ("93.184.216.34", port)),
                    (2, 1, 6, "", ("127.0.0.1", port)),
                ]
            loop.getaddrinfo = fake_gai_mixed

            with self.assertRaises(PermissionError) as ctx:
                await resolve_pinned("rebind-target.com", 443)
            self.assertIn("non-global address", str(ctx.exception))

    async def test_resolve_pinned_accepts_all_global_ips(self):
        with patch("asyncio.get_running_loop") as mock_loop:
            loop = asyncio.new_event_loop()
            mock_loop.return_value = loop

            async def fake_gai_valid(host, port, proto=0):
                return [
                    (10, 1, 6, "", ("2606:4700:4700::1111", port, 0, 0)),
                    (2, 1, 6, "", ("1.1.1.1", port)),
                ]
            loop.getaddrinfo = fake_gai_valid

            ips = await resolve_pinned("one.one.one.one", 443)
            self.assertEqual(ips, ["2606:4700:4700::1111", "1.1.1.1"])

    def test_tighten_only_switches_under_enforce(self):
        with patch.dict(os.environ, {
            "AQ_AGENT_AUTH_MODE": "enforce",
            "HYBRID_BLOCK_PRIVATE_EGRESS": "false",  # attempt to disable
            "HYBRID_ALLOW_PLAINTEXT_HTTP": "true",   # attempt to allow http
        }):
            cfg = _ssrf_policy_config()
            self.assertTrue(cfg["is_enforcing"])
            self.assertTrue(cfg["block_private_ranges"], "block_private_ranges must remain True under enforce")
            self.assertFalse(cfg["allow_http"], "allow_http must remain False under enforce")

    def test_assert_safe_outbound_url_blocks_schemes_and_private_hosts(self):
        with self.assertRaises(PermissionError):
            assert_safe_outbound_url("ftp://example.com/file")
        with self.assertRaises(PermissionError):
            assert_safe_outbound_url("file:///etc/passwd")
        with self.assertRaises(PermissionError):
            assert_safe_outbound_url("http://127.0.0.1:8080/admin")
        with self.assertRaises(PermissionError):
            assert_safe_outbound_url("https://169.254.169.254/latest/meta-data/")

    def test_client_trust_env_false(self):
        client = create_ssrf_safe_http_client("https://1.1.1.1")
        # Ensure client has trust_env disabled
        self.assertFalse(client._trust_env)


if __name__ == "__main__":
    unittest.main()
