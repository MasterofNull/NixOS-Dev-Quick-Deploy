#!/usr/bin/env python3
"""Regression checks for affective reciprocity pipeline wiring."""

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AFFECTIVE_DIR = REPO_ROOT / "ai-stack" / "affective-engine"
HTTP_SERVER = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    source = HTTP_SERVER.read_text(encoding="utf-8")
    assert_true("from reciprocity_tracker import ReciprocityTracker" in source, "pipeline should import ReciprocityTracker")
    assert_true("reciprocity_debt=_reciprocity.get_debt" in source, "AffectiveState should receive real reciprocity debt")
    assert_true("_reciprocity.record_give" in source, "pipeline should record system value before reading debt")

    module_path = AFFECTIVE_DIR / "reciprocity_tracker.py"
    loader = SourceFileLoader("reciprocity_tracker_under_test", str(module_path))
    spec = importlib.util.spec_from_loader("reciprocity_tracker_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    tracker = module.ReciprocityTracker(redis_url="redis://127.0.0.1:1")
    tracker.record_give("test-session", 2.0)
    tracker.record_receive("test-session", 0.5)
    assert_true(tracker.get_debt("test-session") == -1.5, "fallback debt should be receive minus give")

    print("PASS: affective reciprocity wiring validated")


if __name__ == "__main__":
    main()
