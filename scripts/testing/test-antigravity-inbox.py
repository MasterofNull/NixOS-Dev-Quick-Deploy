#!/usr/bin/env python3
"""Regression checks for strict inbox selection and unsafe members."""
from __future__ import annotations
import importlib.machinery, importlib.util, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; SCRIPT=ROOT/"scripts/ai/aq-antigravity-inbox"; loader=importlib.machinery.SourceFileLoader("ag_inbox",str(SCRIPT)); m=importlib.util.module_from_spec(importlib.util.spec_from_loader("ag_inbox",loader)); loader.exec_module(m)
def main():
 assert SCRIPT.stat().st_mode & 0o111, "installed CLI source must remain executable"
 with tempfile.TemporaryDirectory() as td:
  tmp=Path(td); m.REPO=tmp; m.INBOX=tmp/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"good.md").write_text("# task\nRespond by writing only:\n`.agents/plans/good/antigravity.md`\n")
  assert m.main(["next","--json"])==0
  assert m.main(["claim","../good.md","--actor","ide-watch","--json"])==1
  (m.INBOX/"link.md").symlink_to(m.INBOX/"good.md")
  assert m.main(["claim","link.md","--actor","ide-watch","--json"])==1
  assert m.main(["dispatch-once","--attempt-ceiling","0","--json"])==2
  m._receipt_dir().mkdir(exist_ok=True); (m._receipt_path("good")).symlink_to(m.INBOX/"good.md")
  assert m.main(["claim","good.md","--actor","ide-watch","--json"])==1, "receipt symlink must fail closed"
  other=tmp/"second"; m.REPO=other; m.INBOX=other/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  (m.INBOX/"stamp.md").write_text("# task\nOutput: .agents/plans/stamp/antigravity.md\n")
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
  # AM7: preplanted archive symlink must fail before prepared receipt/source move.
  root=tmp/"escape"; m.REPO=root; m.INBOX=root/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
  task=m.INBOX/"escape.md"; task.write_text("Output: .agents/plans/escape/antigravity.md\n"); out=root/".agents/plans/escape/antigravity.md"; out.parent.mkdir(parents=True); out.write_text("ok")
  assert m.main(["claim","escape.md","--actor","ide-watch","--json"])==0
  (root/".agent/archive").symlink_to(root/".agents")
  assert m.main(["complete",".claimed-escape","--output",".agents/plans/escape/antigravity.md","--json"])==1
  assert (m.INBOX/".claimed-escape").exists() and not [r for r in m._load("escape")["records"] if r["type"]=="completion_prepared"], "escape must not write prepared or consume marker"
  # Direct wake admits only the same bounded timeout envelope as dispatch.
  for timeout in (0,121): assert m.main(["wake",".claimed-escape","--timeout",str(timeout),"--json"])==1
  try: m.main(["wake","x.md","--actor","dispatch-once","--json"]); raise AssertionError("dispatch actor spoof accepted")
  except SystemExit as exc: assert exc.code == 2
 print("PASS: strict inbox regression")
if __name__=="__main__": main()
