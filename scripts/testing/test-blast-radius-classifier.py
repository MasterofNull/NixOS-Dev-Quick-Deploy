#!/usr/bin/env python3
import sys
from pathlib import Path

# Dynamically add the hybrid-coordinator module to sys.path for testing
repo_root = Path(__file__).resolve().parent.parent.parent
hybrid_coordinator_path = repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(hybrid_coordinator_path))

from blast_radius_classifier import classify, batch_classify

def test_classifier():
    # Critical
    assert classify("rm -rf /tmp/data") == "critical"
    assert classify("git push origin main --force") == "critical"
    assert classify("DROP TABLE users;") == "critical"
    assert classify("sudo nixos-rebuild switch") == "critical"

    # High
    assert classify("git push origin main") == "high"
    assert classify("systemctl restart nginx") == "high"
    assert classify("DELETE /api/v1/resource") == "high"

    # Medium
    assert classify("git commit -m 'update safety gate'") == "medium"
    assert classify("POST /api/v1/data") == "medium"

    # Low
    assert classify("ls -la /var/log") == "low"
    assert classify("GET /api/v1/health") == "low"

    print("✅ All blast radius classifier tests passed!")

if __name__ == "__main__":
    test_classifier()
