#!/usr/bin/env python3
"""
Regression test for Phase 16.4.3 — Timer-driven oneshot units must have Restart = "no".

Scans systemd service definitions in nix/modules/** for:
  1. Services with Type = "oneshot"
  2. That merge a hardened service base
  3. Verifies Restart = "no" is set (directly or via mkHardenedService restart param)

Prevents a repeat of ai-autonomous-improvement failing 593 times in 3h when
a timer-driven oneshot had Restart = "on-failure" + RestartSec = "10s".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def extract_service_block(content: str, service_name: str) -> str | None:
    """Extract systemd.services.<name> block from Nix.

    Handles nested braces by counting depth to find the matching closing brace.
    """
    pattern = rf'systemd\.services\.{re.escape(service_name)}\s*=\s*\{{'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None

    start = match.end() - 1  # Position of opening brace
    depth = 1
    pos = start + 1

    while pos < len(content) and depth > 0:
        if content[pos] == '{':
            depth += 1
        elif content[pos] == '}':
            depth -= 1
        pos += 1

    if depth == 0:
        return content[start+1:pos-1]
    return None


def is_oneshot(service_block: str) -> bool:
    """Check if service block has Type = "oneshot"."""
    return re.search(r'Type\s*=\s*"oneshot"', service_block, re.IGNORECASE) is not None


def has_no_restart(service_block: str) -> bool:
    """Check if service explicitly sets Restart = "no"."""
    return re.search(r'Restart\s*=\s*"no"', service_block, re.IGNORECASE) is not None


def check_hardened_base_no_restart(service_block: str, nix_file: Path) -> bool:
    """Check if service merges a hardened base created with restart = "no"."""
    # Look for patterns like:
    #   hardenedBase // { ... }
    #   mkHardenedService { ... restart = "no"; ... } // { ... }
    #   oneshotServiceConfig // { ... }

    # Case 1: Direct mkHardenedService call with restart = "no"
    if re.search(r'mkHardenedService\s*\{[^}]*restart\s*=\s*"no"[^}]*\}', service_block, re.DOTALL):
        return True

    # Case 2: Reference to hardenedBase with restart = "no" defined earlier
    if 'hardenedBase' in service_block and 'Type = "oneshot"' in service_block:
        # Check if hardenedBase is defined with restart = "no" in this file
        if re.search(r'hardenedBase\s*=\s*mkHardenedService\s*\{[^}]*restart\s*=\s*"no"[^}]*\}', nix_file.read_text(encoding='utf-8'), re.DOTALL):
            return True

    # Case 3: Reference to oneshotServiceConfig (which should have Restart = "no")
    if 'oneshotServiceConfig' in service_block:
        return True

    return False


def test_oneshot_services():
    """Test that all oneshot units have Restart = "no"."""
    services_to_check = [
        ('nix/modules/services/autonomous-improvement.nix', 'ai-autonomous-improvement'),
        ('nix/modules/services/mcp-servers.nix', 'ai-sync-knowledge-sources'),
        ('nix/modules/services/mcp-servers.nix', 'ai-mcp-integrity-check'),
        ('nix/modules/services/mcp-servers.nix', 'ai-mcp-process-watch'),
    ]

    passed = 0
    failed = 0
    unclassified = []

    for nix_path, service_name in services_to_check:
        nix_file = ROOT / nix_path
        if not nix_file.exists():
            print(f"SKIP: {nix_file} not found")
            continue

        content = nix_file.read_text(encoding='utf-8')
        service_block = extract_service_block(content, service_name)

        if not service_block:
            print(f"SKIP: Service {service_name} not found in {nix_file}")
            continue

        if not is_oneshot(service_block):
            print(f"SKIP: {service_name} is not a oneshot service")
            continue

        # Check if Restart = "no" is set
        if has_no_restart(service_block):
            print(f"PASS: {service_name} has Restart = \"no\"")
            passed += 1
        elif check_hardened_base_no_restart(service_block, nix_file):
            print(f"PASS: {service_name} uses hardened base with restart = \"no\"")
            passed += 1
        else:
            print(f"FAIL: {service_name} is a oneshot but does not have Restart = \"no\"")
            failed += 1
            unclassified.append((service_name, nix_file))

    if unclassified:
        print(f"\nUnclassified oneshot services (require manual review):")
        for service_name, nix_file in unclassified:
            print(f"  {nix_file}: {service_name}")

    total = passed + failed
    if total == 0:
        print("ERROR: No oneshot services found to test")
        return 1

    print(f"\n{passed}/{total} tests passed")

    if failed > 0:
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(test_oneshot_services())
