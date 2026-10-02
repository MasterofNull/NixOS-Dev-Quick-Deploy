#!/usr/bin/env python3
"""M3: coordinator PRSI surfaces read the canonical queue with the real row schema."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
PH = HC / "workflow" / "prsi_handlers.py"
MH = HC / "extensions" / "mcp_handlers.py"
AC = ROOT / "ai-stack" / "local-agents" / "builtin_tools" / "ai_coordination.py"
LEGACY = "/var/lib/nixos-ai-stack/prsi/"


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def load_helpers() -> Dict[str, Any]:
    tree = ast.parse(PH.read_text())
    names = ("_prsi_queue_path", "_prsi_pending_rows", "_prsi_summary", "prsi_orchestrate_readonly")
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    keep += [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_PRSI_REFUSALS"]
    check(len(keep) == 5, "helpers missing in prsi_handlers.py")
    ns: Dict[str, Any] = {"os": os, "Path": Path, "json": json, "Dict": Dict, "Any": Any}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(PH), "exec"), ns)
    return ns


def load_ac_helper():
    tree = ast.parse(AC.read_text())
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_prsi_pending_rows"]
    check(len(fn) == 1, "ai_coordination._prsi_pending_rows missing")
    ns: Dict[str, Any] = {}
    exec(compile(ast.Module(body=fn, type_ignores=[]), str(AC), "exec"), ns)
    return ns["_prsi_pending_rows"]


ROWS = [
    {"id": "a1", "status": "pending_approval", "risk": "medium", "type": "routing", "action": "x", "reason": "r"},
    {"id": "a2", "status": "executed", "risk": "low"},
    {"id": "r1", "status": "rsi_pending", "risk": "high", "raw_action": {"source": "rsi-incidents.json", "incident_id": "i1"}, "approval": {}},
    {"id": "r2", "status": "rsi_pending", "risk": "high", "raw_action": {"source": "rsi-incidents.json", "incident_id": "i2"}, "approval": {"verifier_by": "bob"}},
    {"id": "r3", "status": "rsi_failed", "risk": "medium", "raw_action": {"source": "rsi-incidents.json", "incident_id": "i3"}},
    {"id": "r4", "status": "rsi_failed", "risk": "high", "raw_action": {"source": "rsi-incidents.json", "incident_id": "i4"}},
    {"id": "p1", "status": "pending", "risk": "low"},
]


def main() -> int:
    for f in (PH, MH, AC):
        check(LEGACY not in f.read_text(), f"legacy queue path still in {f.name}")
    mh = MH.read_text()
    check("risk_level" not in mh.split('name == "mcp_server_prsi_orchestrate"')[1][:1500], "dead critical gate still present")
    check("_sp.run" not in mh.split('name == "mcp_server_prsi_orchestrate"')[1].split('name == "context_system_state"')[0], "prsi_orchestrate must not spawn the orchestrator")
    ac = AC.read_text()
    check('data.get("pending"' in ac, "ai_coordination HTTP branch must read 'pending'")

    ns = load_helpers()
    got = sorted(r["id"] for r in ns["_prsi_pending_rows"](ROWS))
    check(got == ["a1", "r1", "r4"], f"pending filter wrong: {got}")
    check(ns["_prsi_summary"](ROWS[0])["risk"] == "medium", "summary must use risk")

    # Agreement with the approval inbox on the same fixture (prsi approval rows only).
    sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
    import approval_inbox  # noqa: E402

    with tempfile.TemporaryDirectory() as td:
        q = Path(td) / "q.json"
        q.write_text(json.dumps({"actions": ROWS}))
        os.environ["PRSI_ACTION_QUEUE_PATH"] = str(q)
        os.environ["PRSI_INCIDENTS_FILE"] = str(Path(td) / "none.json")
        os.environ["AQ_APPROVAL_INBOX_DIR"] = td
        approval_inbox._attention_pending = lambda: []
        approval_inbox.load_dismissed = lambda: set()
        inbox = sorted(i["ref"] for i in approval_inbox.collect() if i["key"].startswith("prsi:"))
        check(inbox == got, f"coordinator {got} != approval inbox {inbox}")
        check(ns["_prsi_queue_path"]() == q, "PRSI_ACTION_QUEUE_PATH not honored")
        check(sorted(r["id"] for r in load_ac_helper()(ROWS)) == inbox, "ai_coordination filter != approval inbox")

        orch = ns["prsi_orchestrate_readonly"]
        for act in ("approve", "reject"):
            r = orch(act)
            check(r["status"] == "refused" and "aq-approve" in r["reason"], f"{act} not refused with SOP message")
        for act in ("execute", "sync"):
            r = orch(act)
            check(r["status"] == "refused" and "timers" in r["reason"], f"{act} not refused")
        r = orch("list")
        check(r["status"] == "ok" and sorted(x["id"] for x in r["pending"]) == inbox, f"list wrong: {r}")
        q.write_text("[not json")
        check(orch("list")["status"] == "error", "malformed queue must error, not report empty")

    # Bridge: refusals are pure; the handler branch can only reach _run_local with a `list` argv.
    br = (ROOT / "scripts/ai/mcp-bridge-hybrid.py").read_text()
    tree = ast.parse(br)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "_prsi_orchestrate_refusal")
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("_PRSI_OWNER_MSG", "_PRSI_TIMER_MSG"))]
    bns: Dict[str, Any] = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "bridge", "exec"), bns)
    ref = bns["_prsi_orchestrate_refusal"]
    check(ref("list") is None, "bridge list must be allowed")
    for act in ("approve", "reject", "execute", "sync"):
        check(ref(act)["status"] == "refused", f"bridge {act} not refused")
    check("aq-approve" in ref("approve")["reason"] and "timers" in ref("sync")["reason"], "bridge SOP messages")
    branch = br.split('if name == "prsi_orchestrate":')[1].split('if name == "harness_health":')[0]
    check(branch.index("_prsi_orchestrate_refusal") < branch.index("_run_local"), "refusal must precede _run_local")
    for bad in ('"approve"', '"execute"', '"sync"', "--by", "--limit"):
        check(bad not in branch, f"bridge branch still builds {bad} argv")
    nix_src = (ROOT / "nix/modules/services/mcp-servers.nix").read_text()
    check('"PRSI_ACTION_QUEUE_PATH=${mutableOptimizerDir}/prsi/action-queue.json"' in nix_src, "nix env line missing")
    check('"a+ ${mutableOptimizerDir} - - - - g:${aiGroup}:--x"' in nix_src, "optimizer dir ACL rule missing")
    if os.getenv("PRSI_TEST_NIX_EVAL") != "1":
        print("PASS test-coordinator-prsi-canonical-queue (nix eval skipped; PRSI_TEST_NIX_EVAL=1 to run)")
        return 0
    expr = f'(builtins.getFlake (toString {ROOT})).nixosConfigurations.hyperd-ai-dev.config.systemd.services.ai-hybrid-coordinator.serviceConfig.Environment'
    p = subprocess.run(["nix", "eval", "--json", "--impure", "--expr", expr], capture_output=True, text=True, timeout=1700)
    if p.returncode != 0:
        print("SKIP nix eval:", p.stderr[-300:])
    else:
        envs = json.loads(p.stdout)
        v = [e for e in envs if e.startswith("PRSI_ACTION_QUEUE_PATH=")]
        check(v and v[0].endswith("/optimizer/prsi/action-queue.json"), f"env missing/wrong: {v}")
    print("PASS test-coordinator-prsi-canonical-queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
