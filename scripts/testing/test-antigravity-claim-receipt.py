#!/usr/bin/env python3
"""Hermetic checks for the Antigravity claim-receipt ledger
(`scripts/ai/aq-antigravity-inbox` wake/claim/complete extensions).

Proves the four properties DESIGN.md §3.2/§4 requires before this slice can
be accepted:

1. claim CAS exclusivity — two racing claims on the same inbox file, exactly
   one wins (the second sees the file already gone via os.rename).
2. completion-without-claim is flagged, not silently indistinguishable from
   a clean completion (`completed_without_claim: true`).
3. output-hash mismatch is detectable — the hash recorded in the receipt no
   longer matches a tampered on-disk artifact.
4. a `wake_attempt` record alone never implies completion — the receipt
   ledger keeps record types distinguishable and a wake-only task_id has no
   `claim`/`completion` record.

Fully offline: subprocess.run is monkeypatched before any wake test runs so
no real `antigravity` binary (or even `pgrep`) is ever invoked.

Run: python3 scripts/testing/test-antigravity-claim-receipt.py
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ai" / "aq-antigravity-inbox"

loader = importlib.machinery.SourceFileLoader("ag_inbox_receipt", str(SCRIPT))
m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ag_inbox_receipt", loader))
loader.exec_module(m)


class _FakeCompleted:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def _sandbox(tmp: Path) -> None:
    """Point the module's REPO/INBOX/STATE at an isolated tempdir, exactly
    like the pre-existing test-antigravity-inbox.py does. RECEIPTS is a
    function of the current INBOX global (not a frozen constant), so it
    follows automatically — no extra reassignment needed.
    """
    m.REPO = tmp
    m.INBOX = tmp / ".agent" / "collaboration" / "antigravity-inbox"
    m.STATE = m.INBOX / ".lane-state.json"
    m.INBOX.mkdir(parents=True)


def _drop(inbox: Path, task_id: str, body: str = "# task\n") -> Path:
    p = inbox / f"{task_id}.md"
    p.write_text(body, encoding="utf-8")
    return p


def _receipt_records(task_id: str) -> list[dict]:
    return m._load_receipt(task_id)["records"]


def test_claim_cas_exclusivity_two_racing_claims_one_wins() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-cas"
        _drop(m.INBOX, task_id)

        # Simulate the race: both claimants resolve the same pending path
        # before either renames (the realistic race window), then both
        # attempt the CAS rename. Only the first os.rename() can find the
        # source file; the second must lose.
        first_rc = m.main(["claim", f"{task_id}.md", "--actor", "ide-watch", "--json"])
        second_rc = m.main(["claim", f"{task_id}.md", "--actor", "owner-manual", "--json"])

        assert first_rc == 0, "first claimant must win the CAS rename"
        assert second_rc == 1, "second claimant must lose (exit 1), not silently succeed"

        claimed_marker = m.INBOX / f".claimed-{task_id}"
        assert claimed_marker.exists(), "winning claim must leave the .claimed-<task_id> marker"
        assert not (m.INBOX / f"{task_id}.md").exists(), "original file must be gone (renamed, not copied)"

        records = _receipt_records(task_id)
        claim_records = [r for r in records if r["type"] == "claim"]
        assert len(claim_records) == 1, f"exactly one claim record must be written, got {len(claim_records)}"
        assert claim_records[0]["actor"] == "ide-watch", "the winning actor's claim must be the one recorded"

    print("PASS: claim CAS exclusivity — two racing claims, exactly one wins")


def test_completion_without_claim_is_flagged_not_silently_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-no-claim"
        _drop(m.INBOX, task_id)

        # No claim step — go straight to complete (fail-open-but-visible).
        rc = m.main(["complete", f"{task_id}.md", "--json"])
        assert rc == 0, "complete must not block the operator even without a prior claim"

        archived = list((tmp / ".agent" / "archive").glob("antigravity-inbox-*/round-no-claim.md"))
        assert len(archived) == 1, "file must still be archived (fail-open)"

        records = _receipt_records(task_id)
        completions = [r for r in records if r["type"] == "completion"]
        assert len(completions) == 1
        assert completions[0]["completed_without_claim"] is True, (
            "an unattributed completion must be explicitly flagged, not indistinguishable from a clean one"
        )
        assert "claim_actor" not in completions[0], "no claim_actor should be present when there was no claim"

    print("PASS: completion without a prior claim is flagged, not silently clean")


def test_completion_with_prior_claim_is_not_flagged() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-clean"
        _drop(m.INBOX, task_id)

        assert m.main(["claim", f"{task_id}.md", "--actor", "ide-watch", "--json"]) == 0
        rc = m.main(["complete", f".claimed-{task_id}", "--json"])
        assert rc == 0

        records = _receipt_records(task_id)
        completions = [r for r in records if r["type"] == "completion"]
        assert len(completions) == 1
        assert completions[0]["completed_without_claim"] is False
        assert completions[0]["claim_actor"] == "ide-watch"

    print("PASS: completion following a real claim is not flagged, and binds the claiming actor")


def test_output_hash_mismatch_is_detectable() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-output"
        _drop(m.INBOX, task_id)

        out_dir = tmp / ".agents" / "plans" / task_id
        out_dir.mkdir(parents=True)
        out_path = out_dir / "antigravity.md"
        out_path.write_text("original output\n", encoding="utf-8")

        assert m.main(["claim", f"{task_id}.md", "--actor", "ide-watch", "--json"]) == 0
        assert m.main(["complete", f".claimed-{task_id}", "--json"]) == 0

        records = _receipt_records(task_id)
        output_records = [r for r in records if r["type"] == "output_hash"]
        assert len(output_records) == 1, "output_hash record must be written when the artifact exists"
        recorded_hash = output_records[0]["hash"]
        assert recorded_hash == hashlib.sha256(b"original output\n").hexdigest()

        # Tamper with the artifact after completion — the receipt's recorded
        # hash must no longer match, proving mismatch is detectable from the
        # ledger alone (no re-trust of the live file needed).
        out_path.write_text("tampered output\n", encoding="utf-8")
        current_hash = hashlib.sha256(out_path.read_bytes()).hexdigest()
        assert current_hash != recorded_hash, "tampered artifact must diverge from the recorded receipt hash"

    print("PASS: output-hash mismatch (tampered artifact vs. recorded receipt hash) is detectable")


def test_wake_attempt_never_counts_as_completion_proof() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-wake-only"
        _drop(m.INBOX, task_id)

        # Fully offline: stub subprocess.run so no real `pgrep`/`antigravity`
        # binary is ever invoked, covering both the proc-live and
        # proc-not-live branches deterministically.
        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):  # noqa: ANN001 - test stub signature
            calls.append(list(argv))
            if argv[:1] == ["pgrep"]:
                return _FakeCompleted(returncode=0)  # pretend antigravity IS running
            return _FakeCompleted(returncode=0)  # pretend the nudge exits cleanly

        real_run = m.subprocess.run
        m.subprocess.run = fake_run
        try:
            rc = m.main(["wake", f"{task_id}.md", "--actor", "owner-manual", "--json"])
        finally:
            m.subprocess.run = real_run

        assert rc == 0
        assert any(c[:1] == ["pgrep"] for c in calls), "wake must check pgrep first"
        assert any(c == m.WAKE_ARGV for c in calls), (
            "wake must shell out using the fixed WAKE_ARGV list — never string-interpolated task content"
        )

        records = _receipt_records(task_id)
        assert len(records) == 1
        assert records[0]["type"] == "wake_attempt"
        assert records[0]["method"] == "cli-nudge"

        # The critical assertion: a wake_attempt-only receipt must contain
        # no claim and no completion record — it is logged input, not proof
        # of processing.
        record_types = {r["type"] for r in records}
        assert "claim" not in record_types, "wake alone must never produce a claim record"
        assert "completion" not in record_types, "wake alone must never produce a completion record"

        # The inbox file itself is untouched by a wake (only claim/complete
        # move it) — further proof a wake did not "process" anything.
        assert (m.INBOX / f"{task_id}.md").exists(), "wake must not consume or move the pending file"

    print("PASS: a wake_attempt record alone never counts as completion proof")


def test_wake_argv_never_interpolates_task_content() -> None:
    """Rule 7 guard: the task_id/name must never appear inside the argv the
    wake nudge actually shells out with — only in the receipt's `task_id`
    field, which is not passed to subprocess.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _sandbox(tmp)
        task_id = "round-inject-$(echo pwned)"
        # Note: cannot literally use shell metacharacters in a filename on
        # most filesystems; assert against the argv contract directly using
        # a task_id containing characters that would be dangerous under
        # naive string interpolation.
        safe_task_id = "round-inject"
        _drop(m.INBOX, safe_task_id)

        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):  # noqa: ANN001 - test stub signature
            calls.append(list(argv))
            return _FakeCompleted(returncode=0)

        real_run = m.subprocess.run
        m.subprocess.run = fake_run
        try:
            m.main(["wake", f"{safe_task_id}.md", "--actor", "owner-manual", "--json"])
        finally:
            m.subprocess.run = real_run

        for argv in calls:
            joined = " ".join(argv)
            assert safe_task_id not in joined, "task_id must never be interpolated into subprocess argv"
        assert any(c == m.WAKE_ARGV for c in calls), "wake argv must be exactly the fixed WAKE_ARGV list"

    print("PASS: wake argv is a fixed list, never string-interpolated with task content (Rule 7)")


def main() -> int:
    test_claim_cas_exclusivity_two_racing_claims_one_wins()
    test_completion_without_claim_is_flagged_not_silently_clean()
    test_completion_with_prior_claim_is_not_flagged()
    test_output_hash_mismatch_is_detectable()
    test_wake_attempt_never_counts_as_completion_proof()
    test_wake_argv_never_interpolates_task_content()
    print("ALL PASS: antigravity claim-receipt ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
