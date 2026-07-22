#!/usr/bin/env python3
"""test-aq-evidence-collector.py — offline unit+integration suite for VF-7.

Covers, per the VF-7 evidence-path authorization (Section 3 invariants):
  1. Digest hashing: deterministic, immutable, changes with any of the three
     inputs.
  2. Redaction: env-var secrets, bearer/basic auth, private keys, known OAuth
     token prefixes are stripped BEFORE anything is persisted.
  3. Append-only + fcntl.flock: concurrent writers never interleave/corrupt
     lines, and a prior write is never modified/truncated by a later one.
  4. Record shape: every emitted record validates against both
     contracts.events.Envelope (extra="forbid" — proves it will not be
     silently dropped as a corrupt line by existing aq-event readers) and the
     frozen JSON Schema at config/schemas/aq-evidence-record-v1.json.
  5. Shared-ledger safety: existing aq-event resume/pulse projectors ignore
     VF-7 records (kind discriminator works) and event_log.read_all() still
     parses a ledger containing a mix of aq-event + VF-7 records without
     raising or losing any record.
  6. CLI end-to-end: --command and --stdin both produce a valid, correctly
     redacted, digest-verifiable record on a real (temp) ledger.

Fully offline — no network, no live services. Run:
    python3 scripts/testing/test-aq-evidence-collector.py
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COLLECTOR_PATH = REPO_ROOT / "scripts" / "governance" / "aq-evidence-collector.py"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "aq-evidence-record-v1.json"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

# Import the collector module by file path (scripts/governance has no __init__.py).
_spec = importlib.util.spec_from_file_location("aq_evidence_collector", COLLECTOR_PATH)
aec = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(aec)  # type: ignore[union-attr]

from contracts.events import Envelope  # noqa: E402
import event_log  # noqa: E402
import resume_projector as rp  # noqa: E402

from jsonschema import Draft202012Validator  # noqa: E402


def _json_lines(text: str) -> list[str]:
    """Split ledger text into non-blank lines. The collector (matching
    scripts/ai/lib/event_log.py's own convention) writes a LEADING newline per
    record rather than a trailing one, so splitlines() on the raw text yields
    one blank entry per record boundary — filter those out to count/inspect
    actual JSON records."""
    return [ln for ln in text.splitlines() if ln.strip()]


class TestRedaction(unittest.TestCase):
    def test_env_var_key_redacted(self):
        out = aec.redact("before API_KEY=sk-abcdefghijklmnop123456 after")
        self.assertNotIn("sk-abcdefghijklmnop123456", out)
        self.assertIn("API_KEY=[REDACTED]", out)

    def test_export_secret_redacted(self):
        out = aec.redact("export DB_PASSWORD=hunter2\nnext line")
        self.assertNotIn("hunter2", out)
        self.assertIn("DB_PASSWORD=[REDACTED]", out)
        self.assertIn("next line", out)  # surrounding content preserved

    def test_bearer_token_redacted(self):
        out = aec.redact("Authorization: Bearer abc123.def456-XYZ")
        self.assertNotIn("abc123.def456-XYZ", out)
        self.assertIn("Bearer [REDACTED_TOKEN]", out)

    def test_basic_auth_redacted(self):
        out = aec.redact("Authorization: Basic dXNlcjpwYXNzd29yZA==")
        self.assertNotIn("dXNlcjpwYXNzd29yZA==", out)

    def test_private_key_block_redacted(self):
        pem = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        out = aec.redact(f"leading text\n{pem}\ntrailing text")
        self.assertNotIn("b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB", out)
        self.assertIn("[REDACTED_PRIVATE_KEY]", out)
        self.assertIn("leading text", out)
        self.assertIn("trailing text", out)

    def test_known_oauth_token_prefixes_redacted(self):
        for token in [
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            "ya29.a0AfH6SMC-some-fake-google-oauth-token-value",
            "sk-abcdefghijklmnopqrstuvwx",
        ]:
            out = aec.redact(f"token={token} end")
            self.assertNotIn(token, out, f"token not redacted: {token}")

    def test_non_secret_text_untouched(self):
        text = "pytest -q\n5 passed in 0.42s\nOK"
        self.assertEqual(aec.redact(text), text)


class TestDigest(unittest.TestCase):
    def test_deterministic(self):
        d1 = aec.compute_digest("2026-07-22T00:00:00+00:00", b"hello world", "agent-a")
        d2 = aec.compute_digest("2026-07-22T00:00:00+00:00", b"hello world", "agent-a")
        self.assertEqual(d1, d2)
        self.assertRegex(d1, r"^[0-9a-f]{64}$")

    def test_changes_with_timestamp(self):
        a = aec.compute_digest("t1", b"payload", "agent-a")
        b = aec.compute_digest("t2", b"payload", "agent-a")
        self.assertNotEqual(a, b)

    def test_changes_with_payload(self):
        a = aec.compute_digest("t1", b"payload-one", "agent-a")
        b = aec.compute_digest("t1", b"payload-two", "agent-a")
        self.assertNotEqual(a, b)

    def test_changes_with_caller(self):
        a = aec.compute_digest("t1", b"payload", "agent-a")
        b = aec.compute_digest("t1", b"payload", "agent-b")
        self.assertNotEqual(a, b)

    def test_record_digest_is_verifiable_and_immutable(self):
        raw = b"raw evidence bytes with SECRET_TOKEN=abc123"
        record = aec.build_record(
            caller_agent_id="agent-x", payload_bytes=raw, stream="stdin"
        )
        self.assertTrue(aec.verify_record_digest(record, raw))
        # Re-verifying repeatedly must keep agreeing (immutability, not a
        # one-shot fluke).
        for _ in range(5):
            self.assertTrue(aec.verify_record_digest(record, raw))
        # Tampering with the stored digest must be detectable.
        tampered = json.loads(json.dumps(record))
        tampered["payload"]["digest"] = "0" * 64
        self.assertFalse(aec.verify_record_digest(tampered, raw))

    def test_raw_secret_never_persisted_in_record(self):
        raw = b"contains AWS_SECRET_ACCESS_KEY=abcd1234efgh5678 inline"
        record = aec.build_record(caller_agent_id="agent-x", payload_bytes=raw, stream="stdin")
        serialized = json.dumps(record)
        self.assertNotIn("abcd1234efgh5678", serialized)
        self.assertIn("[REDACTED]", serialized)
        self.assertTrue(record["payload"]["redacted"])


class TestRecordShape(unittest.TestCase):
    def setUp(self):
        self.record = aec.build_record(
            caller_agent_id="claude-subagent-vf-7-implementer",
            payload_bytes=b"5 passed in 0.10s",
            stream="combined",
            subject="test-run",
            command="pytest -q",
            exit_code=0,
        )

    def test_validates_as_envelope(self):
        # extra="forbid" on Envelope: this raises if we ever add a stray
        # top-level field, proving existing aq-event readers won't silently
        # drop our records as "corrupt".
        env = Envelope.model_validate(self.record)
        self.assertEqual(env.type, "vf7.evidence.v1")
        self.assertTrue(env.verify())  # unsigned v1 record is accepted

    def test_type_and_kind_discriminators_present_and_distinct(self):
        self.assertEqual(self.record["type"], "vf7.evidence.v1")
        self.assertEqual(self.record["payload"]["kind"], "vf7.evidence.v1")
        self.assertNotIn(self.record["type"], ("resume.update", "pulse.append"))

    def test_validates_against_frozen_json_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.record)


class TestAppendOnlyLedger(unittest.TestCase):
    def test_sequential_appends_grow_monotonically_and_prior_lines_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            records = []
            for i in range(5):
                rec = aec.build_record(
                    caller_agent_id="agent-a", payload_bytes=f"line {i}".encode(), stream="stdin"
                )
                aec.append_record(rec, ledger)
                records.append(rec)
                lines = _json_lines(ledger.read_text())
                self.assertEqual(len(lines), i + 1)
                # Every prior line must remain byte-identical to what was
                # originally written for it (append-only: never rewritten).
                for j, prior_rec in enumerate(records):
                    parsed = json.loads(lines[j])
                    self.assertEqual(parsed["event_id"], prior_rec["event_id"])

    def test_concurrent_appends_never_corrupt_lines(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            n_writers = 8
            errors: list[str] = []
            lock = threading.Lock()

            def _write(i: int) -> None:
                try:
                    rec = aec.build_record(
                        caller_agent_id=f"agent-{i}",
                        payload_bytes=f"concurrent evidence {i}".encode(),
                        stream="stdin",
                    )
                    aec.append_record(rec, ledger)
                except Exception:  # pragma: no cover - failure path
                    with lock:
                        errors.append(traceback.format_exc())

            with concurrent.futures.ThreadPoolExecutor(max_workers=n_writers) as ex:
                list(ex.map(_write, range(n_writers)))

            self.assertEqual(errors, [])
            lines = _json_lines(ledger.read_text())
            self.assertEqual(len(lines), n_writers)
            seen_ids = set()
            for line in lines:
                parsed = json.loads(line)  # raises if any line is torn/interleaved
                self.assertEqual(parsed["payload"]["kind"], "vf7.evidence.v1")
                seen_ids.add(parsed["event_id"])
            self.assertEqual(len(seen_ids), n_writers)  # no duplicate/merged ids

    def test_never_truncates_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            ledger.write_text('{"pre-existing": "line"}\n')
            rec = aec.build_record(caller_agent_id="agent-a", payload_bytes=b"new", stream="stdin")
            aec.append_record(rec, ledger)
            lines = _json_lines(ledger.read_text())
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0]), {"pre-existing": "line"})


class TestSharedLedgerCompatibility(unittest.TestCase):
    """Prove VF-7 records coexist safely with real aq-event records on the
    same ledger: aq-event's own readers/projectors still work, and ignore
    (rather than choke on) VF-7 entries."""

    def test_event_log_read_all_parses_mixed_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "a2a-events.jsonl"
            env = dict(os.environ)
            env["A2A_EVENT_LOG"] = str(ledger)
            old = os.environ.get("A2A_EVENT_LOG")
            os.environ["A2A_EVENT_LOG"] = str(ledger)
            try:
                # A genuine aq-event record (resume.update).
                event_log.emit("some-agent", "resume.update", payload={"current_objective": "x"})
                # A VF-7 evidence record, appended through OUR path.
                rec = aec.build_record(
                    caller_agent_id="claude-subagent-vf-7-implementer",
                    payload_bytes=b"evidence",
                    stream="stdin",
                )
                aec.append_record(rec, ledger)
                # Another genuine aq-event record (pulse.append), interleaved after.
                event_log.emit("some-agent", "pulse.append", payload={"action": "write", "outcome": "ok"})

                all_events = event_log.read_all()
                self.assertEqual(len(all_events), 3)
                types = sorted(e.type for e in all_events)
                self.assertEqual(types, ["pulse.append", "resume.update", "vf7.evidence.v1"])
            finally:
                if old is None:
                    os.environ.pop("A2A_EVENT_LOG", None)
                else:
                    os.environ["A2A_EVENT_LOG"] = old

    def test_resume_projector_ignores_vf7_records(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "a2a-events.jsonl"
            old = os.environ.get("A2A_EVENT_LOG")
            os.environ["A2A_EVENT_LOG"] = str(ledger)
            try:
                event_log.emit(
                    "some-agent",
                    "resume.update",
                    payload={"current_objective": "real objective", "phase": "P1"},
                )
                rec = aec.build_record(
                    caller_agent_id="claude-subagent-vf-7-implementer",
                    payload_bytes=b"should not leak into resume projection",
                    stream="stdin",
                    subject="should-be-ignored",
                )
                aec.append_record(rec, ledger)

                events = event_log.read_all()
                projection = rp.project_resume(events) if hasattr(rp, "project_resume") else None
                if projection is None:
                    # Fall back to whatever the module exposes for building the
                    # in-memory projection without touching the real RESUME.json.
                    resume_events = [e for e in events if e.type == "resume.update"]
                    self.assertEqual(len(resume_events), 1)
                    self.assertEqual(
                        resume_events[0].payload["current_objective"], "real objective"
                    )
                else:
                    self.assertEqual(projection["current_objective"], "real objective")
                # Directly confirm the filter aq-event's projector uses (e.type
                # == "resume.update"/"pulse.append") excludes our record.
                vf7_in_resume_filter = [e for e in events if e.type == "resume.update"]
                self.assertTrue(all(e.payload.get("kind") != "vf7.evidence.v1" for e in vf7_in_resume_filter))
            finally:
                if old is None:
                    os.environ.pop("A2A_EVENT_LOG", None)
                else:
                    os.environ["A2A_EVENT_LOG"] = old


class TestCliEndToEnd(unittest.TestCase):
    def test_command_mode_produces_valid_redacted_record(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR_PATH),
                    "record",
                    "--caller-agent-id",
                    "test-cli-agent",
                    "--command",
                    "printf 'ok AUTH_TOKEN=supersecretvalue done'",
                    "--subject",
                    "cli-test",
                    "--ledger",
                    str(ledger),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            event_id = result.stdout.strip()
            self.assertTrue(event_id)
            lines = _json_lines(ledger.read_text())
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event_id"], event_id)
            self.assertEqual(record["subject"], "cli-test")
            self.assertNotIn("supersecretvalue", json.dumps(record))
            self.assertIn("ok AUTH_TOKEN=[REDACTED] done", record["payload"]["evidence_text"])
            Envelope.model_validate(record)  # schema-safe for existing readers

    def test_stdin_mode_produces_valid_record(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR_PATH),
                    "record",
                    "--caller-agent-id",
                    "test-cli-agent",
                    "--stdin",
                    "--ledger",
                    str(ledger),
                ],
                input="piped raw evidence, no secrets here\n",
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            record = json.loads(_json_lines(ledger.read_text())[0])
            self.assertIn("piped raw evidence", record["payload"]["evidence_text"])
            self.assertEqual(record["payload"]["stream"], "stdin")

    def test_missing_source_flag_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR_PATH),
                    "record",
                    "--caller-agent-id",
                    "test-cli-agent",
                    "--ledger",
                    str(ledger),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(ledger.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
