#!/usr/bin/env python3
"""aq-prm-eval process-lifecycle tests (fake delegate, no inference, no real eval)."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent / "ai" / "aq-prm-eval"
loader = importlib.machinery.SourceFileLoader("aq_prm_eval", str(EVAL))
m = importlib.util.module_from_spec(importlib.util.spec_from_loader("aq_prm_eval", loader))
loader.exec_module(m)

FAKE = r'''#!/usr/bin/env bash
# Fake delegate-to-local: mimics a detached (setsid) agent registered in AQ_DELEGATION_DIR.
f=$(printf '%s' "$*" | grep -o '/[^ ]*\.py' | head -1)
echo "$AQ_AGENT_WALL_BUDGET_S" > "$AQ_DELEGATION_DIR/budget.txt"
if [[ "$FAKE_MODE" == fast ]]; then
  printf '%s' "$FAKE_REF" > "$f"
  echo '{"event_type":"agent_tool_call"}' >> "$AQ_AGENT_RUN_EVENTS_PATH"
  echo '{"event_type":"agent_complete","result_preview":"completed: fixed"}' >> "$AQ_AGENT_RUN_EVENTS_PATH"
  exit 0
fi
setsid sleep 300 &
echo "{\"id\":\"t$$\",\"pid\":$!,\"status\":\"running\"}" >> "$AQ_DELEGATION_DIR/registry.jsonl"
[[ "$FAKE_MODE" == hang ]] && sleep 300
exit 0
'''

fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


def alive(pid):
    return m._pid_alive(pid)


def registry_pids(d):
    return [json.loads(l)["pid"] for l in (d / "registry.jsonl").read_text().splitlines()]


def main():
    with tempfile.TemporaryDirectory(prefix="prm-eval-test-") as td:
        td = Path(td)
        fake = td / "fake-delegate"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        m.DELEGATE = fake
        m.GRACE_S = 0
        task = m.build_fixture(td / "fx")[0]
        os.environ["FAKE_REF"] = task["ref"]
        state = td / "state"
        state.mkdir()
        deleg = state / "deleg"

        # 1. timeout kills wrapper group AND the detached child; pass checked after cleanup
        order = []
        real_passes = m.passes
        m.passes = lambda t: (order.append(("passes", [alive(p) for p in registry_pids(deleg)])), real_passes(t))[1]
        os.environ["FAKE_MODE"] = "hang"
        r = m.run_arm(task, True, 1, state)
        pids = registry_pids(deleg)
        check("timeout: child pid gone", pids and not any(alive(p) for p in pids))
        check("timeout: timed_out recorded", r["timed_out"] is True and r["delegate_rc"] == -1)
        check("timeout: passes() ran only after cleanup", order and not any(order[0][1]))
        check("timeout: not completed_cleanly", r["completed_cleanly"] is False and r["cleanup_confirmed"])
        check("timeout: stray agent reaped", r["stray_agents_killed"] >= 1)
        m.passes = real_passes

        # 2. next run detects and kills an orphan from a previous run
        import subprocess
        orphan = subprocess.Popen(["sleep", "300"], start_new_session=True)
        with open(deleg / "registry.jsonl", "a") as fh:
            fh.write(json.dumps({"id": "old", "pid": orphan.pid, "status": "running"}) + "\n")
        os.environ["FAKE_MODE"] = "fast"
        r = m.run_arm(task, False, 5, state)
        orphan.wait(timeout=5)
        check("orphan: killed before next run", orphan.returncode is not None and not alive(orphan.pid))
        check("orphan: orphan_killed recorded + overlapped", r["orphan_killed"] == 1 and r["overlapped"])

        # 3. fast correct run is valid; env budget reaches delegate
        (deleg / "registry.jsonl").write_text("")
        r = m.run_arm(task, True, 600, state)
        check("fast: pass + completed_cleanly", r["pass"] is True and r["completed_cleanly"] and not r["overlapped"])
        check("fast: reason and tool_calls", r["completion_reason"] == "completed: fixed" and r["tool_calls"] == 1)
        check("budget env = timeout-120 reaches delegate", (deleg / "budget.txt").read_text().strip() == "480")

        # 4. valid flag via main()
        import contextlib, io
        for mode, want in (("fast", True), ("hang", False)):
            os.environ["FAKE_MODE"] = mode
            out = td / f"out-{mode}.json"
            sys.argv = ["aq-prm-eval", "--tasks", "1", "--arms", "on", "--timeout", "1" if mode == "hang" else "600",
                        "--out", str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                m.main()
            res = json.loads(out.read_text())
            if mode == "fast":
                check("summary: valid=true, completed_cleanly=1",
                      res["valid"] is True and res["arms"]["on"]["completed_cleanly"] == 1
                      and res["rows"][0]["pass"] is True)
            else:
                check("summary: valid=false on timeout", res["valid"] is False and res["arms"]["on"]["timed_out"] == 1)

        # 5. emergency cleanup reaps active proc and detached agent
        orphan_proc = subprocess.Popen(["sleep", "300"], start_new_session=True)
        orphan_agent = subprocess.Popen(["sleep", "300"], start_new_session=True)
        with open(deleg / "registry.jsonl", "w") as fh:
            fh.write(json.dumps({"id": "sig-test", "pid": orphan_agent.pid, "status": "running"}) + "\n")
        m._ACTIVE_PROC = orphan_proc
        m._ACTIVE_DELEG = deleg
        m.emergency_cleanup()
        check("emergency_cleanup: active proc killed", not alive(orphan_proc.pid))
        check("emergency_cleanup: detached agent killed", not alive(orphan_agent.pid))
        check("emergency_cleanup: active pointers reset", m._ACTIVE_PROC is None and m._ACTIVE_DELEG is None)

        # 6. signal handler invokes emergency cleanup and exits with 128 + sig
        import signal
        orphan_proc2 = subprocess.Popen(["sleep", "300"], start_new_session=True)
        m._ACTIVE_PROC = orphan_proc2
        m._ACTIVE_DELEG = deleg
        try:
            m._signal_handler(signal.SIGTERM, None)
            check("signal_handler: sys.exit raised", False)
        except SystemExit as exc:
            check("signal_handler: exit code 128 + SIGTERM", exc.code == 128 + signal.SIGTERM)
        check("signal_handler: active proc killed", not alive(orphan_proc2.pid))
    print("FAILED %d" % fails if fails else "ALL PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
