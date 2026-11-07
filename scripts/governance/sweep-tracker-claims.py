#!/usr/bin/env python3
"""sweep-tracker-claims: check every .agents/plans/*/tracker.json item against ground truth.

Recovery sweep P2.5 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Offline and read-only:
only local git/file reads, no network, no tracker/status/backlog edits. A dimension that cannot be
determined is reported "unknown" and is never counted as a pass.

Per item: code_on_main, wired, enabled, observable, tested. Finding classes:
  CLAIM_NO_CODE       text or typed status says shipped, but no commit_match hit on the ref
  SHIPPED_NOT_ACTIVE  typed SHIPPED/ACTIVATED while the projector disagrees or the runtime is forced off
  HAND_TYPED_STATUS   tracker item carries a typed status field (Rule 20: status is projected)
  DORMANT             code on main but nothing live calls it (Rule 23)
  STALE_RECORD        an intake/deferral record contradicts what the plan or repo now says

Usage: sweep-tracker-claims.py [--json] [--report PATH] [--fail-on CLASS,...] [--ref REF] [--repo DIR]
"""
from __future__ import annotations

import argparse
import glob
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[2]
CLASSES = ("CLAIM_NO_CODE", "SHIPPED_NOT_ACTIVE", "DORMANT", "STALE_RECORD", "HAND_TYPED_STATUS")
SHIPPED_WORDS = {"SHIPPED", "ACTIVATED", "DONE", "COMPLETE", "COMPLETED", "MERGED", "LANDED"}
PROJ_ACTIVE = {"SHIPPED", "ACTIVATED"}
PAST_INTAKE = {"BUILT", "SHIPPED", "ACTIVATED"}
CLAIM_RE = re.compile(r"\b(shipped|merged|landed|activated)\b", re.I)
NEGATION_RE = re.compile(r"\b(not|never|no|un|awaits?|awaiting|before|until|pending|unless|once|when|if|"
                         r"requires?|needs?|reset|was|dormant|inert)\b[^.;]{0,40}$", re.I)
NIX_VAL = r"(?:lib\.)?(?:mkDefault\s+|mkForce\s+)?"


def git(repo, *args):
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    return r.returncode, r.stdout


def read(repo, rel):
    try:
        return (Path(repo) / rel).read_text(errors="replace")
    except OSError:
        return None


def load_gitlog(repo, ref):
    rc, out = git(repo, "log", ref, "--format=%h %s")
    if rc != 0:
        return None, "unavailable"
    rc, sh = git(repo, "rev-parse", "--is-shallow-repository")
    return out, "shallow_incomplete" if sh.strip() == "true" else "complete"


def hit(pattern, text):
    try:
        if re.search(pattern, text, re.I | re.M):
            return True
    except re.error:
        pass
    return pattern in text


def nix_texts(repo, cache):
    if "nix" not in cache:
        files = sorted(glob.glob(str(Path(repo) / "nix" / "**" / "*.nix"), recursive=True))
        cache["nix"] = {p: Path(p).read_text(errors="replace") for p in files}
    return cache["nix"]


def enable_state(repo, option, cache):
    """yes/no/unknown for a NixOS enable option, from nix/ only. Returns (state, evidence)."""
    texts = nix_texts(repo, cache)
    parts = option.split(".")
    dotted = re.compile(r"\b" + re.escape(option) + r"\s*=\s*" + NIX_VAL + r"(true|false)\b")
    nested = None
    if len(parts) >= 2 and parts[-1] == "enable":
        nested = re.compile(r"\b" + re.escape(parts[-2]) + r"\s*=\s*\{[^{}]*?\benable\s*=\s*" + NIX_VAL + r"(true|false)\b", re.S)
    vals, container_seen, default_true = [], False, False
    for p, t in texts.items():
        rel = os.path.relpath(p, repo)
        for rx in (dotted, nested):
            if rx:
                vals += [(m.group(1), rel) for m in rx.finditer(t)]
        if len(parts) >= 2 and re.search(r"\b" + re.escape(parts[-2]) + r"\b", t):
            container_seen = True
            if re.search(r"\benable\s*=\s*(?:lib\.)?mkOption\s*\{[^{}]*?default\s*=\s*true", t, re.S):
                default_true = True
    if any(v == "true" for v, _ in vals) or default_true:
        return "yes", "set true in " + ", ".join(sorted({f for v, f in vals if v == "true"}) or ["option default"])
    if vals:
        return "no", "only set false in " + ", ".join(sorted({f for _, f in vals}))
    if container_seen:
        return "no", f"{option} is not set true anywhere under nix/"
    return "unknown", f"no nix module mentions {parts[-2] if len(parts) > 1 else option}"


def forced_off_options(repo, cache):
    """Options a nix assertion forces off: assertion = !cfg.X. Returns [(option_path, file)]."""
    out = []
    for p, t in nix_texts(repo, cache).items():
        m = re.search(r"\bcfg\s*=\s*config\.([\w.]+)\s*;", t)
        if not m:
            continue
        for a in re.finditer(r"assertion\s*=\s*!\s*cfg\.(\w+)\s*;", t):
            out.append((f"{m.group(1)}.{a.group(1)}", os.path.relpath(p, repo)))
    return out


def plan_key(plan_id):
    for tok in plan_id.split("-"):
        if len(tok) >= 4 and tok not in ("agent", "agents", "plan", "system"):
            return tok.lower()
    return plan_id.lower()


def ci_registered(repo):
    reg = set()
    try:
        d = json.loads(read(repo, "config/ci-checks.json") or "{}")
    except ValueError:
        return None
    pat = re.compile(r"scripts/testing/[\w./-]+")
    for c in d.get("checks", []):
        reg.update(pat.findall(c.get("cmd", "")))
        reg.update(c.get("tests", []))
    return reg


def load_projector(repo, projector, gitlog, health):
    """Load aq-pm-tracker as a module with git/evidence pinned to the swept repo and ref."""
    spec = importlib.util.spec_from_loader("aq_pm_tracker_sweep",
                                           importlib.machinery.SourceFileLoader("aq_pm_tracker_sweep", str(projector)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO = Path(repo)
    mod._save_git_log_cache = lambda content: None  # read-only: never refresh the shared dashboard cache
    mod._git_log = lambda: (gitlog or "", health)
    return mod


def project_plan(mod, plan_dir):
    try:
        return {i["id"]: i for i in mod.project(Path(plan_dir))["items"]}
    except Exception as e:  # projector failure => unknown, never a guess
        print(f"sweep-tracker-claims: projector failed for {plan_dir}: {e}", file=sys.stderr)
        return None


def manifest_features(repo):
    try:
        return json.loads(read(repo, "config/activation-manifest.json") or "{}").get("features", [])
    except ValueError:
        return []


def manifest_state(repo, f, cache):
    ep, caller = f.get("entrypoint"), f.get("live_caller")
    wired = "unknown"
    if ep and caller:
        t = read(repo, caller)
        wired = "no" if t is None else ("yes" if Path(ep).name in t or Path(ep).stem in t else "no")
    en, en_ev = ("unknown", "no enable option recorded")
    if f.get("enable"):
        en, en_ev = enable_state(repo, f["enable"], cache)
    obs = "unknown"
    hs = f.get("health_signal")
    if hs and ":" in hs:
        hf, sym = hs.split(":", 1)
        t = read(repo, hf)
        obs = "no" if t is None else ("yes" if sym in t else "no")
    return wired, en, en_ev, obs


def sweep(repo, ref="origin/main", projector=None):
    repo = Path(repo)
    projector = Path(projector) if projector else repo / "scripts" / "ai" / "aq-pm-tracker"
    gitlog, health = load_gitlog(repo, ref)
    if gitlog is None and ref == "origin/main":  # CI checkouts may lack the remote-tracking ref
        ref = "HEAD"
        gitlog, health = load_gitlog(repo, ref)
    registered = ci_registered(repo)
    cache = {}
    features = manifest_features(repo)
    forced = forced_off_options(repo, cache)
    mod = load_projector(repo, projector, gitlog, health) if projector.is_file() else None
    cands = []
    try:
        cands = json.loads(read(repo, "config/agent-capability-intake-candidates.json") or "{}").get("candidates", [])
    except ValueError:
        pass
    items, findings = [], []

    def add(cls, plan, item, evidence):
        findings.append({"class": cls, "file": f".agents/plans/{plan}/tracker.json" if plan else "config/activation-manifest.json",
                         "plan": plan, "item": item, "evidence": evidence})

    for tpath in sorted(glob.glob(str(repo / ".agents" / "plans" / "*" / "tracker.json"))):
        plan_dir = Path(tpath).parent
        plan = plan_dir.name
        try:
            manifest = json.loads(Path(tpath).read_text())
        except ValueError as e:
            add("STALE_RECORD", plan, None, f"tracker.json does not parse: {e}")
            continue
        proj = project_plan(mod, plan_dir) if mod else None
        pkey = plan_key(plan)
        plan_forced = [(o, f) for o, f in forced if pkey in o.lower()]
        for it in manifest.get("items", []):
            iid = it.get("id")
            det = it.get("detection") or {}
            blob = json.dumps(it)
            rec = {"plan": plan, "item": iid, "code_on_main": "unknown", "wired": "unknown", "enabled": "unknown",
                   "observable": "unknown", "tested": "unknown", "projected": None, "typed_status": it.get("status"),
                   "evidence": {}}
            pi = (proj or {}).get(iid)
            rec["projected"] = pi["status"] if pi else None
            rec["projected_pct"] = pi.get("pct") if pi else None

            pats = det.get("commit_match") or []
            if pats and gitlog is not None:
                if any(hit(p, gitlog) for p in pats):
                    rec["code_on_main"] = "yes"
                elif health == "complete":
                    rec["code_on_main"] = "no"
                else:
                    rec["evidence"]["code_on_main"] = "no hit but history is shallow"

            wc = det.get("wired_caller")
            covered = [f for f in features if f.get("entrypoint") and Path(f["entrypoint"]).name in blob]
            if isinstance(wc, dict) and wc.get("file"):
                t = read(repo, wc["file"])
                ok = t is not None and hit(wc.get("pattern", ""), t)
                rec["wired"] = "yes" if ok else "no"
                rec["evidence"]["wired"] = f"{wc['file']} {'matches' if ok else 'missing or no match for'} {wc.get('pattern')!r}"
            elif covered:
                w, en, en_ev, obs = manifest_state(repo, covered[0], cache)
                rec["wired"], rec["evidence"]["wired"] = w, f"activation-manifest: {covered[0]['live_caller']}"
                if en != "unknown":
                    rec["enabled"], rec["evidence"]["enabled"] = en, en_ev
                rec["observable"] = obs
            if rec["enabled"] == "unknown" and plan_forced:
                rec["enabled"] = "no"
                rec["evidence"]["enabled"] = "; ".join(f"{f} asserts {o} stays false" for o, f in plan_forced)
            if rec["observable"] == "unknown" and det.get("systemd_unit"):
                rec["evidence"]["observable"] = "systemd_unit declared; live unit state is runtime-only, not checked offline"

            tests = [t for t in (det.get("tests") or []) if isinstance(t, str)]
            if tests and registered is not None:
                missing = [t for t in tests if read(repo, t) is None]
                unreg = [t for t in tests if t not in registered]
                rec["tested"] = "no" if missing or unreg else "yes"
                if missing or unreg:
                    rec["evidence"]["tested"] = (f"missing: {missing} " if missing else "") + (f"not in ci-checks.json: {unreg}" if unreg else "")

            typed = it.get("status")
            typed_u = str(typed).upper() if typed else ""
            texts = " ".join(str(x) for x in (it.get("editorial_note"), it.get("notes"), typed, det.get("notes")) if x)
            claim = typed_u in SHIPPED_WORDS or any(
                not NEGATION_RE.search(texts[max(0, m.start() - 45):m.start()]) for m in CLAIM_RE.finditer(texts))

            if typed:
                add("HAND_TYPED_STATUS", plan, iid, f"item.status={typed!r}; projected={rec['projected']}")
            if det.get("status"):
                add("HAND_TYPED_STATUS", plan, iid, f"detection.status={det['status']!r}")
            if claim and rec["code_on_main"] == "no":
                add("CLAIM_NO_CODE", plan, iid, f"claims shipped ({typed_u or 'text'}); no commit matches {pats} on {ref}")
            if typed_u in PROJ_ACTIVE | {"DONE", "COMPLETE", "COMPLETED"}:
                why = []
                if rec["projected"] and rec["projected"] not in PROJ_ACTIVE:
                    why.append(f"projector says {rec['projected']} ({rec['projected_pct']}%)")
                if rec["enabled"] == "no":
                    why.append(rec["evidence"].get("enabled", "enable option is off"))
                if why:
                    add("SHIPPED_NOT_ACTIVE", plan, iid, f"status {typed}; " + "; ".join(why))
            elif rec["projected"] in PROJ_ACTIVE and rec["enabled"] == "no":
                add("SHIPPED_NOT_ACTIVE", plan, iid, f"projected {rec['projected']}; " + rec["evidence"].get("enabled", ""))
            if rec["code_on_main"] == "yes" and rec["wired"] == "no":
                add("DORMANT", plan, iid, "code on main, " + rec["evidence"].get("wired", "no live caller"))

            for c in cands:
                key = c["id"].split("-")[0].lower()
                stale_state = c.get("state") in ("proposed", "quarantined") or c.get("review_status") == "incomplete"
                if len(key) < 4 or key != pkey or not stale_state:
                    continue
                phase_text = f"{iid} {it.get('name', '')} {it.get('phase', '')}".lower()
                accepted = (it.get("acceptance") or {}).get("status") == "accepted"
                if "intake" in phase_text and (accepted or rec["projected"] in PAST_INTAKE):
                    add("STALE_RECORD", plan, iid, f"plan treats intake as done (accepted={accepted}, projected={rec['projected']}) "
                        f"but config/agent-capability-intake-candidates.json {c['id']} is state={c.get('state')} review_status={c.get('review_status')}")
            items.append(rec)

    for f in features:
        w, en, en_ev, obs = manifest_state(repo, f, cache)
        name = f.get("feature")
        if en == "no" or w == "no":
            add("DORMANT", None, name, f"activation-manifest: wired={w}; enabled={en} ({en_ev})"
                + (f"; deferral {f['deferral'].get('date')}" if f.get("deferral") else ""))
        if f.get("deferral") and en == "yes" and w == "yes":
            add("STALE_RECORD", None, name, f"deferral dated {f['deferral'].get('date')} still recorded but enable is now true and caller wired")

    order = {c: i for i, c in enumerate(CLASSES)}
    findings.sort(key=lambda x: (order[x["class"]], x["plan"] or "", str(x["item"])))
    counts = {c: sum(1 for f in findings if f["class"] == c) for c in CLASSES}
    dims = {}
    for d in ("code_on_main", "wired", "enabled", "observable", "tested"):
        dims[d] = {v: sum(1 for i in items if i[d] == v) for v in ("yes", "no", "unknown")}
    return {"ref": ref, "git_history": health, "plans": len({i["plan"] for i in items}), "items_checked": len(items),
            "counts": counts, "dimensions": dims, "findings": findings, "items": items}


def render_report(res, day, argv):
    c, dims = res["counts"], res["dimensions"]
    L = ["## Objective",
         "Recovery sweep P2.5: check every `.agents/plans/*/tracker.json` item against ground truth (code on main, wired, enabled, "
         "observable, tested) and flag claims the repo does not back. Report-only; findings feed the backlog and P4 and are not fixed here.",
         "", "## Workflow/Session IDs",
         f"Branch feat/sweep-tracker-claims, worktree `.agents/delegation/worktrees/p25-tracker-sweep`. Date {day}.", "",
         "## Delegation Decision",
         "Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17 balanced tier, bounded script + test + registration).", "",
         "## Commands Executed",
         f"- `scripts/governance/sweep-tracker-claims.py {' '.join(argv)}`",
         "- `python3 scripts/testing/test-sweep-tracker-claims.py`", "",
         "## Validation Evidence",
         f"Ref `{res['ref']}`, git history `{res['git_history']}`. {res['plans']} plans, {res['items_checked']} items checked.", "",
         "Counts per class:", "", "| Class | Findings |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in c.items()]
    L += ["", "Dimension results across items (unknown is not a pass):", "", "| Dimension | yes | no | unknown |", "|---|---|---|---|"]
    L += [f"| {d} | {v['yes']} | {v['no']} | {v['unknown']} |" for d, v in dims.items()]
    L += ["", "Full finding list:", "", "| # | Class | Plan | Item | Evidence |", "|---|---|---|---|---|"]
    for n, f in enumerate(res["findings"], 1):
        ev = f["evidence"].replace("|", "\\|").replace("\n", " ")
        L.append(f"| {n} | {f['class']} | {f['plan'] or 'activation-manifest'} | {f['item']} | {ev} |")
    L += ["", "## Rollback Plan", "Delete this report and the sweep script, test and `config/ci-checks.json` entry. No data or config migration.", "",
          "## Residual Risk",
          f"- `observable` is determined only for features in `config/activation-manifest.json`; it is unknown for the other {dims['observable']['unknown']} items.",
          f"- `enabled` is determined only from the activation manifest and nix assertions that force an option off; unknown for {dims['enabled']['unknown']} items.",
          "- Items whose detection is only a `systemd_unit`, `command` or `blocker_note` have no commit evidence, so code_on_main is unknown and CLAIM_NO_CODE cannot fire for them.",
          "- CLAIM_NO_CODE text matching is heuristic (negation window of 45 characters); typed `status` claims are exact.",
          "- STALE_RECORD for intake candidates links candidate to plan by first id token (e.g. herdr); candidates with no matching plan are not checked.",
          "- Runtime state (systemd, `aq-herdr status`) is not probed; the sweep is offline. The herdr runtime finding rests on the nix assertion that forces `runtimeEnable` false.",
          "", "## Hint Feedback", "No hints were consulted."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--report", help="write the dated markdown report to this path")
    ap.add_argument("--fail-on", default="", help="comma list of classes that make the exit status non-zero (default: report only)")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--projector", help="aq-pm-tracker path (default: <repo>/scripts/ai/aq-pm-tracker)")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args(argv)
    fail = [c for c in a.fail_on.split(",") if c]
    bad = [c for c in fail if c not in CLASSES]
    if bad:
        ap.error(f"unknown class {bad}; choose from {CLASSES}")
    res = sweep(a.repo, a.ref, a.projector)
    if a.report:
        Path(a.report).write_text(render_report(res, a.date, sys.argv[1:] if argv is None else argv))
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"sweep-tracker-claims: {res['plans']} plans, {res['items_checked']} items, ref {res['ref']} ({res['git_history']})")
        for k, v in res["counts"].items():
            print(f"  {k:20} {v}")
        for k, v in res["dimensions"].items():
            print(f"  {k:14} yes={v['yes']} no={v['no']} unknown={v['unknown']}")
        for f in res["findings"]:
            if f["class"] != "HAND_TYPED_STATUS":
                print(f"  [{f['class']}] {f['plan'] or 'manifest'}/{f['item']}: {f['evidence']}")
    return 1 if any(res["counts"][c] for c in fail) else 0


if __name__ == "__main__":
    sys.exit(main())
