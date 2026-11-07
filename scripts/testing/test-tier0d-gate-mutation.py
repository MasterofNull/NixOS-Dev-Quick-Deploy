#!/usr/bin/env python3
"""Mutation suite for scripts/governance/tier0.d: every gate must fail on its known-bad input.

P0.8 of system-integrity-recovery ("every tier0.d gate has a test proving it can fail"). Each
table case builds a throwaway git repo, copies only the files the gate needs from this tree,
stages a mutation, runs the COPIED gate there and asserts exit code plus message. Every gate
has a known-good case (must pass) next to its known-bad case (must fail), so a gate that
passes or fails unconditionally is caught. Nothing here touches the real tree's state.

Gates that already carry a bad-input test in another file are listed in COVERED_ELSEWHERE.
The meta-check fails if a gate is in neither table, so a new gate needs a mutation test.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/governance/lib"))
from clean_git_env import clean_git_env  # noqa: E402

GATE_DIR = REPO / "scripts/governance/tier0.d"

# gate file -> test file that already runs the gate (or the entrypoint it execs) on bad input.
COVERED_ELSEWHERE = {
    "check-activation-manifest.sh": "scripts/testing/test-activation-manifest.py",
    "check-anti-fabrication.sh": "scripts/testing/test-anti-fabrication-lint.py",
    "check-ci-manifest-coverage.sh": "scripts/testing/test-ci-checks-manifest.py",
    "check-ci-test-coverage.sh": "scripts/testing/test-ci-test-coverage-gate.py",
    "check-color-echo.sh": "scripts/testing/test-tier0-color-echo-extension.sh",
    "check-flake-age.sh": "scripts/testing/test-check-flake-age.sh",
    "check-frontier-fold": "scripts/testing/test-check-frontier-fold.py",
    "check-gitleaks-ci-parity.sh": "scripts/testing/test-gitleaks-ci-parity.py",
    "check-grype-ignore-expiry.sh": "scripts/testing/test-ffmpeg-cve-mitigations.py",
    "check-lane-hook-parity.sh": "scripts/testing/test-lane-hook-parity.py",
}


class Skip(Exception):
    pass


class Sandbox:
    """A temp git repo that holds a copy of one gate and the files it reads."""

    def __init__(self, root: Path):
        self.root = root
        self.env = {**clean_git_env(), "HOME": str(root / "_home"), "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1", "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        for k in ("SKIP_CVE_SCAN", "OWNED_PATHS", "SCOPE_BASE", "ALLOW_UNCOMMITTED", "AQ_AGENT_AUTH_POLICY"):
            self.env.pop(k, None)
        (root / "_home").mkdir()
        self.git("init", "-q", "-b", "main")

    def git(self, *a, check=True):
        return subprocess.run(["git", "-C", str(self.root), *a], env=self.env, text=True,
                              capture_output=True, check=check)

    def put(self, rel: str, text: str, mode: Optional[int] = None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        if mode:
            p.chmod(mode)

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def copy(self, *rels: str):
        for rel in rels:
            src, dst = REPO / rel, self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "target"))
            else:
                shutil.copy2(src, dst)

    def commit(self, msg="base"):
        self.git("add", "-A")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", msg)

    def stage(self):
        self.git("add", "-A")

    def run(self, gate: str, args=(), env=None, path_prefix: Optional[Path] = None):
        e = {**self.env, **(env or {})}
        if path_prefix:
            e["PATH"] = f"{path_prefix}:{e['PATH']}"
        p = subprocess.run([str(self.root / "scripts/governance/tier0.d" / gate), *args], cwd=self.root,
                           env=e, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=90)
        return p.returncode, p.stdout + p.stderr


@dataclass
class Case:
    gate: str
    name: str
    setup: Callable[[Sandbox], Optional[dict]]  # builds + commits base, stages the mutation; may return run kwargs
    want: str  # "pass" | "fail" | "warn" (rc 0 and a WARN line)
    msg: str  # regex that must appear in the output
    args: tuple = ()
    copy: list = field(default_factory=list)  # files the gate needs from the real tree
    in_place: bool = False  # run the real gate from the real tree (read-only gates with an env override)


# ---- fixtures ---------------------------------------------------------------------------------

CANON_FILES = ["canon", "AGENTS.md", "CLAUDE.md", ".agent/CODEX.md", ".agent/GEMINI.md",
               ".agent/LOCAL-AGENT.md", ".agent/WORKFLOW-CANON.md"]


def base_only(sb):
    sb.commit()


def canon_drift_block(sb):
    sb.commit()
    text = sb.read("CLAUDE.md")
    m = re.search(r"<!-- canon:begin behavioral-rules -->\n", text)
    sb.put("CLAUDE.md", text[:m.end()] + "TAMPERED LINE inside a canon block\n" + text[m.end():])
    sb.stage()


def canon_missing_block(sb):
    sb.commit()
    text = sb.read("CLAUDE.md")
    sb.put("CLAUDE.md", text.replace("<!-- canon:begin fable-parity -->", "", 1))
    sb.stage()


def canon_lane_oversize(sb):
    sb.commit()
    text = sb.read("CLAUDE.md")
    sb.put("CLAUDE.md", text.replace("<!-- lane:end -->", ("x" * 100 + "\n") * 100 + "<!-- lane:end -->", 1))
    sb.stage()


def budget_files(sb, claude_lines=10):
    for f in ("CLAUDE.md", "AGENTS.md", ".agent/CODEX.md", ".agent/GEMINI.md", ".agent/LOCAL-AGENT.md"):
        sb.put(f, "line\n" * (claude_lines if f == "CLAUDE.md" else 10))


def budget_good(sb):
    budget_files(sb)
    sb.commit()


def budget_over(sb):
    budget_files(sb, claude_lines=201)
    sb.commit()


def budget_missing(sb):
    budget_files(sb)
    (sb.root / "AGENTS.md").unlink() if (sb.root / "AGENTS.md").exists() else None
    sb.commit()


def evidence_msg(sb, text):
    sb.commit()
    sb.put("_msg.txt", text)
    return {"args": ("_msg.txt",)}


def config_good(sb):
    sb.commit()


def config_bad(sb):
    sb.commit()
    p = sb.root / "config/switchboard-profiles.yaml"
    p.write_text("profiles: {broken: [this, is, not, a, valid, profile, mapping]}\nunexpected_top_level_key: 1\n")
    sb.stage()


def links_setup(sb, delete_target):
    sb.put("docs/a.md", "# A\n")
    sb.put("docs/b.md", "see [a](a.md)\n" if delete_target == "docs/a.md" else "no links here\n")
    sb.commit()
    (sb.root / delete_target).unlink()
    sb.stage()


def cve_setup(sb, vulns):
    sb.put("pkg/package.json", '{"name":"x","version":"1.0.0"}\n')
    sb.put("pkg/package-lock.json", '{"name":"x","lockfileVersion":3}\n')
    sb.commit()
    sb.put("pkg/package.json", '{"name":"x","version":"1.0.1"}\n')
    sb.stage()
    stub = sb.root / "_stubbin"
    stub.mkdir()
    audit = json.dumps({"metadata": {"vulnerabilities": vulns}})
    sb.put("_stubbin/npm", f"#!/usr/bin/env bash\nprintf '%s' '{audit}'\n", 0o755)
    return {"path_prefix": stub}


def owned_setup(sb, touch):
    if not shutil.which("cargo"):
        raise Skip("cargo not on PATH (gate itself WARN-skips without it)")
    sb.put("owned/a.txt", "a\n")
    sb.put("other/b.txt", "b\n")
    sb.commit()
    sb.put(touch, "changed\n")
    sb.stage()
    # The sandbox HOME is empty, so a rustup-managed cargo (CI runners) finds no toolchain and the gate
    # fails for a reason unrelated to scope; pin the toolchain dirs to the invoking user's real ones.
    real_home = Path(os.environ.get("HOME", "/"))
    return {"env": {"OWNED_PATHS": "owned/", "SCOPE_BASE": "HEAD", "ALLOW_UNCOMMITTED": "1",
                    "CARGO_TARGET_DIR": str(sb.root / "_target"),
                    "CARGO_HOME": os.environ.get("CARGO_HOME", str(real_home / ".cargo")),
                    "RUSTUP_HOME": os.environ.get("RUSTUP_HOME", str(real_home / ".rustup"))}}


def pm_setup(sb, tracker_text):
    if tracker_text:
        sb.put(".agents/plans/p/tracker.json", tracker_text)
    sb.commit()
    # the owner-acceptance check fetches origin/main and fails closed offline; give it a local origin
    origin = sb.root.parent / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=sb.env, check=True)
    sb.git("remote", "add", "origin", str(origin))
    sb.git("push", "-q", "origin", "main")


def shallow_setup(sb, shallow):
    sb.put("f.txt", "1\n")
    sb.commit()
    sb.put("f.txt", "2\n")
    sb.commit("second")
    if shallow:
        clone = sb.root.parent / (sb.root.name + "-shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{sb.root}", str(clone)],
                       env=sb.env, check=True, capture_output=True)
        sb.root = clone


SECRETS_NIX = 'sops.secrets = {\n  "${sec.names.aidbApiKey}" = { };\n  "${sec.names.hybridApiKey}" = { };\n};\n'
OPTIONS_NIX = ('names = {\n  aidbApiKey = lib.mkOption { type = lib.types.str; default = "aidb_api_key"; };\n'
               '  hybridApiKey = lib.mkOption { type = lib.types.str; default = "hybrid_api_key"; };\n};\n')


def sops_setup(sb, sops_body):
    sb.put("nix/modules/core/secrets.nix", SECRETS_NIX)
    sb.put("nix/modules/core/options.nix", OPTIONS_NIX)
    sb.put("_home/.local/share/nixos-quick-deploy/secrets/h/secrets.sops.yaml", sops_body)
    sb.commit()


ENC = "ENC[AES256_GCM,data:abcd,iv:x,tag:y,type:str]"
ENC_EMPTY = "ENC[AES256_GCM,data:,iv:x,tag:y,type:str]"
SOPS_META = "sops:\n  version: 3.9.0\n"


def suspend_setup(sb, add_unit, stage_contract):
    sb.copy("config/suspend-resume-workloads.json", "nix/modules/roles/ai-stack.nix", "scripts/ai/lib/dispatch.py",
            "scripts/ai/aq-local-training-loop")
    # the contract names files it points at; the checker requires each to exist
    for rel in sorted(set(re.findall(r'"((?:scripts|nix|config)/[^"\s]+)"', sb.read("config/suspend-resume-workloads.json")))):
        if (REPO / rel).is_file() and not (sb.root / rel).exists():
            sb.copy(rel)
    sb.commit()
    if add_unit:
        sb.put("nix/modules/example.nix", "{\n  systemd.services.brand-new-worker = {\n    enable = true;\n  };\n}\n")
    if stage_contract:
        text = sb.read("config/suspend-resume-workloads.json")
        sb.put("config/suspend-resume-workloads.json", text + "\n")
    sb.stage()


def pins_setup(sb, with_pins, py_ok=True):
    if with_pins:
        sb.copy("config/tool-pins.json")
    sb.commit()
    if py_ok:
        return None
    stub = sb.root / "_stubbin"
    stub.mkdir()
    real = shutil.which("python3")
    sb.put("_stubbin/python3", f'#!/usr/bin/env bash\n[[ "$*" == *"(3, 11)"* ]] && exit 1\nexec {real} "$@"\n', 0o755)
    return {"path_prefix": stub}


def auth_policy(sb, mutate):
    pol = json.loads((REPO / "config/agent-auth-policy.json").read_text())
    mutate(pol)
    sb.put("_policy.json", json.dumps(pol))
    return {"env": {"AQ_AGENT_AUTH_POLICY": str(sb.root / "_policy.json")}}


def _ungranted_scope(pol):
    pol["classes"]["sandbox"].append("scope.that.was.never.declared")


def _no_guidance(pol):
    pol["scopes"]["read.hints"].pop("hint", None)
    pol["scopes"]["read.hints"].pop("why", None)


CASES = [
    # canon + parity: real canon tree copied in; the gates read it relative to their own location
    Case("check-canon-drift.sh", "good: in-sync canon blocks pass", base_only, "pass", r"PASS: canon blocks in sync",
         copy=CANON_FILES + ["scripts/governance/canon-compile.py"]),
    Case("check-canon-drift.sh", "bad: edited text inside a canon block", canon_drift_block, "fail", r"FAIL: canon drift",
         copy=CANON_FILES + ["scripts/governance/canon-compile.py"]),
    Case("check-agent-instruction-parity.sh", "good: all required blocks + lane region", base_only, "pass", r"\[tier0.d/check-agent-instruction-parity\] PASS",
         copy=CANON_FILES + ["scripts/governance/check-agent-instruction-parity.py"]),
    Case("check-agent-instruction-parity.sh", "bad: required canon block marker removed", canon_missing_block, "fail", r"required canon block 'fable-parity' missing",
         copy=CANON_FILES + ["scripts/governance/check-agent-instruction-parity.py"]),
    Case("check-agent-instruction-parity.sh", "bad: lane region over its byte budget", canon_lane_oversize, "fail", r"lane region \d+ bytes exceeds lane budget",
         copy=CANON_FILES + ["scripts/governance/check-agent-instruction-parity.py"]),

    Case("check-instruction-budget.sh", "good: five files under 200 lines", budget_good, "pass", r"within line budget"),
    Case("check-instruction-budget.sh", "bad: CLAUDE.md at 201 lines", budget_over, "fail", r"CLAUDE\.md exceeds budget \(201 > 200"),
    Case("check-instruction-budget.sh", "bad: required instruction file missing", budget_missing, "fail", r"AGENTS\.md does not exist"),

    Case("check-commit-evidence-warn.sh", "good: message with review trailers is silent",
         lambda sb: evidence_msg(sb, "feat: x\n\nReviewed-by: someone\n"), "pass", r"^(?!.*WARN)"),
    Case("check-commit-evidence-warn.sh", "warn-class: message without trailers warns (never blocks)",
         lambda sb: evidence_msg(sb, "feat: x\n\nno trailers\n"), "warn", r"does not contain independent review trailers"),

    Case("check-config-contracts.sh", "good: registered switchboard config validates", config_good, "pass", r"PASS: 1 registered config",
         copy=["contracts", "scripts/ai/lib/config_loader.py", "config/switchboard-profiles.yaml"]),
    Case("check-config-contracts.sh", "bad: registered config violates its schema", config_bad, "fail", r"FAIL \(validate\)",
         copy=["contracts", "scripts/ai/lib/config_loader.py", "config/switchboard-profiles.yaml"]),

    Case("check-deleted-links.sh", "good: deleting an unreferenced doc passes", lambda sb: links_setup(sb, "docs/b.md"), "pass", r"PASS: 1 deleted doc",
         args=("--pre-commit",)),
    Case("check-deleted-links.sh", "bad: deleting a doc that is still linked", lambda sb: links_setup(sb, "docs/a.md"), "fail", r"FAIL: 1 deleted doc\(s\) still referenced",
         args=("--pre-commit",)),

    Case("check-dependency-cve.sh", "good: audit reports no high/critical", lambda sb: cve_setup(sb, {"high": 0, "critical": 0}), "pass", r"PASS: 0 high/critical CVEs"),
    Case("check-dependency-cve.sh", "bad: audit reports a high CVE in a modified manifest", lambda sb: cve_setup(sb, {"high": 1, "critical": 0}), "fail", r"FAIL: high/critical CVEs in pkg/package.json"),
    Case("check-dependency-cve.sh", "bad: audit reports a critical CVE", lambda sb: cve_setup(sb, {"high": 0, "critical": 2}), "fail", r"critical=2"),

    Case("check-owned-scope.sh", "good: change inside the owned path", lambda sb: owned_setup(sb, "owned/a.txt"), "pass", r"(?s)^(?!.*FAIL|.*violation)",
         copy=["crates/contract-validator"]),
    Case("check-owned-scope.sh", "bad: change outside the owned path", lambda sb: owned_setup(sb, "other/b.txt"), "fail", r"other/b\.txt",
         copy=["crates/contract-validator"]),

    Case("check-pm-tracker.sh", "bad: unparseable plan tracker.json", lambda sb: pm_setup(sb, "{not json"), "fail", r"tracker\.json does not validate/project",
         args=("--pre-commit",), copy=["scripts/ai/aq-pm-tracker", "scripts/ai/aq-refactor-status", "scripts/ai/lib", "config"]),
    Case("check-pm-tracker.sh", "good: no plan trackers and a valid owner-acceptance baseline", lambda sb: pm_setup(sb, ""), "pass", r"no plan trackers yet",
         args=("--pre-commit",), copy=["scripts/ai/aq-pm-tracker", "scripts/ai/aq-refactor-status", "scripts/ai/lib", "config"]),
    Case("check-pm-tracker.sh", "bad: projector missing is a FAIL, never a skip", lambda sb: sb.commit(), "fail", r"projector or python3 unavailable",
         args=("--pre-commit",)),

    Case("check-shallow-repo.sh", "good: full clone passes", lambda sb: shallow_setup(sb, False), "pass", r"PASS: repo is not shallow"),
    Case("check-shallow-repo.sh", "warn-class: shallow clone warns (never blocks)", lambda sb: shallow_setup(sb, True), "warn", r"SHALLOW clone"),

    Case("check-sops-sync.sh", "good: every declared secret is in the SOPS file",
         lambda sb: sops_setup(sb, f"aidb_api_key: {ENC}\nhybrid_api_key: {ENC}\n{SOPS_META}"), "pass", r"PASS: SOPS file keys match"),
    Case("check-sops-sync.sh", "bad: declared secret missing from the SOPS file",
         lambda sb: sops_setup(sb, f"aidb_api_key: {ENC}\n{SOPS_META}"), "fail", r"MISSING from .*\n.*hybrid_api_key"),
    Case("check-sops-sync.sh", "bad: required API key stored as empty ciphertext",
         lambda sb: sops_setup(sb, f"aidb_api_key: {ENC}\nhybrid_api_key: {ENC_EMPTY}\n{SOPS_META}"), "fail", r"empty ciphertext for hybrid_api_key"),

    Case("check-suspend-resume-contract.sh", "good: contract valid, no new unit",
         lambda sb: suspend_setup(sb, False, False), "pass", r"PASS: staged suspend/resume workload contract is valid",
         copy=["scripts/testing/test-suspend-resume-contract.py"]),
    Case("check-suspend-resume-contract.sh", "bad: new systemd service without a staged contract update",
         lambda sb: suspend_setup(sb, True, False), "fail", r"added without a staged config/suspend-resume-workloads\.json update",
         copy=["scripts/testing/test-suspend-resume-contract.py"]),
    Case("check-suspend-resume-contract.sh", "good: new systemd service with the contract staged",
         lambda sb: suspend_setup(sb, True, True), "pass", r"PASS: staged",
         copy=["scripts/testing/test-suspend-resume-contract.py"]),

    Case("check-tool-pins-skew.sh", "good: pins present and python >= 3.11", lambda sb: pins_setup(sb, True), "pass", r"PASS: tool versions meet canonical floors",
         copy=["config/tool-pins.json"]),
    Case("check-tool-pins-skew.sh", "bad: config/tool-pins.json missing", lambda sb: pins_setup(sb, False), "fail", r"missing config/tool-pins\.json"),
    Case("check-tool-pins-skew.sh", "bad: python below the 3.11 floor", lambda sb: pins_setup(sb, True, py_ok=False), "fail", r"below minimum floor",
         copy=["config/tool-pins.json"]),

    Case("check-agent-auth-policy.sh", "good: shipped policy passes the lint", lambda sb: {}, "pass", r"", in_place=True),
    Case("check-agent-auth-policy.sh", "bad: class grants an undeclared scope", lambda sb: auth_policy(sb, _ungranted_scope), "fail", r"FAIL", in_place=True),
    Case("check-agent-auth-policy.sh", "bad: scope without guidance", lambda sb: auth_policy(sb, _no_guidance), "fail", r"FAIL", in_place=True),
]


# ---- runner -----------------------------------------------------------------------------------

def run_case(c: Case):
    with tempfile.TemporaryDirectory(prefix="tier0d-mut-") as d:
        root = Path(d) / "r"
        root.mkdir()
        sb = Sandbox(root)
        sb.copy(f"scripts/governance/tier0.d/{c.gate}")
        sb.copy(*c.copy)
        kw = c.setup(sb) or {}
        kw.setdefault("args", c.args)
        if c.in_place:
            args = kw.get("args", ())
            p = subprocess.run([str(GATE_DIR / c.gate), *args], cwd=REPO, text=True, capture_output=True,
                               stdin=subprocess.DEVNULL, timeout=90,
                               env={**sb.env, "HOME": os.environ.get("HOME", "/"), **kw.get("env", {})})
            rc, out = p.returncode, p.stdout + p.stderr
        else:
            rc, out = sb.run(c.gate, **kw)
    ok = (rc != 0) if c.want == "fail" else (rc == 0)
    if c.want == "warn":
        ok = ok and "WARN" in out
    found = re.search(c.msg, out, re.S) is not None if c.msg else True
    return ok and found, rc, out


def meta_check() -> list:
    errs = []
    gates = sorted(p.name for p in GATE_DIR.iterdir() if p.is_file() and p.name != "README.md")
    table = {c.gate for c in CASES}
    for g in gates:
        in_t, in_e = g in table, g in COVERED_ELSEWHERE
        if not in_t and not in_e:
            errs.append(f"{g}: no mutation test (add Case entries here or name the covering test in COVERED_ELSEWHERE)")
        if in_t and in_e:
            errs.append(f"{g}: listed both in CASES and COVERED_ELSEWHERE")
    for g in sorted(table | set(COVERED_ELSEWHERE)):
        if g not in gates:
            errs.append(f"{g}: listed but no such gate in tier0.d (stale entry)")
    for g in sorted(table):
        wants = {c.want for c in CASES if c.gate == g}
        if "pass" not in wants and not any(c.gate == g and c.want == "warn" for c in CASES):
            errs.append(f"{g}: has no known-good case")
        if not wants & {"fail", "warn"}:
            errs.append(f"{g}: has no known-bad case")
    for g, t in COVERED_ELSEWHERE.items():
        tp = REPO / t
        if not tp.is_file():
            errs.append(f"{g}: covering test {t} does not exist")
        elif g.removesuffix(".sh") not in tp.read_text(encoding="utf-8", errors="replace"):
            errs.append(f"{g}: covering test {t} never names the gate")
    return errs


def main() -> int:
    fails, skips, reasons = [], [], {}
    errs = meta_check()
    for e in errs:
        print(f"FAIL meta: {e}")
    fails += errs
    for c in CASES:
        label = f"{c.gate} :: {c.name}"
        try:
            ok, rc, out = run_case(c)
        except Skip as s:
            print(f"SKIP {label}: {s}")
            skips.append(label)
            continue
        except Exception as e:  # a harness error is a failure, never a pass
            print(f"FAIL {label}: harness error {type(e).__name__}: {e}")
            fails.append(label)
            reasons[label] = f"harness error {type(e).__name__}: {e}"
            continue
        if ok:
            print(f"PASS {label} (rc={rc})")
        else:
            tail = out.strip().replace("\n", "\n    ")[-900:]
            print(f"FAIL {label}: rc={rc} want={c.want} msg=/{c.msg}/\n    " + tail)
            fails.append(label)
            reasons[label] = f"rc={rc} want={c.want} msg=/{c.msg}/ last-output: " + " | ".join(out.strip().splitlines()[-2:])[-300:]
    n = len(CASES)
    # Last lines of output: the CI runner shows only the tail, so failures must be named here.
    for label in fails:
        print(f"  FAILED: {label} -- {reasons.get(label, 'see above')}")
    print(f"gate-mutation: {n - len(fails) - len(skips)}/{n} passed, {len(skips)} skipped, {len(fails)} failed; "
          f"{len({c.gate for c in CASES})} gates mutated here, {len(COVERED_ELSEWHERE)} covered elsewhere")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
