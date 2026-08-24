#!/usr/bin/env python3
"""Focused contract tests for the canonical AQ-OS program tracker.

The tracker (assets/aqos-progress-tracker.html) was a frozen, hand-typed
evidence snapshot through 2026-08. It is now a LIVE page that fetches
GET /api/pm/progress (dashboard/backend/api/routes/pm.py, which shells out
to `scripts/ai/aq-pm-tracker --all-json`) and renders the git-projected
program rollup — no hardcoded track/gate/issue arrays remain. These tests
assert the live-fetch contract, not any frozen content shape.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import types
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "assets" / "aqos-progress-tracker.html"
DASHBOARD = ROOT / "dashboard.html"
CLIENT = ROOT / "assets" / "dashboard.js"
MAIN = ROOT / "dashboard" / "backend" / "api" / "main.py"
PM_ROUTE = ROOT / "dashboard" / "backend" / "api" / "routes" / "pm.py"
PM_TRACKER_CLI = ROOT / "scripts" / "ai" / "aq-pm-tracker"
PHASE0 = ROOT / "scripts" / "testing" / "harness_qa" / "phases" / "phase0.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


STATUS_ORDER = (
    "ACTIVATED", "SHIPPED", "IN-PROGRESS", "FROZEN", "DESIGNED", "BLOCKED", "NOT-STARTED",
)


def dashboard_render_oracle(plans: list[dict]) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    """Small data-only oracle for the tracker projections.

    It mirrors the browser's compatibility posture: missing deps and priority
    labels are harmless, invalid status falls back to NOT-STARTED, and only
    edges whose dependency is present in the same plan can be drawn.
    """
    memberships: list[tuple[str, str, str]] = []
    edges: list[tuple[str, str]] = []
    for plan in plans:
        plan_id = str(plan.get("id") or "")
        items = plan.get("items") or []
        by_id = {str(item.get("id") or ""): item for item in items if str(item.get("id") or "")}
        for item in items:
            item_id = str(item.get("id") or "")
            status = str(item.get("status") or "NOT-STARTED")
            memberships.append((f"{plan_id}:{item_id}", status if status in STATUS_ORDER else "NOT-STARTED", str(item.get("priority_lane") or "")))
            for dependency in item.get("deps") or []:
                dependency_id = str(dependency)
                if dependency_id in by_id:
                    edges.append((f"{plan_id}:{dependency_id}", f"{plan_id}:{item_id}"))
    return memberships, edges


def dependency_marker_id(plan_id: object) -> str:
    """Mirror the browser's stable, document-safe plan-scoped marker ID."""
    text_id = str(plan_id or "")
    code_points = [format(ord(char), "x") for char in text_id]
    return "dependency-arrow-" + ("-".join(code_points) if code_points else "empty")


def load_pm_tracker_module() -> types.ModuleType:
    """Load the stdlib-only tracker under test without invoking its CLI main()."""
    module = types.ModuleType("aq_pm_tracker_under_test")
    module.__file__ = str(PM_TRACKER_CLI)
    exec(compile(text(PM_TRACKER_CLI), str(PM_TRACKER_CLI), "exec"), module.__dict__)
    return module


class ProjectionProvenanceTests(unittest.TestCase):
    def test_git_read_path_never_fetches_or_updates_refs(self) -> None:
        tracker = load_pm_tracker_module()
        calls: list[list[str]] = []

        def fake_run(args, **_kwargs):
            calls.append(list(args))
            if "rev-parse" in args:
                return subprocess.CompletedProcess(args, 0, "false\n", "")
            if "log" in args:
                return subprocess.CompletedProcess(args, 0, "abc ship slice\n", "")
            raise AssertionError(f"unexpected process: {args}")

        tracker.subprocess.run = fake_run
        gitlog, health = tracker._git_log()
        self.assertEqual((gitlog, health), ("abc ship slice\n", "complete"))
        self.assertTrue(all("--no-optional-locks" in call for call in calls))
        forbidden = {"fetch", "pull", "push", "update-ref", "commit", "checkout", "reset"}
        self.assertTrue(all(forbidden.isdisjoint(call) for call in calls), calls)

    def test_shallow_history_marks_missing_commit_evidence_unknown(self) -> None:
        tracker = load_pm_tracker_module()
        item = {"detection": {"commit_match": ["ship PM provenance"]}}
        self.assertEqual(
            tracker.project_item(item, "", "", "shallow_incomplete"), ("UNKNOWN", None)
        )
        # Explicit positive evidence is still truthful when history is partial.
        self.assertEqual(
            tracker.project_item({"acceptance": {"status": "accepted"}, **item}, "", "", "shallow_incomplete"),
            ("SHIPPED", 100),
        )
        self.assertEqual(
            tracker.project_item({"kind": "task", "detection": {"activation_subject": "vf", "blocker_note": "owner acts"}},
                                 "", "activation.grant vf", "shallow_incomplete"),
            ("ACTIVATED", 100),
        )

    def test_git_error_is_unavailable_not_not_started(self) -> None:
        tracker = load_pm_tracker_module()

        def failing_run(args, **_kwargs):
            if "rev-parse" in args:
                raise OSError("git unavailable")
            raise AssertionError(f"unexpected process: {args}")

        tracker.subprocess.run = failing_run
        self.assertEqual(tracker._git_log(), ("", "unavailable"))
        self.assertEqual(
            tracker.project_item({"detection": {"commit_match": ["slice"]}}, "", "", "unavailable"),
            ("UNKNOWN", None),
        )

    def test_malformed_shallow_probe_fails_closed(self) -> None:
        tracker = load_pm_tracker_module()

        def malformed_run(args, **_kwargs):
            if "rev-parse" in args:
                return subprocess.CompletedProcess(args, 0, "perhaps\n", "")
            raise AssertionError(f"git log must not run after malformed probe: {args}")

        tracker.subprocess.run = malformed_run
        self.assertEqual(tracker._git_log(), ("", "unavailable"))

    def test_rollup_excludes_unknown_evidence(self) -> None:
        tracker = load_pm_tracker_module()
        rollup, known, unknown = tracker._rollup([
            {"pct": 100}, {"pct": None}, {"pct": 20},
        ])
        self.assertEqual((rollup, known, unknown), (60, 2, 1))

    def test_malformed_and_escaped_provenance_are_defensive(self) -> None:
        doc = text(TRACKER)
        # The browser does not trust a malformed source_health field, and all
        # displayed dynamic provenance text runs through the same HTML escaper.
        self.assertIn("labels[health] || 'provenance is incomplete'", doc)
        self.assertIn("escapeHtml(labels[health] || 'provenance is incomplete')", doc)
        self.assertIn("status: STATUS_ORDER.includes(rawStatus)", doc)
        self.assertIn("item.pct == null ? 'unknown' : item.pct + '%'", doc)
        self.assertNotIn("(${item.pct}%)", doc)
        route = text(PM_ROUTE)
        self.assertIn("except json.JSONDecodeError", route)


class StaticContractTests(unittest.TestCase):
    def test_exact_runtime_inventory_exists(self) -> None:
        for path in (TRACKER, DASHBOARD, CLIENT, MAIN, PM_ROUTE, PM_TRACKER_CLI, Path(__file__), PHASE0):
            self.assertTrue(path.is_file(), path)

    def test_tracker_is_self_contained_except_same_origin_api(self) -> None:
        """No external asset/script sources — but the live /api/pm/progress
        fetch (a same-origin relative path) is the whole point now."""
        doc = text(TRACKER)
        self.assertNotRegex(doc, r'(?:src|href)=["\']https?://')
        # exactly one fetch call, and it targets the same-origin aggregate route
        self.assertEqual(len(re.findall(r"fetch\(", doc)), 1)
        self.assertIn("const ENDPOINT = '/api/pm/progress';", doc)
        dashboard = text(DASHBOARD)
        self.assertNotRegex(dashboard, r'(?:src|href)\s*=\s*["\'](?:https?:)?//')
        self.assertNotRegex(dashboard, r'@import\s+(?:url\()?\s*["\']?(?:https?:)?//')
        self.assertNotRegex(dashboard, r'@font-face[\s\S]*?url\(\s*["\']?(?:https?:)?//')
        self.assertNotRegex(dashboard, r'font[^;{}]*url\(\s*["\']?(?:https?:)?//')
        self.assertNotIn("fonts.googleapis.com", dashboard)
        self.assertNotIn("fonts.gstatic.com", dashboard)

    def test_no_hardcoded_progress_data(self) -> None:
        """The old mockup baked plan/gate/issue/authority arrays straight into
        the page. None of that may return — all content is server-projected."""
        doc = text(TRACKER)
        for banned in (
            "const tracks = [",
            "const gateRows = [",
            "const issues = [",
            "const authorityTargets = [",
            "FROZEN_IMPLEMENTATION_SNAPSHOT",
            "tracker-provenance",
        ):
            self.assertNotIn(banned, doc, banned)

    def test_live_fetch_and_refresh_contract(self) -> None:
        doc = text(TRACKER)
        self.assertIn("async function load()", doc)
        self.assertIn("REFRESH_INTERVAL_MS = 30000", doc)
        self.assertIn("setInterval(load, REFRESH_INTERVAL_MS)", doc)
        self.assertIn("cache: 'no-store'", doc)

    def test_loading_and_error_states_present(self) -> None:
        doc = text(TRACKER)
        self.assertIn('id="loading-panel"', doc)
        self.assertIn("function renderError(", doc)
        self.assertIn("Retry now", doc)
        self.assertIn("chip-error", doc)
        self.assertIn("chip-live", doc)

    def test_status_legend_present(self) -> None:
        doc = text(TRACKER)
        for label in ("Shipped / Activated", "In progress", "Blocked", "Frozen", "Designed", "Not started"):
            self.assertIn(label, doc)

    def test_program_rollup_route_wired_into_main(self) -> None:
        doc = text(MAIN)
        self.assertIn("from .routes import pm as pm_mod", doc)
        self.assertIn('app.include_router(pm_mod.router, prefix="/api", tags=["pm"])', doc)

    def test_pm_route_shells_out_not_imports_projection(self) -> None:
        """Same BARE-python posture as approvals.py: never import aq-pm-tracker's
        project() at module load — shell out so the dashboard backend's
        narrower deps never couple to the CLI's runtime."""
        doc = text(PM_ROUTE)
        self.assertIn('"--all-json"', doc)
        self.assertIn("create_subprocess_exec", doc)
        self.assertIn('@router.get("/pm/progress")', doc)
        self.assertNotIn("from aq", doc)  # never import the CLI as a module

    def test_aq_pm_tracker_aggregate_mode_exists(self) -> None:
        doc = text(PM_TRACKER_CLI)
        self.assertIn("--all-json", doc)
        self.assertIn("def project_all(", doc)
        self.assertIn("def discover_tracked_plans(", doc)
        self.assertIn('"program_rollup_pct"', doc)

    def test_accessible_and_reduced_motion(self) -> None:
        doc = text(TRACKER)
        self.assertIn('aria-live="polite"', doc)
        self.assertIn("@media (prefers-reduced-motion: reduce)", doc)

    def test_dependency_map_and_status_board_contract(self) -> None:
        """The operational projections remain live-data driven and safe for old manifests."""
        doc = text(TRACKER)
        for token in (
            'data-item-id="${escapeHtml(item.itemId)}"',
            "function renderDependencyArrows(data)",
            "function planMarkerId(planId)",
            "dependency-arrow-${codePoints.length ? codePoints.join('-') : 'empty'}",
            'marker-end="url(#${markerId})"',
            'marker id="${markerId}"',
            "item.deps.map(dep => [dep, item.id])",
            "if (!dependency) return '';",
            "if (!source || !target) return '';",
            "window.addEventListener('resize'",
            "function renderKanban(data)",
            "STATUS_ORDER.map(status => [status, []])",
            "STATUS_ORDER.map(status => {",
            "item.priorityLane ?",
            "priority-lane",
            "Array.isArray(item && item.deps)",
        ):
            self.assertIn(token, doc, token)

    def test_dependency_and_kanban_oracle(self) -> None:
        plans = [{
            "id": "plan-a",
            "items": [
                {"id": "seed", "status": "IN-PROGRESS"},
                {"id": "build", "status": "BLOCKED", "deps": ["seed"], "priority_lane": "gated-Q3"},
                {"id": "orphan", "deps": ["missing"], "priority_lane": None},
                {"id": "legacy", "status": "UNKNOWN"},
            ],
        }]
        memberships, edges = dashboard_render_oracle(plans)
        self.assertEqual(len(memberships), 4)
        self.assertEqual([entry[0] for entry in memberships], ["plan-a:seed", "plan-a:build", "plan-a:orphan", "plan-a:legacy"])
        self.assertEqual([entry[1] for entry in memberships], ["IN-PROGRESS", "BLOCKED", "NOT-STARTED", "NOT-STARTED"])
        self.assertEqual(edges, [("plan-a:seed", "plan-a:build")])
        self.assertEqual(memberships[1][2], "gated-Q3")
        self.assertEqual(memberships[0][2], "")
        self.assertTrue(all("undefined" not in value and "null" not in value for entry in memberships for value in entry))

    def test_plan_scoped_marker_oracle(self) -> None:
        """Distinct plan graphs never reuse an SVG document ID or fragment ref."""
        plan_ids = ["alpha", "alpha/beta", "alpha-2f-beta", ""]
        marker_ids = [dependency_marker_id(plan_id) for plan_id in plan_ids]
        self.assertEqual(len(marker_ids), len(set(marker_ids)))
        self.assertEqual(marker_ids[0], "dependency-arrow-61-6c-70-68-61")
        self.assertEqual(marker_ids[1], "dependency-arrow-61-6c-70-68-61-2f-62-65-74-61")
        self.assertEqual(marker_ids[2], "dependency-arrow-61-6c-70-68-61-2d-32-66-2d-62-65-74-61")
        self.assertEqual(marker_ids[3], "dependency-arrow-empty")
        fragment_refs = [f"url(#{marker_id})" for marker_id in marker_ids]
        self.assertEqual(len(fragment_refs), len(set(fragment_refs)))
        self.assertTrue(all(ref.startswith("url(#dependency-arrow-") for ref in fragment_refs))

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
        self.assertIn("/api/pm/progress", body)
        for path in ("/", "/assets/dashboard.js"):
            status, headers, _ = self.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("x-frame-options"), "DENY")
            self.assertIn("frame-ancestors 'none'", headers.get("content-security-policy", ""))

    def test_live_pm_progress_endpoint(self) -> None:
        status, _headers, body = self.get("/api/pm/progress")
        self.assertEqual(status, 200)
        import json
        data = json.loads(body)
        self.assertIn("plans", data)
        self.assertIn("program_rollup_pct", data)
        self.assertIsInstance(data["plans"], list)
        for plan in data["plans"]:
            self.assertIsInstance(plan.get("id"), str)
            self.assertIsInstance(plan.get("items"), list)
            for item in plan["items"]:
                for field in ("id", "name", "status", "pct"):
                    self.assertIn(field, item)
                self.assertIsInstance(item["id"], str)
                self.assertIsInstance(item["name"], str)
                self.assertIsInstance(item["status"], str)
                self.assertIsInstance(item["deps"], list)
                self.assertTrue(item.get("priority_lane") is None or isinstance(item.get("priority_lane"), str))


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
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionProvenanceTests))
    if not args.static_only:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(LiveHeaderTests))
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
