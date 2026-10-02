"""Approval inbox: one numbered list over the PRSI queue, RSI ledger and attention queue.

State stays in the canonical files; this module only reads them, delegates
decisions to their owners (prsi-orchestrator / attention_queue) and keeps a
dismissed record + audit log. Dismiss hides an item; it never resolves it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _queue_path() -> Path:
    return Path(os.getenv("PRSI_ACTION_QUEUE_PATH", "/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json"))


def _incidents_path() -> Path:
    return Path(os.getenv("PRSI_INCIDENTS_FILE", str(REPO_ROOT / ".agent" / "collaboration" / "rsi-incidents.json")))


def _inbox_dir() -> Path:
    return Path(os.getenv("AQ_APPROVAL_INBOX_DIR", "/var/lib/nixos-ai-stack/optimizer/prsi"))


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def load_dismissed() -> dict:
    d = _load_json(_inbox_dir() / "approval-inbox.json", {})
    dis = d.get("dismissed") if isinstance(d, dict) else None
    return dis if isinstance(dis, dict) else {}


def _save_dismissed(dismissed: dict) -> None:
    d = _inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".approval-inbox.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"dismissed": dismissed}, fh, sort_keys=True, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, d / "approval-inbox.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(action: str, key: str, door: str, note: str, tag: str, ok: bool = True, msg: str = "") -> None:
    d = _inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _now(), "action": action, "key": key, "by": "owner", "door": door,
           "note": note, "tag": tag, "ok": ok}
    if msg:
        rec["msg"] = msg[:300]
    with (d / "approval-inbox-audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _trunc(s: str, n: int = 100) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _sort(items: list) -> list:
    return sorted(items, key=lambda i: (_SEV.get(i["severity"], 9), i["key"]))


def _attention_pending() -> list:
    try:
        import attention_queue  # honors ATTENTION_QUEUE_DIR at import time
        return attention_queue.get_pending()
    except Exception:  # noqa: BLE001 — inbox must render without the attention store
        return []


def collect() -> list:
    dismissed = load_dismissed()
    incidents = (_load_json(_incidents_path(), {}) or {}).get("incidents", {})
    if not isinstance(incidents, dict):
        incidents = {}
    queue = _load_json(_queue_path(), {})
    rows = queue.get("actions", []) if isinstance(queue, dict) else []

    approval, represented = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("raw_action") if isinstance(row.get("raw_action"), dict) else {}
        rid = str(row.get("id", ""))
        if not rid:
            continue
        ap = row.get("approval") if isinstance(row.get("approval"), dict) else {}
        status = row.get("status", "")
        if raw.get("source") == "rsi-incidents.json":
            iid = str(raw.get("incident_id", ""))
            # Any queued RSI row means the incident is in the repair pipeline,
            # not deferred — including rows the owner already signed off.
            represented.add(iid)
            if status not in ("rsi_pending", "rsi_failed") or row.get("risk") != "high" or ap.get("verifier_by"):
                continue
            inc = incidents.get(iid, {}) if isinstance(incidents.get(iid), dict) else {}
            detail = inc.get("error") or row.get("reason") or ""
            title = "RSI repair needs sign-off: " + (inc.get("error") or inc.get("path") or raw.get("incident_path") or rid)
            sev = inc.get("severity") or raw.get("incident_severity") or "high"
            approval.append({"key": f"prsi:{rid}", "section": "approval", "title": _trunc(title),
                             "severity": sev, "source": "rsi-queue", "detail": str(detail),
                             "action": f"aq-approve approve <n> --tag <tag>", "kind": "prsi-rsi",
                             "ref": rid, "incident_id": iid})
        elif status == "pending_approval":
            approval.append({"key": f"prsi:{rid}", "section": "approval",
                             "title": _trunc(f"Approve action: {row.get('action', rid)}"),
                             "severity": row.get("risk") or "medium", "source": "prsi-queue",
                             "detail": str(row.get("reason") or ""), "action": "aq-approve approve <n> --tag <tag>",
                             "kind": "prsi-plain", "ref": rid, "incident_id": ""})

    deferred = []
    for al in _attention_pending():
        aid = str(al.get("id", ""))
        if not aid:
            continue
        sec = "approval" if al.get("executor") else "deferred"
        it = {"key": f"attn:{aid}", "section": sec, "title": _trunc(al.get("title", aid)),
              "severity": al.get("severity") or "medium", "source": f"attention/{al.get('source', '?')}",
              "detail": str(al.get("detail") or ""), "action": str(al.get("proposed_action") or ""),
              "kind": "attn", "ref": aid, "incident_id": ""}
        (approval if sec == "approval" else deferred).append(it)

    for iid, inc in incidents.items():
        if not isinstance(inc, dict) or inc.get("status") != "open" or iid in represented:
            continue
        deferred.append({"key": f"rsi:{iid}", "section": "deferred",
                         "title": _trunc(inc.get("error") or inc.get("path") or iid),
                         "severity": inc.get("severity") or "medium",
                         "source": f"rsi/{inc.get('agent', '?')}", "detail": str(inc.get("error") or ""),
                         "action": str(inc.get("root_fix") or ""), "kind": "rsi", "ref": iid, "incident_id": iid})

    items = _sort(approval) + _sort(deferred)
    return [i for i in items if i["key"] not in dismissed]


def snapshot_tag(items: list) -> str:
    return hashlib.sha256("\n".join(i["key"] + "|" + i["section"] for i in items).encode()).hexdigest()[:8]


def _orch(*args: str) -> tuple:
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "automation" / "prsi-orchestrator.py"), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())[-300:]


def approve(item: dict, note: str = "", alert_fn=None) -> tuple:
    if item["section"] != "approval":
        return False, "deferred items can be dismissed or promoted by fixing them; nothing to approve"
    if item["kind"] == "prsi-rsi":
        return _orch("verify", "--id", item["ref"], "--by", "owner", "--note", note)
    if item["kind"] == "prsi-plain":
        return _orch("approve", "--id", item["ref"], "--by", "owner", "--note", note)
    if item["kind"] == "attn":
        if alert_fn is None:
            return False, "no alert handler"
        rc = alert_fn(item["ref"], "owner")
        return rc == 0, f"aq-approve alert path rc={rc}"
    return False, "unknown item kind"


def deny(item: dict, note: str = "") -> tuple:
    if item["section"] != "approval":
        return False, "deferred items can be dismissed; nothing to deny"
    if item["kind"] in ("prsi-rsi", "prsi-plain"):
        return _orch("reject", "--id", item["ref"], "--by", "owner", "--note", note)
    if item["kind"] == "attn":
        import attention_queue
        ok = attention_queue.resolve(item["ref"], "rejected", resolved_by="owner")
        return ok, "rejected" if ok else "alert not pending"
    return False, "unknown item kind"


def dismiss(item: dict, door: str = "terminal", note: str = "") -> tuple:
    dismissed = load_dismissed()
    dismissed[item["key"]] = {"at": _now(), "by": "owner", "door": door, "note": note}
    _save_dismissed(dismissed)
    return True, "dismissed (hidden from inbox; underlying item unchanged)"


# ── CLI ──────────────────────────────────────────────────────────────────────

def format_list(items: list, tag: str) -> list:
    appr = [i for i in items if i["section"] == "approval"]
    dfr = [i for i in items if i["section"] == "deferred"]
    out = [f"Approval inbox [tag {tag}]", f"Needs approval ({len(appr)})"]
    n = 0
    for i in appr:
        n += 1
        out.append(f"  {n}. [{i['severity']}] {i['title']} — {i['source']}")
    out.append(f"Deferred ({len(dfr)})")
    for i in dfr:
        n += 1
        out.append(f"  {n}. [{i['severity']}] {i['title']} — {i['source']}")
    out.append(f'Say "approve 1 3" / "deny 2" / "dismiss 4" in chat, or run aq-approve approve 1 3 --tag {tag}.')
    return out


def summary_line(items: list) -> str:
    if not items:
        return "Approval inbox: empty"
    a = sum(1 for i in items if i["section"] == "approval")
    return f"Approval inbox: {a} need approval, {len(items) - a} deferred (aq-approve)"


def inbox_cli(argv: list, approve_alert, resolve_actor) -> int:
    import argparse
    legacy = bool(argv) and (argv[0] in ("-h", "--help") or argv[0].startswith("attn-") or argv[0] == "--actor")
    if legacy:
        label = ""
        if "--actor" in argv:
            i = argv.index("--actor")
            if i + 1 >= len(argv):
                print("--actor requires a value", file=sys.stderr)
                return 1
            label = argv[i + 1][:64]
            del argv[i:i + 2]
        if not argv or argv[0] in ("-h", "--help"):
            print("Usage: aq-approve [--actor LABEL] <alert-id>\n"
                  "       aq-approve [list] [--json|--summary]\n"
                  "       aq-approve approve|deny|dismiss N [N...] --tag TAG [--door chat|terminal|dashboard] [--note TEXT]")
            return 1
        return approve_alert(argv[0], resolve_actor(label))

    ap = argparse.ArgumentParser(prog="aq-approve")
    ap.add_argument("cmd", nargs="?", default="list", choices=["list", "approve", "deny", "dismiss"])
    ap.add_argument("nums", nargs="*", type=int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--door", default="terminal", choices=["chat", "terminal", "dashboard"])
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)

    items = collect()
    tag = snapshot_tag(items)
    if args.cmd == "list":
        if args.summary:
            print(summary_line(items))
        elif args.json:
            print(json.dumps({"tag": tag, "items": [
                {"n": n, **{k: i[k] for k in ("key", "section", "title", "severity", "source", "detail")}}
                for n, i in enumerate(items, 1)]}, sort_keys=True))
        else:
            print("\n".join(format_list(items, tag)))
        return 0

    if not args.nums:
        print(f"aq-approve {args.cmd}: give item number(s)", file=sys.stderr)
        return 2
    if args.tag != tag:
        print(f"Inbox changed since tag {args.tag or '(none)'}; current list:")
        print("\n".join(format_list(items, tag)))
        return 3
    rc = 0
    for n in args.nums:
        if not 1 <= n <= len(items):
            print(f"  {n}: no such item", file=sys.stderr)
            rc = 2
            continue
        it = items[n - 1]
        if args.cmd == "approve":
            ok, msg = approve(it, args.note, lambda aid, _a: approve_alert(aid, resolve_actor("owner")))
        elif args.cmd == "deny":
            ok, msg = deny(it, args.note)
        else:
            ok, msg = dismiss(it, args.door, args.note)
        audit(args.cmd, it["key"], args.door, args.note, tag, ok, msg)
        print(f"  {n}. {args.cmd} {'OK' if ok else 'FAILED'}: {it['title']} — {msg}")
        if not ok:
            rc = rc or (2 if it["section"] == "deferred" else 1)
    return rc
