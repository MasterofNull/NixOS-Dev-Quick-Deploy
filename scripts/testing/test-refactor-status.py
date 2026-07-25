#!/usr/bin/env python3
"""Offline tests for scripts/ai/lib/refactor_status.py + scripts/ai/aq-refactor-status.

Builds a fixture manifest + fixture signals (a temp repo_root with its own
.agents/events/ and .agent/collaboration/slice-claims/, and a monkeypatched
git-log stub) so every status branch + the precedence rules + the --check
drift gate are exercised deterministically, with zero dependency on the
real repo's git history or event log.
"""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LIB_MODULE = REPO / "scripts/ai/lib/refactor_status.py"
CLI_MODULE = REPO / "scripts/ai/aq-refactor-status"

_spec = importlib.util.spec_from_file_location("refactor_status_under_test", LIB_MODULE)
assert _spec and _spec.loader
refactor_status = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = refactor_status
_spec.loader.exec_module(refactor_status)

# aq-refactor-status has no .py extension, so use SourceFileLoader directly
# (same pattern as test-agent-ops-projection.py's aq-tui-dashboard import).
_cli_file_loader = SourceFileLoader("aq_refactor_status_cli_under_test", str(CLI_MODULE))
_cli_loader = importlib.util.spec_from_loader(_cli_file_loader.name, _cli_file_loader)
assert _cli_loader and _cli_loader.loader
cli = importlib.util.module_from_spec(_cli_loader)
sys.modules[_cli_loader.name] = cli
# The CLI module inserts scripts/ai/lib onto sys.path and does `import
# refactor_status` at module-exec time; make sure that resolves to our
# already-loaded test module instead of re-importing (or shadowing) it.
sys.modules["refactor_status"] = refactor_status
_cli_loader.loader.exec_module(cli)


FIXTURE_SUBJECTS = [
    "feat(done-track): ship the done thing",
    "feat(ongoing-track): first slice of the ongoing thing",
    "docs(committed-but-blocked): design frozen and committed",
    "feat(claim-track): unrelated commit not touching status",
]


def _make_repo_root(tmp: Path) -> Path:
    (tmp / ".agents" / "events").mkdir(parents=True, exist_ok=True)
    (tmp / ".agent" / "collaboration" / "slice-claims").mkdir(parents=True, exist_ok=True)
    return tmp


def _write_events(repo_root: Path, events: list[dict]) -> None:
    path = repo_root / ".agents" / "events" / "test-events.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for evt in events:
            fh.write(json.dumps(evt) + "\n")


def _write_claim(repo_root: Path, name: str) -> None:
    path = repo_root / ".agent" / "collaboration" / "slice-claims" / f"{name}.claim"
    path.write_text("claimed\n", encoding="utf-8")


def _write_manifest(tmp: Path, tracks: list[dict], gate: list[dict] | None = None, issues: list[dict] | None = None) -> Path:
    manifest = {"tracks": tracks, "gate": gate or [], "issues": issues or []}
    path = tmp / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class ProjectorStatusBranches(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.repo_root = _make_repo_root(self.tmp)
        self._git_patch = mock.patch.object(
            refactor_status, "_git_log_subjects", return_value=list(FIXTURE_SUBJECTS)
        )
        self._git_patch.start()

    def tearDown(self) -> None:
        self._git_patch.stop()
        self._tmpdir.cleanup()

    def _project(self, tracks, gate=None, issues=None):
        manifest_path = _write_manifest(self.tmp, tracks, gate, issues)
        return refactor_status.project(manifest_path, self.repo_root)

    # -- individual branches ------------------------------------------------

    def test_notstarted_when_no_signal_matches(self) -> None:
        tracks = [{"code": "X", "name": "X", "order": 1, "detection": {"commit_match": ["nothing-matches-this"]}}]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "notstarted")
        self.assertEqual(t["pct"], 0)

    def test_done_via_commit_match_non_ongoing(self) -> None:
        tracks = [
            {
                "code": "DONE",
                "name": "Done track",
                "order": 1,
                "ongoing": False,
                "detection": {"commit_match": ["ship the done thing"]},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "done")
        self.assertEqual(t["pct"], 100)

    def test_active_via_commit_match_ongoing(self) -> None:
        tracks = [
            {
                "code": "ONGOING",
                "name": "Ongoing track",
                "order": 1,
                "ongoing": True,
                "pct": 42,
                "detection": {"commit_match": ["first slice of the ongoing thing"]},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "active")
        self.assertEqual(t["pct"], 42)

    def test_active_via_freeze_record_without_activation(self) -> None:
        freeze_path = self.tmp / "FREEZE.md"
        freeze_path.write_text("frozen\n", encoding="utf-8")
        tracks = [
            {
                "code": "FROZEN",
                "name": "Frozen track",
                "order": 1,
                "detection": {"commit_match": ["never-matches"], "freeze_record": "FREEZE.md"},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "active")

    def test_active_via_open_slice_claim(self) -> None:
        # Real slice-claim filenames are hyphen/underscore-delimited tokens
        # (e.g. "foundation-c-c0.claim"); the track code must match a WHOLE
        # token, never a bare substring (see _open_slice_claim docstring —
        # single-letter codes like "A" must not match every ephemeral
        # "local-<timestamp>-<random>.claim" dispatch file).
        _write_claim(self.repo_root, "some-round-claimtrack-slice")
        tracks = [
            {
                "code": "CLAIMTRACK",
                "name": "Claimed track",
                "order": 1,
                "detection": {"commit_match": ["never-matches"]},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "active")

    def test_slice_claim_does_not_substring_match_short_codes(self) -> None:
        # Regression test for the real bug found during manual validation:
        # single-letter codes ("A", "C", "D", ...) must NOT match against
        # unrelated claim filenames that merely happen to contain that
        # letter somewhere in an unrelated token.
        _write_claim(self.repo_root, "local-20260723-095012-zkqr9s")
        tracks = [
            {
                "code": "A",
                "name": "Foundation A",
                "order": 1,
                "detection": {"commit_match": ["never-matches"]},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "notstarted")

    def test_blocked_via_blocker_note_alone(self) -> None:
        tracks = [
            {
                "code": "BLK",
                "name": "Blocked track",
                "order": 1,
                "detection": {"commit_match": ["never-matches"], "blocker_note": "something is wrong"},
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "blocked")

    # -- precedence -----------------------------------------------------------

    def test_precedence_blocked_outranks_committed_and_frozen(self) -> None:
        """A milestone that is BOTH committed AND frozen AND blocked -> BLOCKED.

        This is the C2 scenario from the spec: BLOCKED must outrank FROZEN (and
        SHIPPED/done) so a real gap always surfaces instead of being masked by
        an otherwise-green status.
        """
        freeze_path = self.tmp / "FREEZE-C2-LIKE.md"
        freeze_path.write_text("frozen\n", encoding="utf-8")
        tracks = [
            {
                "code": "C2LIKE",
                "name": "C2-like track",
                "order": 1,
                "detection": {
                    "commit_match": ["design frozen and committed"],
                    "freeze_record": "FREEZE-C2-LIKE.md",
                    "blocker_note": "built-in-tool gap",
                },
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "blocked")

    def test_precedence_activation_outranks_freeze_and_commit(self) -> None:
        """Both a freeze record AND a matching owner activation event -> DONE.

        Activation is the final gate; once granted, a track should read as
        fully done even though its freeze record file is still present.
        """
        freeze_path = self.tmp / "FREEZE-ACTIVATED.md"
        freeze_path.write_text("frozen\n", encoding="utf-8")
        _write_events(
            self.repo_root,
            [
                {
                    "schema_version": 1,
                    "agent": "owner",
                    "type": "activation.grant",
                    "subject": "test-track-activation-subject",
                    "payload": {},
                }
            ],
        )
        tracks = [
            {
                "code": "ACT",
                "name": "Activated track",
                "order": 1,
                "detection": {
                    "commit_match": ["ship the done thing"],
                    "freeze_record": "FREEZE-ACTIVATED.md",
                    "activation_subject": "test-track-activation-subject",
                },
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        self.assertEqual(t["status"], "done")

    def test_activation_event_from_non_owner_agent_does_not_count(self) -> None:
        freeze_path = self.tmp / "FREEZE-NOTOWNER.md"
        freeze_path.write_text("frozen\n", encoding="utf-8")
        _write_events(
            self.repo_root,
            [
                {
                    "schema_version": 1,
                    "agent": "local",  # not "owner" -- must not count as activation
                    "type": "activation.grant",
                    "subject": "not-owner-subject",
                    "payload": {},
                }
            ],
        )
        tracks = [
            {
                "code": "NOTOWNER",
                "name": "Not-owner-activated track",
                "order": 1,
                "detection": {
                    "commit_match": ["never-matches"],
                    "freeze_record": "FREEZE-NOTOWNER.md",
                    "activation_subject": "not-owner-subject",
                },
            }
        ]
        result = self._project(tracks)
        t = result["tracks"][0]
        # freeze record present, activation not granted by owner -> active, not done
        self.assertEqual(t["status"], "active")

    # -- gate resolution --------------------------------------------------

    def test_gate_resolved_true_on_match(self) -> None:
        gate = [{"id": "QX", "decision": "d", "unblocks": "u", "detection": {"ratified_commit_match": ["never-matches", "design frozen and committed"]}}]
        result = self._project([], gate=gate)
        self.assertTrue(result["gate"][0]["resolved"])

    def test_gate_resolved_false_when_no_match(self) -> None:
        gate = [{"id": "QY", "decision": "d", "unblocks": "u", "detection": {"ratified_commit_match": ["absolutely-nothing-matches-this-string"]}}]
        result = self._project([], gate=gate)
        self.assertFalse(result["gate"][0]["resolved"])

    # -- issues + stats -----------------------------------------------------

    def test_issues_pass_through_and_stats_computed(self) -> None:
        tracks = [
            {"code": "D1", "name": "d1", "order": 1, "detection": {"commit_match": ["ship the done thing"]}},
            {"code": "B1", "name": "b1", "order": 2, "detection": {"blocker_note": "x"}},
        ]
        gate = [{"id": "Q1", "decision": "d", "unblocks": "u", "detection": {"ratified_commit_match": ["nope"]}}]
        issues = [{"title": "hi", "sev": "High", "note": "n"}, {"title": "med", "sev": "Med", "note": "n"}]
        result = self._project(tracks, gate=gate, issues=issues)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["stats"]["tracks_done_or_active"], 1)
        self.assertEqual(result["stats"]["blocking_gates"], 1)
        self.assertEqual(result["stats"]["decisions_pending"], 1)
        self.assertEqual(result["stats"]["open_high_issues"], 1)

    # -- robustness ---------------------------------------------------------

    def test_never_raises_on_missing_manifest(self) -> None:
        missing = self.tmp / "does-not-exist.json"
        result = refactor_status.project(missing, self.repo_root)
        self.assertEqual(result["tracks"], [])
        self.assertEqual(result["gate"], [])

    def test_never_raises_on_missing_events_dir(self) -> None:
        # repo_root without .agents/events at all
        bare = self.tmp / "bare-repo"
        bare.mkdir()
        tracks = [{"code": "X", "name": "x", "order": 1, "detection": {"commit_match": ["ship the done thing"]}}]
        manifest_path = _write_manifest(self.tmp, tracks)
        result = refactor_status.project(manifest_path, bare)
        self.assertEqual(result["tracks"][0]["status"], "done")

    def test_determinism_same_inputs_same_output(self) -> None:
        tracks = [{"code": "X", "name": "x", "order": 1, "ongoing": True, "detection": {"commit_match": ["ship the done thing"]}}]
        r1 = self._project(tracks)
        r2 = self._project(tracks)
        self.assertEqual(r1, r2)


class CliCheckDriftGate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.repo_root = _make_repo_root(self.tmp)
        self._git_patch = mock.patch.object(
            refactor_status, "_git_log_subjects", return_value=list(FIXTURE_SUBJECTS)
        )
        self._git_patch.start()
        self.tracks = [
            {"code": "X", "name": "x", "order": 1, "detection": {"commit_match": ["ship the done thing"]}}
        ]
        self.manifest_path = _write_manifest(self.tmp, self.tracks)

    def tearDown(self) -> None:
        self._git_patch.stop()
        self._tmpdir.cleanup()

    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), mock.patch.object(cli, "_REPO_ROOT", self.repo_root):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_check_passes_on_identical_projection(self) -> None:
        baseline = refactor_status.project(self.manifest_path, self.repo_root)
        baseline_path = self.tmp / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

        code, out, err = self._run_cli(
            ["--manifest", str(self.manifest_path), "--check", "--baseline", str(baseline_path)]
        )
        self.assertEqual(code, 0, msg=f"stdout={out} stderr={err}")

    def test_check_ignores_updated_date_only_difference(self) -> None:
        baseline = refactor_status.project(self.manifest_path, self.repo_root)
        baseline["updated"] = "2000-01-01"  # deliberately stale date, content unchanged
        baseline_path = self.tmp / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

        code, _out, _err = self._run_cli(
            ["--manifest", str(self.manifest_path), "--check", "--baseline", str(baseline_path)]
        )
        self.assertEqual(code, 0)

    def test_check_detects_hand_edit_drift(self) -> None:
        baseline = refactor_status.project(self.manifest_path, self.repo_root)
        baseline_path = self.tmp / "baseline.json"
        # Simulate a hand-edit: someone flipped a status in the captured JSON
        # without the underlying signal changing.
        baseline["tracks"][0]["status"] = "notstarted"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

        code, _out, err = self._run_cli(
            ["--manifest", str(self.manifest_path), "--check", "--baseline", str(baseline_path)]
        )
        self.assertEqual(code, 1)
        self.assertIn("DRIFT", err)

    def test_check_detects_drift_when_new_commit_lands(self) -> None:
        baseline = refactor_status.project(self.manifest_path, self.repo_root)
        baseline_path = self.tmp / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

        # A new commit lands that flips the track to done/blocked differently --
        # simulate by adding a blocker_note to the manifest (equivalent to new
        # ground truth appearing) and re-checking against the old baseline.
        tracks = [dict(self.tracks[0])]
        tracks[0]["detection"] = dict(tracks[0]["detection"])
        tracks[0]["detection"]["blocker_note"] = "newly discovered blocker"
        drifted_manifest_path = _write_manifest(self.tmp, tracks)

        code, _out, err = self._run_cli(
            ["--manifest", str(drifted_manifest_path), "--check", "--baseline", str(baseline_path)]
        )
        self.assertEqual(code, 1)
        self.assertIn("DRIFT", err)


class CliJsonAndRender(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.repo_root = _make_repo_root(self.tmp)
        self._git_patch = mock.patch.object(
            refactor_status, "_git_log_subjects", return_value=list(FIXTURE_SUBJECTS)
        )
        self._git_patch.start()
        tracks = [{"code": "X", "name": "x", "order": 1, "detection": {"commit_match": ["ship the done thing"]}}]
        self.manifest_path = _write_manifest(self.tmp, tracks)

    def tearDown(self) -> None:
        self._git_patch.stop()
        self._tmpdir.cleanup()

    def test_json_output_is_valid_json_with_expected_keys(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(cli, "_REPO_ROOT", self.repo_root):
            code = cli.main(["--manifest", str(self.manifest_path), "--json"])
        self.assertEqual(code, 0)
        parsed = json.loads(out.getvalue())
        for key in ("updated", "tracks", "gate", "issues", "stats"):
            self.assertIn(key, parsed)

    def test_render_output_is_nonempty_text(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(cli, "_REPO_ROOT", self.repo_root):
            code = cli.main(["--manifest", str(self.manifest_path), "render"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("TRACKS", text)
        self.assertIn("DECISION GATE", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
