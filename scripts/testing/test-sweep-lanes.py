#!/usr/bin/env python3
"""sweep-lanes: each finding class is detected from fixtures and a throwaway fake MCP stdio server (good, empty,
hanging, crashing, daemonising), a healthy host is not flagged, and no handshake leaves a process behind.
Never runs --probe, never calls a model, never touches the real MCP configs (HOME and repo are temp dirs)."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = Path(os.environ.get("SWEEP_LANES_SCRIPT") or REPO / "scripts/governance/sweep-lanes.py")
spec = importlib.util.spec_from_loader("sweep", importlib.machinery.SourceFileLoader("sweep", str(SCRIPT)))
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL:", msg)


FAKE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
mode, pidfile = sys.argv[1], sys.argv[2]
def spawn():
    # grandchild in its own session: only the env marker can find it
    p = subprocess.Popen(["sleep", "300"], start_new_session=True)
    open(pidfile, "a").write(str(p.pid) + "\n")
if mode == "crash":
    sys.stderr.write("boom: cannot start\n"); sys.exit(1)
if mode in ("hang", "daemon"):
    spawn()
if mode == "hang":
    time.sleep(300)
for line in sys.stdin:
    m = json.loads(line)
    if m.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "fake"}, "capabilities": {}}}), flush=True)
    elif m.get("method") == "tools/list" and mode == "stalltools":
        time.sleep(300)
    elif m.get("method") == "tools/list":
        tools = [] if mode == "empty" else [{"name": "t1"}, {"name": "t2"}]
        print(json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": {"tools": tools}}), flush=True)
'''


def alive(pid):
    try:
        os.kill(pid, 0)
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except (OSError, ValueError):
        return False


def pids_of(pidfile):
    try:
        return [int(x) for x in Path(pidfile).read_text().split()]
    except OSError:
        return []


tmp = Path(tempfile.mkdtemp(prefix="test-sweep-lanes-"))
fake = tmp / "fake-mcp.py"
fake.write_text(FAKE)
fake.chmod(0o755)
copies = {}


def fk(name):
    """Distinct script per logical server: servers are identified across agents by the script they run."""
    if name not in copies:
        copies[name] = tmp / f"fake-{name}.py"
        copies[name].write_text(FAKE)
        copies[name].chmod(0o755)
    return str(copies[name])

# --- handshake states + no surviving process -------------------------------------------------------------------
all_pidfiles = []
for mode, want_state in (("good", "ok"), ("empty", "ok"), ("crash", "closed"), ("hang", "timeout_init"), ("daemon", "ok")):
    pf = tmp / f"pids-{mode}"
    all_pidfiles.append(pf)
    h = sw.handshake_stdio(sys.executable, [str(fake), mode, str(pf)], {"SECRET_TEST_VALUE": "do-not-print"}, timeout=3)
    check(h["state"] == want_state, f"{mode}: state {h['state']!r}, wanted {want_state!r}")
    if mode == "good":
        check(h["tools"] == 2 and h["protocol"] == "2025-03-26", f"good: tools/protocol {h['tools']} {h['protocol']}")
    if mode == "empty":
        check(h["tools"] == 0, "empty: tools should be 0")
    if mode == "crash":
        check("boom" in h["stderr"] and h["exit"] == 1, f"crash: stderr/exit not captured: {h['stderr']!r} {h['exit']}")
    if mode in ("hang", "daemon"):
        check(h["leftover"], f"{mode}: sweep should report the escaped grandchild as leftover, got {h['leftover']}")
time.sleep(0.5)
for pf in all_pidfiles:
    for pid in pids_of(pf):
        check(not alive(pid), f"process {pid} from {pf.name} survived the handshake")

st = sw.handshake_stdio(sys.executable, [str(fake), "stalltools", str(tmp / "pids-stall")], {}, timeout=3)
check(st["state"] == "timeout_tools", f"stalltools: {st['state']}")

# --- run_group: hard timeout kills the whole group -------------------------------------------------------------
pf = tmp / "pids-run-group"
rc, out, err, to, _ = sw.run_group(["sh", "-c", f"sleep 300 & echo $! > {pf}; wait"], 1)
check(to and rc is None, "run_group should time out")
time.sleep(0.3)
check(all(not alive(p) for p in pids_of(pf)), "run_group left the sleeping child alive")
check(sw.classify_probe(None, "", "", True, True)[0] == "HANG", "timeout with no output must be HANG")
check(sw.classify_probe(None, "partial", "", True, True)[0] == "PROBE_SLOW", "timeout with output must be PROBE_SLOW")
check(sw.classify_probe(1, "", "429 Individual quota reached", False, True)[0] == "QUOTA_MODEL", "gemini 429 must be QUOTA_MODEL")
check(sw.classify_probe(1, "", "You've hit your usage limit", False, False)[0] == "BUDGET_EXHAUSTED", "usage limit must be BUDGET_EXHAUSTED")
check(sw.classify_probe(1, "", "segfault", False, False)[0] == "LANE_DOWN", "other failure must be LANE_DOWN")
check(sw.classify_probe(0, "OK", "", False, True)[0] == "OK", "success must be OK")

ev = json.dumps([{"type": "system"}, {"type": "result", "usage": {"input_tokens": 3, "output_tokens": 4, "cache_read_input_tokens": 10}}])
check(sw.claude_tokens(ev) == 17, "claude event-array token total wrong")
check(sw.claude_tokens(json.dumps({"type": "result", "usage": {"input_tokens": 2}})) == 2, "claude single-object token total wrong")
check(sw.claude_tokens("not json") is None, "unparseable claude output must be unknown")

# --- end-to-end MCP collect over a fake HOME + repo ------------------------------------------------------------
home, repo = tmp / "home", tmp / "repo"
(repo / "scripts/ai").mkdir(parents=True)
(home / ".codex").mkdir(parents=True)
(home / ".gemini").mkdir()
py = sys.executable
(repo / ".mcp.json").write_text(json.dumps({"mcpServers": {
    "good": {"command": py, "args": [fk("good"), "good", str(tmp / "p1")]},
    "onlyrepo": {"command": py, "args": [fk("empty"), "empty", str(tmp / "p2")]},
}}))
(home / ".gemini/settings.json").write_text(json.dumps({"mcpServers": {
    "Good Alias": {"command": py, "args": [fk("good"), "good", str(tmp / "p1")]},
    "broken": {"command": "/nonexistent/bin/mcp-nope", "args": []},
    "crashy": {"command": py, "args": [fk("crash"), "crash", str(tmp / "p3")]},
    "slow": {"command": py, "args": [fk("hang"), "hang", str(tmp / "p4")]},
    "fetcher": {"command": "npx", "args": ["-y", "some-pkg"]},
}}))
(home / ".codex/config.toml").write_text(f'[mcp_servers.good]\ncommand = "{py}"\nargs = ["{fk("good")}", "good", "{tmp / "p1"}"]\n')
os.environ["HOME"] = str(home)
sw.MCP_TIMEOUT_S = 3
orig = sw.handshake_stdio
sw.handshake_stdio = lambda c, a, e, timeout=3, cwd=None: orig(c, a, e, timeout=3, cwd=cwd)
mcp = sw.collect_mcp(repo)
sw.handshake_stdio = orig
res = sw.analyse({"now": int(time.time()), "lanes": {}, "registry": {"present": True, "lanes": {}}, "mcp": mcp, "retired_refs": []})
got = {(f["class"], f["subject"]) for f in res["findings"]}
check(("MCP_CONFIG_MISSING_BINARY", "mcp-nope") in got, f"missing binary not flagged: {got}")
check(any(c == "MCP_CONNECT_FAIL" for c, _ in got), "crashing server not flagged MCP_CONNECT_FAIL")
check(any(c == "MCP_TIMEOUT" for c, _ in got), "hanging server not flagged MCP_TIMEOUT")
check(any(c == "MCP_NO_TOOLS" for c, _ in got), "empty tools/list not flagged MCP_NO_TOOLS")
drift = {s for c, s in got if c == "MCP_DRIFT"}
check(any(s.endswith("@gemini") for s in drift) and any(s.endswith("@codex") for s in drift), f"drift not flagged for gemini+codex: {drift}")
check("fake-good.py@claude" not in drift and "fake-good.py@codex" not in drift, f"good server wrongly drifted: {drift}")
check(any("npx" in u["what"] for u in res["unknown"]), "side-effect launcher must be unknown, not started")
check(not any(c == "MCP_CONNECT_FAIL" and s == "npx" for c, s in got), "npx server must not be started")
with tempfile.TemporaryDirectory() as wd:
    wrapper = Path(wd) / "pip-wrapper.sh"
    wrapper.write_text("#!/bin/sh\npip install some-pkg\n", encoding="utf-8")
    wrapper.chmod(0o755)
    reason = sw.side_effect_reason({"command": str(wrapper), "args": []}) or ""
    check("side effect" in reason, f"pip wrapper not classified as side-effecting: {reason!r}")
good = [r for r in res["mcp"] if r["agents"].count(",") == 2]
check(good and good[0]["result"] == "ok" and good[0]["protocol"] == "2025-03-26", f"good server not ok across 3 agents: {res['mcp']}")
check("do-not-print" not in json.dumps(res) and "SECRET_TEST_VALUE" not in json.dumps(mcp), "env value or key leaked into output")
time.sleep(0.5)
for pf in ("p1", "p2", "p3", "p4"):
    for pid in pids_of(tmp / pf):
        check(not alive(pid), f"collect_mcp left {pf} pid {pid} alive")

# --- lane analysis over a fixture ------------------------------------------------------------------------------
NOW = 1_800_000_000


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def lane_fixture(**over):
    lanes = {l: {"wrapper": f"scripts/ai/delegate-to-{l}", "wrapper_ok": True, "cli": l, "cli_path": f"/bin/{l}",
                 "auth_file": "~/x", "auth_present": True, "auth_age_days": 1, "budget": None} for l in sw.LANES}
    lanes["local"].update(cli=None, cli_path=None, auth_file=None, auth_present=None)
    lanes["codex"]["budget"] = {"exit": 0, "timed_out": False, "text": "ok"}
    reg = {"present": True, "lanes": {l: {"rows": 5, "done_total": 5, "done_recent": 3, "failed_recent": 0,
                                           "last_success": {"id": "x", "created": iso(NOW - 600)}, "last_failure": None,
                                           "stuck_running": []} for l in sw.LANES}, "antigravity_rows_30d": []}
    d = {"now": NOW, "lanes": lanes, "registry": reg, "retired_refs": [], "probes": None, "mcp": None,
         "local": {"base_url": "http://127.0.0.1:1", "health": {"status": 200}, "slots": {"count": 1, "busy": 0}}}
    d.update(over)
    return d


def classes(d):
    return {f["class"] for f in sw.analyse(d)["findings"]}


check(classes(lane_fixture()) == set(), f"healthy fixture flagged: {classes(lane_fixture())}")
d = lane_fixture(); d["lanes"]["codex"]["wrapper_ok"] = False
check("LANE_DOWN" in classes(d), "missing wrapper not LANE_DOWN")
d = lane_fixture(); d["lanes"]["gemini"]["cli_path"] = None
check("LANE_DOWN" in classes(d), "missing CLI not LANE_DOWN")
d = lane_fixture(); d["lanes"]["claude"]["auth_present"] = False
check("LANE_DOWN" in classes(d), "missing auth not LANE_DOWN")
d = lane_fixture(); d["local"]["health"] = {"status": None}
check("LANE_DOWN" in classes(d), "local /health down not LANE_DOWN")
d = lane_fixture(); d["lanes"]["codex"]["budget"] = {"exit": 3, "timed_out": False, "text": "refused"}
check("BUDGET_EXHAUSTED" in classes(d), "budget exit 3 not BUDGET_EXHAUSTED")
d = lane_fixture(); d["registry"]["lanes"]["gemini"].update(done_recent=0, last_success={"id": "x", "created": iso(NOW - 3 * 86400)})
check("NO_RECENT_SUCCESS" in classes(d), "stale lane not NO_RECENT_SUCCESS")
d = lane_fixture(); d["registry"]["lanes"]["gemini"]["stuck_running"] = [{"id": "g1", "age_s": 5760}]
check("HANG" in classes(d), "stuck running task not HANG")
d = lane_fixture(retired_refs=[{"file": "config/x.json", "line": 3, "text": "antigravity"}])
check("RETIRED_REF" in classes(d), "antigravity config ref not RETIRED_REF")
d = lane_fixture(); d["registry"]["antigravity_rows_30d"] = [{"id": "a", "created": iso(NOW), "status": "done"}]
check("RETIRED_REF" in classes(d), "recent antigravity dispatch not RETIRED_REF")
d = lane_fixture(probes=[
    {"lane": "gemini", "model": "cli-default", "verdict": "QUOTA_MODEL", "why": "429", "elapsed_s": 2, "timeout_s": 60},
    {"lane": "gemini", "model": "flash", "verdict": "OK", "elapsed_s": 3, "timeout_s": 60, "tokens": None},
    {"lane": "codex", "model": "cli-default", "verdict": "HANG", "elapsed_s": 60, "timeout_s": 60}])
r = sw.analyse(d)
subj = {(f["class"], f["subject"]) for f in r["findings"]}
check(("QUOTA_MODEL", "gemini:cli-default") in subj and not any(s == "gemini:flash" for _, s in subj), f"per-model quota split wrong: {subj}")
check(("HANG", "codex:cli-default") in subj, "probe hang not HANG")
d = lane_fixture(probes=[{"lane": "local", "model": "llama.cpp", "verdict": "PROBE_SLOW", "elapsed_s": 120, "timeout_s": 120}])
check("PROBE_SLOW" in classes(d), "slow probe not PROBE_SLOW")

# --- registry reader: latest row per id wins; running rows past the threshold are stuck --------------------------
dd = tmp / "deleg"
dd.mkdir()
rows = [{"id": "g1", "agent": "gemini", "status": "running", "created": iso(NOW - 7000)},
        {"id": "g2", "agent": "gemini", "status": "running", "created": iso(NOW - 7000)},
        {"id": "g2", "agent": "gemini", "status": "done", "created": iso(NOW - 7000)},
        {"id": "l1", "agent": "local-direct", "status": "failed", "created": iso(NOW - 100), "output_file": "nolog.txt"}]
(dd / "registry.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
rg = sw.collect_registry(dd, tmp, NOW)
check([s["id"] for s in rg["lanes"]["gemini"]["stuck_running"]] == ["g1"], f"stuck rows wrong: {rg['lanes']['gemini']}")
check(rg["lanes"]["gemini"]["done_total"] == 1 and rg["lanes"]["local"]["last_failure"]["id"] == "l1", "latest-row-per-id wrong")

# --- CLI: skip without a live host, --fixture replays, --fail-on gates, report writes ----------------------------
fx = tmp / "fx.json"
d = lane_fixture(); d["lanes"]["codex"]["budget"] = {"exit": 3, "timed_out": False, "text": "refused"}
fx.write_text(json.dumps(d))
env = {**os.environ, "CI": "1"}
p = subprocess.run([sys.executable, str(SCRIPT), "--json"], capture_output=True, text=True, env=env)
check(p.returncode == 0 and json.loads(p.stdout).get("skipped") is True, f"CI skip failed: {p.returncode} {p.stdout[:100]}")
p = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(fx), "--json"], capture_output=True, text=True)
check(p.returncode == 0 and json.loads(p.stdout)["counts"]["BUDGET_EXHAUSTED"] == 1, "report-only default must exit 0 with the finding")
p = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(fx), "--fail-on", "BUDGET_EXHAUSTED", "--report", str(tmp / "r.md")],
                   capture_output=True, text=True)
check(p.returncode == 1, "--fail-on BUDGET_EXHAUSTED must exit 1")
check("BUDGET_EXHAUSTED" in (tmp / "r.md").read_text(), "report missing finding")
p = subprocess.run([sys.executable, str(SCRIPT), "--fail-on", "NOPE"], capture_output=True, text=True)
check(p.returncode == 2, "unknown --fail-on class must be a usage error")

if FAILS:
    print(f"FAIL: {len(FAILS)} check(s) failed")
    sys.exit(1)
print("PASS: sweep-lanes detects every class from fixtures and a fake MCP server, and leaves no process behind")
