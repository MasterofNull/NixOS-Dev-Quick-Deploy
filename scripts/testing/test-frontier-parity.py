#!/usr/bin/env python3
"""Tests for FA-5 (frontier parity): whole-taxonomy backstop sweep (on-demand, not timer).

FA-5 parity is the reverse gap check: for each concept in the taxonomy (core/supporting),
verify we have at least one source tracking it AND at least one candidate assessed.
A concept with no source or no candidate is a blind spot (gap).

Tests verify:
  1. A deliberately-untracked concept in the taxonomy emits a gap
  2. A fully-covered taxonomy (all concepts have sources + candidates) emits no gaps
  3. Gap count is accurate per tier
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the aq-frontier lib to path
SCRIPTS_LIB = Path(__file__).resolve().parent.parent / "ai" / "lib"
sys.path.insert(0, str(SCRIPTS_LIB))

import frontier_relevance as fr


def test_parity_untracked_concept_emits_gap():
    """A core concept with no source AND no candidate should be reported as a gap."""
    concepts_catalog = {
        "weights": {"core": 3, "supporting": 2, "peripheral": 1},
        "concepts": [
            {"id": "tracked-core", "tier": "core", "keywords": ["tracked"]},
            {"id": "untracked-core", "tier": "core", "keywords": ["untracked"]},
        ]
    }

    # Sources tracking only "tracked"
    sources = [
        {"name": "some-source", "why": "tracks tracked concepts", "pillar": "example"}
    ]

    # Backlog with only candidates for "tracked"
    backlog = [
        {
            "id": "FE-1",
            "technique": "tracked technique",
            "claim": "tracked concept",
            "verdict": "adopt",
        }
    ]

    # Run parity check
    cov = fr.concept_coverage(concepts_catalog, sources, backlog)

    # Verify gaps detected
    assert cov["gap_count"] >= 1, f"Expected at least 1 gap, got {cov['gap_count']}"

    # Find the untracked-core gap
    untracked_row = next((r for r in cov["concepts"] if r["concept"] == "untracked-core"), None)
    assert untracked_row is not None, "untracked-core concept not found in coverage"
    assert untracked_row["gap"] is True, f"Expected untracked-core to be a gap, got {untracked_row}"
    assert untracked_row["sources_tracking"] == 0, "untracked concept should have 0 sources"
    assert untracked_row["candidates_found"] == 0, "untracked concept should have 0 candidates"

    print("✓ test_parity_untracked_concept_emits_gap PASSED")


def test_parity_fully_covered_no_gaps():
    """When all core/supporting concepts have sources AND candidates, no gaps."""
    concepts_catalog = {
        "weights": {"core": 3, "supporting": 2, "peripheral": 1},
        "concepts": [
            {"id": "concept-a", "tier": "core", "keywords": ["alpha"]},
            {"id": "concept-b", "tier": "supporting", "keywords": ["beta"]},
            {"id": "concept-c", "tier": "peripheral", "keywords": ["gamma"]},
        ]
    }

    # Sources tracking all
    sources = [
        {"name": "source-a", "why": "alpha source", "pillar": "example"},
        {"name": "source-b", "why": "beta source", "pillar": "example"},
        {"name": "source-c", "why": "gamma source", "pillar": "example"},
    ]

    # Candidates for all
    backlog = [
        {"id": "FE-1", "technique": "alpha tech", "claim": "alpha", "verdict": "adopt"},
        {"id": "FE-2", "technique": "beta tech", "claim": "beta", "verdict": "adopt"},
        {"id": "FE-3", "technique": "gamma tech", "claim": "gamma", "verdict": "adopt"},
    ]

    # Run parity check
    cov = fr.concept_coverage(concepts_catalog, sources, backlog)

    # Verify NO gaps
    assert cov["gap_count"] == 0, f"Expected 0 gaps, got {cov['gap_count']}"
    assert not cov["gaps"], f"Expected no gap concepts, got {cov['gaps']}"

    # Verify all concepts are not marked as gaps
    for row in cov["concepts"]:
        if row["tier"] in ("core", "supporting"):
            assert row["gap"] is False, f"Core/supporting concept {row['concept']} should not be a gap"

    print("✓ test_parity_fully_covered_no_gaps PASSED")


def test_parity_peripheral_ignored():
    """Peripheral concepts without sources/candidates should NOT be gaps (they're optional)."""
    concepts_catalog = {
        "weights": {"core": 3, "supporting": 2, "peripheral": 1},
        "concepts": [
            {"id": "core-x", "tier": "core", "keywords": ["core"]},
            {"id": "periph-y", "tier": "peripheral", "keywords": ["peripheral"]},
        ]
    }

    # Only track core
    sources = [
        {"name": "core-source", "why": "core tracking", "pillar": "example"}
    ]
    backlog = [
        {"id": "FE-1", "technique": "core", "claim": "core concept", "verdict": "adopt"}
    ]

    # Run parity check
    cov = fr.concept_coverage(concepts_catalog, sources, backlog)

    # Only core-x should be non-gap; periph-y should also be non-gap (peripheral is exempt)
    assert cov["gap_count"] == 0, f"Expected 0 gaps (peripheral ignored), got {cov['gap_count']}"

    periph_row = next((r for r in cov["concepts"] if r["concept"] == "periph-y"), None)
    assert periph_row is not None
    assert periph_row["gap"] is False, "Peripheral concept should not be marked as gap"

    print("✓ test_parity_peripheral_ignored PASSED")


def test_parity_gap_per_tier():
    """Gap count should distinguish by tier and only flag core/supporting."""
    concepts_catalog = {
        "weights": {"core": 3, "supporting": 2, "peripheral": 1},
        "concepts": [
            {"id": "core-1", "tier": "core", "keywords": ["core-1"]},
            {"id": "core-2", "tier": "core", "keywords": ["core-2"]},
            {"id": "supp-1", "tier": "supporting", "keywords": ["supp-1"]},
        ]
    }

    # No sources, no backlog — all are gaps (for core/supporting)
    sources = []
    backlog = []

    cov = fr.concept_coverage(concepts_catalog, sources, backlog)

    # All 3 should be gaps (2 core + 1 supporting)
    assert cov["gap_count"] == 3, f"Expected 3 gaps (2 core + 1 supporting), got {cov['gap_count']}"

    # Verify each tier
    core_gaps = sum(1 for r in cov["concepts"] if r["tier"] == "core" and r["gap"])
    supp_gaps = sum(1 for r in cov["concepts"] if r["tier"] == "supporting" and r["gap"])

    assert core_gaps == 2, f"Expected 2 core gaps, got {core_gaps}"
    assert supp_gaps == 1, f"Expected 1 supporting gap, got {supp_gaps}"

    print("✓ test_parity_gap_per_tier PASSED")


if __name__ == "__main__":
    test_parity_untracked_concept_emits_gap()
    test_parity_fully_covered_no_gaps()
    test_parity_peripheral_ignored()
    test_parity_gap_per_tier()
    print("\n✓ All FA-5 tests passed")
