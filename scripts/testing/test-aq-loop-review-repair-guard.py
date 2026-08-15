#!/usr/bin/env python3
"""Hermetic bounded review-repair guard."""
import importlib.util
import importlib.machinery
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("loop_state", ROOT / "ai-stack/local-agents/loop_state.py")
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
scope = {key: "a" * 64 for key in ("subject_hash", "baseline_hash", "criteria_hash", "roster_hash", "policy_hash")}
def rejected(*ids): return {"verdict":"REJECTED", "scope":scope, "blockers":[{"invariant_id":item,"finding_hash":"b"*64} for item in ids]}
state = module.LoopState("t", "x", 0, 3, "VERIFY")
action, detail = module.consume_review_result(state, rejected("schema", "privacy"))
assert action == "repair" and len(detail["findings"]) == 2
action, detail = module.consume_review_result(state, rejected("schema"))
assert action == "escalated" and detail["reason"] == "invariant_recurrence"
action2, detail2 = module.consume_review_result(state, rejected("schema"))
assert action2 == "escalated" and detail2["signal"] == detail["signal"] and len(state.review_repair["issue_signals"]) == 1
drift = rejected("other"); drift["scope"] = {**scope, "policy_hash":"c"*64}
assert module.consume_review_result(state, drift)[0] == "escalated"
for bad in (None, {}, {"verdict":"CONCERNS","scope":scope,"blockers":[]}): assert module.consume_review_result(state, bad)[0] == "escalated"
assert module.consume_review_result(module.LoopState("u","x",0,3,"VERIFY"), {"verdict":"APPROVED","scope":scope,"blockers":[]})[0] == "approved"
upper = {**scope, "subject_hash":"A" * 64}
assert module.consume_review_result(module.LoopState("v","x",0,3,"VERIFY"), {"verdict":"REJECTED","scope":upper,"blockers":[{"invariant_id":"x","finding_hash":"b"*64}]})[0] == "escalated"

# Exercise aq-loop's real terminal review branch with hermetic fakes.  No
# subprocess, provider, filesystem state writer, or backlog mutation is used.
loader = importlib.machinery.SourceFileLoader("aq_loop", str(ROOT / "scripts/ai/aq-loop"))
loop_spec = importlib.util.spec_from_loader(loader.name, loader)
aq_loop = importlib.util.module_from_spec(loop_spec); sys.modules[loader.name] = aq_loop; loader.exec_module(aq_loop)

def review(verdict, blockers, scope_value=scope): return {"verdict":verdict, "scope":scope_value, "blockers":blockers}
finding = [{"invariant_id":"schema", "finding_hash":"b" * 64}]

def terminal_case(reviews, max_iter=1):
    phases, escalations = [], []
    queue = list(reviews)
    aq_loop._loop_id = lambda: "guard-loop"
    aq_loop.write_state = lambda state: phases.append(state.phase)
    aq_loop.append_pulse = lambda *args, **kwargs: None
    aq_loop.update_resume = lambda *args, **kwargs: None
    aq_loop.archive_state = lambda state: phases.append("ARCHIVED")
    aq_loop.write_escalation = lambda state: escalations.append(state.review_repair.copy())
    aq_loop.get_hints = lambda intent: ""
    aq_loop.get_skills = lambda intent: ""
    aq_loop.fanout_ground = lambda *args, **kwargs: ""
    aq_loop.run_inner_loop = lambda *args, **kwargs: {"success":True, "incomplete_result":False, "result":"COMPLETED: proof", "status":"completed", "tool_calls":[], "elapsed_seconds":0}
    aq_loop.fanout_verify = lambda *args, **kwargs: {"structured":queue.pop(0), "output":"fake"}
    rc = aq_loop.run_loop("guard", max_iter=max_iter, fanout=True, fanout_timeout=0)
    return rc, phases, escalations

for bad in (None, {"verdict":"CONCERNS","scope":scope,"blockers":[]}):
    rc, phases, escalations = terminal_case([bad])
    assert rc == 1 and phases[-1] == "ESCALATED" and "COMPLETE" not in phases and len(escalations) == 1
rc, phases, escalations = terminal_case([review("REJECTED", finding)])
assert rc == 1 and phases[-1] == "ESCALATED" and "COMPLETE" not in phases and len(escalations) == 1
rc, phases, escalations = terminal_case([review("REJECTED", finding), review("REJECTED", finding)], max_iter=2)
assert rc == 1 and phases[-1] == "ESCALATED" and "COMPLETE" not in phases and len(escalations) == 1
drift_scope = {**scope, "policy_hash":"c" * 64}
rc, phases, escalations = terminal_case([review("REJECTED", finding), review("REJECTED", [{"invariant_id":"other","finding_hash":"d"*64}], drift_scope)], max_iter=2)
assert rc == 1 and phases[-1] == "ESCALATED" and len(escalations) == 1
rc, phases, escalations = terminal_case([review("APPROVED", [])])
assert rc == 0 and "COMPLETE" in phases and "ESCALATED" not in phases and not escalations
print("aq-loop-review-repair-guard: PASS")
