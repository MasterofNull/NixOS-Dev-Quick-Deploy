#!/usr/bin/env python3
"""Focused contract tests for the canonical AQ-OS program tracker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "assets" / "aqos-progress-tracker.html"
DASHBOARD = ROOT / "dashboard.html"
CLIENT = ROOT / "assets" / "dashboard.js"
MAIN = ROOT / "dashboard" / "backend" / "api" / "main.py"
PHASE0 = ROOT / "scripts" / "testing" / "harness_qa" / "phases" / "phase0.py"

SOURCE_CLASSES = {
    ".agents/plans/UNIFIED-PROGRAM-PLAN.md": "governing",
    ".agents/plans/unified-program/OWNER-DECISION-SHEET.md": "governing",
    "config/system-state-authorities.yaml": "governing",
    ".agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md": "governing",
    ".agent/memory/issues-backlog.md": "operational_snapshot",
    ".agent/collaboration/RESUME.json": "operational_snapshot",
    ".agent/collaboration/PULSE.log": "operational_snapshot",
    ".agents/delegation/registry.jsonl": "operational_snapshot",
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def manifest() -> dict:
    match = re.search(
        r'<script type="application/json" id="tracker-provenance">\s*(.*?)\s*</script>',
        text(TRACKER),
        re.DOTALL,
    )
    if not match:
        raise AssertionError("tracker provenance manifest missing")
    return json.loads(match.group(1))


def normalize_headers(headers) -> dict[str, str]:
    """Preserve RFC case-insensitive header lookup across HTTP client implementations."""
    return {str(key).lower(): str(value) for key, value in headers.items()}


def configure_live_base_url(value: str) -> str:
    """Bind live verification to the caller-selected candidate origin."""
    selected = value.rstrip("/")
    if not re.fullmatch(r"https?://[^/]+", selected):
        raise ValueError("--base-url must name one HTTP(S) origin without a path")
    LiveHeaderTests.base_url = selected
    return selected


def validate_provenance(data: dict, current_hashes: dict[str, str]) -> list[str]:
    """Validate closed source classes while treating operational hashes as historical evidence."""
    errors: list[str] = []
    if data.get("manifest_state") != "FROZEN_IMPLEMENTATION_SNAPSHOT":
        errors.append("manifest_state")
    if not re.fullmatch(r"2026-07-18T\d{2}:\d{2}:\d{2}Z", str(data.get("snapshot_at", ""))):
        errors.append("snapshot_at")
    sources = data.get("sources")
    if not isinstance(sources, list):
        return errors + ["sources"]
    paths = [source.get("path") for source in sources]
    digests = [source.get("sha256") for source in sources]
    if len(paths) != len(set(paths)):
        errors.append("duplicate_path")
    if len(digests) != len(set(digests)):
        errors.append("duplicate_digest")
    if set(paths) != set(SOURCE_CLASSES):
        errors.append("source_paths")
    for source in sources:
        path = source.get("path")
        source_class = source.get("source_class")
        digest = source.get("sha256")
        if source_class not in {"governing", "operational_snapshot"}:
            errors.append(f"source_class:{path}")
        if SOURCE_CLASSES.get(path) != source_class:
            errors.append(f"class_mapping:{path}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            errors.append(f"digest:{path}")
        if source_class == "governing" and current_hashes.get(path) != digest:
            errors.append(f"governing_drift:{path}")
    return errors


class StaticContractTests(unittest.TestCase):
    def test_exact_runtime_inventory_exists(self) -> None:
        for path in (TRACKER, DASHBOARD, CLIENT, MAIN, Path(__file__), PHASE0):
            self.assertTrue(path.is_file(), path)

    def test_tracker_is_self_contained(self) -> None:
        doc = text(TRACKER)
        self.assertNotRegex(doc, r'(?:src|href)=["\']https?://')
        self.assertNotIn("fetch(", doc)
        dashboard = text(DASHBOARD)
        self.assertNotRegex(dashboard, r'(?:src|href)\s*=\s*["\'](?:https?:)?//')
        self.assertNotRegex(dashboard, r'@import\s+(?:url\()?\s*["\']?(?:https?:)?//')
        self.assertNotRegex(dashboard, r'@font-face[\s\S]*?url\(\s*["\']?(?:https?:)?//')
        self.assertNotRegex(dashboard, r'font[^;{}]*url\(\s*["\']?(?:https?:)?//')
        self.assertNotIn("fonts.googleapis.com", dashboard)
        self.assertNotIn("fonts.gstatic.com", dashboard)

    def test_frozen_manifest_is_current(self) -> None:
        data = manifest()
        self.assertEqual(len(data["sources"]), 8)
        current_hashes = {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path, source_class in SOURCE_CLASSES.items()
            if source_class == "governing"
        }
        self.assertEqual(validate_provenance(data, current_hashes), [])
        self.assertEqual(
            {source["path"]: source["source_class"] for source in data["sources"]},
            SOURCE_CLASSES,
        )
        doc = text(TRACKER)
        self.assertIn("Operational records are historical commitments", doc)

    def test_operational_snapshot_liveness_boundary(self) -> None:
        data = copy.deepcopy(manifest())
        current_hashes = {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in SOURCE_CLASSES
        }
        operational = ".agent/collaboration/PULSE.log"
        current_hashes[operational] = hashlib.sha256(b"advanced operational bytes").hexdigest()
        self.assertEqual(validate_provenance(data, current_hashes), [])

        governing = ".agents/plans/UNIFIED-PROGRAM-PLAN.md"
        governing_drift = dict(current_hashes)
        governing_drift[governing] = hashlib.sha256(b"changed governing bytes").hexdigest()
        errors = validate_provenance(data, governing_drift)
        self.assertIn(f"governing_drift:{governing}", errors)

    def test_explicit_state_counts(self) -> None:
        data = manifest()["expected_counts"]
        self.assertEqual(data, {
            "tracks": 10,
            "active_tracks": 2,
            "foundation_a_blocking_gates": 1,
            "pending_q_decisions": 9,
            "authority_rows": 10,
            "open_high_severity_issues": 2,
        })
        doc = text(TRACKER)
        self.assertEqual(len(re.findall(r"status: 'PENDING'", doc)), 9)
        self.assertEqual(len(re.findall(r"status: 'DIRECTION_RECORDED', observed: 'SPLIT_BRAIN'", doc)), 10)
        self.assertEqual(len(re.findall(r"status: 'active', inclusion_status: 'INCLUDED'", doc)), 2)

    def test_truthful_foundation_projection(self) -> None:
        doc = text(TRACKER)
        self.assertIn("owner adjudication + ten-row projection (bec9bc0d)", doc.lower())
        self.assertIn("All ten observed rows remain SPLIT_BRAIN", doc)
        self.assertIn("generic flake exports + source-complete package baseline (befc4141)", doc.lower())

    def test_accessible_disclosures_and_reduced_motion(self) -> None:
        doc = text(TRACKER)
        self.assertIn('aria-describedby="lane-${t.code}-detail"', doc)
        self.assertIn("bar.addEventListener('focus'", doc)
        self.assertIn("e.key === 'Escape'", doc)
        self.assertIn("@media (prefers-reduced-motion: reduce)", doc)

    def test_program_panel_embed_contract(self) -> None:
        doc = text(DASHBOARD)
        self.assertIn('id="tab-program"', doc)
        self.assertIn('id="panel-program"', doc)
        self.assertIn('src="/assets/aqos-progress-tracker.html"', doc)
        self.assertIn('sandbox="allow-scripts"', doc)
        self.assertNotRegex(doc, r'sandbox="[^"]*allow-same-origin')
        self.assertRegex(doc, r'<iframe[\s\S]*?title="[^"]+"')
        self.assertIn('href="/assets/aqos-progress-tracker.html"', doc)

    def test_tab_controller_contract(self) -> None:
        doc = text(CLIENT)
        for token in (
            'setAttribute("role", "tab")', 'setAttribute("role", "tabpanel")',
            'setAttribute("aria-controls"', 'setAttribute("aria-selected"',
            'event.key === "ArrowRight"', 'event.key === "ArrowLeft"',
            'event.key === "Home"', 'event.key === "End"',
            'options.focusPanel', 'panel.focus()',
        ):
            self.assertIn(token, doc)

    def test_exact_path_header_exception(self) -> None:
        doc = text(MAIN)
        self.assertIn('request.url.path == "/assets/aqos-progress-tracker.html"', doc)
        self.assertIn('headers["X-Frame-Options"] = "SAMEORIGIN"', doc)
        self.assertIn("response.headers[name] = value", doc)
        self.assertIn('filtered.append("frame-ancestors \'self\'")', doc)
        self.assertIn('"X-Frame-Options": "DENY"', doc)
        self.assertIn('"frame-ancestors \'none\'"', doc)
        self.assertNotIn('request.url.path.startswith("/assets/aqos-progress-tracker', doc)

    def test_phase0_registration(self) -> None:
        doc = text(PHASE0)
        self.assertIn('"0.10.40"', doc)
        self.assertIn("results.extend(_check_dashboard_program_progress(ctx))", doc)
        self.assertIn('"--static-only"', doc)

    def test_live_verifier_regressions(self) -> None:
        original = LiveHeaderTests.base_url
        try:
            selected = configure_live_base_url("http://127.0.0.1:18889/")
            self.assertEqual(selected, "http://127.0.0.1:18889")
            self.assertEqual(LiveHeaderTests.base_url, selected)
            with self.assertRaises(ValueError):
                configure_live_base_url("http://127.0.0.1:18889/untrusted-path")
        finally:
            LiveHeaderTests.base_url = original
        lower = normalize_headers({
            "x-frame-options": "SAMEORIGIN",
            "content-security-policy": "default-src 'self'; frame-ancestors 'self'",
        })
        self.assertEqual(lower["x-frame-options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", lower["content-security-policy"])


class LiveHeaderTests(unittest.TestCase):
    base_url = "http://127.0.0.1:8889"

    def get(self, path: str) -> tuple[int, dict[str, str], str]:
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return response.status, normalize_headers(response.headers), response.read().decode("utf-8")

    def test_live_tracker_and_negative_headers(self) -> None:
        status, headers, body = self.get("/assets/aqos-progress-tracker.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-frame-options"), "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", headers.get("content-security-policy", ""))
        self.assertIn("FROZEN_IMPLEMENTATION_SNAPSHOT", body)
        for path in ("/", "/assets/dashboard.js"):
            status, headers, _ = self.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("x-frame-options"), "DENY")
            self.assertIn("frame-ancestors 'none'", headers.get("content-security-policy", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8889",
        help="dashboard candidate origin (default: loopback production dashboard)",
    )
    args = parser.parse_args()
    configure_live_base_url(args.base_url)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StaticContractTests)
    if not args.static_only:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(LiveHeaderTests))
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
