#!/usr/bin/env python3
"""Hermetic adversarial checks for claim-bound Antigravity inbox receipts."""
from __future__ import annotations
import contextlib, importlib.machinery, importlib.util, io, json, os, tempfile, threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; SCRIPT=ROOT/"scripts/ai/aq-antigravity-inbox"
loader=importlib.machinery.SourceFileLoader("ag_receipt",str(SCRIPT)); m=importlib.util.module_from_spec(importlib.util.spec_from_loader("ag_receipt",loader)); loader.exec_module(m)
class Result:
 def __init__(self,rc=0): self.returncode=rc; self.stdout=""; self.stderr=""
def box(tmp:Path):
 m.REPO=tmp; m.INBOX=tmp/".agent/collaboration/antigravity-inbox"; m.STATE=m.INBOX/".lane-state.json"; m.INBOX.mkdir(parents=True)
def drop(name:str,out:str|None=None):
 body="# advisory\n"+(f"Output: {out}\n" if out else "")
 p=m.INBOX/f"{name}.md"; p.write_text(body); return p
def output(path:str):
 p=m.REPO/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text("result\n"); return p
def call(args): return m.main(args+["--json"])

def test_protocol_metadata_generation_and_completion():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/r/antigravity.md"; drop("r",declared); output(declared)
  assert call(["next"])==0
  assert call(["claim","r.md","--actor","ide-watch"])==0
  assert call(["complete",".claimed-r","--output",declared])==0
  rec=m._load("r")["records"]; assert rec[-1]["type"]=="completion" and rec[-1]["generation"]==rec[0]["generation"]
 print("PASS: metadata-bound claim and completion")

def test_fail_closed_stale_corrupt_and_recovery():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/x/antigravity.md"; drop("x",declared); output(declared)
  assert call(["complete","x.md","--output",declared])==1
  assert call(["claim","x.md","--actor","ide-watch"])==0
  (m.INBOX/".claimed-x").write_text("# replacement\nOutput: .agents/plans/x/antigravity.md\n")
  assert call(["complete",".claimed-x","--output",declared])==1, "generation replacement must fail"
  drop("bad",declared); (m._receipt_dir()).mkdir(exist_ok=True); m._receipt_path("bad").write_text("not json")
  assert call(["claim","bad.md","--actor","ide-watch"])==1 and m._receipt_path("bad").read_text()=="not json"
  drop("recover",declared)
  assert call(["complete","recover.md","--output",declared,"--recovery-allow-unclaimed","--recovery-allow-missing-output","--recovery-actor","owner-manual","--recovery-reason","owner repair"])==0
  assert m._load("recover")["records"][-1]["recovery"] is True
  missing=".agents/plans/missing/antigravity.md"; drop("missing",missing)
  assert call(["claim","missing.md","--actor","ide-watch"])==0
  assert call(["complete",".claimed-missing","--output",missing,"--recovery-allow-missing-output","--recovery-actor","owner-manual","--recovery-reason","missing artifact"])==0
  drop("unclaimed",declared)
  assert call(["complete","unclaimed.md","--output",declared,"--recovery-allow-unclaimed","--recovery-actor","owner-manual","--recovery-reason","owner archive"])==0
 print("PASS: stale/corrupt fail closed; owner recovery visible")

def test_lock_wake_and_dispatch():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); d1=".agents/plans/a/antigravity.md"; d2=".agents/plans/b/antigravity.md"; drop("a",d1); drop("b",d2)
  threads=[threading.Thread(target=m._append,args=("a",{"type":"test","generation":"g","n":i})) for i in range(16)]
  [t.start() for t in threads]; [t.join() for t in threads]; assert len(m._records("a","test","g"))==16
  calls=[]; old=m.subprocess.run
  m.subprocess.run=lambda argv,**kw:(calls.append(list(argv)) or Result(0))
  try:
   assert call(["dispatch-once","--attempt-ceiling","1","--retry-interval","1"])==0
   assert calls==[m.WAKE_ARGV]
   assert call(["dispatch-once","--attempt-ceiling","1","--retry-interval","1"])==0
   assert m._is_parked("a",m._metadata(m._read_regular(m.INBOX/"a.md"))[1])
   assert call(["dispatch-once","--attempt-ceiling","1","--retry-interval","1"])==0, "parked oldest must not starve b"
  finally: m.subprocess.run=old
 print("PASS: locked receipts, truthful fixed wake, park skip/no starvation")

def test_am3_reservation_concurrency_and_claim_during_provider():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/live/antigravity.md"; drop("live",declared)
  started=threading.Event(); release=threading.Event(); calls=[]; old=m.subprocess.run
  def provider(argv,**kw): calls.append(argv); started.set(); release.wait(2); return Result(0)
  m.subprocess.run=provider
  try:
   first=threading.Thread(target=lambda:m.main(["dispatch-once","--json"])); first.start(); assert started.wait(1)
   # Prior flagship failure: provider used to retain the supervisor lock and
   # block the IDE claim.  Claim must now complete while provider is waiting.
   assert call(["claim","live.md","--actor","ide-watch"])==0
   second=threading.Thread(target=lambda:m.main(["dispatch-once","--json"])); second.start(); second.join(1)
   release.set(); first.join(2)
   assert len(calls)==1, "two concurrent dispatchers must reserve exactly one wake"
   rec=m._load("live")["records"]; assert len([r for r in rec if r["type"]=="wake_reservation"])==1
   assert not [r for r in rec if r["type"]=="wake_attempt" and r.get("method")=="cli-nudge-ok"], "claim generation change must CAS-reject final"
  finally: m.subprocess.run=old
 print("PASS: reservation prevents double wake and provider never blocks claim")

def test_am4_stale_reservation_cas_becomes_typed_final_once():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/stale/antigravity.md"; drop("stale",declared); gen=m._metadata(m._read_regular(m.INBOX/"stale.md"))[1]
  m._append("stale",{"type":"wake_reservation","task_id":"stale","generation":gen,"ts":"2000-01-01T00:00:00+00:00","actor":"dispatch-once","nonce":"old"})
  old=m.subprocess.run; m.subprocess.run=lambda *a,**k:Result(0)
  try: assert call(["dispatch-once","--attempt-ceiling","3","--retry-interval","1"])==0
  finally: m.subprocess.run=old
  records=m._load("stale")["records"]; stale=[r for r in records if r.get("reservation")=="old"]
  assert len(stale)==1 and stale[0]["method"]=="reservation-stale", "stale reservation must finalize once before a fresh CAS wake"
 print("PASS: stale reservation becomes one typed final and fresh reservation proceeds")

def test_am5_generation_reuse_recovery_and_stale_budget():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/reuse/antigravity.md"; output(declared)
  drop("reuse",declared); assert call(["claim","reuse.md","--actor","ide-watch"])==0; assert call(["complete",".claimed-reuse","--output",declared])==0
  # Same task id, new bytes, same UTC day: the archive must not collide or
  # inherit the previous generation's prepared/completion evidence.
  (m.INBOX/"reuse.md").write_text("# new generation\nOutput: .agents/plans/reuse/antigravity.md\n")
  assert call(["claim","reuse.md","--actor","ide-watch"])==0; assert call(["complete",".claimed-reuse","--output",declared])==0
  archived=list((m.REPO/".agent/archive").rglob(".claimed-reuse-*")); assert len(archived)==2 and archived[0].name != archived[1].name
  # A self-consistent prepared record still has no authority without claim or
  # constrained owner recovery and must be rejected.
  drop("authority",declared); gen=m._metadata(m._read_regular(m.INBOX/"authority.md"))[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}/.claimed-authority-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True); os.link(m.INBOX/"authority.md",dest)
  m._append("authority",{"type":"completion_prepared","task_id":"authority","generation":gen,"declared_output":declared,"ts":m._now(),"archived_path":m._rel(dest),"output_path":declared,"output_hash":__import__("hashlib").sha256(m._read_regular(output(declared))).hexdigest(),"recovery":False})
  assert call(["complete",".claimed-authority","--output",declared])==1
  # Repeated stale reservations finalize once each and reach the bounded park.
  box(Path(td)/"park-case")
  drop("park",declared); gen=m._metadata(m._read_regular(m.INBOX/"park.md"))[1]
  for nonce in ("a","b"):
   m._append("park",{"type":"wake_reservation","task_id":"park","generation":gen,"ts":"2000-01-01T00:00:00+00:00","actor":"dispatch-once","nonce":nonce})
  old=m.subprocess.run; m.subprocess.run=lambda *a,**k:Result(0)
  try: assert call(["dispatch-once","--attempt-ceiling","2","--retry-interval","1"])==0; assert call(["dispatch-once","--attempt-ceiling","2","--retry-interval","1"])==0
  finally: m.subprocess.run=old
  assert m._is_parked("park",gen) and len(m._records("park","parked",gen))==1
 print("PASS: generation reuse, forged authority, and repeated stale budget")

def test_am5_midnight_and_recovery_crash_replay():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/recover/antigravity.md"; output(declared)
  # Prepared timestamp, not the current UTC date, determines the trusted archive directory.
  drop("midnight",declared); assert call(["claim","midnight.md","--actor","ide-watch"])==0; marker=m.INBOX/".claimed-midnight"; gen=m._metadata(m._read_regular(marker))[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-20000101/.claimed-midnight-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True); os.link(marker,dest)
  m._append("midnight",{"type":"completion_prepared","task_id":"midnight","generation":gen,"declared_output":declared,"source_name":marker.name,"ts":"2000-01-01T23:59:59+00:00","archived_path":m._rel(dest),"output_path":declared,"output_hash":__import__("hashlib").sha256(m._read_regular(output(declared))).hexdigest(),"recovery":False})
  assert call(["complete",".claimed-midnight","--output",declared])==0, "next-day reconcile must trust prepared UTC date"
  # Unclaimed owner-recovery crashes after prepared/link: retry finalizes the pending source.
  drop("uncrash",declared); source=m.INBOX/"uncrash.md"; gen=m._metadata(m._read_regular(source))[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}/uncrash.md-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True); os.link(source,dest)
  m._append("uncrash",{"type":"completion_prepared","task_id":"uncrash","generation":gen,"declared_output":declared,"source_name":source.name,"ts":m._now(),"archived_path":m._rel(dest),"output_path":declared,"output_hash":__import__("hashlib").sha256(m._read_regular(output(declared))).hexdigest(),"recovery":True,"recovery_actor":"owner-manual","recovery_reason":"owner repair","recovery_unclaimed":True,"recovery_missing_output":False})
  os.unlink(source)  # crash after archive link/unlink, before terminal receipt
  assert call(["complete","uncrash.md","--output",declared,"--recovery-allow-unclaimed","--recovery-actor","owner-manual","--recovery-reason","owner repair"])==0 and not source.exists()
  # Missing-output recovery retains a claimed source but finalizes without a hash.
  missing=".agents/plans/none/antigravity.md"; drop("mocrash",missing); assert call(["claim","mocrash.md","--actor","ide-watch"])==0; source=m.INBOX/".claimed-mocrash"; gen=m._metadata(m._read_regular(source))[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}/{source.name}-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True); os.link(source,dest)
  m._append("mocrash",{"type":"completion_prepared","task_id":"mocrash","generation":gen,"declared_output":missing,"source_name":source.name,"ts":m._now(),"archived_path":m._rel(dest),"recovery":True,"recovery_actor":"owner-manual","recovery_reason":"missing output","recovery_unclaimed":False,"recovery_missing_output":True})
  assert call(["complete",".claimed-mocrash","--output",missing,"--recovery-allow-missing-output","--recovery-actor","owner-manual","--recovery-reason","missing output"])==0 and not source.exists()
 print("PASS: UTC-midnight and both owner-recovery crash/replay paths")

def test_am3_completion_crash_reconcile_and_forgery():
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/crash/antigravity.md"; drop("crash",declared); output(declared); assert call(["claim","crash.md","--actor","ide-watch"])==0
  marker=m.INBOX/".claimed-crash"; raw=m._read_regular(marker); gen=m._metadata(raw)[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}/.claimed-crash-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True)
  prepared={"type":"completion_prepared","task_id":"crash","generation":gen,"declared_output":declared,"ts":m._now(),"archived_path":m._rel(dest),"output_path":declared,"output_hash":__import__("hashlib").sha256(m._read_regular(output(declared))).hexdigest(),"recovery":False}
  m._append("crash",prepared); os.link(marker,dest)  # crash after link, before unlink
  assert call(["complete",".claimed-crash","--output",declared])==0 and not marker.exists()
  # Crash after unlink, before terminal: a second task has archive only.
  drop("gone",declared); assert call(["claim","gone.md","--actor","ide-watch"])==0; marker=m.INBOX/".claimed-gone"; gen=m._metadata(m._read_regular(marker))[1]; dest=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}/.claimed-gone-{gen[:12]}"; dest.parent.mkdir(parents=True,exist_ok=True); os.link(marker,dest); os.unlink(marker)
  m._append("gone",{**prepared,"task_id":"gone","generation":gen,"archived_path":m._rel(dest)})
  assert call(["complete",".claimed-gone","--output",declared])==0
  drop("forged",declared); assert call(["claim","forged.md","--actor","ide-watch"])==0; gen=m._metadata(m._read_regular(m.INBOX/".claimed-forged"))[1]
  m._append("forged",{**prepared,"task_id":"forged","generation":gen,"archived_path":".agent/archive/antigravity-inbox-20000101/.claimed-forged","output_hash":"bad"})
  assert call(["complete",".claimed-forged","--output",declared])==1
 print("PASS: both completion crash windows reconcile; forged prepared is rejected")

def test_am3_metadata_output_json_and_symlink_preplants():
 corpus=ROOT/".agent/archive/antigravity-inbox-20260729/agent-model-config-parity-design-input.md"
 if corpus.exists():
  text=corpus.read_bytes(); path,_=m._metadata(text); assert path.startswith(".agents/")
 with tempfile.TemporaryDirectory() as td:
  box(Path(td)); declared=".agents/plans/sub/antigravity.md"; drop("sub",declared); output(declared); assert call(["claim","sub.md","--actor","ide-watch"])==0
  assert call(["complete",".claimed-sub","--output",".agents/plans/other/antigravity.md"])==1, "output substitution must fail"
  # The old CLI emitted a wake record and a dispatch result: assert one JSON object.
  drop("json",declared); old=m.subprocess.run; m.subprocess.run=lambda *a,**k:Result(0); stream=io.StringIO()
  try:
   with contextlib.redirect_stdout(stream): rc=m.main(["dispatch-once","--json"])
  finally: m.subprocess.run=old
  assert rc==0 and len(stream.getvalue().splitlines())==1 and json.loads(stream.getvalue())["state"] in {"woken","reserved"}
  m._receipt_dir().mkdir(exist_ok=True); m._task_lock("json").unlink(); (m._task_lock("json")).symlink_to(m.INBOX/"json.md")
  try: m._append("json",{"type":"x"}); raise AssertionError("lock symlink accepted")
  except m.InboxError: pass
  tmp=m._receipt_path("json").with_name(".json.json.tmp"); tmp.symlink_to(m.INBOX/"json.md")
  try: m._append("json",{"type":"x"}); raise AssertionError("tmp symlink accepted")
  except m.InboxError: pass
 print("PASS: production corpus, JSON, substitution, lock/tmp preplants")

def test_am7_archive_and_wake_failure_boundaries():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)
  # A parent and an exact-day archive symlink must both be rejected before a
  # prepared receipt is written or the claimed source is consumed.
  for kind in ("archive", "dated"):
   box(root/kind); declared=f".agents/plans/{kind}/antigravity.md"; drop("safe",declared); output(declared)
   assert call(["claim","safe.md","--actor","ide-watch"])==0
   marker=m.INBOX/".claimed-safe"; generation=m._metadata(m._read_regular(marker))[1]
   if kind == "archive":
    (m.REPO/".agent/archive").symlink_to(m.REPO/".agents")
   else:
    dated=m.REPO/f".agent/archive/antigravity-inbox-{m.datetime.now(m.timezone.utc):%Y%m%d}"; dated.parent.mkdir(parents=True,exist_ok=True); dated.symlink_to(m.REPO/".agents")
   assert call(["complete",".claimed-safe","--output",declared])==1
   assert marker.exists() and not m._records("safe","completion_prepared",generation)
  # A matching pre-existing archive is an idempotent crash-window completion:
  # it removes only the verified marker and then writes one terminal record.
  box(root/"identical"); declared=".agents/plans/identical/antigravity.md"; drop("same",declared); output(declared)
  assert call(["claim","same.md","--actor","ide-watch"])==0
  marker=m.INBOX/".claimed-same"; generation=m._metadata(m._read_regular(marker))[1]; dest=m._archive_destination(marker.name,generation,m.datetime.now(m.timezone.utc)); os.link(marker,dest)
  assert call(["complete",".claimed-same","--output",declared])==0
  records=m._load("same")["records"]
  assert not marker.exists() and len([r for r in records if r.get("type")=="completion_prepared" and r.get("generation")==generation])==1 and len([r for r in records if r.get("type")=="completion" and r.get("generation")==generation])==1
  # A missing-output recovery never implies unclaimed recovery.  A marker with
  # no attributable claim must fail before prepared evidence or source change.
  box(root/"missing-claim"); declared=".agents/plans/no-claim/antigravity.md"; drop("orphan",declared); source=m.INBOX/"orphan.md"; marker=m.INBOX/".claimed-orphan"; os.rename(source,marker); generation=m._metadata(m._read_regular(marker))[1]
  assert call(["complete",".claimed-orphan","--output",declared,"--recovery-allow-missing-output","--recovery-actor","owner-manual","--recovery-reason","missing artifact"])==1
  assert marker.exists() and not m._records("orphan","completion_prepared",generation)
  # Provider failures have the same one-JSON, nonzero semantics for direct
  # wake and dispatch.  Dispatch exposes the provider exit code as well.
  cases=[("nonzero",lambda _argv,_kw:Result(7),"cli-nudge-nonzero",7),("timeout",lambda argv,kw:(_ for _ in ()).throw(m.subprocess.TimeoutExpired(argv,kw["timeout"])),"cli-nudge-timeout",None),("missing",lambda _argv,_kw:(_ for _ in ()).throw(FileNotFoundError()),"cli-nudge-binary-missing",None)]
  old=m.subprocess.run
  try:
   for name,provider,method,exit_code in cases:
    box(root/f"wake-{name}"); declared=f".agents/plans/wake-{name}/antigravity.md"; drop("wake",declared)
    m.subprocess.run=lambda argv,**kw:provider(argv,kw); stream=io.StringIO()
    with contextlib.redirect_stdout(stream): rc=m.main(["wake","wake.md","--json"])
    lines=stream.getvalue().splitlines(); payload=json.loads(lines[0]); assert rc==1 and len(lines)==1 and payload=={"ok":False,"task_id":"wake","method":method,"exit_code":exit_code}
    box(root/f"dispatch-{name}"); declared=f".agents/plans/dispatch-{name}/antigravity.md"; drop("dispatch",declared)
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream): rc=m.main(["dispatch-once","--json"])
    lines=stream.getvalue().splitlines(); payload=json.loads(lines[0]); assert rc==1 and len(lines)==1 and payload=={"ok":False,"state":"wake-failed","task_id":"dispatch","method":method,"exit_code":exit_code}
  finally: m.subprocess.run=old
 print("PASS: AM7 archive safety, terminal idempotence, and provider failure semantics")

def main():
 assert "claim <basename>" in m.WAKE_PROMPT and "complete .claimed-<task-id>" in m.WAKE_PROMPT
 test_protocol_metadata_generation_and_completion(); test_fail_closed_stale_corrupt_and_recovery(); test_lock_wake_and_dispatch(); test_am3_reservation_concurrency_and_claim_during_provider(); test_am4_stale_reservation_cas_becomes_typed_final_once(); test_am5_generation_reuse_recovery_and_stale_budget(); test_am5_midnight_and_recovery_crash_replay(); test_am3_completion_crash_reconcile_and_forgery(); test_am3_metadata_output_json_and_symlink_preplants(); test_am7_archive_and_wake_failure_boundaries(); print("ALL PASS: claim receipt")
if __name__=="__main__": main()
