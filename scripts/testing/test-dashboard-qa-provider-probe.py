#!/usr/bin/env python3
"""Focused offline tests for the A2 QA-provider-probe dashboard projection.

Covers design-packet sections 4.1 (bounded backend projection reader +
`projection_only=true` route branch) and 4.2 (existing-card UI wiring).
Entirely offline: no live provider process, no network, no real browser.
All heartbeat fixtures are synthetic files written under a temporary
REPO_ROOT; nothing here touches the real `.agent/qa/` state or invokes
qa-provider-probe.py.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))
os.environ.setdefault("DASHBOARD_MODE", "test")

from api.services import qa_runner  # noqa: E402
from api.routes import aistack  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _baseline_heartbeat(**overrides: object) -> dict:
    base = {
        "schema_version": "qa.provider-probe-active.v1",
        "qa_invocation_id": "8d363559-e25d-4dbc-be8f-4822346240fe",
        "provider_id": "pi",
        "lifecycle_state": "terminal",
        "elapsed_ms": 1727,
        "heartbeat_utc": _iso(datetime.now(timezone.utc)),
        "deadline_ms": 45000,
        "last_terminal_failure_class": "none",
    }
    base.update(overrides)
    return base


class _RepoRootSandbox:
    """Points qa_runner._repo_root() at a scratch dir with .agent/qa/."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="qppr-a2-projection-")
        self.root = Path(self._tmp.name)
        self.qa_dir = self.root / ".agent" / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path = self.qa_dir / "provider-probe-active.json"
        self._prev_repo_root = os.environ.get("REPO_ROOT")
        self._prev_confined = os.environ.get("AQ_QA_DASHBOARD_SAFE")
        os.environ["REPO_ROOT"] = str(self.root)
        os.environ.pop("AQ_QA_DASHBOARD_SAFE", None)

    def write(self, obj: object) -> None:
        self.heartbeat_path.write_text(json.dumps(obj), encoding="utf-8")

    def write_raw(self, text: str) -> None:
        self.heartbeat_path.write_text(text, encoding="utf-8")

    def remove(self) -> None:
        if self.heartbeat_path.exists() or self.heartbeat_path.is_symlink():
            self.heartbeat_path.unlink()

    def set_confined(self, value: bool) -> None:
        if value:
            os.environ["AQ_QA_DASHBOARD_SAFE"] = "1"
        else:
            os.environ.pop("AQ_QA_DASHBOARD_SAFE", None)

    def close(self) -> None:
        if self._prev_repo_root is None:
            os.environ.pop("REPO_ROOT", None)
        else:
            os.environ["REPO_ROOT"] = self._prev_repo_root
        if self._prev_confined is None:
            os.environ.pop("AQ_QA_DASHBOARD_SAFE", None)
        else:
            os.environ["AQ_QA_DASHBOARD_SAFE"] = self._prev_confined
        self._tmp.cleanup()


def test_missing_file_is_unavailable(sbx: _RepoRootSandbox) -> None:
    sbx.remove()
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "missing heartbeat must be unavailable")
    assert_true(proj["lifecycle_state"] == "unavailable", "missing heartbeat lifecycle_state must be 'unavailable'")
    assert_true(proj["provider_id"] is None, "missing heartbeat must not report a provider_id")
    assert_true(proj["freshness_ms"] is None, "missing heartbeat must not report freshness_ms")
    assert_true(proj["host_execution"] == "unavailable", "missing heartbeat host_execution must be unavailable")


def test_malformed_json_is_unavailable(sbx: _RepoRootSandbox) -> None:
    sbx.write_raw("{not valid json")
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "malformed JSON must be unavailable")


def test_unknown_field_is_rejected(sbx: _RepoRootSandbox) -> None:
    obj = _baseline_heartbeat()
    obj["extra_unexpected_field"] = "x"
    sbx.write(obj)
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "unknown/extra field must be rejected as unbound")


def test_wrong_schema_version_is_rejected(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(schema_version="qa.provider-probe-active.v2"))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "foreign schema_version must be rejected")


def test_invalid_provider_enum_is_rejected(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(lifecycle_state="running", provider_id="not_a_real_provider", last_terminal_failure_class=None))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "invalid provider_id enum must be rejected")


def test_invalid_uuid_is_rejected(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(qa_invocation_id="not-a-uuid"))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "malformed invocation id must be rejected")


def test_symlinked_target_is_rejected(sbx: _RepoRootSandbox) -> None:
    sbx.remove()
    real_target = sbx.qa_dir / "real-heartbeat.json"
    real_target.write_text(json.dumps(_baseline_heartbeat()), encoding="utf-8")
    os.symlink(real_target, sbx.heartbeat_path)
    try:
        proj = qa_runner.get_provider_probe_projection()
        assert_true(proj["availability"] == "unavailable", "symlinked heartbeat target must be rejected")
    finally:
        sbx.remove()
        real_target.unlink()


def test_oversized_file_is_rejected(sbx: _RepoRootSandbox) -> None:
    padding = " " * (qa_runner._PROBE_ACTIVE_MAX_BYTES + 4096)
    sbx.write_raw(padding + json.dumps(_baseline_heartbeat()))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "oversized heartbeat file must be rejected")


def test_future_dated_is_unavailable(sbx: _RepoRootSandbox) -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    sbx.write(_baseline_heartbeat(heartbeat_utc=_iso(future)))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "unavailable", "future-dated heartbeat must never be trusted")


def test_fresh_terminal_is_current(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(lifecycle_state="terminal", provider_id="claude", last_terminal_failure_class="none"))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "current", "fresh valid heartbeat must be current")
    assert_true(proj["lifecycle_state"] == "terminal", "terminal state must pass through")
    assert_true(proj["provider_id"] == "claude", "provider_id must pass through")
    assert_true(proj["last_failure_class"] == "none", "last_failure_class must pass through")
    assert_true(proj["host_execution"] == "terminal", "non-confined terminal heartbeat must report host_execution=terminal")
    assert_true(isinstance(proj["freshness_ms"], int) and proj["freshness_ms"] < qa_runner._PROBE_FRESHNESS_MS, "fresh heartbeat freshness_ms must be small")


def test_running_is_active_host_execution(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(lifecycle_state="running", provider_id="qwen", last_terminal_failure_class=None))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "current", "fresh running heartbeat must be current")
    assert_true(proj["host_execution"] == "active", "non-terminal non-confined heartbeat must report host_execution=active")


def test_idle_state_nulls_provider(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(lifecycle_state="idle", provider_id=None, last_terminal_failure_class=None, elapsed_ms=0))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "current", "idle heartbeat must still be a valid current projection")
    assert_true(proj["provider_id"] is None, "idle state must report provider_id=null")


def test_stale_data_still_renders_last_known_values(sbx: _RepoRootSandbox) -> None:
    old = datetime.now(timezone.utc) - timedelta(seconds=10)
    sbx.write(_baseline_heartbeat(heartbeat_utc=_iso(old), lifecycle_state="terminal", provider_id="codex", last_terminal_failure_class="deadline_exceeded"))
    proj = qa_runner.get_provider_probe_projection()
    assert_true(proj["availability"] == "stale", "heartbeat older than the 5s freshness ceiling must be stale")
    assert_true(proj["provider_id"] == "codex", "stale data must still surface the last known provider_id (evidence exists)")
    assert_true(proj["last_failure_class"] == "deadline_exceeded", "stale data must still surface the last known failure class")


def test_dashboard_confinement_overrides_host_execution(sbx: _RepoRootSandbox) -> None:
    sbx.remove()
    sbx.set_confined(True)
    try:
        proj = qa_runner.get_provider_probe_projection()
        assert_true(proj["host_execution"] == "dashboard_confined_skip", "dashboard-confined reads must report dashboard_confined_skip even with no heartbeat")
        sbx.write(_baseline_heartbeat(lifecycle_state="terminal"))
        proj = qa_runner.get_provider_probe_projection()
        assert_true(proj["host_execution"] == "dashboard_confined_skip", "dashboard-confined reads must report dashboard_confined_skip regardless of a valid terminal heartbeat")
    finally:
        sbx.set_confined(False)


async def _run_projection_route(phase: str, projection_only: bool):
    return await aistack.run_aq_qa_phase(phase, projection_only=projection_only)


def test_route_projection_only_short_circuits(sbx: _RepoRootSandbox) -> None:
    sbx.write(_baseline_heartbeat(lifecycle_state="terminal", provider_id="pi"))
    aistack._AQ_QA_CACHE.clear()
    aistack._AQ_QA_RUNNING.clear()
    cache_before = dict(aistack._AQ_QA_CACHE)
    running_before = dict(aistack._AQ_QA_RUNNING)

    payload = asyncio.run(_run_projection_route("0", True))

    assert_true(payload["phase"] == "0", "projection_only response must report phase 0")
    assert_true(payload["projection_only"] is True, "projection_only response must echo projection_only=true")
    assert_true("provider_probe" in payload, "projection_only response must carry provider_probe")
    assert_true(payload["provider_probe"]["provider_id"] == "pi", "projection_only response must reflect the bounded reader's output")
    assert_true("passed" not in payload and "tests" not in payload, "projection_only response must not carry QA result/evidence fields")
    assert_true(dict(aistack._AQ_QA_CACHE) == cache_before, "projection_only must never populate the QA cache")
    assert_true(dict(aistack._AQ_QA_RUNNING) == running_before, "projection_only must never mark a background QA run as running")


def test_route_projection_only_ignored_for_other_phases(sbx: _RepoRootSandbox) -> None:
    aistack._AQ_QA_CACHE.clear()
    aistack._AQ_QA_CACHE["1"] = {
        "payload": {"phase": "1", "passed": 3, "failed": 0, "skipped": 0, "tests": []},
        "cached_at": __import__("time").time(),
    }
    payload = asyncio.run(_run_projection_route("1", True))
    assert_true("provider_probe" not in payload, "projection_only must only short-circuit phase 0")
    assert_true(payload.get("passed") == 3, "phase 1 must still return the ordinary cached QA payload")


def test_dashboard_html_has_exactly_six_probe_rows() -> None:
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    required_ids = [
        "qaProbeProvider",
        "qaProbeState",
        "qaProbeElapsed",
        "qaProbeFailureClass",
        "qaProbeFreshness",
        "qaProbeInvocation",
    ]
    for row_id in required_ids:
        assert_true(f'id="{row_id}"' in html, f"QA Phase 0 Status card must expose #{row_id}")
    for label in ("Active Provider", "Probe State", "Probe Elapsed", "Last Failure Class", "Heartbeat Freshness", "Evidence Invocation"):
        assert_true(f'<span class="fk">{label}</span>' in html, f"probe row must carry visible label '{label}'")
    card_html = _slice_between(html, "QA Phase 0 Status", "Runtime Summary")
    assert_true("innerHTML" not in card_html, "QA Phase 0 Status card must not use innerHTML for projection rows")
    # 5 pre-existing rows (Passed/Failed/Skipped/Duration/Result) + 6 new probe rows = 11.
    assert_true(card_html.count('class="fw-row"') == 11, "QA Phase 0 Status card must have exactly 5 pre-existing + 6 new probe rows")


def _slice_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_dashboard_js_has_bounded_single_flight_poller() -> None:
    js = (ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    assert_true("/aistack/aq-qa/run/0?projection_only=true" in js, "poller must call the projection_only route")
    assert_true("function _qaProbePollOnce" in js, "poller function must exist")
    assert_true("_qaProbeInFlight" in js, "poller must track single-flight in-progress state")
    assert_true("new AbortController()" in _slice_between(js, "function _qaProbePollOnce", "function _qaProbeScheduleNext"), "poller must use its own AbortController")
    assert_true("_qaProbeController.abort()" in js, "poller must be able to cancel a superseded request")
    assert_true("setTimeout(() => ctrl.abort(), 750)" in js, "poller request must carry a 750ms deadline")
    assert_true("activeLens === \"operations\"" in js, "poller visibility check must gate on the Operations panel")
    assert_true("document.hidden" in js, "poller visibility check must respect document.hidden")
    assert_true("? 1000 : 2000" in js, "poller must switch between the 1s active / 2s idle cadence")
    assert_true("qaProbeNotifyVisibility()" in js and "setLens" in _slice_between(js, "function setLens", "qaProbeNotifyVisibility()"), "setLens must notify the poller on lens switches")
    assert_true('document.addEventListener("visibilitychange", qaProbeNotifyVisibility)' in js, "poller must resume/stop on document visibility changes")
    assert_true("setText(\"qaProbeProvider\"" in js, "poller must render via setText (no innerHTML) for projection fields")
    assert_true("innerHTML" not in _slice_between(js, "function _qaProbeRenderState", "function _qaProbePollOnce"), "projection rendering must never use innerHTML")
    assert_true("loadQA()" not in _slice_between(js, "_qaProbePollOnce", "_qaProbeScheduleNext"), "dedicated poller must never call loadQA()/the active QA route")


def test_dashboard_js_poller_cadence_semantics() -> None:
    """R3 (A2 revision): assert cadence SEMANTICS, not merely the literal
    "? 1000 : 2000" substring. That literal check passed even when the
    predicate polled `idle` and non-terminal `stale` states at 1s instead of
    the design-mandated 2s (the defect fixed in this revision), because it
    never exercised the branch condition against real probe states.

    This test executes the actual `_qaProbeRenderState` function body
    (extracted verbatim from assets/dashboard.js) under node against
    representative probe fixtures and asserts the resulting `_qaProbeActive`
    flag (which feeds `setTimeout(_qaProbePollOnce, _qaProbeActive ? 1000 :
    2000)`) is true (1s) only when genuinely active, false (2s) for idle,
    terminal, stale, and unavailable — per design §4.2.
    """
    js = (ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    fn_src = _slice_between(js, "function _qaProbeRenderState", "async function _qaProbePollOnce")
    assert_true("_qaProbeActive" in fn_src, "cadence flag must be set inside _qaProbeRenderState")
    assert_true(
        '!["terminal", "unavailable"].includes(' not in fn_src,
        "predicate must not regress to the availability-blind terminal/unavailable-only check",
    )

    cases = [
        ({"availability": "current", "lifecycle_state": "running"}, True, "current+running must poll at 1s (active)"),
        ({"availability": "current", "lifecycle_state": "starting"}, True, "current+starting must poll at 1s (active)"),
        ({"availability": "current", "lifecycle_state": "idle"}, False, "idle must poll at 2s even when availability is current"),
        ({"availability": "current", "lifecycle_state": "terminal"}, False, "terminal must poll at 2s even when availability is current"),
        ({"availability": "current", "lifecycle_state": "unavailable"}, False, "unavailable lifecycle_state must poll at 2s"),
        ({"availability": "stale", "lifecycle_state": "running"}, False, "stale availability must poll at 2s regardless of lifecycle_state"),
        ({"availability": "unavailable", "lifecycle_state": "running"}, False, "unavailable availability must poll at 2s"),
        ({}, False, "empty/missing probe must default to 2s (unavailable)"),
    ]

    node = shutil.which("node")
    assert_true(node is not None, "node (declared Nix system package) is required to execute real cadence semantics")

    harness = (
        "let _qaProbeActive = false;\n"
        "function setText() {}\n"
        "const document = { getElementById: () => null };\n"
        f"{fn_src}\n"
        f"const cases = {json.dumps([c[0] for c in cases])};\n"
        "const results = cases.map((c) => { _qaProbeRenderState(c); return _qaProbeActive; });\n"
        "process.stdout.write(JSON.stringify(results));\n"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(harness)
        harness_path = f.name
    try:
        proc = subprocess.run([node, harness_path], capture_output=True, text=True, timeout=10)
        assert_true(proc.returncode == 0, f"node execution of extracted poller predicate failed: {proc.stderr}")
        actual = json.loads(proc.stdout.strip())
    finally:
        os.unlink(harness_path)

    assert_true(len(actual) == len(cases), "node harness must return one result per cadence case")
    for (probe, expected, message), got in zip(cases, actual):
        assert_true(got == expected, f"{message} (probe={probe!r}, expected active={expected}, got={got})")

    assert_true("_qaProbeActive ? 1000 : 2000" in js, "scheduler must still branch 1s/2s on the cadence flag")


def main() -> int:
    sbx = _RepoRootSandbox()
    try:
        test_missing_file_is_unavailable(sbx)
        test_malformed_json_is_unavailable(sbx)
        test_unknown_field_is_rejected(sbx)
        test_wrong_schema_version_is_rejected(sbx)
        test_invalid_provider_enum_is_rejected(sbx)
        test_invalid_uuid_is_rejected(sbx)
        test_symlinked_target_is_rejected(sbx)
        test_oversized_file_is_rejected(sbx)
        test_future_dated_is_unavailable(sbx)
        test_fresh_terminal_is_current(sbx)
        test_running_is_active_host_execution(sbx)
        test_idle_state_nulls_provider(sbx)
        test_stale_data_still_renders_last_known_values(sbx)
        test_dashboard_confinement_overrides_host_execution(sbx)
        test_route_projection_only_short_circuits(sbx)
        test_route_projection_only_ignored_for_other_phases(sbx)
        test_dashboard_html_has_exactly_six_probe_rows()
        test_dashboard_js_has_bounded_single_flight_poller()
        test_dashboard_js_poller_cadence_semantics()
    finally:
        sbx.close()

    print("PASS: A2 QA-provider-probe dashboard projection (reader + route + card + poller) behaves as designed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
