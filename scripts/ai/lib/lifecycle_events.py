"""Typed lifecycle event adapter (ECC parity P0-C).

Stdlib-only. Handlers are explicitly registered argv commands run as child
processes with a minimal explicit environment, a timeout and crash isolation.
No root search, no plugin discovery, no network, no inherited environment.
Ships dormant: nothing registers a production handler.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import deque
from pathlib import Path

EVENTS = ("pre", "post", "failure", "compact", "stop")
CLASSIFICATIONS = ("public", "internal", "sensitive")
FAIL_POLICIES = ("open", "closed")
OUTCOMES = ("ok", "handler_error", "timeout", "missing_tool", "disabled",
            "no_handler", "suppressed", "budget_exhausted", "lease_missing")
FIELDS = ("source", "target", "event", "payload_classification", "capability_lease",
          "timeout_s", "fail_policy", "loop_budget", "outcome", "evidence_id", "payload")

MAX_PAYLOAD_BYTES = 65_536
MAX_OUTPUT_BYTES = 65_536
MAX_STATE_BYTES = 1_048_576
MAX_TIMEOUT_S = 60.0
MAX_LOOP_BUDGET = 8
MINIMAL_PATH = "/run/current-system/sw/bin:/usr/bin:/bin"

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_LEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ENV_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class EventRejected(ValueError):
    """Stable, non-content-bearing rejection code in args[0]."""


def _reject(code: str) -> "EventRejected":
    return EventRejected(code)


def _name(value: object, code: str) -> str:
    if not isinstance(value, str) or not _NAME.match(value):
        raise _reject(code)
    return value


def validate_event(raw: object, *, require_lease: bool = False) -> dict:
    """Return a normalized event or raise EventRejected(<code>)."""
    if not isinstance(raw, dict):
        raise _reject("not_object")
    if set(raw) - set(FIELDS):
        raise _reject("unknown_field")
    ev = {
        "source": _name(raw.get("source"), "bad_source"),
        "target": _name(raw.get("target"), "bad_target"),
        "event": raw.get("event"),
        "payload_classification": raw.get("payload_classification", "internal"),
        "capability_lease": raw.get("capability_lease", ""),
        "timeout_s": raw.get("timeout_s", 5.0),
        "fail_policy": raw.get("fail_policy", "closed"),
        "loop_budget": raw.get("loop_budget", 2),
        "outcome": raw.get("outcome", "pending"),
        "evidence_id": raw.get("evidence_id", ""),
        "payload": raw.get("payload", {}),
    }
    if ev["event"] not in EVENTS:
        raise _reject("bad_event")
    if ev["payload_classification"] not in CLASSIFICATIONS:
        raise _reject("bad_classification")
    if ev["fail_policy"] not in FAIL_POLICIES:
        raise _reject("bad_fail_policy")
    lease = ev["capability_lease"]
    if not isinstance(lease, str) or (lease and not _LEASE.match(lease)):
        raise _reject("bad_lease")
    if require_lease and not lease:
        raise _reject("lease_required")
    t = ev["timeout_s"]
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 < t <= MAX_TIMEOUT_S:
        raise _reject("bad_timeout")
    b = ev["loop_budget"]
    if isinstance(b, bool) or not isinstance(b, int) or not 0 <= b <= MAX_LOOP_BUDGET:
        raise _reject("bad_loop_budget")
    if not isinstance(ev["outcome"], str) or len(ev["outcome"]) > 32:
        raise _reject("bad_outcome")
    eid = ev["evidence_id"]
    if not isinstance(eid, str) or (eid and not _NAME.match(eid)):
        raise _reject("bad_evidence_id")
    payload = ev["payload"]
    if not isinstance(payload, dict):
        raise _reject("bad_payload")
    try:
        encoded = json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError):
        raise _reject("bad_payload") from None
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise _reject("payload_too_large")
    if not eid:
        digest = hashlib.sha256(json.dumps(
            {k: ev[k] for k in ("source", "target", "event")} | {"p": encoded},
            sort_keys=True).encode()).hexdigest()[:16]
        ev["evidence_id"] = f"lce-{digest}"
    return ev


class Handler:
    def __init__(self, name, argv, events, *, timeout_s=5.0, fail_policy="closed",
                 env=None, require_lease=False):
        self.name = _name(name, "bad_handler_name")
        if (not isinstance(argv, (list, tuple)) or not argv
                or not all(isinstance(a, str) and a for a in argv)):
            raise _reject("bad_argv")
        self.argv = list(argv)
        events = tuple(events)
        if not events or any(e not in EVENTS for e in events):
            raise _reject("bad_event")
        self.events = events
        if not 0 < float(timeout_s) <= MAX_TIMEOUT_S:
            raise _reject("bad_timeout")
        self.timeout_s = float(timeout_s)
        if fail_policy not in FAIL_POLICIES:
            raise _reject("bad_fail_policy")
        self.fail_policy = fail_policy
        env = dict(env or {})
        if any(not _ENV_KEY.match(k) or not isinstance(v, str) for k, v in env.items()):
            raise _reject("bad_env")
        self.env = env
        self.require_lease = bool(require_lease)

    def resolve(self) -> str | None:
        exe = self.argv[0]
        if os.path.isabs(exe):
            return exe if os.access(exe, os.X_OK) and os.path.isfile(exe) else None
        return shutil.which(exe, path=MINIMAL_PATH)

    def child_env(self, event: dict) -> dict:
        env = {"PATH": MINIMAL_PATH, "LANG": "C", "LIFECYCLE_EVENT": event["event"],
               "LIFECYCLE_EVIDENCE_ID": event["evidence_id"]}
        env.update(self.env)
        return env


def _blank_stats() -> dict:
    return {"count": 0, "failures": 0, "timeouts": 0, "missing_tool": 0,
            "latency_total_ms": 0.0, "latency_max_ms": 0.0, "latency_last_ms": 0.0}


class LifecycleRunner:
    def __init__(self, *, max_queue=64):
        self.max_queue = int(max_queue)
        self.handlers: dict[str, Handler] = {}
        self.disabled: set[str] = set()
        self.queue: deque = deque()
        self.stats: dict[str, dict] = {}
        self.totals = {"rejected": 0, "recursion_suppressed": 0, "backpressure_dropped": 0,
                       "budget_exhausted": 0, "cancelled": 0, "emitted": 0}

    # -- registry -------------------------------------------------------
    def register(self, handler: Handler) -> None:
        if handler.name in self.handlers:
            raise _reject("duplicate_handler")
        self.handlers[handler.name] = handler
        self.stats.setdefault(handler.name, _blank_stats())

    def disable(self, name: str) -> None:
        self.disabled.add(name)

    def enable(self, name: str) -> None:
        self.disabled.discard(name)

    # -- queue ----------------------------------------------------------
    def emit(self, raw: object) -> str:
        """Validate and enqueue. Returns 'queued', or a drop reason."""
        try:
            ev = validate_event(raw)
        except EventRejected:
            self.totals["rejected"] += 1
            return "rejected"
        if len(self.queue) >= self.max_queue:
            self.totals["backpressure_dropped"] += 1
            return "backpressure"
        self.queue.append(ev)
        self.totals["emitted"] += 1
        return "queued"

    def cancel(self) -> int:
        n = len(self.queue)
        self.queue.clear()
        self.totals["cancelled"] += n
        return n

    def drain(self) -> list[dict]:
        results = []
        while self.queue:
            results.append(self._dispatch(self.queue.popleft()))
        return results

    # -- dispatch -------------------------------------------------------
    def _dispatch(self, ev: dict) -> dict:
        matching = [h for h in self.handlers.values() if ev["event"] in h.events]
        res = {"evidence_id": ev["evidence_id"], "event": ev["event"], "decision": "allow",
               "outcome": "no_handler", "handlers": []}
        for h in matching:
            r = self._run_one(h, ev)
            res["handlers"].append(r)
            if r["decision"] == "deny":
                res["decision"] = "deny"
        if res["handlers"]:
            bad = [r["outcome"] for r in res["handlers"] if r["outcome"] != "ok"]
            res["outcome"] = bad[0] if bad else "ok"
        return res

    def _run_one(self, h: Handler, ev: dict) -> dict:
        r = {"handler": h.name, "outcome": "ok", "decision": "allow", "latency_ms": 0.0}
        st = self.stats[h.name]

        def fail(outcome):
            r["outcome"] = outcome
            r["decision"] = "allow" if h.fail_policy == "open" else "deny"

        if h.name in self.disabled:
            r["outcome"] = "disabled"
            return r
        if h.require_lease and not ev["capability_lease"]:
            fail("lease_missing")
            st["failures"] += 1
            return r
        st["count"] += 1
        exe = h.resolve()
        if exe is None:
            st["missing_tool"] += 1
            st["failures"] += 1
            fail("missing_tool")
            return r
        timeout = min(h.timeout_s, float(ev["timeout_s"]))
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [exe, *h.argv[1:]], input=json.dumps(ev), capture_output=True, text=True,
                timeout=timeout, env=h.child_env(ev), cwd="/", check=False)
            out, rc = proc.stdout, proc.returncode
        except subprocess.TimeoutExpired:
            out, rc = "", None
            st["timeouts"] += 1
        except (OSError, ValueError):
            out, rc = "", -1
        ms = (time.monotonic() - started) * 1000.0
        r["latency_ms"] = round(ms, 2)
        st["latency_total_ms"] += ms
        st["latency_last_ms"] = ms
        st["latency_max_ms"] = max(st["latency_max_ms"], ms)
        if rc is None:
            st["failures"] += 1
            fail("timeout")
            return r
        if rc != 0:
            st["failures"] += 1
            fail("handler_error")
            return r
        self._ingest_emitted(out[:MAX_OUTPUT_BYTES], ev, r)
        return r

    def _ingest_emitted(self, out: str, parent: dict, r: dict) -> None:
        """Handler stdout lines that are JSON objects are follow-up events."""
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                child = json.loads(line)
            except ValueError:
                continue
            if isinstance(child, dict) and child.get("event") == parent["event"]:
                self.totals["recursion_suppressed"] += 1
                r["outcome"] = "ok"
                continue
            if parent["loop_budget"] <= 0:
                self.totals["budget_exhausted"] += 1
                continue
            if isinstance(child, dict):
                child = dict(child)
                child["loop_budget"] = parent["loop_budget"] - 1
                self.emit(child)

    # -- telemetry / state ----------------------------------------------
    def telemetry(self) -> dict:
        handlers = {}
        for name in self.handlers:
            s = self.stats[name]
            handlers[name] = {
                **{k: s[k] for k in ("count", "failures", "timeouts", "missing_tool")},
                "latency_avg_ms": round(s["latency_total_ms"] / s["count"], 2) if s["count"] else 0.0,
                "latency_max_ms": round(s["latency_max_ms"], 2),
                "disabled": name in self.disabled,
            }
        return {"handlers": handlers, "disabled": sorted(self.disabled),
                "queue_depth": len(self.queue), "totals": dict(self.totals)}

    def snapshot(self) -> dict:
        return {"version": 1, "queue": list(self.queue), "disabled": sorted(self.disabled),
                "stats": self.stats, "totals": self.totals}

    def restore(self, snap: object) -> int:
        """Restore queue/counters; re-validates every event. Returns events restored."""
        if not isinstance(snap, dict) or snap.get("version") != 1:
            raise _reject("bad_snapshot")
        queue = deque()
        dropped = 0
        for raw in snap.get("queue", []):
            try:
                queue.append(validate_event(raw))
            except EventRejected:
                dropped += 1
        self.queue = queue
        self.disabled = {d for d in snap.get("disabled", []) if isinstance(d, str)}
        for name, s in (snap.get("stats") or {}).items():
            if name in self.stats and isinstance(s, dict):
                for k in self.stats[name]:
                    if isinstance(s.get(k), (int, float)):
                        self.stats[name][k] = s[k]
        for k in self.totals:
            v = (snap.get("totals") or {}).get(k)
            if isinstance(v, int):
                self.totals[k] = v
        self.totals["rejected"] += dropped
        return len(queue)

    def save_state(self, path: str | os.PathLike) -> None:
        path = Path(path)
        data = {"snapshot": self.snapshot(), "telemetry": self.telemetry(),
                "saved_at": time.time()}
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".lce-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def load_state(self, path: str | os.PathLike) -> int:
        raw = Path(path).read_bytes()[:MAX_STATE_BYTES + 1]
        if len(raw) > MAX_STATE_BYTES:
            raise _reject("state_too_large")
        return self.restore(json.loads(raw).get("snapshot"))


def health_summary(state_path: str | os.PathLike | None = None) -> dict:
    """Read-only, bounded, metadata-only projection for the dashboard."""
    base = {"available": True, "status": "dormant", "handlers_registered": 0,
            "disabled": [], "queue_depth": 0, "calls": 0, "failures": 0,
            "latency_avg_ms": 0.0, "latency_max_ms": 0.0,
            "recursion_suppressed": 0, "rejected": 0, "evidence_scope": "metadata-only"}
    if not state_path:
        return base
    try:
        p = Path(state_path)
        if not p.is_file():
            return base
        raw = p.read_bytes()[:MAX_STATE_BYTES + 1]
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("too_large")
        tel = json.loads(raw)["telemetry"]
        hs = tel["handlers"]
        calls = sum(int(h["count"]) for h in hs.values())
        fails = sum(int(h["failures"]) for h in hs.values())
        total_ms = sum(float(h["latency_avg_ms"]) * int(h["count"]) for h in hs.values())
        base.update(
            handlers_registered=len(hs), disabled=[str(d) for d in tel["disabled"]][:64],
            queue_depth=int(tel["queue_depth"]), calls=calls, failures=fails,
            latency_avg_ms=round(total_ms / calls, 2) if calls else 0.0,
            latency_max_ms=max([float(h["latency_max_ms"]) for h in hs.values()] or [0.0]),
            recursion_suppressed=int(tel["totals"]["recursion_suppressed"]),
            rejected=int(tel["totals"]["rejected"]),
            status="degraded" if fails or tel["disabled"] else ("healthy" if hs else "dormant"))
    except (OSError, ValueError, KeyError, TypeError):
        return {**base, "status": "unverified", "reason": "state_invalid_or_unavailable"}
    return base
