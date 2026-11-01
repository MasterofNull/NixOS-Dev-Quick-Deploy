#!/usr/bin/env python3
"""Verified owner acceptance, slice 1 (interim recorded-evidence delivery).

Covers: approval_ref schema + hash binding + shape validation, the frozen remove-only allowlist gate
(`aq-pm-tracker --check-owner-acceptance`, R4 amendments A and C) against real temporary git repos with a
real bare origin, projection labels/counters, the pm.py API passthrough, dashboard markup, the health-spider
probe, and the unconditional gate wiring. Offline; everything runs in temp dirs."""
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REAL = Path(__file__).resolve().parents[2]
TRACKER = REAL / "scripts" / "ai" / "aq-pm-tracker"
_N = [0]


def load_tracker():
    _N[0] += 1
    loader = importlib.machinery.SourceFileLoader(f"aq_pm_tracker_oa{_N[0]}", str(TRACKER))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(mod)
    return mod


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def acc(note="n", **over):
    d = {"status": "accepted", "by": "hyperd", "date": "2026-10-31", "note": note}
    d.update(over)
    return d


def tracker_doc(items):
    out = []
    for iid, a in items.items():
        it = {"id": iid, "name": iid, "phase": "p1", "goal": "g", "validation_goal": "v"}
        if a is not None:
            it["acceptance"] = a
        out.append(it)
    return {"plan": {"title": "t"}, "phases": [{"id": "p1", "name": "P1"}], "items": out}


def cfg_bytes(entries, note="x"):
    ents = sorted(entries, key=lambda e: (e["plan"], e["item"]))
    return (json.dumps({"schema": 1, "frozen": "2026-10-31", "note": note, "entries": ents}, indent=2) + "\n").encode()


def entry(mod, plan, iid, a):
    return {"plan": plan, "item": iid, "acceptance_sha256": mod.acceptance_sha256(plan, iid, a)}


class Tree:
    """A repo-shaped temp dir (no git) used for validator/projection tests: mod.REPO points here."""

    def __init__(self, td, mod=None):
        self.root = Path(td)
        self.mod = mod or load_tracker()
        self.mod.REPO = self.root

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def plan(self, plan, items):
        self.write(f".agents/plans/{plan}/tracker.json", json.dumps(tracker_doc(items)))
        return self.root / ".agents" / "plans" / plan

    def allowlist(self, entries):
        self.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(entries))

    def record(self, name, plan, iid, h, **over):
        d = {"schema": 1, "kind": "tracker-acceptance", "alert_id": "attn-1", "decision": "approved",
             "plan": plan, "items": [{"id": iid, "acceptance_sha256": h}]}
        d.update(over)
        raw = json.dumps(d, indent=1).encode()
        rel = f".agent/approvals/acceptance/{name}.json"
        self.write(rel, raw)
        return {"record": rel, "sha256": sha(raw)}

    def errors(self, plan_dir):
        return self.mod.validate_manifest(plan_dir)


class RefValidation(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.t = Tree(self._td.name)
        self.addCleanup(self._td.cleanup)
        self.a = acc("block-1")
        self.h = self.t.mod.acceptance_sha256("plan-x", "I1", self.a)

    def check(self, a):
        pd = self.t.plan("plan-x", {"I1": a})
        return self.t.errors(pd)

    def with_ref(self, ref):
        return {**self.a, "approval_ref": ref}

    def test_no_ref_not_allowlisted_is_error(self):
        errs = self.check(self.a)
        self.assertEqual(len(errs), 1)
        self.assertIn("no approval_ref", errs[0])
        self.assertIn("plan-x", errs[0])

    def test_allowlisted_passes_and_projects_unverified(self):
        self.t.allowlist([{"plan": "plan-x", "item": "I1", "acceptance_sha256": self.h}])
        self.assertEqual(self.check(self.a), [])
        self.assertEqual(self.t.mod.UNBACKED_OWNER_ACCEPTANCES, ["plan-x:I1"])
        d = self.t.mod.project(self.t.root / ".agents/plans/plan-x")
        it = d["items"][0]
        self.assertEqual((it["status"], it["acceptance_assurance"], it["status_label"]),
                         ("SHIPPED", "unverified", "SHIPPED (unverified)"))
        self.assertEqual(d["rollup_pct"], 100)   # label only, no score cut
        self.assertEqual((d["shipped_unverified"], d["shipped_recorded"], d["unbacked_owner_acceptances"],
                          d["owner_verified_signed"]), (1, 0, 1, 0))

    def test_allowlist_hash_binding_edited_note_date_by_or_moved_block(self):
        self.t.allowlist([{"plan": "plan-x", "item": "I1", "acceptance_sha256": self.h}])
        for edit in ({"note": "changed"}, {"date": "2026-11-01"}, {"by": "hyperd (owner directive 2026-09-26)"}):
            self.assertTrue(self.check({**self.a, **edit}), edit)
        pd = self.t.plan("plan-x", {"I2": self.a})   # same block moved to another item
        self.assertTrue(self.t.errors(pd))

    def test_valid_ref_is_recorded(self):
        ref = self.t.record("r1", "plan-x", "I1", self.h)
        a = self.with_ref(ref)
        self.assertEqual(self.check(a), [])
        d = self.t.mod.project(self.t.root / ".agents/plans/plan-x")
        it = d["items"][0]
        self.assertEqual((it["acceptance_assurance"], it["status_label"]), ("recorded", "SHIPPED (recorded)"))
        self.assertEqual((d["shipped_unverified"], d["shipped_recorded"], d["owner_verified_signed"]), (0, 1, 0))
        # approval_ref never changes the binding hash
        self.assertEqual(self.t.mod.acceptance_sha256("plan-x", "I1", a), self.h)

    def test_malformed_record_items_fail_validation_and_project_unverified(self):
        for malformed_items in (1, {"id": "I1"}, "I1", None):
            with self.subTest(items=malformed_items):
                ref = self.t.record("bad-items", "plan-x", "I1", self.h, items=malformed_items)
                a = self.with_ref(ref)
                errors = self.check(a)
                self.assertEqual(len(errors), 1)
                self.assertIn("items must be a list", errors[0])
                pd = self.t.plan("plan-x", {"I1": a})
                projected = self.t.mod.project(pd)["items"][0]
                self.assertEqual(
                    (projected["status"], projected["acceptance_assurance"], projected["status_label"]),
                    ("SHIPPED", "unverified", "SHIPPED (unverified)"),
                )

    def test_tamper_matrix_each_is_an_error(self):
        good = self.t.record("good", "plan-x", "I1", self.h)
        cases = {
            "wrong record sha": {**good, "sha256": "0" * 64},
            "uppercase sha": {**good, "sha256": good["sha256"].upper()},
            "short sha": {**good, "sha256": "ab"},
            "record lists other item": self.t.record("o1", "plan-x", "I9", self.h),
            "record lists other hash": self.t.record("o2", "plan-x", "I1", "1" * 64),
            "record other plan": self.t.record("o3", "plan-y", "I1", self.h),
            "decision rejected": self.t.record("o4", "plan-x", "I1", self.h, decision="rejected"),
            "schema 2": self.t.record("o5", "plan-x", "I1", self.h, schema=2),
            "wrong kind": self.t.record("o6", "plan-x", "I1", self.h, kind="other"),
            "path dotdot": {"record": ".agent/approvals/acceptance/../x.json", "sha256": good["sha256"]},
            "path absolute": {"record": str(self.t.root / good["record"]), "sha256": good["sha256"]},
            "path outside dir": {"record": "README.md", "sha256": good["sha256"]},
            "path nested": {"record": ".agent/approvals/acceptance/sub/r.json", "sha256": good["sha256"]},
            "log file as record": {"record": ".agent/approvals/acceptance/LOG.jsonl", "sha256": good["sha256"]},
            "record missing": {"record": ".agent/approvals/acceptance/nope.json", "sha256": good["sha256"]},
        }
        self.assertEqual(self.check(self.with_ref(good)), [])
        for name, ref in cases.items():
            errs = self.check(self.with_ref(ref))
            self.assertTrue(errs and "approval_ref invalid" in errs[0], f"{name}: {errs}")
        # edited acceptance fields invalidate an otherwise good ref
        for edit in ({"note": "x"}, {"date": "2026-11-02"}, {"by": "hyperd (owner directive 2026-09-26)"}):
            errs = self.check({**self.with_ref(good), **edit})
            self.assertTrue(errs, edit)

    def test_ref_shapes(self):
        good = self.t.record("g", "plan-x", "I1", self.h)
        signed = {"envelope_seq": 3, "envelope_sha256": "a" * 64}
        for name, ref in {
            "both shapes": {**good, **signed},
            "unknown key": {**good, "extra": 1},
            "record only": {"record": good["record"]},
            "empty": {},
            "string": "x",
            "list": [],
            "null": None,
            "signed bool seq": {"envelope_seq": True, "envelope_sha256": "a" * 64},
            "signed negative seq": {"envelope_seq": -1, "envelope_sha256": "a" * 64},
            "signed bad hash": {"envelope_seq": 1, "envelope_sha256": "zz"},
            "signed extra": {**signed, "record": "x"},
            "well-formed signed (verifier is slice 3)": signed,
        }.items():
            errs = self.check(self.with_ref(ref))
            self.assertTrue(errs and "approval_ref invalid" in errs[0], f"{name}: {errs}")
        # a signed-shaped ref is never satisfied by a recorded record and never projects recorded/signed
        a = self.with_ref(signed)
        self.assertEqual(self.t.mod.acceptance_assurance({"id": "I1", "acceptance": a}, "plan-x"), "unverified")

    def test_record_modified_or_deleted_after_the_fact(self):
        ref = self.t.record("g", "plan-x", "I1", self.h)
        a = self.with_ref(ref)
        self.assertEqual(self.check(a), [])
        p = self.t.root / ref["record"]
        p.write_bytes(p.read_bytes() + b" ")
        self.assertIn("modified", self.check(a)[0])
        p.unlink()
        self.assertIn("missing", self.check(a)[0])

    def test_decision_log_replay(self):
        ref = self.t.record("g", "plan-x", "I1", self.h)
        a = self.with_ref(ref)

        def log(*lines):
            self.t.write(".agent/approvals/acceptance/LOG.jsonl",
                         "".join(json.dumps(x) + "\n" for x in lines))

        def ln(n, decision, h=None):
            return {"dseq": n, "plan": "plan-x", "item": "I1", "acceptance_sha256": h or self.h,
                    "decision": decision, "wave_digest": "0" * 64, "record": ref["record"]}
        log(ln(1, "approved"))
        self.assertEqual(self.check(a), [])
        log(ln(1, "approved"), ln(2, "rejected"))          # approve -> reject -> restore old block and old ref
        self.assertIn("superseded", self.check(a)[0])
        log(ln(1, "approved"), ln(2, "rejected"), ln(3, "approved", "2" * 64))   # later approve of a different hash
        self.assertIn("superseded", self.check(a)[0])
        log(ln(1, "approved"), ln(3, "approved"))          # gap
        self.assertIn("decision log invalid", self.check(a)[0])
        log(ln(1, "approved"), ln(1, "approved"))          # duplicate
        self.assertIn("decision log invalid", self.check(a)[0])

    def test_non_owner_acceptors_unchanged(self):
        pd = self.t.plan("plan-x", {"I1": {"status": "accepted", "by": "codex", "date": "2026-10-31"}})
        errs = self.t.errors(pd)
        self.assertTrue(errs and "not an owner" in errs[0])    # still needs a receipt; owner rules not applied

    def test_non_accepted_owner_block_ignored(self):
        pd = self.t.plan("plan-x", {"I1": {"status": "pending", "by": "hyperd", "date": "2026-10-31"}})
        self.assertEqual(self.t.errors(pd), [])


class Labels(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.t = Tree(self._td.name)
        self.addCleanup(self._td.cleanup)

    def test_activated_keeps_status_and_has_no_marker_but_emits_flag(self):
        m = self.t.mod
        a = acc("act")
        pd = self.t.plan("plan-z", {"A1": a, "S1": acc("ship"), "N1": None})
        self.t.allowlist([entry(m, "plan-z", "A1", a), entry(m, "plan-z", "S1", acc("ship"))])
        orig = m._item_activation
        m._item_activation = lambda item, plan, ctx: (item.get("id") == "A1", "")
        try:
            d = m.project(pd)
        finally:
            m._item_activation = orig
        by_id = {i["id"]: i for i in d["items"]}
        self.assertEqual(by_id["A1"]["status"], "ACTIVATED")
        self.assertEqual(by_id["A1"]["status_label"], "ACTIVATED")
        self.assertEqual(by_id["A1"]["acceptance_assurance"], "unverified")
        self.assertEqual(by_id["S1"]["status_label"], "SHIPPED (unverified)")
        self.assertIsNone(by_id["N1"]["acceptance_assurance"])
        self.assertEqual(by_id["N1"]["status_label"], by_id["N1"]["status"])
        self.assertEqual(d["shipped_unverified"], 1)        # ACTIVATED excluded
        self.assertEqual(d["unbacked_owner_acceptances"], 2)
        self.assertEqual(d["shipped"], 2)                    # existing semantics unchanged

    def test_provenance_hold_keeps_unverified_status_and_reports_flag(self):
        m = self.t.mod
        a = acc("held")
        pd = self.t.plan("plan-h", {"H1": a})
        orig = m._untrusted_hold
        m._untrusted_hold = lambda *x, **k: {"degraded": False, "lane": "l", "since": "s", "prs": [1], "reason": "r"}
        try:
            d = m.project(pd)
        finally:
            m._untrusted_hold = orig
        it = d["items"][0]
        self.assertEqual((it["status"], it["status_label"], it["acceptance_assurance"]), ("UNVERIFIED", "UNVERIFIED", "unverified"))
        self.assertEqual((d["held"], d["shipped_unverified"], d["unbacked_owner_acceptances"]), (1, 0, 1))

    def test_aggregate_totals_and_api_passthrough(self):
        m = self.t.mod
        a1, a2 = acc("1"), acc("2")
        self.t.plan("plan-1", {"A": a1})
        self.t.plan("plan-2", {"B": a2, "C": None})
        agg = m.project_all()
        self.assertEqual((agg["shipped_unverified"], agg["shipped_recorded"], agg["unbacked_owner_acceptances"],
                          agg["owner_verified_signed"]), (2, 0, 2, 0))
        for p in agg["plans"]:
            for k in ("shipped_unverified", "shipped_recorded", "unbacked_owner_acceptances", "owner_verified_signed"):
                self.assertIn(k, p)
            for i in p["items"]:
                self.assertIn("acceptance_assurance", i)
                self.assertIn("status_label", i)
        pm = _load_pm_route()
        payload = json.dumps(agg).encode()
        data = _run_route(pm, payload)
        self.assertEqual(data["shipped_unverified"], 2)
        self.assertEqual(data["owner_verified_signed"], 0)
        labels = {i["id"]: i["status_label"] for p in data["plans"] for i in p["items"]}
        self.assertEqual(labels, {"A": "SHIPPED (unverified)", "B": "SHIPPED (unverified)", "C": "DESIGNED"})

    def test_human_output_uses_labels_and_counts(self):
        a = acc("h")
        pd = self.t.plan("plan-p", {"I": a})
        r = subprocess.run([sys.executable, str(TRACKER), str(pd)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[SHIPPED (unverified)]", r.stdout)
        self.assertIn("1 SHIPPED (unverified)", r.stdout)
        live = subprocess.run([sys.executable, str(TRACKER), "--all"], capture_output=True, text=True, timeout=180, cwd=REAL)
        agg = json.loads(subprocess.run([sys.executable, str(TRACKER), "--all-json"], capture_output=True,
                                        text=True, timeout=180, cwd=REAL).stdout)
        if agg["shipped_unverified"]:
            self.assertIn("SHIPPED (unverified)]", live.stdout)
            self.assertIn("SHIPPED (unverified)", live.stdout.split("\n\n")[1] + live.stdout)

    def test_dashboard_markup(self):
        html = (REAL / "assets" / "aqos-progress-tracker.html").read_text()
        for needle in ("acceptance_assurance", "data-assurance", "assuranceTag", "stat-assurance",
                       "shipped_unverified", "shipped_recorded", "owner_verified_signed", "(${escapeHtml(item.assurance)})"):
            self.assertIn(needle, html)
        # marker is SHIPPED-only: the tag function guards on status
        self.assertIn("item.status === 'SHIPPED' && (item.assurance === 'unverified'", html)


def _load_pm_route():
    try:
        import fastapi  # noqa: F401
    except ImportError:   # bare CI python: stub just enough to import the route module unmodified
        import types
        fa = types.ModuleType("fastapi")

        class _R:
            def __init__(self, **k):
                pass

            def get(self, *a, **k):
                return lambda f: f

        class _E(Exception):
            def __init__(self, status_code=500, detail=""):
                self.status_code, self.detail = status_code, detail
        fa.APIRouter, fa.HTTPException = _R, _E
        sys.modules["fastapi"] = fa
    spec = importlib.util.spec_from_file_location("pm_route_under_test", REAL / "dashboard" / "backend" / "api" / "routes" / "pm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_route(pm, payload: bytes):
    import asyncio

    class Proc:
        returncode = 0

        async def communicate(self):
            return payload, b""

    async def fake_exec(*a, **k):
        return Proc()
    orig = pm.asyncio.create_subprocess_exec
    pm.asyncio.create_subprocess_exec = fake_exec
    try:
        return asyncio.run(pm.get_pm_progress())
    finally:
        pm.asyncio.create_subprocess_exec = orig


class GitHarness(unittest.TestCase):
    """Real git: bare origin + working clone. mod.REPO is the clone; the gate fetches origin/main itself."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        td = Path(self._td.name)
        self.origin, self.work = td / "origin.git", td / "work"
        self.git0("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git0("init", "-q", "-b", "main", str(self.work))
        self.t = Tree(self.work)
        self.mod = self.t.mod
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.git("remote", "add", "origin", str(self.origin))
        self.accs = {"i1": acc("one"), "i2": acc("two"), "i3": acc("three")}

    def git0(self, *a):
        r = subprocess.run(["git", *a], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def git(self, *a):
        return self.git0("-C", str(self.work), *a)

    def commit_push(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        self.git("push", "-q", "origin", "HEAD:main")

    def entries(self, ids=None):
        return [entry(self.mod, "plan-a", i, self.accs[i]) for i in (ids or self.accs)]

    def write_trackers(self):
        self.t.plan("plan-a", {i: a for i, a in self.accs.items()})

    def write_cfgs(self, base_ids=None, allow_ids=None):
        b = cfg_bytes(self.entries(base_ids))
        self.t.write(self.mod.OWNER_BASELINE_REL, b)
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries(allow_ids)))
        return sha(b)

    def seed_main(self, with_cfg=True):
        """origin/main = trackers (+ cfgs). Returns the baseline sha (pin)."""
        self.write_trackers()
        pin = self.write_cfgs() if with_cfg else None
        self.commit_push("seed")
        return pin

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)

    def gate(self, pin, mod=None):
        mod = mod or self.mod
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.check_owner_acceptance(pinned=pin)
        return rc, buf.getvalue()

    def assertFail(self, pin, code, mod=None):
        rc, out = self.gate(pin, mod)
        self.assertEqual(rc, 1, out)
        self.assertIn(code, out)
        return out


class GateBootstrapAndSteadyState(GitHarness):
    def test_bootstrap_passes(self):
        self.seed_main(with_cfg=False)
        self.branch("feat")
        pin = self.write_cfgs()
        rc, out = self.gate(pin)
        self.assertEqual(rc, 0, out)
        self.assertIn("bootstrap", out)

    def test_bootstrap_wrong_digest_or_unequal_sets_fail(self):
        self.seed_main(with_cfg=False)
        self.branch("feat")
        pin = self.write_cfgs()
        self.assertFail("f" * 64, "(b)")
        self.write_cfgs(allow_ids=["i1", "i2"])    # unequal sets; i3 left unbacked
        self.assertFail(pin, "FAIL")

    def test_bootstrap_with_extra_tuple_fails(self):
        self.seed_main(with_cfg=False)
        self.branch("feat")
        self.accs["i4"] = acc("four")
        self.t.plan("plan-a", self.accs)
        pin = self.write_cfgs(base_ids=["i1", "i2", "i3"], allow_ids=["i1", "i2", "i3", "i4"])
        self.assertFail(pin, "(d)")

    def test_unchanged_full_allowlist_after_bootstrap_passes(self):
        pin = self.seed_main()
        self.branch("feat")
        rc, out = self.gate(pin)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("bootstrap", out)

    def test_files_untouched_with_unrelated_change_passes(self):
        pin = self.seed_main()
        self.branch("feat")
        self.t.write("docs/x.md", "x")
        self.assertEqual(self.gate(pin)[0], 0)

    def test_a_file_missing_in_candidate(self):
        pin = self.seed_main()
        self.branch("feat")
        (self.work / self.mod.OWNER_ALLOWLIST_REL).unlink()
        self.assertFail(pin, "(a)")
        self.git("checkout", "-q", "--", ".")
        (self.work / self.mod.OWNER_BASELINE_REL).unlink()
        self.assertFail(pin, "(a)")

    def test_b_baseline_edited_differs_from_pin(self):
        pin = self.seed_main()
        self.branch("feat")
        p = self.work / self.mod.OWNER_BASELINE_REL
        p.write_bytes(p.read_bytes().replace(b"x", b"y", 1))
        self.assertFail(pin, "(b)")

    def test_c_inconsistent_presence(self):
        self.seed_main(with_cfg=False)
        self.t.write(self.mod.OWNER_BASELINE_REL, cfg_bytes(self.entries()))
        self.commit_push("only baseline")
        self.branch("feat")
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries()))
        pin = sha((self.work / self.mod.OWNER_BASELINE_REL).read_bytes())
        self.assertFail(pin, "(c)")

    def test_c_branch_cut_before_bootstrap_landed_on_main(self):
        self.seed_main(with_cfg=False)
        self.git("branch", "old")
        pin = self.write_cfgs()
        self.commit_push("bootstrap on main")
        self.git("checkout", "-q", "old")
        pin = self.write_cfgs()
        self.assertFail(pin, "(c)")

    def test_d_added_replaced_duplicate_tuple(self):
        pin = self.seed_main()
        self.branch("feat")
        # added: a new unbacked acceptance + allowlist entry, baseline untouched
        self.accs["i4"] = acc("four")
        self.t.plan("plan-a", self.accs)
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries()))
        self.assertFail(pin, "(d)")
        # replaced: i1 note edited, allowlist hash replaced
        self.git("checkout", "-q", "--", ".")
        self.git("clean", "-fdq")
        self.accs.pop("i4", None)
        self.accs["i1"] = acc("one edited")
        self.t.plan("plan-a", self.accs)
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries()))
        out = self.assertFail(pin, "(d)")
        self.assertIn("not in the frozen baseline", out)
        # duplicate tuple
        self.git("checkout", "-q", "--", ".")
        self.accs["i1"] = acc("one")
        e = self.entries()
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(e + [e[0]]))
        self.assertFail(pin, "duplicate")

    def test_edited_note_without_allowlist_change_fails_on_state(self):
        pin = self.seed_main()
        self.branch("feat")
        self.accs["i2"] = acc("two edited")
        self.t.plan("plan-a", self.accs)
        self.assertFail(pin, "state:")


class GateStaleBranchAndRemovals(GitHarness):
    def remove_i1_on_main(self):
        self.git("checkout", "-q", "main")
        accs = {k: v for k, v in self.accs.items()}
        accs["i1"] = None
        self.t.plan("plan-a", accs)
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries(["i2", "i3"])))
        self.commit_push("remove i1 acceptance")

    def test_removal_with_block_removed_passes_on_main(self):
        pin = self.seed_main()
        self.remove_i1_on_main()
        rc, out = self.gate(pin)
        self.assertEqual(rc, 0, out)

    def test_stale_branch_cannot_restore_removed_tuple(self):
        pin = self.seed_main()
        self.git("branch", "stale")
        self.remove_i1_on_main()
        self.git("checkout", "-q", "stale")      # still carries i1 tuple + acceptance block
        os.environ["AQ_PM_BASE"] = "HEAD"        # no env var may select the base
        try:
            out = self.assertFail(pin, "(d)")
        finally:
            del os.environ["AQ_PM_BASE"]
        self.assertIn("i1", out)

    def test_rebased_branch_reintroducing_removed_tuple_fails(self):
        pin = self.seed_main()
        self.remove_i1_on_main()
        self.branch("feat")
        self.t.plan("plan-a", self.accs)         # acceptance block restored
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries()))
        self.assertFail(pin, "(d)")

    def test_check_function_takes_no_base_parameter(self):
        self.assertEqual(list(inspect.signature(self.mod.check_owner_acceptance).parameters), ["git", "pinned"])

    def test_e_removal_without_tracker_change_fails_and_with_change_passes(self):
        pin = self.seed_main()
        self.branch("feat")
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, cfg_bytes(self.entries(["i1", "i3"])))
        self.assertFail(pin, "(e)")
        # same removal with the acceptance block removed
        accs = dict(self.accs)
        accs["i2"] = None
        self.t.plan("plan-a", accs)
        self.assertEqual(self.gate(pin)[0], 0)
        # same removal with a valid approval_ref added instead
        a2 = self.accs["i2"]
        ref = self.t.record("r2", "plan-a", "i2", self.mod.acceptance_sha256("plan-a", "i2", a2))
        accs["i2"] = {**a2, "approval_ref": ref}
        self.t.plan("plan-a", accs)
        rc, out = self.gate(pin)
        self.assertEqual(rc, 0, out)
        # an approval_ref that does not validate does not justify the removal
        accs["i2"] = {**a2, "approval_ref": {**ref, "sha256": "0" * 64}}
        self.t.plan("plan-a", accs)
        self.assertFail(pin, "(e)")


class GateFailClosed(GitHarness):
    def test_fetch_failure(self):
        pin = self.seed_main()
        self.branch("feat")
        self.git("remote", "set-url", "origin", str(self.origin) + "-missing")
        out = self.assertFail(pin, "cannot fetch origin/main")
        self.assertIn("prereq", out)

    def test_unresolvable_origin_main_and_git_errors(self):
        pin = self.seed_main()
        base = self.mod._git_run

        def fake(fail_cmd):
            def git(*a):
                if a[0] == fail_cmd:
                    return subprocess.CompletedProcess(a, 128, "", "boom")
                return base(*a)
            return git
        for cmd in ("fetch", "rev-parse", "merge-base", "ls-tree", "show"):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = self.mod.check_owner_acceptance(git=fake(cmd), pinned=pin)
            self.assertEqual(rc, 1, f"{cmd}: {buf.getvalue()}")

    def test_missing_or_malformed_pin_fails(self):
        self.seed_main()
        for pin in (None, "", "zz", "A" * 64):
            self.assertEqual(self.gate(pin)[0], 1)

    def test_unparsable_candidate_or_historical_config_fails(self):
        pin = self.seed_main()
        self.branch("feat")
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, "not json")
        self.assertFail(pin, "prereq")
        self.git("checkout", "-q", "--", ".")
        self.git("checkout", "-q", "main")
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, "not json")
        self.commit_push("corrupt main")
        self.branch("feat2")
        self.git("checkout", "-q", "HEAD~1", "--", self.mod.OWNER_ALLOWLIST_REL)
        self.assertFail(pin, "prereq")


class GateAppendOnly(GitHarness):
    def setUp(self):
        super().setUp()
        self.accs = {"i1": acc("one"), "i2": acc("two")}
        a2 = self.accs["i2"]
        self.h2 = self.mod.acceptance_sha256("plan-a", "i2", a2)

    def seed_with_record(self, with_log=True):
        ref = self.t.record("r2", "plan-a", "i2", self.h2)
        self.accs["i2"] = {**self.accs["i2"], "approval_ref": ref}
        self.write_trackers()
        a1 = self.entries(["i1"])
        pin_bytes = cfg_bytes(a1)
        self.t.write(self.mod.OWNER_BASELINE_REL, pin_bytes)
        self.t.write(self.mod.OWNER_ALLOWLIST_REL, pin_bytes)
        if with_log:
            self.t.write(self.mod.APPROVAL_LOG_REL, json.dumps(
                {"dseq": 1, "plan": "plan-a", "item": "i2", "acceptance_sha256": self.h2, "decision": "approved",
                 "wave_digest": "0" * 64, "record": ref["record"]}) + "\n")
        self.commit_push("seed with record")
        return sha(pin_bytes), ref

    def test_unchanged_records_and_appended_log_pass(self):
        pin, ref = self.seed_with_record()
        self.branch("feat")
        self.assertEqual(self.gate(pin)[0], 0)
        p = self.work / self.mod.APPROVAL_LOG_REL
        p.write_text(p.read_text() + json.dumps({"dseq": 2, "plan": "plan-a", "item": "i1", "acceptance_sha256": "3" * 64,
                                                 "decision": "rejected", "wave_digest": "0" * 64, "record": "x"}) + "\n")
        rc, out = self.gate(pin)
        self.assertEqual(rc, 0, out)

    def test_record_modified_or_deleted_fails(self):
        pin, ref = self.seed_with_record()
        self.branch("feat")
        p = self.work / ref["record"]
        p.write_bytes(p.read_bytes() + b" ")
        self.assertFail(pin, "append-only: " + ref["record"] + " modified")
        p.unlink()
        self.assertFail(pin, "deleted")

    def test_log_line_edited_or_removed_fails(self):
        pin, ref = self.seed_with_record()
        self.branch("feat")
        p = self.work / self.mod.APPROVAL_LOG_REL
        p.write_text(p.read_text().replace("approved", "rejected"))
        self.assertFail(pin, "append-only")
        p.unlink()
        self.assertFail(pin, "deleted")


class GateWiring(unittest.TestCase):
    def test_gate_invocation_is_unconditional_and_pinned(self):
        text = (REAL / "scripts" / "governance" / "tier0.d" / "check-pm-tracker.sh").read_text()
        self.assertIn('--check-owner-acceptance --baseline-sha256 "${BASELINE_SHA256}"', text)
        self.assertNotIn("SKIP:", text)
        lines = text.splitlines()
        idx = next(i for i, l in enumerate(lines) if "--check-owner-acceptance" in l)
        pre = "\n".join(lines[:idx])
        # reached before any early exit 0, and not under a conditional that could skip it
        self.assertNotIn("exit 0", pre)
        self.assertTrue(lines[idx].lstrip().startswith("if ! owner_out="), lines[idx])
        self.assertIn("exit 1", pre)    # missing projector/python fails, never passes
        literal = [l for l in lines if l.startswith("BASELINE_SHA256=")]
        self.assertEqual(len(literal), 1)
        pinned = literal[0].split('"')[1]
        base = (REAL / "config" / "pm-tracker-unbacked-owner-acceptances.baseline.json").read_bytes()
        self.assertEqual(pinned, sha(base))
        gate = (REAL / "scripts" / "governance" / "tier0-validation-gate.sh").read_text()
        self.assertIn('"${TIER0D}"/*.sh', gate)     # every tier0.d check runs under --pre-commit

    def test_cli_requires_pin_and_real_repo_state_is_consistent(self):
        r = subprocess.run([sys.executable, str(TRACKER), "--check-owner-acceptance"], capture_output=True,
                           text=True, cwd=REAL, timeout=120)
        self.assertEqual(r.returncode, 1)
        self.assertIn("pinned baseline sha256", r.stdout)
        m = load_tracker()
        base = set(m._owner_entries_list((REAL / m.OWNER_BASELINE_REL).read_text()))
        allow = m._owner_entries_list((REAL / m.OWNER_ALLOWLIST_REL).read_text())
        self.assertEqual(len(allow), len(set(allow)))
        self.assertTrue(set(allow) <= base)
        for pd in m.discover_tracked_plans():
            owner_errs = [e for e in m.validate_manifest(pd) if "owner acceptance" in e]
            self.assertEqual(owner_errs, [], pd.name)


class HealthSpiderProbe(unittest.TestCase):
    def setUp(self):
        self.hs = importlib.machinery.SourceFileLoader("aq_health_spider_oa", str(REAL / "scripts" / "ai" / "aq-health-spider")).load_module()
        self.events = []
        self.hs._emit_event = lambda t, p: self.events.append((t, p))
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.state = Path(self._td.name) / "state.json"

    def key(self, n):
        return ["plan-x", f"I{n}", f"{n:064x}"]

    def runner(self, live, count=None, rc=0):
        """live: list of item numbers whose unbacked key is projected."""
        n = len(live) if count is None else count
        body = {"shipped_unverified": n, "shipped_recorded": 0, "unbacked_owner_acceptances": n, "owner_verified_signed": 0,
                "plans": [{"items": [{"id": f"I{i}", "unbacked_key": self.key(i)} for i in live] + [{"id": "ok"}]}]}
        return lambda: (rc, json.dumps(body))

    def _entries(self, listed):
        return json.dumps({"entries": [dict(zip(("plan", "item", "acceptance_sha256"), self.key(i))) for i in listed]})

    def allow(self, listed, working=None):
        """Trusted blob = origin/main in a temp repo; working-tree file defaults to the same entries."""
        repo = Path(self._td.name) / "repo"
        if not repo.exists():
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
        g = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)
        f = repo / "config" / "pm-tracker-unbacked-owner-acceptances.json"
        f.parent.mkdir(exist_ok=True)
        f.write_text(self._entries(listed))
        g("add", "-A"); g("commit", "-q", "-m", "allow")
        g("update-ref", "refs/remotes/origin/main", "HEAD")
        f.write_text(self._entries(listed if working is None else working))
        self.repo = repo

    def types(self, runner):
        return sorted(x["type"] for x in self.hs._owner_acceptance_check(runner, self.state, getattr(self, "repo", Path(self._td.name) / "norepo")))

    def test_counters_published_and_listed_is_quiet(self):
        self.allow([1, 2, 3])
        self.assertEqual(self.types(self.runner([1, 2, 3])), [])
        t, payload = self.events[-1]
        self.assertEqual(t, "owner_acceptance_assurance")
        self.assertEqual((payload["shipped_unverified"], payload["owner_verified_signed"]), (3, 0))

    def test_new_unlisted_acceptance_alerts_even_when_count_falls(self):
        self.allow([1, 2, 3])
        self.assertEqual(self.types(self.runner([1, 2, 4])), ["owner_acceptance_unbacked_rising"])   # swap: same count

    def test_removing_entry_from_allowlist_and_reality_is_quiet(self):
        self.allow([1, 2])
        self.assertEqual(self.types(self.runner([1, 2])), [])
        self.allow([1])
        self.assertEqual(self.types(self.runner([1])), [])
        self.assertEqual(self.types(self.runner([1, 2])), ["owner_acceptance_unbacked_rising"])   # not re-addable

    def test_state_file_content_never_changes_the_decision(self):
        self.allow([1, 2])
        for content in (None, "not json", "{}", '{"unbacked": 0}', '{"unbacked": 131}', '{"unbacked": 99999}', '{"unbacked": -1}'):
            for live, want in (([1, 2], []), ([1, 2, 9], ["owner_acceptance_unbacked_rising"])):
                if content is None:
                    self.state.unlink(missing_ok=True)
                else:
                    self.state.write_text(content)
                self.assertEqual(self.types(self.runner(live)), want, (content, live))

    def test_upward_overwrite_within_range_cannot_suppress(self):
        self.allow(range(1, 132))
        self.state.write_text(json.dumps({"unbacked": 131}))
        self.assertEqual(self.types(self.runner(list(range(1, 121)) + [500])), ["owner_acceptance_unbacked_rising"])

    def test_count_key_mismatch_alerts(self):
        self.allow([1])
        self.assertEqual(self.types(self.runner([1], count=2)), ["owner_acceptance_unbacked_rising"])

    def test_unreadable_projection_is_an_anomaly_not_green(self):
        self.allow([1])
        for runner in (lambda: (1, ""), lambda: (0, "not json"), lambda: (0, json.dumps({"shipped_unverified": 1})),
                       lambda: (0, json.dumps({k: "x" for k in ("shipped_unverified", "shipped_recorded", "unbacked_owner_acceptances", "owner_verified_signed")}))):
            self.assertEqual(self.types(runner), ["owner_acceptance_probe_failed"])
        self.assertEqual(self.events, [])    # nothing measured, nothing published as a count

    def test_unreadable_allowlist_is_probe_failed(self):
        self.assertEqual(self.types(self.runner([1])), ["owner_acceptance_probe_failed"])     # no repo at all
        self.allow([1])
        subprocess.run(["git", "-C", str(self.repo), "update-ref", "-d", "refs/remotes/origin/main"], check=True)
        self.assertEqual(self.types(self.runner([1])), ["owner_acceptance_probe_failed"])     # no origin/main

    def test_codex_repro_working_tree_addition_cannot_silence(self):
        self.allow([1, 2], working=[1, 2, 9])
        self.assertEqual(self.types(self.runner([1, 2, 9])),
                         ["owner_acceptance_allowlist_unauthorized", "owner_acceptance_unbacked_rising"])
        self.assertEqual(self.types(self.runner([1, 2])), ["owner_acceptance_allowlist_unauthorized"])

    def test_working_tree_removal_is_quiet(self):
        self.allow([1, 2, 3], working=[1])
        self.assertEqual(self.types(self.runner([1])), [])

    def test_state_write_failure_is_reported(self):
        self.allow([1])
        ro = Path(self._td.name) / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        self.addCleanup(ro.chmod, 0o700)
        if os.access(ro, os.W_OK):
            self.skipTest("cannot make a directory unwritable (running as root)")
        a = sorted(x["type"] for x in self.hs._owner_acceptance_check(self.runner([1]), ro / "state.json", self.repo))
        self.assertEqual(a, ["owner_acceptance_state_unwritable"])

    def test_real_projection_keys_are_all_in_real_allowlist(self):
        real = json.loads((REAL / "config" / "pm-tracker-unbacked-owner-acceptances.json").read_text())["entries"]
        self.allow([])
        repo = self.repo
        f = repo / "config" / "pm-tracker-unbacked-owner-acceptances.json"
        f.write_text(json.dumps({"entries": real}))
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "real"], check=True)
        subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        r = subprocess.run([sys.executable, str(TRACKER), "--all-json"], capture_output=True, text=True, cwd=str(REAL))
        self.assertEqual(self.types(lambda: (r.returncode, r.stdout)), [])


if __name__ == "__main__":
    unittest.main()
