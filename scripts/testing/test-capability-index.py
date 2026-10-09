#!/usr/bin/env python3
"""Capability index generator (ci-4): determinism, dead-candidate exclusion, size bound, wiring."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import capability_index as ci  # noqa: E402


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    audit = {"window_days": 30, "capabilities": [
        {"name": "aq-hints", "kinds": ["script"], "paths": ["scripts/ai/aq-hints"], "class": "ACTIVE"},
        {"name": "aq-zzz-dead", "kinds": ["script"], "paths": ["scripts/ai/aq-zzz-dead"], "class": "DEAD-CANDIDATE"},
        {"name": "x@y", "kinds": ["artifact"], "paths": ["y"], "class": "ACTIVE"},
        {"name": "get_hints", "kinds": ["mcp-tool"], "paths": ["scripts/ai/mcp-bridge-hybrid.py"], "class": "UNUSED-AVAILABLE"},
        {"name": "agent-tool-map", "kinds": ["skill"], "paths": [".agent/skills/agent-tool-map/SKILL.md"], "class": "UNDISCOVERABLE"},
    ]}
    a = ci.build_index(audit, ROOT, "t.json")
    b = ci.build_index(json.loads(json.dumps(audit)), ROOT, "t.json")
    check(a == b and ci.render_markdown(a) == ci.render_markdown(b), "generator must be deterministic")
    names = [e["name"] for e in a["entries"]]
    check("aq-zzz-dead" not in names, "DEAD-CANDIDATE must be excluded")
    check("x@y" not in names, "artifact kind must be excluded")
    check({"aq-hints", "get_hints", "agent-tool-map"} <= set(names), f"live capabilities missing: {names}")
    h = next(e for e in a["entries"] if e["name"] == "aq-hints")
    check(h["purpose"] and h["category"] and h["class"] == "ACTIVE" and h["kind"] == "script", f"entry fields: {h}")
    check("aq-zzz-dead" not in ci.render_markdown(a), "dead candidate leaked into markdown")

    # committed outputs: bound, consistency with the json, no dead candidates, CLI --check is read-only
    md = (ROOT / "docs" / "agent-guides" / "CAPABILITY-INDEX.md").read_bytes()
    check(len(md) <= ci.MAX_BYTES, f"CAPABILITY-INDEX.md is {len(md)} bytes (> {ci.MAX_BYTES})")
    js = json.loads((ROOT / "config" / "capability-index.json").read_text())
    check(js["schema"] == ci.SCHEMA and js["count"] == len(js["entries"]) > 100, "bad committed json")
    check(all(e["class"] != "DEAD-CANDIDATE" for e in js["entries"]), "dead candidate in committed index")
    check(all(e["name"] and e["category"] and e["kind"] for e in js["entries"]), "entry missing required field")
    check(ci.render_markdown(js) == md.decode(), "markdown out of sync with json")

    with tempfile.TemporaryDirectory() as td:
        rep = Path(td) / "capability-audit-1.json"
        rep.write_text(json.dumps(audit))
        out = [Path(td) / "i.md", Path(td) / "i.json"]
        cmd = [sys.executable, "-I", str(ROOT / "scripts/ai/aq-capability-index"), "--audit", str(rep),
               "--md-out", str(out[0]), "--json-out", str(out[1])]
        env = {"AQ_USAGE_TELEMETRY": "0", "PATH": "/usr/bin:/bin"}
        r1 = subprocess.run(cmd, capture_output=True, text=True, env=env)
        first = [p.read_bytes() for p in out]
        r2 = subprocess.run(cmd, capture_output=True, text=True, env=env)
        check(r1.returncode == 0 and r2.returncode == 0, f"CLI failed: {r1.stderr}{r2.stderr}")
        check(first == [p.read_bytes() for p in out], "CLI output not byte-identical across runs")
        check(subprocess.run(cmd + ["--check"], capture_output=True, env=env).returncode == 0, "--check should pass when current")

    # wiring: manifest tool, disclosure domain, hint rule, audit discovery source
    sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))
    from tooling_manifest import build_tooling_manifest, workflow_tool_catalog
    tools = workflow_tool_catalog("write a new helper script")
    check(any(t["name"] == "capability_index" for t in tools), "tooling manifest catalog lacks capability_index")
    man = build_tooling_manifest("write a new helper script", tools, max_tools=6)
    check(any(t["name"] == "capability_index" for t in man["tools"]), "capability_index dropped by manifest")
    dom = json.loads((ROOT / "config" / "progressive-disclosure-domains.json").read_text())["domains"]
    check("CAPABILITY-INDEX" in json.dumps(dom.get("capability-reuse", {})), "disclosure domain missing")
    from knowledge.static_rules import STATIC_RULES
    check(any(r["id"] == "check_capability_index_before_new_code" for r in STATIC_RULES), "hint rule missing")
    check("capability-index.json" in (ROOT / "scripts/ai/lib/capability_audit.py").read_text(), "audit discovery list lacks the index")

    # instruction-file budgets untouched
    for f in ("CLAUDE.md", "AGENTS.md"):
        n = len((ROOT / f).read_bytes())
        check(n <= 24000, f"{f} over 24000-byte budget: {n}")
    print(f"PASS: capability index ({js['count']} entries, {len(md)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
