#!/usr/bin/env python3
"""sweep-gates: find gates that cannot fail, are untested, fail open, are masked, not required, or never run.

Recovery sweep P2.2 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Report only: nothing is
fixed, no gate is edited. Re-runnable; the dated report becomes a standing check (scripts/testing/test-sweep-gates.py).

Gate inventory (nothing about stages is hardcoded; stages are derived from who references a gate):
  tier0.d/*            files in a tier0.d directory next to a tier0-validation-gate.sh
  tier0 gate_*()       shell functions inside tier0-validation-gate.sh
  .githooks/*          every hook except README
  workflow jobs        each job in .github/workflows/*.yml, plus repo scripts its steps run
  ci-checks            every entry of config/ci-checks.json
  orphan check scripts check-/lint-/verify-/validate-* scripts under scripts/ that nothing references
  required checks      branch-protection contexts (only with --github or --required-checks)

Finding classes (each finding says whether the basis is static or exercised):
  CANNOT_FAIL        no reachable non-zero exit (only exit 0, prints, or a masked deciding command)
  NO_BAD_INPUT_TEST  no test names the gate with a failure expectation and it is not in the tier0.d mutation suite
  FAIL_OPEN          missing tool / empty input / swallowed error / absent file is treated as pass
  MASKED_IN_CI       a workflow step hides its result (|| true, continue-on-error, pipe without pipefail)
  NOT_REQUIRED       the CI job runs but is not a required status check (claimed = a report says it gates)
  UNCOVERED          no stage runs the gate
Anything that cannot be determined is reported under `unknown` and is never counted as a pass.

Usage: sweep-gates.py [--json] [--report PATH] [--fail-on CLASS,...] [--repo DIR] [--date YYYY-MM-DD]
                      [--github] [--required-checks A,B] [--exercise]
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[2]
CLASSES = ("CANNOT_FAIL", "NO_BAD_INPUT_TEST", "FAIL_OPEN", "MASKED_IN_CI", "NOT_REQUIRED", "UNCOVERED")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "target", ".venv", "archive", ".understand-anything", "delegation"}
GATE_PREFIX = re.compile(r"^(check|lint|verify|validate)-")
FAIL_WORDS = re.compile(
    r"returncode\s*!=\s*0|\brc\s*!=\s*0|assertNotEqual|assertRaises|pytest\.raises|-ne 0|!= 0|expect[_ -]?fail|"
    r"should fail|must fail|want\W{0,4}fail|nonzero|non-zero|\"fail\"|'fail'|known[- ]bad|\bbad\b|mutat|tamper|reject",
    re.I)
PIPE_LEFT = re.compile(r"(scripts/|\./|\bpython3?\b|\bpytest\b|\bbash\b|\bnix\b|\bcargo\b|\bnpm\b|\bshellcheck\b)")
PIPE_RIGHT = re.compile(r"^\s*(tee|head|tail|cat|sed|awk|cut|sort|uniq)\b")
CLAIM = re.compile(r"\b(required|blocking|merge[- ]gate|hard gate|CI-hard|must pass)\b", re.I)
TOOL_PROBE = re.compile(r"command -v|\bwhich\s+[\w./-]+\s*(?:>|&>|2>|\)|\|\||&&|;|$)|type -P|shutil\.which|hash \S+ 2>")
TOOL_SKIP = re.compile(r"return 0|exit 0|\bskip|\bSKIP|\bWARN|\bwarn|not (?:found|installed|available)|continue\b|return True")
HARD_FAIL = re.compile(r"\bexit\s+[1-9]|\bexit\s+\$|return 1\b|\bfail\b|sys\.exit\((?!0\))|raise\b|die\b")


def rd(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(repo: Path, p: Path) -> str:
    return str(p.relative_to(repo))


def walk(repo: Path, sub: str, pred=lambda n: True):
    base = repo / sub
    if base.is_file():
        yield base
        return
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in sorted(fns):
            if pred(fn):
                yield Path(dp) / fn


# ---- static script analysis -------------------------------------------------------------------------

def strip_heredocs(text: str) -> tuple[str, str]:
    """Return (bash text without heredoc bodies, concatenated heredoc bodies)."""
    out, bodies, tag = [], [], None
    for line in text.splitlines():
        if tag is not None:
            if line.strip() == tag:
                tag = None
            else:
                bodies.append(line)
            continue
        out.append(line)
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if m:
            tag = m.group(1)
    return "\n".join(out), "\n".join(bodies)


def analyze_script(text: str, path: str) -> dict:
    """Static facts about one script: can it exit non-zero, and does it fail open."""
    is_py = path.endswith(".py") or text.startswith("#!/usr/bin/env python") or text.startswith("#!/usr/bin/python")
    facts = {"lang": "python" if is_py else "bash", "fail_open": [], "or_true": []}
    lines = text.splitlines()
    if is_py:
        code = [(i + 1, ln) for i, ln in enumerate(lines) if not ln.lstrip().startswith("#")]
        nonzero = [n for n, ln in code if re.search(
            r"sys\.exit\((?!0\)|\))|\bexit\((?!0\))|raise SystemExit\((?!0\))|\braise\b|\bassert\b|check=True|unittest\.main|pytest\.main", ln)]
        reads = [n for n, ln in code if re.search(r"json\.load|\.read_text\(|\bopen\(|subprocess\.run|yaml\.", ln)]
        facts.update(can_fail=bool(nonzero), may_crash=bool(reads), errexit=False)
    else:
        body, heredoc = strip_heredocs(text)
        blines = [(i + 1, ln) for i, ln in enumerate(body.splitlines()) if ln.strip() and not ln.lstrip().startswith("#")]
        nonzero = [n for n, ln in blines if re.search(r"\bexit\s+(?!0\b)[\w$\"{]|return\s+[1-9]\b", ln)]
        errexit = bool(re.search(r"^\s*set\s+-[a-zA-Z]*e|^#!.*\s-[a-zA-Z]*e\b", body, re.M))
        last = blines[-1][1].strip() if blines else ""
        quiet_tail = bool(re.match(r"(exit 0|echo\b|printf\b|true\b|:)", last))
        facts.update(can_fail=bool(nonzero) or errexit or not quiet_tail, may_crash=False, errexit=errexit, last=last[:80])
    facts["nonzero_lines"] = nonzero[:6]
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#"):
            continue
        if re.search(r"\|\|\s*true\b", ln):
            facts["or_true"].append(i + 1)
        window = "\n".join(lines[i:i + 5])
        if TOOL_PROBE.search(ln) and TOOL_SKIP.search(window) and not HARD_FAIL.search(window):
            facts["fail_open"].append((i + 1, "tool-missing treated as pass/skip", ln.strip()[:90]))
        if re.search(r"\[\[?\s+-[xfe]\s+[^\]]+\]\]?\s*\|\|\s*(return|exit)\s+0", ln):
            facts["fail_open"].append((i + 1, "absent file/runner treated as pass", ln.strip()[:90]))
        if re.search(r"except\s*(\(?\s*Exception|\(?\s*OSError|\(?\s*ValueError|\(?\s*json\.JSONDecodeError|:)", ln):
            nxt = "\n".join(lines[i + 1:i + 3])
            if re.search(r"^\s*(pass|return 0|return True|sys\.exit\(0\)|continue)\b", nxt, re.M) and not HARD_FAIL.search(nxt):
                facts["fail_open"].append((i + 1, "parse/IO error swallowed as pass", ln.strip()[:90]))
    return facts


def split_functions(text: str) -> dict:
    funcs, name, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\(\)\s*\{", line)
        if m and name is None:
            name, buf = m.group(1), [line]
        elif name is not None:
            buf.append(line)
            if line.startswith("}"):
                funcs[name] = "\n".join(buf)
                name = None
    return funcs


# ---- inventory --------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, repo: Path):
        self.repo = repo
        self.hooks = {p.name: rd(p) for p in walk(repo, ".githooks") if p.name != "README.md"}
        self.workflows, self.workflow_yaml = {}, {}
        try:
            import yaml
            self.yaml_ok = True
        except ImportError:
            self.yaml_ok = False
        for p in sorted(walk(repo, ".github/workflows", lambda n: n.endswith((".yml", ".yaml")))):
            t = rd(p)
            self.workflows[rel(repo, p)] = t
            if self.yaml_ok:
                try:
                    self.workflow_yaml[rel(repo, p)] = yaml.safe_load(t) or {}
                except Exception:
                    self.workflow_yaml[rel(repo, p)] = None
        mp = repo / "config/ci-checks.json"
        self.manifest = json.loads(rd(mp)) if mp.is_file() else {"checks": []}
        self.tier0_path = next((p for p in walk(repo, "scripts") if p.name == "tier0-validation-gate.sh"), None)
        self.tier0_text = rd(self.tier0_path) if self.tier0_path else ""
        self.tests = {rel(repo, p): rd(p) for sub in ("scripts/testing", "tests") if (repo / sub).is_dir()
                      for p in walk(repo, sub, lambda n: n.endswith((".py", ".sh")))}
        self.scripts = {rel(repo, p): rd(p) for sub in ("scripts", "nix") if (repo / sub).is_dir()
                        for p in walk(repo, sub, lambda n: n.endswith((".py", ".sh", ".nix")) or "." not in n)
                        if not rel(repo, p).startswith("scripts/testing/test-")}
        self.runner = next((k for k in self.scripts if k.endswith("run-ci-checks.sh")), None)
        self.runner_text = self.scripts.get(self.runner or "", "")
        self.mutation = self._mutation_tables()

    def _mutation_tables(self) -> dict:
        p = self.repo / "scripts/testing/test-tier0d-gate-mutation.py"
        if not p.is_file():
            return {"cases": {}, "elsewhere": {}, "known": False}
        try:
            spec = importlib.util.spec_from_file_location("_mut", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            cases = {}
            for c in m.CASES:
                cases.setdefault(c.gate, set()).add(c.want)
            return {"cases": cases, "elsewhere": dict(m.COVERED_ELSEWHERE), "known": True}
        except Exception as e:  # unknown stays unknown
            return {"cases": {}, "elsewhere": {}, "known": False, "error": f"{type(e).__name__}: {e}"}

    def tests_naming(self, *needles) -> list:
        needles = [n for n in needles if n]
        return sorted(t for t, txt in self.tests.items() if any(n in txt for n in needles))

    def references(self, relpath: str) -> list:
        """Stages that reference a script: hooks, workflows, tier0, manifest cmds, other scripts, nix units."""
        base = os.path.basename(relpath)
        stages = [f"hook:{h}" for h, t in self.hooks.items() if base in t]
        stages += [f"workflow:{os.path.basename(w)}" for w, t in self.workflows.items() if base in t]
        if self.tier0_text and base in self.tier0_text:
            stages.append("tier0")
        stages += [f"manifest:{c['id']}" for c in self.manifest["checks"] if relpath in c["cmd"].split()]
        for s, t in self.scripts.items():
            if s != relpath and base in t:
                stages.append(f"{'nix' if s.endswith('.nix') else 'script'}:{s}")
        return stages

    def runner_callers(self) -> list:
        """(source, mode, only_ids) for every hook or workflow that invokes the manifest runner."""
        out = []
        pat = re.compile(r"(?:run-ci-checks\.sh|ci-clean-env\.sh)((?:[^\n&|;\\]|\\\n)*)")
        srcs = [(f"hook:{h}", t) for h, t in self.hooks.items()] + \
               [(f"workflow:{os.path.basename(w)}", t) for w, t in self.workflows.items()]
        for src, text in srcs:
            for m in pat.finditer(text):
                args = m.group(1).replace("\\\n", " ")
                mode = "changed" if "--changed" in args else "all" if ("--all" in args or "--maintenance" in args) else "other"
                out.append((src, mode, set(re.findall(r"--only[ =]([\w-]+)", args))))
        return out


def tier0_globs(ctx: Ctx) -> list:
    """Globs tier0 uses to pick tier0.d entries, parsed from the runner text."""
    return re.findall(r"\"\$\{?TIER0D\}?\"/(\S+?)[;\s]", ctx.tier0_text)


# ---- analysis ---------------------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.findings, self.unknown, self.units, self.notes = [], [], [], []

    def unit(self, kind, uid, **kw):
        self.units.append({"kind": kind, "unit": uid, **kw})

    def add(self, uid, kind, cls, sev, ev, basis="static"):
        f = {"unit": uid, "kind": kind, "class": cls, "severity": sev, "evidence": ev, "basis": basis}
        if f not in self.findings:
            self.findings.append(f)

    def unk(self, uid, what):
        self.unknown.append({"unit": uid, "what": what})


def script_findings(rep, ctx, uid, kind, relpath, text, is_test=False):
    facts = analyze_script(text, relpath)
    if not facts["can_fail"] and not facts["may_crash"]:
        why = ("no sys.exit non-zero, raise, assert or check=True; only prints" if facts["lang"] == "python"
               else f"no non-zero exit, no errexit, ends in `{facts.get('last', '')}`")
        rep.add(uid, kind, "CANNOT_FAIL", "high", f"{why} (static)")
    elif not facts["can_fail"]:
        rep.add(uid, kind, "CANNOT_FAIL", "medium", "no explicit failure path; can only fail by crashing on unreadable input (static)")
    for ln, why, snip in facts["fail_open"]:
        rep.add(uid, kind, "FAIL_OPEN", "medium", f"line {ln}: {why}: `{snip}` (static)")
    if not is_test:
        base = os.path.basename(relpath)
        gate_tests = ctx.tests_naming(base, relpath)
        if base in ctx.mutation["cases"] or base in ctx.mutation["elsewhere"]:
            return facts
        if not gate_tests:
            rep.add(uid, kind, "NO_BAD_INPUT_TEST", "medium", "no test names this gate and it is not in the tier0.d mutation suite (static)")
        elif not any(FAIL_WORDS.search(ctx.tests[t]) for t in gate_tests):
            rep.add(uid, kind, "NO_BAD_INPUT_TEST", "low",
                    f"named by {len(gate_tests)} test(s) but none expresses a failing expectation: {', '.join(gate_tests[:2])} (static)")
    return facts


def sweep_tier0d(rep, ctx):
    if not ctx.tier0_path:
        rep.unk("tier0.d", "no tier0-validation-gate.sh found; cannot tell which stage runs tier0.d")
    tdir = (ctx.tier0_path.parent / "tier0.d") if ctx.tier0_path else ctx.repo / "scripts/governance/tier0.d"
    globs = tier0_globs(ctx) if ctx.tier0_path else []
    if ctx.tier0_path and not globs:
        rep.unk("tier0.d", "could not parse which files tier0 runs from tier0.d")
    if not tdir.is_dir():
        return
    for p in sorted(tdir.iterdir()):
        if not p.is_file() or p.name == "README.md":
            continue
        uid, relp = f"tier0.d/{p.name}", rel(ctx.repo, p)
        in_tier0 = bool(globs) and any(fnmatch.fnmatch(p.name, g) for g in globs)
        others = [s for s in ctx.references(relp) if s != "tier0" and not s.startswith("script:" + relp)]
        others = [s for s in others if not s.startswith("script:") or "tier0-validation-gate" not in s]
        stages = (["tier0"] if in_tier0 else []) + others
        rep.unit("tier0.d", uid, path=relp, stages=stages)
        if globs and not stages:
            rep.add(uid, "tier0.d", "UNCOVERED", "high",
                    f"tier0 runs only {globs} from tier0.d; this file matches none and nothing else references it (static)")
        elif globs and not in_tier0:
            rep.add(uid, "tier0.d", "UNCOVERED", "medium",
                    f"not run by tier0 (it globs {globs}); referenced only by {others[:3]} (static)")
        script_findings(rep, ctx, uid, "tier0.d", relp, rd(p))


def sweep_tier0_functions(rep, ctx):
    if not ctx.tier0_text:
        return
    funcs = split_functions(ctx.tier0_text)
    gates = {n: b for n, b in funcs.items() if n.startswith("gate_")}
    helpers = {n: b for n, b in funcs.items() if not n.startswith("gate_")}
    for n, b in gates.items():
        uid, kind = f"tier0:{n}", "tier0-function"
        outside = ctx.tier0_text.replace(b, "")
        called = bool(re.search(rf"^\s*{n}(\s|$)", outside, re.M))
        rep.unit(kind, uid, path=rel(ctx.repo, ctx.tier0_path), stages=["tier0"] if called else [])
        if not called:
            rep.add(uid, kind, "UNCOVERED", "high", "defined but never called in tier0-validation-gate.sh (static)")
        code = re.sub(r"^\s*#.*$", "", b, flags=re.M)
        if not re.search(r"\bfail\b|return 1\b|exit [1-9]", code):
            rep.add(uid, kind, "CANNOT_FAIL", "high", "body has no fail(), return 1 or exit (static)")
        for i, ln in enumerate(b.splitlines(), 1):
            if re.search(r"\bskip\b", ln) and not ln.lstrip().startswith("#"):
                rep.add(uid, kind, "FAIL_OPEN", "low", f"body line {i}: skip() path is not a failure: `{ln.strip()[:80]}` (static)")
                break
        if re.search(r"\bpass\b[^\n]*(No .* (changes|files)|nothing|empty)", b, re.I) or re.search(r"\$\{#files\[@\]\}\s*-eq\s*0", b):
            for hn, hb in helpers.items():
                if re.search(rf"\b{hn}\b", b) and re.search(r"\bgit\b[^\n]*\|\|\s*true", hb):
                    rep.add(uid, kind, "FAIL_OPEN", "high",
                            f"empty file list passes and the list comes from {hn}() whose commands end in `|| true`: a git failure gives an empty list and a 'No changes' PASS (static)")
        if re.search(r"\|\s*grep -q\b", b) and re.search(r"\bpass\b", b):
            rep.add(uid, kind, "FAIL_OPEN", "low", "verdict comes from grepping the sub-command's output text, not its exit status (static)")
        named = ctx.tests_naming(n)
        if not named:
            rep.add(uid, kind, "NO_BAD_INPUT_TEST", "medium", f"no test names {n} (static)")
        elif not any(FAIL_WORDS.search(ctx.tests[t]) for t in named):
            rep.add(uid, kind, "NO_BAD_INPUT_TEST", "low", f"named by {named[:2]} but none expresses a failing expectation (static)")


def sweep_hooks(rep, ctx):
    installers = [p for p, t in ctx.scripts.items() if "hooksPath" in t]
    for h, text in sorted(ctx.hooks.items()):
        uid, relp = f".githooks/{h}", f".githooks/{h}"
        rep.unit("hook", uid, path=relp, stages=[f"git:{h}"] if installers else [])
        if not installers:
            rep.add(uid, "hook", "UNCOVERED", "high", "nothing in scripts/ sets core.hooksPath to .githooks (static)")
        script_findings(rep, ctx, uid, "hook", relp, text)
        for m in re.finditer(r"\$\{?(SKIP_\w+|AQ_ALLOW\w*|AQ_DELEGATE_HANDBACK)[:\-=]", text):
            rep.notes.append(f"{uid}: env bypass `{m.group(1)}`")


def parse_workflows(rep, ctx):
    """Returns {uid: jobinfo}. Context is the job `name` (what a required status check matches) or id."""
    jobs = {}
    if not ctx.yaml_ok:
        rep.unk("workflows", "PyYAML missing: workflow jobs not parsed")
        return jobs
    for wf, doc in ctx.workflow_yaml.items():
        if doc is None:
            rep.unk(wf, "workflow YAML did not parse")
            continue
        triggers = doc.get(True, doc.get("on", {}))  # YAML 1.1 reads the key `on` as True
        trig = list(triggers) if isinstance(triggers, (dict, list)) else [triggers]
        for jid, job in (doc.get("jobs") or {}).items():
            if isinstance(job, dict):
                jobs[f"workflow:{os.path.basename(wf)}#{jid}"] = {"wf": wf, "jid": jid, "context": str(job.get("name") or jid),
                                                                   "triggers": trig, "job": job}
    return jobs


def claim_for(ctx, j) -> str:
    d = ctx.manifest.get("description", "")
    ids = [c["id"] for c in ctx.manifest["checks"] if str(c.get("ci_workflow", "")) == f"{j['wf']}#{j['jid']}"]
    if ids and CLAIM.search(d):
        return f"manifest description says `{CLAIM.search(d).group(0)}` and {len(ids)} check(s) point here via ci_workflow"
    m = CLAIM.search(ctx.workflows[j["wf"]])
    return f"workflow text says `{m.group(0)}`" if m else ""


def sweep_workflows(rep, ctx, required):
    mask_re = re.compile(r"\|\|\s*true\b|continue-on-error:\s*true\b")
    annot_re = re.compile(r"#\s*(KNOWN-FAILING|NON-GATING):\s*\S")
    cwm_path = ctx.repo / "scripts/governance/check-workflow-masks.py"
    if cwm_path.is_file():
        try:
            spec = importlib.util.spec_from_file_location("_cwm", cwm_path)
            cwm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cwm)
            mask_re, annot_re = cwm.MASK, cwm.ANNOTATION
        except Exception as e:
            rep.unk("check-workflow-masks.py", f"could not import, used built-in regexes: {e}")
    jobs = parse_workflows(rep, ctx)
    direct = set()
    for uid, j in jobs.items():
        job, wf = j["job"], j["wf"]
        rep.unit("workflow-job", uid, path=wf, stages=[uid], context=j["context"], triggers=j["triggers"])
        lines = ctx.workflows[wf].splitlines()
        start = next((i for i, ln in enumerate(lines) if re.match(rf"^  {re.escape(j['jid'])}:\s*$", ln)), None)
        if start is not None:
            end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  \S", lines[i])), len(lines))
            for i in range(start, end):
                ln = lines[i]
                if ln.lstrip().startswith("#") or not mask_re.search(ln):
                    continue
                m = annot_re.search(ln) or annot_re.search(lines[i - 1] if i else "")
                tag = m.group(1) if m else "UNANNOTATED"
                rep.add(uid, "workflow-job", "MASKED_IN_CI", "low" if tag == "NON-GATING" else "high",
                        f"{wf}:{i + 1} `{ln.strip()[:80]}` annotated {tag} (static; mask regex reused from check-workflow-masks)")
        default_shell = (job.get("defaults") or {}).get("run", {}).get("shell") if isinstance(job.get("defaults"), dict) else None
        for si, st in enumerate(job.get("steps") or []):
            run = st.get("run", "") if isinstance(st, dict) else ""
            if not run:
                continue
            shell = st.get("shell") or default_shell
            if not ("pipefail" in run or (shell and str(shell).split()[0] == "bash")):
                for raw in run.splitlines():
                    parts = re.split(r"(?<!\|)\|(?!\|)", raw)
                    if len(parts) > 1 and PIPE_LEFT.search(parts[0]) and PIPE_RIGHT.match(parts[1]):
                        rep.add(uid, "workflow-job", "MASKED_IN_CI", "medium",
                                f"step {si + 1} `{raw.strip()[:70]}`: default shell has no pipefail, so the left command's status is lost (static)")
                        break
            for sp in re.findall(r"(scripts/[\w./-]+\.(?:sh|py))", run):
                if sp in ctx.scripts and GATE_PREFIX.match(os.path.basename(sp)) and sp not in direct:
                    direct.add(sp)
                    rep.unit("workflow-script", f"script:{sp}", path=sp, stages=[uid])
                    script_findings(rep, ctx, f"script:{sp}", "workflow-script", sp, ctx.scripts[sp])
        if required is None:
            rep.unk(uid, "required status checks not collected (use --github or --required-checks)")
        elif j["context"] not in required and j["jid"] not in required:
            claim = claim_for(ctx, j)
            rep.add(uid, "workflow-job", "NOT_REQUIRED", "medium" if claim else "info",
                    f"context `{j['context']}` is not a required status check; claim: {claim or 'none found'} (static + branch protection read)")
        elif not any(t in ("pull_request", "pull_request_target") for t in j["triggers"]):
            rep.add(uid, "workflow-job", "UNCOVERED", "high",
                    "required check but the workflow has no pull_request trigger: it can never report on a PR (static)")
    return jobs


def sweep_manifest(rep, ctx, jobs, required):
    callers = ctx.runner_callers()
    warn_local = bool(re.search(r"\"WARN\"\s+if\s+maintenance\s+or\s+not\s+ci", ctx.runner_text))
    for c in ctx.manifest["checks"]:
        uid = f"ci-check:{c['id']}"
        parts = c["cmd"].split()
        script = parts[0] if parts else ""
        stages = [f"{src}({mode}{',--only' if only else ''})" for src, mode, only in callers
                  if (not only and mode in ("all", "changed")) or c["id"] in only]
        rep.unit("ci-check", uid, path=script, stages=stages)
        if not stages:
            rep.add(uid, "ci-check", "UNCOVERED", "high", "no hook or workflow invokes the runner for this id (static)")
        is_test = bool(re.search(r"scripts/testing/test-|run-test-group", c["cmd"]))
        p = ctx.repo / script
        if p.is_file():
            script_findings(rep, ctx, uid, "ci-check", script, rd(p), is_test=is_test)
        else:
            rep.unk(uid, f"cmd script {script} not found")
        absent = [t for t in c.get("needs", []) if not shutil.which(t)]
        if absent and warn_local:
            rep.add(uid, "ci-check", "FAIL_OPEN", "medium",
                    f"runner reports missing tool(s) {absent} as WARN, not FAIL, whenever CI != true; absent on this host (exercised: shutil.which)",
                    basis="exercised")
        wf = c.get("ci_workflow")
        if wf:
            wfile, _, jid = wf.partition("#")
            m = [u for u, j in jobs.items() if os.path.basename(j["wf"]) == os.path.basename(wfile) and j["jid"] == jid]
            if jobs and not m:
                rep.add(uid, "ci-check", "UNCOVERED", "medium", f"ci_workflow `{wf}` names a job that does not exist (static)")
            elif m and required is not None and jobs[m[0]]["context"] not in required and jid not in required:
                rep.add(uid, "ci-check", "NOT_REQUIRED", "medium",
                        f"claims CI via {wf}; that job is not a required status check, so a red run does not block merge (static + branch protection read)")


def sweep_orphans(rep, ctx):
    seen = {u["path"] for u in rep.units if "path" in u}
    for relp in sorted(ctx.scripts):
        base = os.path.basename(relp)
        if not (relp.startswith(("scripts/governance/", "scripts/testing/")) and GATE_PREFIX.match(base)
                and base.endswith((".sh", ".py")) and "/tier0.d/" not in relp):
            continue
        uid = f"script:{relp}"
        refs = [s for s in ctx.references(relp) if s != f"script:{relp}"]
        exempt = [e for e in ctx.manifest.get("ci_exempt", []) if e.get("script") == relp]
        if relp in seen and refs:
            continue
        if not any(u["unit"] == uid for u in rep.units):
            rep.unit("script", uid, path=relp, stages=refs)
        if not refs:
            rep.add(uid, "script", "UNCOVERED", "medium" if exempt else "high",
                    f"no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: {exempt[0]['reason'][:80] if exempt else 'none'} (static)")
        if relp not in seen:
            script_findings(rep, ctx, uid, "script", relp, ctx.scripts[relp])


# ---- exercised probes -------------------------------------------------------------------------------

def sandbox_env(home: Path) -> dict:
    keep = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "TERM")}
    keep.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1",
                GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                GIT_COMMITTER_EMAIL="t@example.invalid")
    return keep


def _append(rel_path, text):
    def f(work):
        with open(work / rel_path, "a", encoding="utf-8") as fh:
            fh.write(text)
    return f


def _write(rel_path, text):
    def f(work):
        p = work / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return f


def _git(*a):
    def f(work):
        subprocess.run(["git", "-c", "commit.gpgsign=false", *a], cwd=work, capture_output=True,
                       env=sandbox_env(work.parent / "home"))
    return f


def _seq(*fns):
    def f(work):
        for fn in fns:
            fn(work)
    return f


def _remove(rel_path):
    def f(work):
        (work / rel_path).unlink()
    return f


# Runs one tier0 helper function in isolation: the real function text is cut out of the runner, so nothing else executes.
_TIER0 = "scripts/governance/tier0-validation-gate.sh"
_FN = ("set -u; src=$(sed -n '/^%s() {/,/^}/p' " + _TIER0 + "); eval \"$src\"; ")
_SECRET = "AKIA" + "QWERTYUIOPASDFGH"  # built at runtime so this file holds no scannable key

# Each probe seeds ONE bad input in a throwaway copy and runs the gate; a gate that exits 0 is a finding.
# `ctl` marks a control that must fail, proving the probe itself can detect the bad input.
PROBES: list = [
    {"id": "collect-staged-control", "unit": "tier0:collect_changed_files", "script": _TIER0, "ctl": True,
     "seed": "staged bad.py, --pre-commit (control)",
     "setup": _seq(_write("bad.py", "def (:\n")),
     "cmd": ["bash", "-c", _FN % "collect_changed_files" + "MODE=--pre-commit; collect_changed_files | grep -qx bad.py && exit 1 || exit 0"]},
    {"id": "collect-no-origin", "unit": "tier0:collect_changed_files", "script": _TIER0,
     "seed": "committed bad.py, --pre-deploy, no origin/main",
     "setup": _seq(_write("bad.py", "def (:\n"), _git("add", "-A"), _git("commit", "-q", "--no-verify", "-m", "bad")),
     "cmd": ["bash", "-c", _FN % "collect_changed_files" + "MODE=--pre-deploy; collect_changed_files | grep -qx bad.py && exit 1 || exit 0"]},
    {"id": "deploy-batch-zero", "unit": "tier0:gate_deploy_batch_size", "script": _TIER0,
     "seed": "0 commits ahead of origin/main (batch too small)",
     "setup": lambda w: None,
     "cmd": ["bash", "-c", _FN % "gate_deploy_batch_size" + "log(){ :; }; pass(){ :; }; gate_deploy_batch_size"]},
    {"id": "root-shim-rogue", "unit": "script:scripts/governance/check-root-script-shim-only.sh",
     "script": "scripts/governance/check-root-script-shim-only.sh",
     "seed": "scripts/rogue.sh that is not a compatibility shim",
     "setup": _write("scripts/rogue.sh", "#!/usr/bin/env bash\necho real logic\n"),
     "cmd": ["bash", "scripts/governance/check-root-script-shim-only.sh"]},
    {"id": "script-header-missing", "unit": "script:scripts/governance/check-script-header-standards.sh",
     "script": "scripts/governance/check-script-header-standards.sh",
     "seed": "new script with no shebang and no purpose line, --all",
     "setup": _write("scripts/governance/zz-nohdr.sh", "echo hi\n"),
     "cmd": ["bash", "scripts/governance/check-script-header-standards.sh", "--all"]},
    {"id": "precommit-secret", "unit": ".githooks/pre-commit", "script": ".githooks/pre-commit",
     "seed": "staged file holding an AKIA-shaped key, on a non-main branch",
     "setup": _seq(_git("checkout", "-q", "-b", "probe"), _write("scripts/zz-leak.txt", f"aws_key = {_SECRET}\n")),
     "cmd": ["bash", ".githooks/pre-commit"]},
    {"id": "premerge-guard-missing", "unit": ".githooks/pre-merge-commit", "script": ".githooks/pre-merge-commit",
     "seed": "shallow-merge guard script absent",
     "setup": _remove("scripts/governance/check-mergeable.sh"),
     "cmd": ["bash", ".githooks/pre-merge-commit"]},
]


def exercise(rep, repo: Path, timeout=90):
    """Run PROBES in a throwaway clone with HOME redirected. Never touches live state."""
    results = []
    with tempfile.TemporaryDirectory(prefix="sweep-gates-") as d:
        root = Path(d)
        (root / "home").mkdir()
        env = sandbox_env(root / "home")
        clone = root / "clone"
        r = subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(repo), str(clone)], env=env, capture_output=True,
                           text=True, timeout=300)
        if r.returncode != 0:
            rep.unk("exercise", f"clone failed: {r.stderr.strip()[:200]}")
            return results
        for pr in PROBES:
            if not (clone / pr["script"]).is_file():
                results.append({"probe": pr["id"], "unit": pr["unit"], "outcome": "NOT_RUN", "seed": pr["seed"],
                                "detail": f"{pr['script']} not in HEAD of the clone"})
                continue
            work = root / ("w-" + pr["id"])
            shutil.copytree(clone, work, symlinks=True, ignore=shutil.ignore_patterns(".git"))
            for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                         ["-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "base"]):
                subprocess.run(["git", *args], cwd=work, env=env, capture_output=True)
            try:
                pr["setup"](work)
                subprocess.run(["git", "add", "-A"], cwd=work, env=env, capture_output=True)
                p = subprocess.run(pr["cmd"], cwd=work, env={**env, **pr.get("env", {})}, capture_output=True, text=True,
                                   timeout=timeout, stdin=subprocess.DEVNULL)
                tail = " | ".join((p.stdout + p.stderr).strip().splitlines()[-2:])[-220:]
                results.append({"probe": pr["id"], "unit": pr["unit"], "seed": pr["seed"], "rc": p.returncode, "detail": tail,
                                "outcome": "FAILED_AS_EXPECTED" if p.returncode != 0 else "PASSED_ON_BAD_INPUT"})
                if pr.get("ctl"):
                    results[-1]["outcome"] = "CONTROL_OK" if p.returncode != 0 else "CONTROL_BROKEN"
            except subprocess.TimeoutExpired:
                results.append({"probe": pr["id"], "unit": pr["unit"], "outcome": "TIMEOUT", "seed": pr["seed"], "detail": f">{timeout}s"})
            except Exception as e:
                results.append({"probe": pr["id"], "unit": pr["unit"], "outcome": "ERROR", "seed": pr["seed"],
                                "detail": f"{type(e).__name__}: {e}"})
    for r in results:
        if r["outcome"] == "PASSED_ON_BAD_INPUT":
            rep.add(r["unit"], "exercised", "CANNOT_FAIL", "high",
                    f"exercised: seeded bad input ({r['seed']}) and the gate exited 0: {r['detail']}", basis="exercised")
        elif r["outcome"] in ("ERROR", "TIMEOUT", "NOT_RUN", "CONTROL_BROKEN"):
            rep.unk(r["unit"], f"probe {r['probe']} {r['outcome']}: {r['detail']}")
    return results


# ---- orchestration + rendering ----------------------------------------------------------------------

def collect_required(args):
    if args.required_checks is not None:
        return {c for c in args.required_checks.split(",") if c}
    gh = shutil.which("gh") if args.github else None
    if not gh:
        return None
    try:
        url = subprocess.run(["git", "-C", args.repo, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?\s*$", url)
        if not m:
            return None
        r = subprocess.run([gh, "api", f"repos/{m.group(1)}/branches/main/protection"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        rc = json.loads(r.stdout).get("required_status_checks") or {}
        return set(rc.get("contexts", [])) | {c.get("context") for c in rc.get("checks", [])}
    except Exception:
        return None


def sweep(repo: Path, required=None, do_exercise=False):
    ctx, rep = Ctx(repo), Report()
    sweep_tier0d(rep, ctx)
    sweep_tier0_functions(rep, ctx)
    sweep_hooks(rep, ctx)
    jobs = sweep_workflows(rep, ctx, required)
    sweep_manifest(rep, ctx, jobs, required)
    sweep_orphans(rep, ctx)
    if required is not None:
        for r in sorted(required):
            if not any(j["context"] == r or j["jid"] == r for j in jobs.values()):
                rep.add(f"required:{r}", "required-check", "UNCOVERED", "high",
                        "required status check has no workflow job with that name or id: it can never report (static)")
    ex = exercise(rep, repo) if do_exercise else []
    rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    rep.findings.sort(key=lambda f: (rank[f["severity"]], f["class"], f["unit"]))
    by_kind = {}
    for u in rep.units:
        by_kind[u["kind"]] = by_kind.get(u["kind"], 0) + 1
    return {"units": rep.units, "units_by_kind": by_kind, "findings": rep.findings,
            "counts": {c: len({f["unit"] for f in rep.findings if f["class"] == c}) for c in CLASSES},
            "finding_rows": {c: sum(1 for f in rep.findings if f["class"] == c) for c in CLASSES},
            "unknown": rep.unknown, "notes": rep.notes, "exercised": ex,
            "required_checks": sorted(required) if required is not None else None,
            "mutation_suite_known": ctx.mutation["known"]}


def render_report(res, day, argv):
    L = [f"# {day} sweep-gates", "",
         "## Objective",
         "Recovery sweep P2.2 (system-integrity-recovery): list gates that cannot fail, have no bad-input test, fail open, "
         "are masked in CI, are not required, or are not run by any stage. Report only; no gate or finding was fixed.", "",
         "## Workflow/Session IDs",
         f"Branch feat/sweep-gates, date {day}. Sweeps this tree only. fix/gates-placement (S2) moves checks between stages, "
         "so UNCOVERED, NOT_REQUIRED and stage results will change when S2 merges; the script derives stages from references and hardcodes none.", "",
         "## Delegation Decision",
         "Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixture tests).", "",
         "## Commands Executed",
         f"- `scripts/governance/sweep-gates.py {' '.join(argv)}`".rstrip(),
         "- `gh api repos/<owner>/<repo>/branches/main/protection` (read-only GET, required status checks only)",
         "- Probes: `git clone` into a temp dir with HOME redirected, seed one bad input, run the gate, record the exit code", "",
         "## Validation Evidence", "",
         "Gates inventoried: " + ", ".join(f"{k} {v}" for k, v in sorted(res["units_by_kind"].items())) + f" (total {len(res['units'])}).", "",
         "Gates affected per class (a gate counts once per class):", "",
         "| Class | Gates | Finding rows |", "|---|---|---|"]
    L += [f"| {c} | {n} | {res['finding_rows'][c]} |" for c, n in res["counts"].items()]
    rc = res["required_checks"]
    L += ["", f"Required status checks (branch protection, main): {rc if rc is not None else 'not collected (unknown)'}.", "",
          "### Findings", "", "| # | Sev | Class | Basis | Gate | Evidence |", "|---|---|---|---|---|---|"]
    for i, f in enumerate(res["findings"], 1):
        L.append(f"| {i} | {f['severity']} | {f['class']} | {f['basis']} | `{f['unit']}` | {f['evidence'].replace('|', chr(92) + '|')} |")
    if not res["findings"]:
        L.append("| - | - | - | - | none | - |")
    L += ["", "### Exercised (throwaway clone, one seeded bad input each)", ""]
    if res["exercised"]:
        L += ["| Probe | Gate | Seed | Outcome | rc | Detail |", "|---|---|---|---|---|---|"]
        L += [f"| {r['probe']} | `{r['unit']}` | {r.get('seed', '')} | {r['outcome']} | {r.get('rc', '')} | {r['detail'].replace('|', '/')} |"
              for r in res["exercised"]]
    else:
        L.append("- none run (pass --exercise)")
    L += ["", "### Unknown / not determined (never counted as pass)", ""]
    unk = {}
    for u in res["unknown"]:
        unk.setdefault(u["what"], []).append(u["unit"])
    L += [f"- {w}: {len(us)} gate(s), e.g. {', '.join(sorted(set(us))[:3])}" for w, us in sorted(unk.items())] or ["- none"]
    if res["notes"]:
        L += ["", "### Env-var bypasses noted (not classed)", ""] + [f"- {n}" for n in sorted(set(res["notes"]))]
    L += ["", "### Static versus exercised", "",
          "- Static: every CANNOT_FAIL, NO_BAD_INPUT_TEST, FAIL_OPEN (except tool absence), MASKED_IN_CI, UNCOVERED and NOT_REQUIRED row is "
          "text or YAML analysis of this tree. Heuristics can misjudge a script that fails through an indirect command; each row names what matched.",
          "- Exercised: the probe table, tool presence via `shutil.which` on this host, and the branch-protection read.",
          "- Not exercised: every other gate (no tier0 run, no `run-ci-checks.sh --all`, no hook against a real commit, no live-stack gate); "
          "tool availability in the GitHub runner image is unknown.", "",
          "## Rollback Plan", "Delete this report, the sweep script, its test and the manifest entry; nothing else was changed.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", help="write the dated markdown report to this path")
    ap.add_argument("--fail-on", default="", help="comma list of classes that make the exit status non-zero (default: report only)")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--github", action="store_true", help="read required status checks from branch protection via gh (read-only)")
    ap.add_argument("--required-checks", help="comma list of required check contexts (offline use and fixtures)")
    ap.add_argument("--exercise", action="store_true", help="run the seeded bad-input probes in a throwaway clone")
    a = ap.parse_args(argv)
    fail = [c for c in a.fail_on.split(",") if c]
    bad = [c for c in fail if c not in CLASSES]
    if bad:
        ap.error(f"unknown class {bad}; choose from {CLASSES}")
    res = sweep(Path(a.repo), collect_required(a), a.exercise)
    if a.report:
        Path(a.report).write_text(render_report(res, a.date, sys.argv[1:] if argv is None else argv))
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print(f"sweep-gates: {len(res['units'])} gates inventoried, {len(res['unknown'])} unknown, report-only")
        for k, v in res["counts"].items():
            print(f"  {k:18} {v}")
    return 1 if any(res["counts"][c] for c in fail) else 0


if __name__ == "__main__":
    sys.exit(main())
