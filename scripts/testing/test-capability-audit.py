#!/usr/bin/env python3
"""Fixture-repo tests for scripts/ai/lib/capability_audit.py (all six classes)."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ai" / "lib"))
import capability_audit as ca  # noqa: E402

NOW = time.time()


def w(root: Path, rel: str, text: str, mode: int = 0o755) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    p.chmod(mode)


def iso(ts: float) -> str:
    return ca._iso(ts)


class CapabilityAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        r = cls.root = Path(cls.tmp.name) / "repo"
        py = "#!/usr/bin/env python3\nprint('x')\n"
        # ACTIVE: used (audit log) + discoverable (CLAUDE.md) + wired
        w(r, "scripts/ai/aq-active", py)
        # UNUSED-AVAILABLE: discoverable only
        w(r, "scripts/ai/aq-shelf", py)
        # UNDISCOVERABLE: wired from another script, no docs, no use
        w(r, "scripts/ai/aq-hidden", py)
        w(r, "scripts/ai/aq-caller", "#!/usr/bin/env bash\naq-hidden --go\naq-active\n")
        # STALE-CLAIM: catalog says enabled/integrated, never used
        w(r, "scripts/ai/aq-claimed", py)
        w(r, "scripts/ai/aq-gated", py)
        w(r, "scripts/ai/aq-kept", py)
        w(r, ".understand-anything/knowledge-graph.json", "{}", 0o644)
        os.utime(r / ".understand-anything/knowledge-graph.json", (NOW - 100 * 86400, NOW - 100 * 86400))
        # DEAD-CANDIDATE: nothing references it
        w(r, "scripts/ai/aq-orphan", py)
        # KEEP-DECLARED: would be DEAD-CANDIDATE but declared in config/capability-triage.json
        w(r, "scripts/ai/aq-hostonly", py)
        w(r, "config/capability-triage.json", json.dumps({"keep": [{"name": "aq-hostonly", "reason": "other host"}]}), 0o644)
        # BROKEN: python syntax error
        w(r, "scripts/ai/aq-broken", "#!/usr/bin/env python3\ndef (:\n")
        # tested
        w(r, "scripts/testing/test-aq-active.sh", "aq-active\n")
        w(r, "CLAUDE.md", "use `aq-active` and aq-shelf. aq-caller too.\n", 0o644)
        w(r, "AGENTS.md", "", 0o644)
        w(r, ".agent/skills/lonely-skill/SKILL.md", "---\nname: lonely-skill\n---\n", 0o644)
        w(r, "ai-stack/mcp-servers/hybrid-coordinator/knowledge/tooling_manifest.py", "# x\n", 0o644)
        w(r, "scripts/ai/mcp-bridge-hybrid.py",
          'TOOLS = [\n    {"name": "qa_check", "description": "d"},\n]\n')
        w(r, "nix/modules/x.nix",
          'systemd.services.dead-unit = {};\nsystemd.timers.live-timer = {};\nsystemd.services.live-timer = {};\n'
          'systemd.services.crashed-unit = {};\n', 0o644)
        w(r, "config/system-capability-catalog.json", json.dumps({"entries": [
            {"id": "claimed-thing", "state": "enabled", "maturity": "integrated",
             "primary_refs": ["scripts/ai/aq-claimed"]},
            {"id": "gated-thing", "state": "enabled", "maturity": "scope-gated",
             "primary_refs": ["scripts/ai/aq-gated"]},
            {"id": "kept-thing", "state": "enabled", "maturity": "integrated",
             "usage_evidence": "audit false positive; claim kept",
             "primary_refs": ["scripts/ai/aq-kept"]},
            {"id": "active-thing", "state": "enabled", "maturity": "production",
             "primary_refs": ["scripts/ai/aq-active"]},
            {"id": "quarantined-thing", "state": "quarantined", "maturity": "official",
             "primary_refs": ["scripts/ai/aq-orphan"]},
        ]}), 0o644)
        # telemetry fixtures
        tel = Path(cls.tmp.name) / "tel"
        tel.mkdir()
        audit = tel / "tool-audit.jsonl"
        audit.write_text(
            json.dumps({"timestamp": iso(NOW - 3600), "tool_name": "aq-active"}) + "\n"
            + json.dumps({"timestamp": iso(NOW - 90 * 86400), "tool_name": "aq-claimed"}) + "\n"  # outside window
            + json.dumps({"timestamp": iso(NOW - 3600), "tool_name": "qa_check"}) + "\n"
        )
        (tel / "hybrid-events.jsonl").write_text(
            json.dumps({"timestamp": iso(NOW - 60), "event_type": "aq-hidden-seen"}) + "\n")
        states = {
            "dead-unit.service": {"Id": "dead-unit.service", "LoadState": "not-found", "ActiveState": "inactive"},
            "live-timer.timer": {"Id": "live-timer.timer", "LoadState": "loaded", "ActiveState": "active",
                                 "LastTriggerUSec": f"@{int(NOW - 600)}"},
            "live-timer.service": {"Id": "live-timer.service", "LoadState": "loaded", "ActiveState": "inactive",
                                   "Result": "success"},
            "crashed-unit.service": {"Id": "crashed-unit.service", "LoadState": "loaded",
                                     "ActiveState": "failed", "Result": "exit-code"},
        }
        cls.rep = ca.run_audit(r, now=NOW, tool_audit=audit, telemetry_dir=tel, delegation_dir=tel / "deleg",
                               use_systemd=False, use_journal=False, unit_states=states)
        cls.by = {c["key"]: c for c in cls.rep["capabilities"]}

    def cls_of(self, key):
        return self.by[key]["class"]

    def test_active(self):
        c = self.by["aq-active"]
        self.assertEqual(c["class"], "ACTIVE")
        self.assertEqual(c["next_action"], "none")
        self.assertTrue(c["evidence"]["tested"])

    def test_unused_available(self):
        self.assertEqual(self.cls_of("aq-shelf"), "UNUSED-AVAILABLE")
        self.assertEqual(self.by["aq-shelf"]["next_action"], "integrate-into-repertoire")

    def test_undiscoverable(self):
        self.assertEqual(self.cls_of("aq-hidden"), "UNDISCOVERABLE")
        self.assertEqual(self.by["aq-hidden"]["next_action"], "add-discovery")

    def test_stale_claim_and_window(self):
        # use 90d ago is outside the 30d window -> still stale
        self.assertEqual(self.cls_of("aq-claimed"), "STALE-CLAIM")
        self.assertEqual(self.by["aq-claimed"]["next_action"], "refresh")

    def test_non_integrated_maturity_is_never_stale_claim(self):
        self.assertNotEqual(self.cls_of("aq-gated"), "STALE-CLAIM")

    def test_documented_kept_claim_is_acknowledged(self):
        self.assertEqual(self.cls_of("aq-kept"), "ACKNOWLEDGED")
        self.assertEqual(self.by["aq-kept"]["next_action"], "none")

    def test_stale_artifact_separate_from_claims(self):
        art = [c for c in self.rep["capabilities"] if "artifact" in c["kinds"]][0]
        self.assertEqual(art["class"], "STALE-ARTIFACT")
        self.assertEqual(self.rep["audit_version"], ca.AUDIT_VERSION)

    def test_quarantined_claim_is_not_stale(self):
        self.assertEqual(self.cls_of("aq-orphan"), "DEAD-CANDIDATE")
        self.assertEqual(self.by["aq-orphan"]["next_action"], "archive-candidate")

    def test_broken_script(self):
        self.assertEqual(self.cls_of("aq-broken"), "BROKEN")
        self.assertEqual(self.by["aq-broken"]["next_action"], "fix")

    def test_skill_dead_when_unreferenced(self):
        self.assertEqual(self.cls_of("lonely-skill"), "DEAD-CANDIDATE")
        self.assertEqual(self.cls_of("aq-hostonly"), "KEEP-DECLARED")

    def test_mcp_tool_used_and_registry_discoverable(self):
        self.assertEqual(self.cls_of("qa-check"), "ACTIVE")

    def test_units(self):
        self.assertEqual(self.cls_of("dead-unit"), "DEAD-CANDIDATE")       # not loaded
        self.assertEqual(self.cls_of("crashed-unit"), "BROKEN")
        self.assertIn(self.cls_of("live-timer"), ("UNDISCOVERABLE", "ACTIVE"))
        self.assertTrue(self.by["live-timer"]["evidence"]["used"])

    def test_dedup_and_totals(self):
        keys = [c["key"] for c in self.rep["capabilities"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sum(self.rep["totals"]["by_class"].values()), len(keys))
        self.assertEqual(self.by["live-timer"]["kinds"], ["unit"])

    def test_read_only_and_deterministic(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        again = ca.run_audit(self.root, now=NOW, tool_audit=None, telemetry_dir=None,
                             delegation_dir=self.root / "none", use_systemd=False, unit_states={})
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        again2 = ca.run_audit(self.root, now=NOW, tool_audit=None, telemetry_dir=None,
                              delegation_dir=self.root / "none", use_systemd=False, unit_states={})
        self.assertEqual(again["capabilities"], again2["capabilities"])

    def test_actions_never_delete(self):
        self.assertTrue(set(c["next_action"] for c in self.rep["capabilities"])
                        <= {"none", "integrate-into-repertoire", "add-discovery", "fix", "refresh",
                            "archive-candidate", "regenerate"})


if __name__ == "__main__":
    unittest.main(verbosity=1)
