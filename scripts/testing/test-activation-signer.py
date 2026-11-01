#!/usr/bin/env python3
"""Activation signer (slice 2) tests that need no root: the signer runs in-process against temp
state/etc dirs with a temp key; slice 1's verifier then reads what it wrote (end-to-end)."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
import activation_chain as ac  # noqa: E402
import activation_signer as sg  # noqa: E402

GOOD_UNIT = ("ExecStart={ path=/nix/store/aaaa-x/bin/x ; argv[]=/nix/store/aaaa-x/bin/x --a ; ignore_errors=no ; "
             "start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n"
             "Environment=PATH=/nix/store/bbbb-p/bin:/nix/store/cccc-q/bin\nEnvironmentFiles=\n")


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
                          unit_show=lambda u: self.unit_text, invoker=lambda: (os.getuid(), os.getgid()), now=lambda: "2026-10-31T00:00:00Z", out=self.out.append)

    def _confirm(self, display, token):
        self.displayed.append(display)
        if self.on_confirm:
            self.on_confirm()
        return self.confirm_answer

    def write_etc(self, signers=None, dep="dep-test-1", eligible=None):
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

    def att_text(self, item="i1", **over):
        dims = {"Integrated": "scripts/x.py:10", "Turned ON": "services.x.enable; systemctl is-active x",
                "Validated": "ran x, observed ok", "Observable": "deferred: no dashboard yet, 2026-11-15",
                "Intervenable": "N/A: no bad-state surface", "PM-tracked": "tracker.json editorial updated"}
        hdr = {"Author-Lane": "claude", "System-Closure": self.closure, "Config-Revision": "2e411909c85a"}
        dims.update({k: v for k, v in over.items() if k in dims})
        hdr.update({k: v for k, v in over.items() if k in hdr})
        lines = [f"Definition-of-Done attestation - {item}"] + [f"  {i} {k}: {v}" for i, (k, v) in enumerate(dims.items(), 1) if v is not None]
        return "\n".join(lines + [f"{k}: {v}" for k, v in hdr.items() if v is not None]) + "\n"

    def rev_text(self, vd, **over):
        f = {"Review-Disposition": "PASS", "Reviewer-Lane": "codex", "Reviewed-Closure": self.closure,
             "Reviewed-Validation-Digest": vd}
        f.update(over)
        return "".join(f"{k}: {v}\n" for k, v in f.items())

    def grant_req(self, item="i1", rid="req00001", att_text=None, rev_over=None, **over):
        att = self.file(f"att-{item}.md", att_text if att_text is not None else self.att_text(item))
        val = self.file(f"val-{item}.md", f"validation ran on {self.closure}\n")
        vd = sg.sha256_hex(val.read_bytes())
        rev = self.file(f"rev-{item}.md", self.rev_text(vd, **(rev_over or {})))
        req = {"request_id": rid, "op": "grant", "plan": "p", "item_id": item, "subject": f"p:{item}",
               "attestation_path": str(att), "validation_path": str(val), "review_path": str(rev),
               "attestation_sha256": sg.sha256_hex(att.read_bytes()),
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
        return ac.load_chain(self.paths.log, self.paths.head, [self.pub], "dep-test-1")


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
             "attestation_sha256": sha or sg.sha256_hex(self.f.att_text(item).encode())}
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
        self.assertEqual({p.name for p in ev.iterdir()}, {"attestation.md", "validation.md", "review.md", "baseline-inputs.json", "envelope-digests.json"})
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
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(att_text=self.f.att_text(Validated="MISSING: none yet"))), "MISSING")
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
        rev.write_text(self.f.rev_text("0" * 64))
        req["review_digest"] = sg.sha256_hex(rev.read_bytes())
        self.refuses(lambda: self.f.run("grant", req), "review artifact must name")

    def test_unit_path_rules(self):
        self.f.init()
        bad = {
            "home": "ExecStart={ path=/home/hyperd/x ; argv[]=/home/hyperd/x }\n",
            "checkout": "ExecStart={ path=/nix/store/a-x/bin/x ; argv[]=/nix/store/a-x/bin/x /opt/repo/run.sh }\n",
            "env": GOOD_UNIT + "Environment=CFG=/etc/mutable.conf\n",
            "envfile": GOOD_UNIT + "EnvironmentFiles=/var/lib/foo.env (ignore_errors=no)\n",
            "traversal": "ExecStart={ path=/nix/store/a-x/../../../home/x/run ; argv[]=/nix/store/a-x/../../x }\n",
            "empty-execstart": "ExecStart=\nEnvironment=PATH=/nix/store/b/bin\n",
            "state-as-exec": "ExecStart={ path=/var/lib/foo/run ; argv[]=/var/lib/foo/run }\n",
            "state-as-env": GOOD_UNIT + "Environment=CFG=/var/lib/foo/cfg\n",
            "ro": GOOD_UNIT + "ReadOnlyPaths=/home/hyperd/cfg\n",
            "empty": "",
            "noexec": "Environment=PATH=/nix/store/b/bin\n",
        }
        for name, text in bad.items():
            self.f.unit_text = text
            with self.assertRaises(sg.SignerError, msg=name):
                self.f.run("grant", self.f.grant_req())
        # declared state paths satisfy only state-class properties (never exec/config), /home never
        self.f.write_etc(signers=[self.f.pub], eligible=[{"plan": "p", "item": "i1", "units": ["x.service"],
                                                          "paths": [], "state_paths": ["/var/lib/foo", "/var/lib/foo/run"]}])
        for name in ("state-as-exec", "state-as-env", "envfile"):
            self.f.unit_text = bad[name]
            with self.assertRaises(sg.SignerError, msg=name):
                self.f.run("grant", self.f.grant_req())
        self.f.unit_text = GOOD_UNIT + "ReadOnlyPaths=/var/lib/foo/data\n"
        self.assertEqual(self.f.run("grant", self.f.grant_req()), 0)

    def test_relative_and_mutable_dependencies_refused(self):
        self.f.init()
        py = "/nix/store/aaaa-py/bin/python3"
        def ex(prop, argv, path=py):
            return (f"{prop}={{ path={path} ; argv[]={path} {argv} ; ignore_errors=no ; start_time=[n/a] ; "
                    "stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n")
        base = ex("ExecStart", "/nix/store/aaaa-x/w.py")
        wd = "WorkingDirectory=/var/lib/foo\n"
        self.f.write_etc(signers=[self.f.pub], eligible=[{"plan": "p", "item": "i1", "units": ["x.service"],
                                                          "paths": [], "state_paths": ["/var/lib/foo"]}])
        bad = {
            "relative-script": ex("ExecStart", "worker.py") + wd,
            "relative-subdir": ex("ExecStart", "bin/run") + wd,
            "dot-relative": ex("ExecStart", "./run") + wd,
            "relative-opt-value": ex("ExecStart", "--config=conf/a") + wd,
            "inline-code": ex("ExecStart", "-c print(1)") + wd,
            "relative-exe": ex("ExecStart", "", path="bin/x") + wd,
            "pythonpath-relative": base + wd + "Environment=PYTHONPATH=.\n",
            "pythonpath-empty-entry": base + wd + "Environment=PYTHONPATH=/nix/store/a-p::/nix/store/b-p\n",
            "pythonpath-mutable": base + wd + "Environment=PYTHONPATH=/var/lib/foo\n",
            "path-relative": base + "Environment=PATH=bin:/nix/store/a-b/bin\n",
            "ld-library-path": base + "Environment=LD_LIBRARY_PATH=/var/lib/foo\n",
            "ld-preload-relative": base + "Environment=LD_PRELOAD=evil.so\n",
            "stopPost-mutable": base + "ExecStopPost={ path=/var/lib/foo/x ; argv[]=/var/lib/foo/x ; ignore_errors=no }\n",
            "condition-relative": base + ex("ExecCondition", "check.sh") + wd,
            "condition-mutable": base + ex("ExecCondition", "", path="/var/lib/foo/c") + wd,
            "startpre-relative": base + ex("ExecStartPre", "prep.sh"),
            "unparseable": "ExecStart=garbage\n",
        }
        for name, text in bad.items():
            self.f.unit_text = text
            with self.assertRaises(sg.SignerError, msg=name):
                self.f.run("grant", self.f.grant_req())
        # store-only dependencies (python running a store script, store PYTHONPATH) are accepted
        self.f.unit_text = (base + wd + "Environment=PYTHONPATH=/nix/store/a-p/lib:/nix/store/b-p/lib "
                            "PATH=/nix/store/c-b/bin\nExecCondition={ path=/nix/store/d-t/bin/test ; "
                            "argv[]=/nix/store/d-t/bin/test -f /var/lib/foo/flag ; ignore_errors=no }\n")
        with self.assertRaises(sg.SignerError):      # a mutable absolute arg is still not a store path
            self.f.run("grant", self.f.grant_req())
        self.f.unit_text = base + wd + "Environment=PYTHONPATH=/nix/store/a-p/lib:/nix/store/b-p/lib PATH=/nix/store/c-b/bin\n"
        self.assertEqual(self.f.run("grant", self.f.grant_req()), 0)

    def test_fifo_final_component_does_not_block(self):
        fifo = self.td / "fifo"
        os.mkfifo(fifo, 0o644)
        done = []
        t = threading.Thread(target=lambda: done.append(self._try_read(str(fifo))), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "safe_read blocked on a FIFO")
        self.assertIn("not a regular file", done[0])

    def _try_read(self, path):
        try:
            sg.safe_read(path, invoker=(os.geteuid(), os.getegid()))
        except sg.SignerError as e:
            return str(e)
        return "read"

    def test_store_symlink_escape_refused(self):
        self.assertTrue(sg._store_path("/nix/store/aaaa-x/bin/x"))
        self.assertFalse(sg._store_path("/nix/storeX/a"))
        self.refuses(lambda: sg._canon("/nix/store/a/../b"), "'..'")

    # ---- attestation / review validation (signer-side, rev7)
    def attest_refused(self, text, msg, **kw):
        if not self.f.paths.head.exists():
            self.f.init()
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(att_text=text, **kw)), msg)
        self.assertEqual(self.f.state_view().head_seq, 0)

    def test_attestation_one_liner_malformed(self):
        self.attest_refused("attestation for i1\n", "dimension 'Integrated' is absent")

    def test_attestation_missing_dimension(self):
        self.attest_refused(self.f.att_text(Intervenable=None), "'Intervenable' is absent")

    def test_attestation_undated_deferral(self):
        self.attest_refused(self.f.att_text(Observable="deferred: later"), "reason and a date")
        self.attest_refused(self.f.att_text(Observable="deferred: soon, 2026-13-45"), "not a valid date")

    def test_attestation_closure_revision_digest(self):
        self.attest_refused(self.f.att_text(**{"System-Closure": "/nix/store/other"}), "System-Closure")
        self.attest_refused(self.f.att_text(**{"Config-Revision": "abc1234-dirty"}), "Config-Revision")
        req = self.f.grant_req()
        req["attestation_sha256"] = "0" * 64
        self.refuses(lambda: self.f.run("grant", req), "attestation_sha256")

    def test_negative_review_mentioning_closure_and_digest_rejected(self):
        self.f.init()
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(rev_over={"Review-Disposition": "REQUEST_CHANGES"})), "not PASS")
        req = self.f.grant_req()
        vd = sg.sha256_hex(Path(req["validation_path"]).read_bytes())
        Path(req["review_path"]).write_text(f"Review-Disposition: REQUEST_CHANGES\nReviewer-Lane: codex\n"
                                            f"Reviewed-Closure: {self.f.closure}\nReviewed-Validation-Digest: {vd}\n"
                                            f"PASS is wrong; Review-Disposition: PASS would be dishonest\n")
        req["review_digest"] = sg.sha256_hex(Path(req["review_path"]).read_bytes())
        self.refuses(lambda: self.f.run("grant", req), "not PASS")
        Path(req["review_path"]).write_text(f"verdict was PASS on {self.f.closure} digest {vd}\n")
        req["review_digest"] = sg.sha256_hex(Path(req["review_path"]).read_bytes())
        self.refuses(lambda: self.f.run("grant", req), "missing field")

    def test_same_lane_review_rejected(self):
        self.f.init()
        self.refuses(lambda: self.f.run("grant", self.f.grant_req(rev_over={"Reviewer-Lane": "Claude"})), "self-review")
        self.assertEqual(self.f.run("grant", self.f.grant_req(rev_over={"Review-Disposition": "PASS_WITH_FOLLOWUPS"})), 0)

    def test_evidence_values_authenticated_and_displayed(self):
        self.f.init()
        self.f.run("grant", self.f.grant_req())
        seg = json.loads((self.f.paths.log / "1.json").read_text())
        raw = (self.f.paths.evidence / "1" / "baseline-inputs.json").read_bytes()
        self.assertEqual(sg.sha256_hex(raw), seg["envelope"]["evidence_baseline_sha256"])
        got = json.loads(raw)
        self.assertEqual(got["enable_evidence"], "services.x.enable = true")
        self.assertEqual(got["detection_snapshot"], {"systemd_unit": "x.service"})
        self.assertIn('"systemd_unit": "x.service"', self.f.displayed[-1])

    # ---- deployment identity
    def test_deployment_identity_single_resolution(self):
        paths = sg.Paths(state=self.f.state, etc=self.td / "etc2", machine_id=self.td / "machine-id")
        paths.etc.mkdir()
        # signer's load path reads only the provisioned file (the verifier reads the same one)
        self.refuses(lambda: sg.load_deployment_id(paths), "absent")
        self.refuses(lambda: sg.init_id(paths), "cannot derive")
        (paths.etc / "deployment-salt").write_text("salt\n")
        paths.machine_id.write_text("0" * 32 + "\n")
        self.refuses(lambda: sg.init_id(paths), "machine-id")
        paths.machine_id.write_text("a" * 32 + "\n")
        a = sg.init_id(paths)
        self.assertEqual(a, sg.sha256_hex(("salt:" + "a" * 32).encode())[:32])
        self.assertEqual(sg.load_deployment_id(paths), a)
        paths.machine_id.write_text("b" * 32 + "\n")          # never overwrites an existing id
        self.assertEqual(sg.init_id(paths), a)
        (paths.etc / "deployment-id").write_text("\n")
        self.refuses(lambda: sg.load_deployment_id(paths), "malformed")
        (paths.etc / "deployment-id").write_text("explicit-id-1\n")
        self.assertEqual(sg.load_deployment_id(paths), "explicit-id-1")

    def test_invoking_identity_fails_closed_under_root(self):
        real = os.geteuid
        os.geteuid = lambda: 0
        try:
            self.refuses(lambda: sg.invoking_identity({}), "SUDO_UID")
            self.refuses(lambda: sg.invoking_identity({"SUDO_UID": "0", "SUDO_GID": "0"}), "root")
            self.assertEqual(sg.invoking_identity({"SUDO_UID": "1000", "SUDO_GID": "100"}), (1000, 100))
        finally:
            os.geteuid = real

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
        self.refuses(lambda: sg.safe_read(str(self.td / ".." / "x")), "bad path")
        reqlink = self.td / "request-link.json"
        reqlink.symlink_to(self.f.req_file(self.f.grant_req()))
        self.refuses(lambda: sg.sign(self.f.env, "grant", str(reqlink)), "cannot open")

    def test_private_and_symlinked_ancestors_refused(self):
        me = (os.getuid(), os.getgid())
        other = (os.getuid() + 1, os.getgid() + 1)
        self.td.chmod(0o755)
        priv = self.td / "priv"
        priv.mkdir()
        f = priv / "doc.md"
        f.write_text("x\n")
        f.chmod(0o644)
        priv.chmod(0o700)
        self.assertEqual(sg.safe_read(str(f), invoker=me), b"x\n")
        self.refuses(lambda: sg.safe_read(str(f), invoker=other), "cannot search")
        priv.chmod(0o755)
        self.assertEqual(sg.safe_read(str(f), invoker=other), b"x\n")
        f.chmod(0o640)
        self.refuses(lambda: sg.safe_read(str(f), invoker=other), "cannot read")
        f.chmod(0o644)
        link = self.td / "linkdir"
        link.symlink_to(priv)
        self.refuses(lambda: sg.safe_read(str(link / "doc.md"), invoker=me), "cannot open")

    def test_snapshot_signed_bytes_are_the_displayed_bytes(self):
        self.f.init()
        req = self.f.grant_req()
        original = Path(req["attestation_path"]).read_bytes()
        self.f.on_confirm = lambda: Path(req["attestation_path"]).write_text("swapped after display\n")
        self.f.run("grant", req)
        seg = json.loads((self.f.paths.log / "1.json").read_text())
        self.assertEqual(seg["envelope"]["attestation_sha256"], sg.sha256_hex(original))
        self.assertEqual((self.f.paths.evidence / "1" / "attestation.md").read_bytes(), original)
        self.assertIn("Definition-of-Done attestation - i1", self.f.displayed[-1])

    def test_terminal_escapes_stripped_from_display(self):
        self.f.init()
        req = self.f.grant_req()
        req = self.f.grant_req(att_text=self.f.att_text(Integrated="hello \x1b[2J\x07 world"))
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
