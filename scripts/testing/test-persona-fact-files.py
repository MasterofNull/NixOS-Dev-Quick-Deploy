#!/usr/bin/env python3
"""Persona P3: fact-file check (tier0.d/check-fact-files.py), conflict report and session-start listing."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("cff", ROOT / "scripts/governance/tier0.d/check-fact-files.py")
assert _spec and _spec.loader
cff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cff)  # type: ignore[union-attr]

CODEX = "Simurg@codex/gpt-6.1#ab12cd34"
CLAUDE = "Simurg@claude/sonnet-5.5#2222"


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *a],
                          capture_output=True, text=True, check=True).stdout


def fact(repo: Path, subject: str, claim: str = "12 layers is the ceiling", evidence: str = "CLAUDE.md:80",
         instance: str = CODEX, reply: str = "", extra: str = "") -> Path:
    p = repo / ".agent/memory/facts" / f"{subject}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    r = f"owner_reply: {reply}\n" if reply else ""
    p.write_text(f"---\nsubject: {subject}\nclaim: {claim}\nevidence: {evidence}\ninstance: {instance}\n{r}---\n{extra}", encoding="utf-8")
    return p


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        t = Path(self.td.name)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(t / "origin.git")], check=True)
        self.repo = t / "w"
        subprocess.run(["git", "clone", "-q", str(t / "origin.git"), str(self.repo)], check=True, capture_output=True)
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "README").write_text("x\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        git(self.repo, "push", "-q", "origin", "HEAD:main")
        git(self.repo, "fetch", "-q")
        git(self.repo, "checkout", "-qb", "slice")

    def tearDown(self) -> None:
        self.td.cleanup()

    def land(self, subject: str, **kw) -> None:
        """Land a fact on origin/main, then return to a fresh slice branch from it."""
        git(self.repo, "checkout", "-q", "main")
        fact(self.repo, subject, **kw)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", f"fact {subject}")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "checkout", "-qb", "slice2")

    def check(self) -> list[str]:
        return cff.check_repo(self.repo)

    def stage(self) -> None:
        git(self.repo, "add", "-A")


class Format(Base):
    def test_valid_labels_and_persona_off_pass(self) -> None:
        fact(self.repo, "llama-cpp.n_gpu_layers")
        fact(self.repo, "llama-cpp.kv", instance="codex/gpt-6.1")
        self.stage()
        self.assertEqual(self.check(), [])
        self.assertEqual(cff.lane_of(CODEX), cff.lane_of("codex/gpt-6.1"))
        self.assertEqual(cff.lane_of(CODEX), "codex")

    def test_missing_subject_evidence_and_filename_mismatch(self) -> None:
        p = fact(self.repo, "a.b")
        p.write_text("---\nclaim: x\ninstance: codex/g\n---\n")
        self.stage()
        e = "\n".join(self.check())
        self.assertIn("subject", e)
        self.assertIn("evidence", e)

    def test_cap_of_ten(self) -> None:
        for i in range(11):
            fact(self.repo, f"topic.s{i}")
        self.stage()
        self.assertTrue(any("cap is 10" in e for e in self.check()))

    def test_privacy_rejections(self) -> None:
        for bad in ("see /home/alice/x", "mail bob@example.com", "tok " + "Ab1" * 12):
            fact(self.repo, "p.q", claim=bad)
            self.stage()
            self.assertTrue(self.check(), bad)
        fact(self.repo, "p.q", evidence="0123456789abcdef0123456789abcdef01234567")
        self.stage()
        self.assertEqual(self.check(), [], "a full commit sha is evidence, not a secret")


class Conflicts(Base):
    def test_sequential_overwrite_needs_fresh_owner_reply_and_prints_both_claims(self) -> None:
        self.land("llama-cpp.n_gpu_layers", claim="12 layers")
        fact(self.repo, "llama-cpp.n_gpu_layers", claim="16 layers", instance=CLAUDE)
        self.stage()
        errs = self.check()
        self.assertTrue(any("12 layers" in e and "16 layers" in e and "owner_reply" in e for e in errs), errs)
        fact(self.repo, "llama-cpp.n_gpu_layers", claim="16 layers", instance=CLAUDE, reply="1 keep mine")
        self.stage()
        self.assertEqual(self.check(), [])

    def test_same_lane_update_is_free(self) -> None:
        self.land("llama-cpp.n_gpu_layers", claim="12 layers")
        fact(self.repo, "llama-cpp.n_gpu_layers", claim="12 layers, verified", instance="Simurg@codex/gpt-7#9999")
        self.stage()
        self.assertEqual(self.check(), [])

    def test_stale_branch_compares_against_fetched_origin_main(self) -> None:
        git(self.repo, "checkout", "-q", "slice")
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "branch fact")
        # another lane lands the same subject after this branch was cut
        git(self.repo, "checkout", "-q", "main")
        fact(self.repo, "x.y", claim="theirs", instance=CODEX)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "theirs")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "checkout", "-q", "slice")
        errs = self.check()  # committed branch diff, no staged change
        self.assertTrue(any("theirs" in e and "mine" in e for e in errs), errs)

    def _commit_branch(self, msg: str) -> None:
        self.stage()
        git(self.repo, "commit", "-qm", msg)

    def test_cross_lane_overwrite_within_branch_needs_owner_reply(self) -> None:
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("a")
        fact(self.repo, "x.y", claim="theirs", instance=CODEX)
        self._commit_branch("b")
        errs = self.check()
        self.assertTrue(any("mine" in e and "theirs" in e and "owner_reply" in e for e in errs), errs)

    def test_cross_lane_overwrite_within_branch_with_reply_passes(self) -> None:
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("a")
        fact(self.repo, "x.y", claim="theirs", instance=CODEX, reply="2 keep theirs")
        self._commit_branch("b")
        self.assertEqual(self.check(), [])

    def test_staged_overwrite_of_committed_branch_fact_needs_reply(self) -> None:
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("a")
        fact(self.repo, "x.y", claim="theirs", instance=CODEX)
        self.stage()
        self.assertTrue(any("owner_reply" in e for e in self.check()))

    def test_metadata_only_lane_transfer_then_claim_change_fails(self) -> None:
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("a")
        fact(self.repo, "x.y", claim="mine", instance=CODEX)  # metadata-only transfer
        self._commit_branch("b")
        self.assertTrue(any("transferred across lanes" in e for e in self.check()))
        fact(self.repo, "x.y", claim="rewritten", instance=CODEX)  # same-lane edit now looks free
        self._commit_branch("c")
        self.assertTrue(any("transferred across lanes" in e for e in self.check()))

    def test_lane_transfer_with_fresh_reply_passes(self) -> None:
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("a")
        fact(self.repo, "x.y", claim="mine", instance=CODEX, reply="2 keep theirs")
        self._commit_branch("b")
        self.assertEqual(self.check(), [])

    def _stale_branch(self) -> None:
        git(self.repo, "checkout", "-q", "slice")
        fact(self.repo, "x.y", claim="mine", instance=CLAUDE)
        self._commit_branch("branch fact")
        git(self.repo, "checkout", "-q", "main")
        fact(self.repo, "x.y", claim="theirs", instance=CODEX)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "theirs")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "checkout", "-q", "slice")

    def test_stale_branch_resolved_by_final_commit_with_reply_passes(self) -> None:
        self._stale_branch()
        self.assertTrue(self.check())
        fact(self.repo, "x.y", claim="merged", instance=CLAUDE, reply="1 keep mine")
        self._commit_branch("resolve")
        self.assertEqual(self.check(), [])

    def test_stale_branch_final_commit_without_reply_fails(self) -> None:
        self._stale_branch()
        fact(self.repo, "x.y", claim="merged", instance=CLAUDE)
        self._commit_branch("resolve")
        self.assertTrue(any("owner_reply" in e for e in self.check()))

    def test_delete_then_readd_on_branch_judged_on_final_state(self) -> None:
        self.land("a.b", claim="one", instance=CLAUDE)
        (self.repo / ".agent/memory/facts/a.b.md").unlink()
        self._commit_branch("drop")
        fact(self.repo, "a.b", claim="two", instance=CODEX)
        self._commit_branch("readd")
        self.assertTrue(any("owner_reply" in e for e in self.check()))

    def test_net_delete_of_main_fact_by_same_lane_needs_reply(self) -> None:
        self.land("a.b", claim="one", instance=CLAUDE)
        (self.repo / ".agent/memory/facts/a.b.md").unlink()
        self.stage()
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "claude"}):
            self.assertTrue(any("deletes or renames" in e or "net delete" in e for e in self.check()))

    def _main_fact_path(self) -> Path:
        self.land("a.b", claim="one", instance=CLAUDE)
        return self.repo / ".agent/memory/facts/a.b.md"

    def _approved_delete(self, p: Path) -> None:
        p.unlink()
        self.stage()
        git(self.repo, "commit", "-qm", "drop\n\nowner_reply: 1 keep theirs gone")

    def _restore(self) -> None:
        fact(self.repo, "a.b", claim="one", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "restore")

    def test_earlier_delete_approval_does_not_authorize_later_unapproved_delete(self) -> None:
        p = self._main_fact_path()
        self._approved_delete(p)
        self._restore()
        p.unlink()
        self.stage()
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "claude"}):
            self.assertTrue(any("net delete" in e for e in self.check()), self.check())

    def test_approved_delete_as_final_transition_passes(self) -> None:
        p = self._main_fact_path()
        self._approved_delete(p)
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "claude"}):
            self.assertEqual(self.check(), [])

    def test_restore_then_approved_delete_passes(self) -> None:
        p = self._main_fact_path()
        p.unlink()
        self.stage()
        git(self.repo, "commit", "-qm", "drop")
        self._restore()
        self._approved_delete(p)
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "claude"}):
            self.assertEqual(self.check(), [])

    def test_subdirectory_fact_is_not_a_fact_file(self) -> None:
        p = self.repo / ".agent/memory/facts/sub/a.b.md"
        p.parent.mkdir(parents=True)
        p.write_text("junk")
        self.stage()
        self.assertEqual(self.check(), [])

    def test_delete_and_split(self) -> None:
        self.land("llama-cpp.n_gpu_layers", claim="12 layers")
        (self.repo / ".agent/memory/facts/llama-cpp.n_gpu_layers.md").unlink()
        self.stage()
        self.assertTrue(any("deletes or renames" in e for e in self.check()))
        fact(self.repo, "llama-cpp.n_gpu_layers.codex", instance=CODEX, reply="3 keep both")
        fact(self.repo, "llama-cpp.n_gpu_layers.claude", claim="16", instance=CLAUDE, reply="3 keep both")
        self.stage()
        self.assertEqual(self.check(), [])

    def test_rename_is_delete_plus_add(self) -> None:
        self.land("llama-cpp.n_gpu_layers", claim="12 layers")
        git(self.repo, "mv", ".agent/memory/facts/llama-cpp.n_gpu_layers.md", ".agent/memory/facts/llama-cpp.layers.md")
        p = self.repo / ".agent/memory/facts/llama-cpp.layers.md"
        p.write_text(p.read_text().replace("subject: llama-cpp.n_gpu_layers", "subject: llama-cpp.layers"))
        self.stage()
        self.assertTrue(any("net delete or rename" in e for e in self.check()))

    def test_same_lane_delete_of_branch_only_fact_is_free(self) -> None:
        p = fact(self.repo, "a.b")
        self.stage()
        git(self.repo, "commit", "-qm", "add")
        p.unlink()
        self.stage()
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "codex"}):
            self.assertEqual(self.check(), [])

    def test_cross_lane_delete_of_branch_only_fact_needs_reply(self) -> None:
        p = fact(self.repo, "a.b", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "add")
        p.unlink()
        self.stage()
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": "codex"}):
            self.assertTrue(any("deletes or renames" in e for e in self.check()))

    def test_committed_cross_lane_delete_detected_from_trailer_alone(self) -> None:
        p = fact(self.repo, "a.b", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "add")
        p.unlink()
        self.stage()
        git(self.repo, "commit", "-qm", "drop", "-m", "Co-Authored-By: Codex <noreply@openai.com>")
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": ""}):
            self.assertTrue(any("deletes or renames" in e and "lane unknown" not in e for e in self.check()))

    def test_committed_same_lane_delete_via_trailer_passes_and_unknown_trailer_fails_closed(self) -> None:
        p = fact(self.repo, "a.b", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "add")
        p.unlink()
        self.stage()
        git(self.repo, "commit", "-qm", "drop", "-m", "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
        self.assertEqual(self.check(), [])
        git(self.repo, "reset", "-q", "--soft", "HEAD~1")
        git(self.repo, "commit", "-qm", "drop", "-m", "Co-Authored-By: Mystery <x@example.invalid>")
        with mock.patch.dict(os.environ, {"AQ_INSTANCE_LANE": ""}):
            self.assertTrue(any("lane unknown" in e for e in self.check()))

    def test_cross_lane_split_of_branch_only_fact_with_reply_passes(self) -> None:
        p = fact(self.repo, "a.b", instance=CLAUDE)
        self.stage()
        git(self.repo, "commit", "-qm", "add")
        p.unlink()
        fact(self.repo, "a.b.claude", instance=CLAUDE, reply="3 keep both")
        fact(self.repo, "a.b.codex", claim="other", instance=CODEX, reply="3 keep both")
        self.stage()
        self.assertEqual(self.check(), [])


class Report(Base):
    def test_report_counts(self) -> None:
        git(self.repo, "checkout", "-q", "main")
        fact(self.repo, "a.b", claim="one", instance=CODEX)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "a")
        fact(self.repo, "a.b", claim="two", instance=CLAUDE, reply="1 keep mine")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "b")
        out = cff.report(self.repo)
        for want in ("facts_total=1", "multi_lane_subjects=1", "claim_changes=1", "owner_reply_entries=1"):
            self.assertIn(want, out)


    def _history(self, *revs: dict) -> str:
        git(self.repo, "checkout", "-q", "main")
        for i, kw in enumerate(revs):
            fact(self.repo, "a.b", **kw)
            git(self.repo, "add", ".")
            git(self.repo, "commit", "-qm", f"r{i}")
        return cff.report(self.repo)

    def test_reversion_counts_two_changes(self) -> None:
        out = self._history(dict(claim="A"), dict(claim="B", instance=CLAUDE, reply="1"), dict(claim="A"))
        self.assertIn("claim_changes=2", out)

    def test_evidence_only_edit_is_not_a_claim_change(self) -> None:
        out = self._history(dict(claim="A"), dict(claim="A", evidence="CLAUDE.md:81"))
        self.assertIn("claim_changes=0", out)

    def test_unchanged_owner_reply_not_recounted(self) -> None:
        out = self._history(dict(claim="A"), dict(claim="B", instance=CLAUDE, reply="1 keep mine"),
                            dict(claim="B", instance=CLAUDE, reply="1 keep mine", evidence="CLAUDE.md:81"))
        self.assertIn("owner_reply_entries=1", out)
        self.assertIn("claim_changes=1", out)


class SessionStart(unittest.TestCase):
    def test_lists_subjects_newest_first_capped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = Path(td)
            subprocess.run(["git", "init", "-q", td], check=True)
            for i in range(25):
                fact(r, f"topic.s{i:02d}", claim=f"c{i}")
            git(r, "-c", "user.email=t@e.invalid", "-c", "user.name=t", "add", ".")
            git(r, "-c", "user.email=t@e.invalid", "-c", "user.name=t", "commit", "-qm", "f")
            out = subprocess.run(["python3", str(ROOT / "scripts/ai/lib/fact_subjects.py"), td],
                                 capture_output=True, text=True, check=True).stdout
            lines = [ln for ln in out.splitlines() if ln.startswith("- ")]
            self.assertEqual(len(lines), 20)
            self.assertIn("topic.s", lines[0])
            self.assertIn("(codex)", lines[0])
            self.assertIn("25 total", out)

    def test_empty_prints_nothing_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = subprocess.run(["python3", str(ROOT / "scripts/ai/lib/fact_subjects.py"), td],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("no fact files", out)

    def test_aq_session_start_calls_it(self) -> None:
        src = (ROOT / "scripts/ai/aq-session-start").read_text()
        self.assertIn("fact_subjects.py", src)
        self.assertIn("## Shared Facts", src)


if __name__ == "__main__":
    unittest.main()
