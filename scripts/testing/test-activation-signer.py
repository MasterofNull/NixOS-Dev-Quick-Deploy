#!/usr/bin/env python3
"""Activation signer (slice 2) tests that need no root: the signer runs in-process against temp
state/etc dirs with a temp key; slice 1's verifier then reads what it wrote (end-to-end)."""
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
import activation_signer as sg  # noqa: E402

GOOD_UNIT = ("ExecStart={ path=/nix/store/aaaa-x/bin/x ; argv[]=/nix/store/aaaa-x/bin/x --a ; ignore_errors=no ; "
             "start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n"
             "Environment=PATH=/nix/store/bbbb-p/bin:/nix/store/cccc-q/bin\nEnvironmentFile=\n")


class Fixture:
    def __init__(self, td: Path, unit_text=GOOD_UNIT, tty=True, confirm=True):
        self.td = td
        self.state, self.etc = td / "state", td / "etc"
        self.state.mkdir()
        self.etc.mkdir()
        self.sysdir = td / "sys-1-closure"
        self.sysdir.mkdir()
        (td / "current-system").symlink_to(self.sysdir)
        self.closure = os.path.realpath(self.sysdir)
        self.paths = sg.Paths(state=self.state, etc=self.etc, current_system=td / "current-system")
        self.pub = sg.init_key(self.paths)
        self.write_etc(signers=[self.pub])
        self.unit_text = unit_text
        self.tty, self.confirm_answer, self.displayed, self.on_confirm = tty, confirm, [], None
        self.out = []
        self.env = sg.Env(paths=self.paths, approver="hyperd", is_tty=lambda: self.tty, confirm=self._confirm,
                          unit_show=lambda u: self.unit_text, now=lambda: "2026-10-31T00:00:00Z", out=self.out.append)

    def _confirm(self, display, token):
        self.displayed.append(display)
        if self.on_confirm:
            self.on_confirm()
        return self.confirm_answer

    def write_etc(self, signers=None, dep="dep1", eligible=None):
        (self.etc / "signers.json").write_text(json.dumps({"keys": signers if signers is not None else []}))
        (self.etc / "deployment-id").write_text(dep + "\n")
        (self.etc / "eligible.json").write_text(json.dumps(
            eligible if eligible is not None else [{"plan": "p", "item": "i1", "units": ["x.service"], "paths": [], "state_paths": []},
                                                    {"plan": "p", "item": "i2", "units": ["x.service"], "paths": [], "state_paths": []}]))

    def file(self, name, text, mode=0o644):
        p = self.td / name
        p.write_text(text)
        p.chmod(mode)
        return p

    def grant_req(self, item="i1", rid="req00001", **over):
        att = self.file(f"att-{item}.md", f"attestation for {item}\n")
        val = self.file(f"val-{item}.md", f"validation ran on {self.closure}\n")
        vd = sg.sha256_hex(val.read_bytes())
        rev = self.file(f"rev-{item}.md", f"PASS reviewed validation {vd} on {self.closure}\n")
        req = {"request_id": rid, "op": "grant", "plan": "p", "item_id": item, "subject": f"p:{item}",
               "attestation_path": str(att), "validation_path": str(val), "review_path": str(rev),
               "review_digest": sg.sha256_hex(rev.read_bytes()), "enable_evidence": "services.x.enable = true",
               "detection_snapshot": {"systemd_unit": "x.service"}}
        req.update(over)
        return req

    def req_file(self, req, name="request.json"):
        return str(self.file(name, json.dumps(req)))

    def run(self, op, req, name="request.json"):
        return sg.sign(self.env, op, self.req_file(req, name))

    def init(self):
        return sg.init_chain(self.env)

    def state_view(self):
        return ac.load_chain(self.paths.log, self.paths.head, [self.pub], "dep1")


class SignerTests(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.td, True)
        self.f = Fixture(self.td)

    def refuses(self, fn, text=""):
        with self.assertRaises(sg.SignerError) as cm:
            fn()
        self.assertIn(text, str(cm.exception))

    def activated(self, item="i1", sha=None):
        v = {"plan": "p", "item_id": item, "subject": f"p:{item}",
             "attestation_sha256": sha or sg.sha256_hex(f"attestation for {item}\n".encode())}
        return ac.activation_status(v, self.f.state_view(), self.f.closure)

    # ---- key + init-chain
    def test_key_file_mode_and_idempotent(self):
        self.assertEqual(self.f.paths.key.stat().st_mode & 0o777, 0o400)
        again = sg.init_key(self.f.paths)
        self.assertEqual(again, self.f.pub)
        self.assertEqual(self.f.paths.pub.read_text().strip(), self.f.pub)

    def test_init_chain_then_verifies_and_refuses_reinit(self):
        self.f.init()
        s = self.f.state_view()
        self.assertTrue(s.ok, s.reason)
        self.refuses(self.f.init, "refusing to initialise")
        self.f.paths.head.unlink()
        self.refuses(self.f.init, "not empty")   # segments with no head: only --recover may repair

    def test_requires_tty_and_confirmation(self):
        self.f.tty = False
        self.refuses(self.f.init, "interactive terminal")
        self.f.tty = True
        self.f.confirm_answer = False
        self.refuses(self.f.init, "not confirmed")
        self.assertFalse(self.f.paths.head.exists())

    def test_unpinned_key_refused(self):
        self.f.write_etc(signers=[])
        self.refuses(self.f.init, "no signer public key")
        self.f.write_etc(signers=["0" * 64])
        self.refuses(self.f.init, "not pinned")

    # ---- end to end
    def test_grant_end_to_end_activates(self):
        self.f.init()
        self.assertEqual(self.f.run("grant", self.f.grant_req()), 0)
        self.assertEqual(self.activated(), "activated")
        self.assertEqual(self.activated("i2"), "none")
        seg = json.loads((self.f.paths.log / "1.json").read_text())
        self.assertEqual(seg["envelope"]["approver"], "hyperd")
        ev = self.f.paths.evidence / "1"
        self.assertEqual({p.name for p in ev.iterdir()}, {"attestation.md", "validation.md", "review.md", "envelope-digests.json"})
        self.assertIn("manifest entry relied on", self.f.displayed[-1])
        v = {"plan": "p", "item_id": "i1", "subject": "p:i1", "attestation_sha256": seg["envelope"]["attestation_sha256"]}
        self.assertTrue(ac.activation_verified(v, self.f.state_view(), self.f.closure))
        self.assertFalse(ac.activation_verified(v, self.f.state_view(), "/nix/store/other"))

    def test_revoke_then_wave_cannot_clear(self):
        self.f.init()
        self.f.run("grant", self.f.grant_req("i1", "req00001"), "r1.json")
        self.f.run("revoke", {"request_id": "req00002", "op": "revoke", "plan": "p", "item_id": "i1", "subject": "p:i1"}, "r2.json")
        self.assertEqual(self.activated(), "revoked")
        wave = {"request_id": "req00003", "op": "wave-grant", "wave_id": "w1",
                "items": [self.f.grant_req("i2", "x" * 8), self.f.grant_req("i1", "y" * 8)]}
        self.f.run("wave-grant", wave, "r3.json")
        self.assertEqual(self.activated("i2"), "activated")
        self.assertEqual(self.activated("i1"), "revoked")
        self.f.run("grant", self.f.grant_req("i1", "req00004"), "r4.json")
        self.assertEqual(self.activated("i1"), "activated")
        self.assertEqual(self.f.state_view().head_seq, 4)

    # ---- request validation / refusals
    def test_request_id_and_op_validation(self):
        self.f.init()
        for rid in ("../etc/passwd", "short", "UPPERCASE1", "a" * 41, ""):
            self.refuses(lambda r=rid: self.f.run("grant", self.f.grant_req(rid=r)), "request_id")
        self.refuses(lambda: self.f.run("revoke", self.f.grant_req()), "op does not match")
        self.assertEqual(self.f.state_view().head_seq, 0)

    def test_item_refusals(self):
        self.f.init()
        self.refuses(lambda: self.f.run("grant", self.f.grant_req("i9")), "not eligible")
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(subject="p:other")), "subject")
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(plan="../x")), "plan/item_id")
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(review_digest="0" * 64)), "review_digest")
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(system_closure="/nix/store/other")), "closure")
        att = self.f.grant_req()
        Path(att["attestation_path"]).write_text("dim 3: MISSING: none yet\n")
        self.refuses(lambda: self.f.run("grant", att), "MISSING")
        self.f.write_etc(signers=[self.f.pub], eligible=[{"plan": "p", "item": "i1", "units": [], "paths": [], "state_paths": []}])
        self.refuses(lambda: self.f.run("grant", self.f.grant_req()), "no units")
        self.assertEqual(self.f.state_view().head_seq, 0)

    def test_artifact_binding(self):
        self.f.init()
        req = self.f.grant_req()
        Path(req["validation_path"]).write_text("validated something else\n")
        rev = Path(req["review_path"])
        req["review_digest"] = sg.sha256_hex(rev.read_bytes())
        self.refuses(lambda: self.f.run("grant", req), "validation artifact does not reference")
        req = self.f.grant_req()
        rev = Path(req["review_path"])
        rev.write_text(f"PASS on {self.f.closure} but no digest\n")
        req["review_digest"] = sg.sha256_hex(rev.read_bytes())
        self.refuses(lambda: self.f.run("grant", req), "review artifact must embed")

    def test_unit_path_rules(self):
        self.f.init()
        bad = {
            "home": "ExecStart={ path=/home/hyperd/x ; argv[]=/home/hyperd/x }\n",
            "checkout": "ExecStart={ path=/nix/store/a-x/bin/x ; argv[]=/nix/store/a-x/bin/x /opt/repo/run.sh }\n",
            "env": GOOD_UNIT + "Environment=CFG=/etc/mutable.conf\n",
            "envfile": GOOD_UNIT + "EnvironmentFile=/var/lib/foo.env (ignore_errors=no)\n",
            "ro": GOOD_UNIT + "ReadOnlyPaths=/home/hyperd/cfg\n",
            "empty": "",
            "noexec": "Environment=PATH=/nix/store/b/bin\n",
        }
        for name, text in bad.items():
            self.f.unit_text = text
            with self.assertRaises(sg.SignerError, msg=name):
                self.f.run("grant", self.f.grant_req())
        # a declared manifest path is acceptable; /home never is
        self.f.write_etc(signers=[self.f.pub], eligible=[{"plan": "p", "item": "i1", "units": ["x.service"],
                                                          "paths": ["/etc/mutable.conf"], "state_paths": ["/var/lib/foo"]}])
        self.f.unit_text = GOOD_UNIT + "Environment=CFG=/etc/mutable.conf\nEnvironmentFile=/var/lib/foo/e (ignore_errors=no)\n"
        self.assertEqual(self.f.run("grant", self.f.grant_req()), 0)

    # ---- file safety
    def test_symlink_and_private_file_not_followed(self):
        self.f.init()
        req = self.f.grant_req()
        link = self.td / "att-link.md"
        link.symlink_to(req["attestation_path"])
        req["attestation_path"] = str(link)
        self.refuses(lambda: self.f.run("grant", req), "cannot open")
        req = self.f.grant_req()
        os.chmod(req["review_path"], 0o600)
        self.refuses(lambda: self.f.run("grant", req), "world-readable")
        self.refuses(lambda: sg.safe_read("relative/path"), "bad path")
        reqlink = self.td / "request-link.json"
        reqlink.symlink_to(self.f.req_file(self.f.grant_req()))
        self.refuses(lambda: sg.sign(self.f.env, "grant", str(reqlink)), "cannot open")

    def test_snapshot_signed_bytes_are_the_displayed_bytes(self):
        self.f.init()
        req = self.f.grant_req()
        original = Path(req["attestation_path"]).read_bytes()
        self.f.on_confirm = lambda: Path(req["attestation_path"]).write_text("swapped after display\n")
        self.f.run("grant", req)
        seg = json.loads((self.f.paths.log / "1.json").read_text())
        self.assertEqual(seg["envelope"]["attestation_sha256"], sg.sha256_hex(original))
        self.assertEqual((self.f.paths.evidence / "1" / "attestation.md").read_bytes(), original)
        self.assertIn("attestation for i1", self.f.displayed[-1])

    def test_terminal_escapes_stripped_from_display(self):
        self.f.init()
        req = self.f.grant_req()
        Path(req["attestation_path"]).write_text("hello \x1b[2J\x07 world\n")
        self.f.run("grant", req)
        self.assertNotIn("\x1b", self.f.displayed[-1])

    # ---- crash recovery
    def test_crash_between_segment_and_head_blocks_then_completes(self):
        self.f.init()
        self.f.run("grant", self.f.grant_req("i1", "req00001"), "r1.json")
        real = sg._write_file
        calls = {"n": 0}

        def boom(path, data, mode=0o644):
            if path.name == "head":
                calls["n"] += 1
                raise OSError("simulated crash")
            return real(path, data, mode)
        sg._write_file = boom
        try:
            with self.assertRaises(OSError):
                self.f.run("revoke", {"request_id": "req00002", "op": "revoke", "plan": "p", "item_id": "i1", "subject": "p:i1"}, "r2.json")
        finally:
            sg._write_file = real
        s = self.f.state_view()
        self.assertTrue(s.blocked_all)
        self.assertEqual(self.activated("i1"), "chain-invalid")   # nothing projects ACTIVATED while pending
        self.f.run("grant", self.f.grant_req("i2", "req00003"), "r3.json")   # next signer run completes the head first
        self.assertTrue(any("completed pending head" in o for o in self.f.out))
        self.assertEqual(self.activated("i1"), "revoked")
        self.assertEqual(self.activated("i2"), "activated")
        seqs = sorted(int(p.stem) for p in self.f.paths.log.glob("[0-9]*.json"))
        self.assertEqual(seqs, [0, 1, 2, 3])

    def test_recover_rebuilds_missing_head_and_refuses_tampering(self):
        self.f.init()
        self.f.run("grant", self.f.grant_req(), "r1.json")
        self.f.paths.head.unlink()
        self.refuses(lambda: self.f.run("grant", self.f.grant_req("i2", "req00009"), "r2.json"), "not healthy")
        self.assertEqual(sg.recover(self.f.env), 0)
        self.assertEqual(self.activated(), "activated")
        self.assertEqual(sg.recover(self.f.env), 0)
        # tampered segment: recovery refuses and writes no head
        self.f.paths.head.unlink()
        seg = self.f.paths.log / "1.json"
        data = json.loads(seg.read_text())
        data["envelope"]["system_closure"] = "/nix/store/forged"
        seg.write_text(json.dumps(data))
        self.refuses(lambda: sg.recover(self.f.env), "does not verify")
        self.assertFalse(self.f.paths.head.exists())

    def test_main_usage_and_refusal_exit_codes(self):
        self.assertEqual(sg.main(["bogus"], environ={}, env=self.f.env), 2)
        self.f.tty = False
        self.assertEqual(sg.main(["--init-chain"], environ={}, env=self.f.env), 1)
        self.assertEqual(sg.main(["--init-key"], environ={}, env=self.f.env), 0)
        self.assertEqual(sg.main(["--init-key"], environ={"SUDO_USER": "bad user!"}, paths=self.f.paths), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
