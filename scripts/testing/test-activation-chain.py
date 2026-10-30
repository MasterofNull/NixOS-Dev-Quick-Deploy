#!/usr/bin/env python3
"""Activation chain verifier + aq-pm-tracker single ACTIVATED path (ACTIVATION-PIPELINE.md acceptance tests
that need no root). Keys and chains are generated in a temp dir; nothing touches /var/lib or /etc."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
import activation_chain as ac  # noqa: E402
try:
    from cryptography.hazmat.primitives import serialization  # noqa: E402
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
except ImportError:
    # The CI syntax job runs the runner's bare python; locally (NixOS env) the module is always present.
    if os.environ.get("CI") == "true":
        print("SKIP: python 'cryptography' not installed in CI python; signature-dependent tests not run")
        sys.exit(0)
    raise

_loader = importlib.machinery.SourceFileLoader("aq_pm_tracker_ac", str(REPO / "scripts" / "ai" / "aq-pm-tracker"))
tracker = importlib.util.module_from_spec(importlib.util.spec_from_loader("aq_pm_tracker_ac", _loader))
_loader.exec_module(tracker)

CLOSURE = "/nix/store/aaaa-nixos-system-1"
SHA = "a" * 64
BASE = "b" * 64


def pub_hex(k):
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


class Chain:
    """Builds a signed chain on disk the way the slice-2 signer will."""

    def __init__(self, root: Path, key=None):
        self.key = key or Ed25519PrivateKey.generate()
        self.log, self.head = root / "log", root / "head"
        self.log.mkdir()
        self.seq, self.prev = 0, ac.GENESIS_PREV
        self.hashes = []
        self.add("genesis", finalize=True)

    def add(self, op, finalize=True, **f):
        env = {"v": 1, "domain": ac.DOMAIN, "op": op, "deployment_id": "dep1", "approver": "hyperd",
               "ts": "2026-10-30T00:00:00Z", "request_id": f"req{self.seq:08d}", "seq": self.seq,
               "prev_hash": self.prev, **f}
        sig = self.key.sign(ac.signing_input(env)).hex()
        (self.log / f"{self.seq}.json").write_text(json.dumps({"envelope": env, "sig": sig}))
        self.prev = ac.envelope_hash(env, sig)
        self.hashes.append(self.prev)
        self.seq += 1
        if finalize:
            self.write_head()

    def write_head(self):
        self.head.write_text(json.dumps({"seq": self.seq - 1, "hash": self.prev}))

    def tup(self, item, closure=CLOSURE, sha=SHA):
        return {"plan": "p", "item_id": item, "subject": f"p:{item}", "attestation_sha256": sha,
                "system_closure": closure, "evidence_baseline_sha256": BASE}

    def grant(self, item, **kw):
        self.add("grant", **self.tup(item, **kw))

    def revoke(self, item, finalize=True):
        self.add("revoke", finalize=finalize, plan="p", item_id=item, subject=f"p:{item}")

    def wave(self, *items):
        self.add("wave-grant", wave_id="w1", items=sorted((self.tup(i) for i in items), key=lambda t: t["item_id"]))

    def state(self):
        return ac.load_chain(self.log, self.head, [pub_hex(self.key)])


def view(item="i1", sha=SHA):
    return {"plan": "p", "item_id": item, "subject": f"p:{item}", "attestation_sha256": sha}


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.td, True)
        self.c = Chain(self.td)

    def status(self, item="i1", closure=CLOSURE):
        return ac.activation_status(view(item), self.c.state(), closure)

    def test_grant_activates_and_requires_all_identity(self):
        self.c.grant("i1")
        self.assertEqual(self.status(), "activated")
        st = self.c.state()
        self.assertEqual(ac.activation_status(view(sha="c" * 64), st, CLOSURE), "grant-stale")
        self.assertEqual(ac.activation_status({**view(), "subject": "p:other"}, st, CLOSURE), "none")
        self.assertEqual(ac.activation_status({**view(), "plan": "q"}, st, CLOSURE), "none")

    def test_relabel_revoke_as_grant_fails(self):
        self.c.grant("i1")
        self.c.revoke("i1")
        seg = self.c.log / "2.json"
        d = json.loads(seg.read_text())
        d["envelope"]["op"] = "grant"           # signed op changed
        d["envelope"].update({"attestation_sha256": SHA, "system_closure": CLOSURE, "evidence_baseline_sha256": BASE})
        d["type"] = "activation.grant"           # unsigned label is ignored
        seg.write_text(json.dumps(d))
        st = self.c.state()
        self.assertFalse(st.ok)
        self.assertEqual(ac.activation_status(view(), st, CLOSURE), "chain-invalid")

    def test_domain_separation(self):
        self.c.grant("i1")
        d = json.loads((self.c.log / "1.json").read_text())
        pk = [pub_hex(self.c.key)]
        self.assertTrue(ac.verify_signature(d["envelope"], d["sig"], pk))
        # same signature over canonical bytes without the domain prefix must not verify
        raw = self.c.key.sign(ac.canonical(d["envelope"])).hex()
        self.assertFalse(ac.verify_signature(d["envelope"], raw, pk))

    def test_wrong_key_rejected(self):
        self.c.grant("i1")
        st = ac.load_chain(self.c.log, self.c.head, [pub_hex(Ed25519PrivateKey.generate())])
        self.assertFalse(st.ok)

    def test_replay_of_older_grant_breaks_chain(self):
        self.c.grant("i1")
        self.c.revoke("i1")
        old = (self.c.log / "1.json").read_text()
        self.c.grant("i2")
        (self.c.log / "3.json").write_text(old)    # replay seq1 envelope at seq 3 (after the revoke)
        self.assertFalse(self.c.state().ok)
        self.assertEqual(self.status(), "chain-invalid")

    def test_deleted_revoke_fails_closed(self):
        self.c.grant("i1")
        self.c.revoke("i1")
        self.c.grant("i2")
        (self.c.log / "2.json").unlink()
        self.assertFalse(self.c.state().ok)
        self.assertEqual(self.status("i2"), "chain-invalid")

    def test_truncated_segment_tail_fails_closed(self):
        self.c.grant("i1")
        self.c.revoke("i1")
        (self.c.log / "2.json").unlink()
        st = self.c.state()
        self.assertFalse(st.ok)
        self.assertEqual(self.status(), "chain-invalid")

    def test_segment_beyond_head_blocks_all(self):
        self.c.grant("i1")
        self.c.grant("i2")
        self.assertEqual(self.status("i2"), "activated")
        self.c.revoke("i1", finalize=False)        # persisted, head not updated (crash window)
        st = self.c.state()
        self.assertTrue(st.blocked_all)
        for it in ("i1", "i2"):
            self.assertEqual(self.status(it), "chain-invalid")
        self.c.write_head()                        # recovery completes
        self.assertEqual(self.status("i2"), "activated")
        self.assertEqual(self.status("i1"), "revoked")

    def test_missing_corrupt_head_and_dir_fail_closed(self):
        self.c.grant("i1")
        self.c.head.write_text("{not json")
        self.assertEqual(self.status(), "chain-invalid")
        self.c.head.unlink()
        self.assertEqual(self.status(), "chain-invalid")
        self.c.write_head()
        self.assertEqual(self.status(), "activated")
        self.c.head.write_text(json.dumps({"seq": 1, "hash": "f" * 64}))
        self.assertEqual(self.status(), "chain-invalid")        # hash mismatch
        self.c.write_head()
        shutil.rmtree(self.c.log)
        self.assertEqual(self.status(), "chain-invalid")

    def test_wave_cannot_clear_revoke_regrant_can(self):
        self.c.grant("i1")
        self.c.revoke("i1")
        self.c.wave("i1", "i2")                    # higher seq than the revoke
        self.assertEqual(self.status("i1"), "revoked")
        self.assertEqual(self.status("i2"), "activated")
        # replay of the whole wave later is still ignored for i1
        self.c.wave("i1", "i2")
        self.assertEqual(self.status("i1"), "revoked")
        self.c.grant("i1")                         # individual regrant, higher seq
        self.assertEqual(self.status("i1"), "activated")

    def test_wave_forgery_and_duplicates_rejected(self):
        self.c.grant("i1")
        self.c.wave("i2")
        seg = self.c.log / "2.json"
        d = json.loads(seg.read_text())
        d["envelope"]["items"].append(self.c.tup("i9"))        # fabricated membership
        seg.write_text(json.dumps(d))
        self.assertFalse(self.c.state().ok)
        c2 = Chain(self.td / "x") if (self.td / "x").mkdir() is None else None
        c2.add("wave-grant", wave_id="w", items=[c2.tup("a"), c2.tup("a")])
        self.assertFalse(c2.state().ok)                         # duplicate entry fails closed

    def test_closure_change_stales_grant(self):
        self.c.grant("i1")
        self.assertEqual(self.status(closure="/nix/store/bbbb-nixos-system-2"), "grant-stale")
        self.assertEqual(self.status(closure=None), "grant-stale")
        self.assertFalse(ac.activation_verified(view(), self.c.state(), "/nix/store/bbbb-nixos-system-2"))

    def test_deployment_id_mismatch_rejected(self):
        self.c.grant("i1")
        st = ac.load_chain(self.c.log, self.c.head, [pub_hex(self.c.key)], deployment_id="other-machine")
        self.assertFalse(st.ok)

    def test_no_genesis_dir_fails(self):
        shutil.rmtree(self.c.log)
        self.c.log.mkdir()
        self.assertFalse(self.c.state().ok)


def run_item(item, ctx, plan="p", gitlog=""):
    return tracker.project_item_full(item, gitlog, "complete", {"prs": {}, "clears": {}, "items": {}, "lanes": []}, plan, ctx)[:2]


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.td, True)
        self.c = Chain(self.td)
        self.att = self.td / "att"
        (self.att / "p").mkdir(parents=True)
        self.body = b"attestation body"
        self.sha = hashlib.sha256(self.body).hexdigest()
        tracker._ACTIVATION_ATTESTATIONS = self.att
        self.addCleanup(setattr, tracker, "_ACTIVATION_ATTESTATIONS", REPO / ".agents" / "activation" / "attestations")

    def ctx(self, closure=CLOSURE):
        return {"ac": ac, "state": self.c.state(), "closure": closure}

    def grant(self, item="i1"):
        self.c.grant(item, sha=self.sha)
        (self.att / "p" / f"{item}-{self.sha[:12]}.md").write_bytes(self.body)

    def test_accepted_without_grant_is_not_activated(self):
        acc = {"status": "accepted", "by": "hyperd", "date": "2026-10-30"}
        items = [
            {"id": "i1", "kind": "task", "acceptance": acc,
             "detection": {"activation_subject": "p:i1", "blocker_note": "owner acts"}},
            {"id": "i2", "acceptance": acc, "detection": {"activation_subject": "p:i2", "systemd_unit": "x.service"}},
            {"id": "i3", "acceptance": acc, "detection": {"activation_subject": "p:i3", "command": "sh"}},
        ]
        self.grant("zzz")                       # a valid chain exists, but not for these items
        tracker._SYSTEMD_CACHE["x.service"] = {"ActiveState": "active"}
        self.addCleanup(tracker._SYSTEMD_CACHE.pop, "x.service", None)
        for it in items:
            self.assertNotEqual(run_item(it, self.ctx())[0], "ACTIVATED", it["id"])
            self.assertNotEqual(run_item(it, None)[0], "ACTIVATED", it["id"])

    def test_service_item_with_verified_grant_is_activated(self):
        tracker._SYSTEMD_CACHE["x.service"] = {"ActiveState": "active"}
        self.addCleanup(tracker._SYSTEMD_CACHE.pop, "x.service", None)
        item = {"id": "i1", "detection": {"activation_subject": "p:i1", "systemd_unit": "x.service"}}
        self.assertEqual(run_item(item, self.ctx())[0], "IN-PROGRESS")
        self.grant()
        self.assertEqual(run_item(item, self.ctx()), ("ACTIVATED", 100))
        self.assertEqual(run_item(item, self.ctx("/nix/store/other"))[0], "IN-PROGRESS")   # stale
        (self.att / "p" / f"i1-{self.sha[:12]}.md").write_bytes(b"edited after signing")
        self.assertEqual(run_item(item, self.ctx())[0], "IN-PROGRESS")                     # attestation replaced
        # service not actually running => live ground truth wins, no ACTIVATED
        tracker._SYSTEMD_CACHE["x.service"] = {"ActiveState": "inactive", "UnitFileState": "disabled"}
        (self.att / "p" / f"i1-{self.sha[:12]}.md").write_bytes(self.body)
        self.assertNotEqual(run_item(item, self.ctx())[0], "ACTIVATED")

    def test_owner_act_and_plain_items_activate_only_via_grant(self):
        self.grant()
        owner = {"id": "i1", "kind": "task", "detection": {"activation_subject": "p:i1", "blocker_note": "owner acts"}}
        plain = {"id": "i1", "phase": "build", "detection": {"activation_subject": "p:i1"}}
        for it in (owner, plain):
            self.assertEqual(run_item(it, self.ctx()), ("ACTIVATED", 100))
            self.assertNotEqual(run_item(it, None)[0], "ACTIVATED")
        self.c.revoke("i1")
        self.assertNotEqual(run_item(plain, self.ctx())[0], "ACTIVATED")

    def test_projector_has_no_other_activated_route(self):
        src = (REPO / "scripts" / "ai" / "aq-pm-tracker").read_text()
        self.assertNotIn("_aq_grants", src)
        self.assertNotIn("activation.grant {", src)
        body = src[src.index("def project_item("):src.index("def _rollup")]
        rs = (REPO / "scripts" / "ai" / "lib" / "refactor_status.py").read_text()
        for needle in ("_activation_events", "activated_subjects"):
            self.assertNotIn(needle, rs)    # second unsigned route (agent=owner events) stays removed
        out = []
        for root in ("scripts/ai", "ai-stack", "dashboard/backend"):
            for f in (REPO / root).rglob("*"):
                if f.is_file() and f.suffix in ("", ".py", ".sh", ".js", ".ts") and "node_modules" not in f.parts:
                    try:
                        if "ACTIVATED" in f.read_text(encoding="utf-8", errors="ignore"):
                            out.append(f.relative_to(REPO).as_posix())
                    except OSError:
                        pass
        allowed = {"scripts/ai/aq-pm-tracker", "scripts/ai/lib/activation_chain.py",
                   "scripts/ai/lib/refactor_status.py", "scripts/ai/lib/oncalld_engine.py"}
        self.assertEqual(set(out) - allowed, set(),
                         "new file mentions ACTIVATED: route it through activation_verified, then add it here")
        lines = body.splitlines()
        for n, line in enumerate(lines):
            if "ACTIVATED" in line and "return" in line:   # the return, or the `if verified:` guarding it
                self.assertIn("verified", line + lines[n - 1], line)

    def test_false_shipped_command_and_freeze(self):
        acc = {"status": "accepted", "by": "hyperd", "date": "2026-10-30"}
        cmd = {"id": "c", "acceptance": acc, "detection": {"command": "sh", "commit_match": ["never-appears-xyz"]}}
        self.assertEqual(run_item(cmd, None, gitlog="abc unrelated")[0], "IN-PROGRESS")
        self.assertEqual(run_item(cmd, None, gitlog="abc never-appears-xyz (#1)")[0], "SHIPPED")
        # freeze record + commit hit, not accepted: not SHIPPED
        fr = {"id": "f", "detection": {"freeze_record": "README.md", "commit_match": ["hit-me"]}}
        self.assertEqual(run_item(fr, None, gitlog="abc hit-me (#1)")[0], "IN-PROGRESS")
        fr["acceptance"] = acc
        self.assertEqual(run_item(fr, None, gitlog="abc hit-me (#1)")[0], "SHIPPED")


if __name__ == "__main__":
    unittest.main(verbosity=1)
