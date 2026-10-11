#!/usr/bin/env python3
"""Regression checks for strict inbox selection and unsafe members."""
from __future__ import annotations
import importlib.machinery, importlib.util, io, json, tempfile
from contextlib import redirect_stdout
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; SCRIPT=ROOT/"scripts/ai/aq-antigravity-inbox"; loader=importlib.machinery.SourceFileLoader("ag_inbox",str(SCRIPT)); m=importlib.util.module_from_spec(importlib.util.spec_from_loader("ag_inbox",loader)); loader.exec_module(m)
def invoke_json(argv):
 stream=io.StringIO()
 with redirect_stdout(stream): result=m.main(argv)
 return result,json.loads(stream.getvalue())
def main():
 assert SCRIPT.stat().st_mode & 0o111, "installed CLI source must remain executable"
 with tempfile.TemporaryDirectory() as td:
  tmp=Path(td); m.REPO=tmp; m.INBOX=tmp/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"good.md").write_text("# task\nRole: reviewer\nRespond by writing only:\n`.agents/plans/good/antigravity.md`\n")
  assert m.main(["next","--json"])==0
  assert m.main(["claim","../good.md","--actor","ide-watch","--json"])==1
  (m.INBOX/"link.md").symlink_to(m.INBOX/"good.md")
  assert m.main(["claim","link.md","--actor","ide-watch","--json"])==1
  assert m.main(["dispatch-once","--attempt-ceiling","0","--json"])==2
  m._receipt_dir().mkdir(exist_ok=True); (m._receipt_path("good")).symlink_to(m.INBOX/"good.md")
  assert m.main(["claim","good.md","--actor","ide-watch","--json"])==1, "receipt symlink must fail closed"
  other=tmp/"second"; m.REPO=other; m.INBOX=other/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"stamp.md").write_text("# task\nRole: review\nOutput: .agents/plans/stamp/antigravity.md\n")
  m._append("stamp",{"type":"wake_attempt","task_id":"stamp","generation":m._metadata(m._read_regular(m.INBOX/"stamp.md"))[1],"actor":"dispatch-once","non_passive":True,"ts":"not-a-time"})
  assert m.main(["dispatch-once","--json"])==1, "invalid timestamp must fail closed"
  empty=tmp/"empty"; m.REPO=empty; m.INBOX=empty/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  assert m.main(["next","--json"])==1, "empty JSON selection is a nonzero result"
  # AM6 traversal payload must be rejected before any source unlink/read.
  victim=empty/"victim"; victim.write_text("keep")
  forged={"type":"completion_prepared","task_id":"evil","generation":"a"*64,"declared_output":".agents/x","source_name":"../../victim","ts":"2000-01-01T00:00:00+00:00","archived_path":".agent/archive/antigravity-inbox-20000101/../../victim-aaaaaaaaaaaa","recovery":True,"recovery_actor":"owner-manual","recovery_reason":"x","recovery_unclaimed":True,"recovery_missing_output":True}
  try: m._reconcile_prepared("evil",{"task_id":"evil","records":[forged]}); raise AssertionError("traversal prepared accepted")
  except m.InboxError: assert victim.read_text()=="keep"
  # Archive symlink/parent traversal and source-mode swaps cannot reach mutation.
  for source,unclaimed in (("evil.md",False),(".claimed-evil",True),("../evil.md",True)):
   bad={**forged,"source_name":source,"recovery_unclaimed":unclaimed,"archived_path":".agent/archive/antigravity-inbox-20000101/evil.md-aaaaaaaaaaaa"}
   try: m._reconcile_prepared("evil",{"task_id":"evil","records":[bad]}); raise AssertionError("source mode accepted")
   except m.InboxError: assert victim.read_text()=="keep"
  archive=empty/".agent/archive/antigravity-inbox-20000101"; archive.parent.mkdir(parents=True,exist_ok=True); archive.symlink_to(victim.parent)
  bad={**forged,"source_name":"evil.md","recovery_unclaimed":True,"archived_path":".agent/archive/antigravity-inbox-20000101/evil.md-aaaaaaaaaaaa"}
  try: m._reconcile_prepared("evil",{"task_id":"evil","records":[bad]}); raise AssertionError("archive symlink accepted")
  except m.InboxError: assert victim.read_text()=="keep"
  # Admission rejects empty/oversized owner reasons before moving pending input.
  m.INBOX.mkdir(parents=True,exist_ok=True); (m.INBOX/"reason.md").write_text("Output: .agents/x\n")
  for reason in ("", "x"*241):
   assert m.main(["complete","reason.md","--output",".agents/x","--recovery-allow-unclaimed","--recovery-actor","owner-manual","--recovery-reason",reason,"--json"])==1
   assert (m.INBOX/"reason.md").exists()
  # A successful completion must contain more than whitespace before it consumes the claim.
  blank=tmp/"blank-output"; m.REPO=blank; m.INBOX=blank/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  for index, content in enumerate((b"", b" \n\t"), start=1):
   tid=f"blank{index}"; task=m.INBOX/f"{tid}.md"; task.write_text(f"Role: reviewer\nOutput: .agents/plans/{tid}/antigravity.md\n")
   output=blank/f".agents/plans/{tid}/antigravity.md"; output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(content)
   assert m.main(["claim",task.name,"--actor","ide-watch","--json"])==0
   assert m.main(["complete",f".claimed-{tid}","--output",f".agents/plans/{tid}/antigravity.md","--json"])==1
   assert (m.INBOX/f".claimed-{tid}").exists() and not [r for r in m._load(tid)["records"] if r["type"]=="completion_prepared"]
  # AM7: preplanted archive symlink must fail before prepared receipt/source move.
  root=tmp/"escape"; m.REPO=root; m.INBOX=root/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  task=m.INBOX/"escape.md"; task.write_text("Role: reviewer\nOutput: .agents/plans/escape/antigravity.md\n"); out=root/".agents/plans/escape/antigravity.md"; out.parent.mkdir(parents=True); out.write_text("ok")
  assert m.main(["claim","escape.md","--actor","ide-watch","--json"])==0
  (root/".agent/archive").symlink_to(root/".agents")
  assert m.main(["complete",".claimed-escape","--output",".agents/plans/escape/antigravity.md","--json"])==1
  assert (m.INBOX/".claimed-escape").exists() and not [r for r in m._load("escape")["records"] if r["type"]=="completion_prepared"], "escape must not write prepared or consume marker"
  # Direct wake admits only the same bounded timeout envelope as dispatch.
  for timeout in (0,121): assert m.main(["wake",".claimed-escape","--timeout",str(timeout),"--json"])==1
  try: m.main(["wake","x.md","--actor","dispatch-once","--json"]); raise AssertionError("dispatch actor spoof accepted")
  except SystemExit as exc: assert exc.code == 2
  # Regression (Codex catch-up DEFECT[MEDIUM]): drain-verify is generation-aware and keys on the
  # canonical `completion` record type — a reused task-ID's prior-generation evidence must not mask a
  # fresh generation, and a mislabeled `complete` record must not count as drained.
  drn=tmp/"drain"; m.REPO=drn; m.INBOX=drn/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"dt.md").write_text("# task\nOutput: .agents/plans/dt/antigravity.md\n")
  genA=m._metadata(m._read_regular(m.INBOX/"dt.md"))[1]; old="2000-01-01T00:00:00+00:00"
  m._append("dt",{"type":"wake_attempt","task_id":"dt","generation":genA,"method":"cli-nudge-ok","ts":old})
  assert m._drain_status("dt",genA)[0]=="undrained-stale", "nudged + no completion past grace = undrained"
  m._append("dt",{"type":"complete","task_id":"dt","generation":genA,"ts":old})
  assert m._drain_status("dt",genA)[0]=="undrained-stale", "mislabeled `complete` must NOT count as drained"
  m._append("dt",{"type":"completion","task_id":"dt","generation":genA,"ts":old})
  assert m._drain_status("dt",genA)[0]=="drained", "canonical `completion` for this generation = drained"
  assert m._drain_status("dt","f"*64)[0]=="unnudged", "a different generation is NOT masked by genA evidence"
  # Regression: wake debounce prevents retrigger storms
  dbn=tmp/"debounce"; m.REPO=dbn; m.INBOX=dbn/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"db.md").write_text("# task\nRole: reviewer\nOutput: .agents/plans/db/antigravity.md\n")
  genDB=m._metadata(m._read_regular(m.INBOX/"db.md"))[1]
  now_iso=m._now()
  m._append("db",{"type":"wake_attempt","task_id":"db","generation":genDB,"method":"cli-nudge-ok","ts":now_iso})
  recs_before = len(m._load("db")["records"])
  assert m.main(["wake","db.md","--json"])==0
  assert len(m._load("db")["records"])==recs_before+1 and m._load("db")["records"][-1]["method"]=="skipped-recent-wake", "deduped wake must only record skipped-recent-wake"
  # Blocked tasks must not starve advisory work, and every accepted role is explicit.
  roles=tmp/"roles"; m.REPO=roles; m.INBOX=roles/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"a-edit.md").write_text("Role: implementer\nOutput: .agents/plans/a/antigravity.md\n")
  (m.INBOX/"b-missing.md").write_text("Output: .agents/plans/b/antigravity.md\n")
  (m.INBOX/"c-unknown.md").write_text("Role: unknown\nOutput: .agents/plans/c/antigravity.md\n")
  (m.INBOX/"d-review.md").write_text("Role: review\nOutput: .agents/plans/d/antigravity.md\n")
  status,next_task=invoke_json(["next","--json"])
  assert status==0 and next_task["basename"]=="d-review.md" and next_task["blocked_count"]==3
  status,state=invoke_json(["status","--json"])
  assert status==0 and state["blocked_count"]==3 and state["next"].endswith("d-review.md")
  old_wake=m._invoke_wake; m._invoke_wake=lambda timeout: ("cli-nudge-ok",0)
  try: status,dispatched=invoke_json(["dispatch-once","--json"])
  finally: m._invoke_wake=old_wake
  assert status==0 and dispatched["state"]=="woken" and dispatched["task_id"]=="d-review" and dispatched["blocked_count"]==3
  for p in (m.INBOX/"d-review.md",): p.unlink()
  status,blocked_only=invoke_json(["dispatch-once","--json"])
  assert status==1 and blocked_only["state"]=="blocked" and blocked_only["blocked_count"]==3
  # Pending parse/receipt failures are visible blockers, never a false empty inbox.
  malformed=tmp/"malformed"; m.REPO=malformed; m.INBOX=malformed/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"bad id.md").write_text("Role: reviewer\n")
  status,next_task=invoke_json(["next","--json"])
  assert status==1 and next_task["state"]=="blocked" and next_task["blocked"]==[{"task_id":"invalid-task-id","reason":"task requires exactly one Output: or output_file: metadata line"}]
  status,state=invoke_json(["status","--json"])
  assert status==0 and state["claim_required_count"]==1 and state["blocked_count"]==1
  status,blocked_only=invoke_json(["dispatch-once","--json"])
  assert status==1 and blocked_only["state"]=="blocked" and blocked_only["blocked_count"]==1
  invalid_utf8=tmp/"invalid-utf8"; m.REPO=invalid_utf8; m.INBOX=invalid_utf8/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"utf8.md").write_bytes(b"Role: reviewer\nOutput: .agents/plans/utf8/antigravity.md\n\xff")
  status,next_task=invoke_json(["next","--json"])
  assert status==1 and next_task["state"]=="blocked" and next_task["blocked"]==[{"task_id":"utf8","reason":"task metadata is not valid UTF-8"}]
  corrupt=tmp/"corrupt"; m.REPO=corrupt; m.INBOX=corrupt/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"corrupt.md").write_text("Role: reviewer\nOutput: .agents/plans/corrupt/antigravity.md\n")
  m._receipt_dir().mkdir(); m._receipt_path("corrupt").write_text("{")
  status,next_task=invoke_json(["next","--json"])
  assert status==1 and next_task["state"]=="blocked" and next_task["blocked_count"]==1 and next_task["blocked"][0]["task_id"]=="corrupt" and next_task["blocked"][0]["reason"].startswith("corrupt receipt:")
  status,blocked_only=invoke_json(["dispatch-once","--json"])
  assert status==1 and blocked_only["state"]=="blocked" and blocked_only["blocked_count"]==1
  mixed=tmp/"mixed"; m.REPO=mixed; m.INBOX=mixed/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"good.md").write_text("Role: reviewer\nOutput: .agents/plans/good/antigravity.md\n")
  (m.INBOX/"bad id.md").write_text("Role: reviewer\n")
  (m.INBOX/"corrupt.md").write_text("Role: reviewer\nOutput: .agents/plans/corrupt/antigravity.md\n")
  m._receipt_dir().mkdir(); m._receipt_path("corrupt").write_text("{")
  status,next_task=invoke_json(["next","--json"])
  assert status==0 and next_task["basename"]=="good.md" and next_task["blocked_count"]==2
  old_wake=m._invoke_wake; m._invoke_wake=lambda timeout: ("cli-nudge-ok",0)
  try: status,dispatched=invoke_json(["dispatch-once","--json"])
  finally: m._invoke_wake=old_wake
  assert status==0 and dispatched["state"]=="woken" and dispatched["task_id"]=="good" and dispatched["blocked_count"]==2
  for role in ("architect","full-expert-team","orchestrator","plan","research","reviewer"):
   m._require_advisory_ide_lane(f"Role: {role}\nOutput: .agents/plans/x/antigravity.md\n".encode())
  for role in ("", "unknown"):
   try: m._require_advisory_ide_lane(f"Role: {role}\nOutput: .agents/plans/x/antigravity.md\n".encode()); raise AssertionError("unrecognized role accepted")
   except m.InboxError: pass
 print("PASS: strict inbox regression")
if __name__=="__main__": main()
