#!/usr/bin/env python3
"""Regression coverage for the read-only session size diagnostic."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "ai" / "aq-session-compact"
SPEC = importlib.util.spec_from_loader("aq_session_compact", SourceFileLoader("aq_session_compact", str(SCRIPT)))
COMPACTOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(COMPACTOR)


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


class SessionCompactTests(unittest.TestCase):
    def test_native_compaction_requires_measured_reduction(self):
        def usage(n):
            return {"type": "token_usage_record", "payload": {"usage": {"input_tokens": n}}}
        compact = {"type": "compacted", "payload": {}}
        cases = [([], "unknown"), ([usage(80000)], "handoff_required"),
                 ([usage(30000)], "within_budget_unverified"),
                 ([usage(80000), compact], "awaiting_post_compaction_measurement"),
                 ([usage(80000), compact, usage(30000)], "verified_reduction"),
                 ([usage(80000), compact, usage(75000)], "handoff_required"),
                 ([usage(80000), compact, usage(30000), usage(60000)], "handoff_required"),
                 ([usage(80000), compact, usage(30000), compact], "awaiting_post_compaction_measurement")]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "rollout.jsonl"
            for records, expected in cases:
                write_jsonl(p, records)
                original = p.read_bytes()
                self.assertEqual(COMPACTOR.verify_rollout(p, 50000)["status"], expected)
                self.assertEqual(p.read_bytes(), original)

    def test_guard_is_provider_neutral_and_rejects_unmeasured_success(self):
        for provider in ("codex", "claude", "gemini", "local", "future-model"):
            data = {"provider": provider, "session_id": "fixture", "input_tokens": 30000,
                    "context_window_tokens": 200000, "before_input_tokens": 80000,
                    "compaction_observed": True, "before_request_sequence": 1, "request_sequence": 2}
            self.assertEqual(COMPACTOR.verify_usage(data, 50000)["status"], "verified_reduction")
            self.assertEqual(COMPACTOR.verify_usage({**data, "request_sequence": 1}, 50000)["status"], "within_budget_unverified")
            self.assertEqual(COMPACTOR.verify_usage({**data, "input_tokens": 70000}, 50000)["status"], "handoff_required")
            self.assertEqual(COMPACTOR.verify_usage({**data, "context_window_tokens": 8192}, 50000)["status"], "handoff_required")
            self.assertEqual(COMPACTOR.verify_usage({**data, "input_tokens": True}, 50000)["status"], "unknown")
        self.assertEqual(COMPACTOR.verify_usage({}, 50000)["status"], "unknown")

    def test_claude_record_is_reported_without_mutating_any_session_state(self):
        repo = Path(__file__).resolve().parents[2]
        encoded_repo = str(repo).replace("/", "-")
        resume = repo / ".agent" / "collaboration" / "RESUME.json"
        pulse = repo / ".agent" / "collaboration" / "PULSE.log"
        resume_before = resume.read_bytes() if resume.exists() else None
        pulse_before = pulse.read_bytes() if pulse.exists() else None

        with tempfile.TemporaryDirectory() as home_name:
            home = Path(home_name)
            claude_dir = home / ".claude" / "projects" / encoded_repo
            user_record = {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Continue the current task." * 100}],
                },
            }
            transcript = claude_dir / "claude-session-full-id.jsonl"
            write_jsonl(transcript, [user_record])
            # A valid Claude record with enough data to pass the small fixture limit.
            threshold = 10
            results = COMPACTOR.scan_claude(home, repo, threshold)
            self.assertEqual([entry["session_id"] for entry in results], ["claude-session-full-id"])
            self.assertTrue(transcript.is_file())
            self.assertFalse((claude_dir / "archive").exists())

            env = dict(os.environ, HOME=home_name)
            for extra_args in ([], ["--dry-run"]):
                result = subprocess.run(
                    [str(SCRIPT), "--agent", "claude", "--threshold-mb", "0.00001", *extra_args],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("claude-session-full-id", result.stdout)
                self.assertIn("provider's native compaction", result.stdout)
                self.assertTrue(transcript.is_file())
                self.assertFalse((claude_dir / "archive").exists())

        self.assertEqual(resume.read_bytes() if resume.exists() else None, resume_before)
        self.assertEqual(pulse.read_bytes() if pulse.exists() else None, pulse_before)

    def test_codex_requires_matching_repository_metadata_and_keeps_full_id(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            home = base / "home"
            repo = base / "repo"
            repo.mkdir()
            sessions = home / ".codex" / "sessions"
            full_id = "12345678-1234-5678-9abc-def012345678"
            records = [{"type": "session_meta", "payload": {"id": full_id, "cwd": str(repo)}}]
            current = sessions / "2026" / "rollout-current.jsonl"
            write_jsonl(current, records)
            with current.open("a", encoding="utf-8") as stream:
                stream.write("x" * 100 + "\n")

            foreign = sessions / "2026" / "rollout-foreign.jsonl"
            write_jsonl(foreign, [{"type": "session_meta", "payload": {"id": "foreign-id", "cwd": str(base / "other")}}])
            unknown = sessions / "2026" / "rollout-unknown.jsonl"
            write_jsonl(unknown, [{"type": "event_msg", "payload": {"cwd": str(repo)}}])
            missing_id = sessions / "2026" / "rollout-full-file-derived-id.jsonl"
            write_jsonl(missing_id, [{"type": "session_meta", "payload": {"cwd": str(repo)}}])
            with missing_id.open("a", encoding="utf-8") as stream:
                stream.write("y" * 100)

            results = COMPACTOR.scan_codex(home, repo, 10)
            ids = {entry["session_id"] for entry in results}
            self.assertEqual(ids, {full_id, "full-file-derived-id"})
            self.assertTrue(current.exists())
            self.assertTrue(foreign.exists())
            self.assertTrue(unknown.exists())
            self.assertFalse((sessions / "archive").exists())
            # Codex scanning is independent of state_5.sqlite.
            self.assertFalse((home / ".codex" / "state_5.sqlite").exists())

    def test_invalid_thresholds_fail_at_cli_boundary(self):
        for value in ("0", "-1", "nan", "inf", "-inf", "not-a-number"):
            result = subprocess.run(
                [str(SCRIPT), f"--threshold-mb={value}"], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 2, (value, result.stderr))
            self.assertIn("finite positive number", result.stderr)


if __name__ == "__main__":
    unittest.main()
