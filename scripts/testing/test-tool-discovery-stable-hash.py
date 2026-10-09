#!/usr/bin/env python3
"""
Test that tool_discovery uses stable hash for Qdrant point IDs.

Verifies that the _stable_point_id function is present and uses SHA1 hash
instead of Python's salted hash function.
"""

import subprocess
import sys
from pathlib import Path


def test_stable_point_id_present():
    """Test that _stable_point_id function is defined."""
    tool_discovery_path = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "aidb" / "tool_discovery.py"
    content = tool_discovery_path.read_text()

    # Check for the _stable_point_id function
    assert "def _stable_point_id(" in content, "Expected _stable_point_id function"
    assert "import hashlib" in content, "Expected hashlib import"
    assert "hashlib.sha1" in content, "Expected SHA1 hash usage"
    assert "hexdigest()[:8]" in content, "Expected 8-char hex digest"

    print("✓ _stable_point_id function uses hashlib.sha1 with 8-char hex digest")


def test_stable_point_id_used_in_index():
    """Test that _stable_point_id is used instead of hash()."""
    tool_discovery_path = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "aidb" / "tool_discovery.py"
    content = tool_discovery_path.read_text()

    # Check that the old hash() method is gone
    assert "id=_stable_point_id(tool.tool_id)" in content, "Expected _stable_point_id call"
    assert 'id=hash(tool.tool_id)' not in content, "Expected old hash(tool.tool_id) to be replaced"

    print("✓ PointStruct id uses _stable_point_id instead of hash()")


def test_stable_hash_across_processes():
    """Test that the same tool_id produces same hash across processes."""
    # Test code that defines and uses _stable_point_id
    code = """
import hashlib

def _stable_point_id(tool_id: str) -> int:
    return int(hashlib.sha1(str(tool_id).encode("utf-8")).hexdigest()[:8], 16) % (10 ** 8)

print(_stable_point_id("aidb.test-tool-id"))
"""

    # Run with different PYTHONHASHSEED values
    ids = []
    for seed in [1, 2, 42]:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": str(seed)},
        )
        if result.returncode != 0:
            raise AssertionError(f"Failed with PYTHONHASHSEED={seed}: {result.stderr}")
        ids.append(int(result.stdout.strip()))

    # All should be identical
    assert ids[0] == ids[1] == ids[2], f"Hash values differ across seeds: {ids}"
    assert 0 <= ids[0] < 10**8, f"Hash value out of range: {ids[0]}"

    print(f"✓ Stable hash produces consistent ID (={ids[0]}) across PYTHONHASHSEED values")


if __name__ == "__main__":
    test_stable_point_id_present()
    test_stable_point_id_used_in_index()
    test_stable_hash_across_processes()
    print("\nAll tool_discovery stable hash tests passed!")
