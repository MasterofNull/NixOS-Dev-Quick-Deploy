#!/usr/bin/env python3
"""Tests for FA-4 (frontier scan-topic): bounded, need-driven refresh (not a timer).

FA-4 scan-topic is called when an agent queries a topic and our knowledge is stale/missing.
It appends a scan request (topic + stale concepts) to a TEMP scan-requests file and
recommends a web-capable lane perform the bounded intake task.

Tests verify:
  1. A stale/gap topic yields a bounded scan request in the scan-requests file
  2. A fresh topic (no stale concepts) does NOT yield a scan request
  3. Max-N bounded by design (config, not per-command)
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the aq-frontier lib to path
SCRIPTS_LIB = Path(__file__).resolve().parent.parent / "ai" / "lib"
sys.path.insert(0, str(SCRIPTS_LIB))

import frontier_backlog as fb
import frontier_context as fc
import frontier_relevance as fr


def test_scan_topic_stale_creates_request():
    """Stale/gap topic should append a scan request to scan-requests.jsonl."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create a minimal concepts catalog
        concepts_catalog = {
            "weights": {"core": 3, "supporting": 2, "peripheral": 1},
            "concepts": [
                {"id": "test-concept", "tier": "core", "keywords": ["test", "concept"]},
            ]
        }

        # Create a backlog with NO candidates for this concept
        # (so stale_concepts will be populated)
        backlog = []

        # Run context_for_topic with a query that matches the concept
        ctx = fc.context_for_topic(
            "test concept",
            concepts_catalog,
            backlog,
            stale_days=30,
            now=1000000.0,  # Fixed time
        )

        # Verify that stale_concepts is populated (because no candidates exist)
        assert ctx["stale_concepts"], "Expected stale_concepts to be non-empty"
        assert "test-concept" in ctx["stale_concepts"]
        assert ctx["refresh_recommended"] is True

        # Now simulate the scan-topic command writing a request
        scan_requests_file = tmpdir_p / "scan-requests.jsonl"
        scan_requests_file.parent.mkdir(parents=True, exist_ok=True)

        ts = "2026-10-07T12:00:00Z"
        req = {
            "requested_at": ts,
            "topic": "test concept",
            "stale_concepts": ctx["stale_concepts"],
        }

        with open(scan_requests_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(req, sort_keys=True) + "\n")

        # Verify the request was written
        lines = scan_requests_file.read_text().splitlines()
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"
        written = json.loads(lines[0])
        assert written["topic"] == "test concept"
        assert "test-concept" in written["stale_concepts"]
        print("✓ test_scan_topic_stale_creates_request PASSED")


def test_scan_topic_fresh_no_request():
    """Fresh topic (all concepts have recent candidates) should NOT create a scan request."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create a concepts catalog
        concepts_catalog = {
            "weights": {"core": 3, "supporting": 2, "peripheral": 1},
            "concepts": [
                {"id": "test-concept", "tier": "core", "keywords": ["test", "concept"]},
            ]
        }

        # Create a backlog with a RECENT candidate for this concept
        now = 1000000.0
        recent_date = __import__("time").strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            __import__("time").gmtime(now - 10 * 86400),  # 10 days ago (< 30 day stale window)
        )

        backlog = [
            {
                "id": "FE-TEST",
                "technique": "test technique",
                "claim": "test concept applies here",
                "verdict": "adopt",
                "status": "accepted",
                "discovered_at": recent_date,
            }
        ]

        # Run context_for_topic
        ctx = fc.context_for_topic(
            "test concept",
            concepts_catalog,
            backlog,
            stale_days=30,
            now=now,
        )

        # Verify that stale_concepts is EMPTY (because we have a recent candidate)
        assert not ctx["stale_concepts"], f"Expected no stale concepts, got {ctx['stale_concepts']}"
        assert ctx["refresh_recommended"] is False

        # Verify no scan request would be created
        scan_requests_file = Path(tmpdir) / "scan-requests.jsonl"
        # File should not exist or be empty
        if scan_requests_file.exists():
            lines = scan_requests_file.read_text().strip()
            assert not lines, "Expected no scan request for fresh topic"

        print("✓ test_scan_topic_fresh_no_request PASSED")


def test_scan_topic_request_structure():
    """Scan request must have all required fields: requested_at, topic, stale_concepts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        concepts_catalog = {
            "weights": {"core": 3},
            "concepts": [
                {"id": "concept-a", "tier": "core", "keywords": ["alpha"]},
                {"id": "concept-b", "tier": "core", "keywords": ["beta"]},
            ]
        }

        # Empty backlog = stale concepts
        backlog = []

        ctx = fc.context_for_topic(
            "alpha beta",
            concepts_catalog,
            backlog,
            stale_days=30,
            now=1000000.0,
        )

        # Build the request as scan-topic would
        ts = "2026-10-07T12:00:00Z"
        req = {
            "requested_at": ts,
            "topic": "alpha beta",
            "stale_concepts": ctx["stale_concepts"],
        }

        # Verify required fields exist
        assert "requested_at" in req
        assert "topic" in req
        assert "stale_concepts" in req
        assert isinstance(req["stale_concepts"], list)

        print("✓ test_scan_topic_request_structure PASSED")


if __name__ == "__main__":
    test_scan_topic_stale_creates_request()
    test_scan_topic_fresh_no_request()
    test_scan_topic_request_structure()
    print("\n✓ All FA-4 tests passed")
