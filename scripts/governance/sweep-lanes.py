#!/usr/bin/env python3
"""sweep-lanes: check every MCP server connects and every agent lane can be dispatched, against live state.

Recovery sweep P2.6 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Report only: no config, tracker
or backlog edits. A fact that cannot be determined is "unknown" and never counts as a pass. Collection
(`collect`) is separate from analysis (`analyse`, a pure function over the collected facts), so `--fixture` replays a
captured run and tests never touch the live host.

Default mode spends no model tokens. Lanes: wrapper present+executable, CLI resolves, auth file present (existence and
mtime only, never contents), `delegate-to-codex|claude --budget-check-only`, `.agents/delegation/registry.jsonl`
recency per lane, last failure reason, local llama.cpp `/health` and `/slots` (URL from LLAMA_CPP_BASE_URL, else the
defaults in config/service-endpoints.sh). `--probe` additionally sends one tiny prompt per lane under a hard timeout
(remote 60 s, local 120 s); Gemini is probed on its CLI default model and on the Flash model from
config/model-coordinator.json, separately.

MCP: every stdio/HTTP server from every config an agent reads (.mcp.json, ~/.claude.json, repo+user Claude settings,
~/.codex/config.toml, repo+user Gemini settings, .agents/mcp_config.json). Each unique server gets ONE real
`initialize` + `tools/list` handshake (no tool is ever called), in its own process group that is killed afterwards and
verified gone (an env marker also finds processes that left the group). Env/header values are never printed. A server
whose launcher may have side effects at start (npx/uvx/docker, or a wrapper that does) is reported unknown, not started.

Finding classes:
  LANE_DOWN            wrapper/CLI/auth missing, local /health not ok, or a probe failed for a non-quota reason
  QUOTA_MODEL          probe hit a per-model quota (429 / quota reached); reported per model
  HANG                 probe timed out with no output, or a registry task is stuck `running`
  PROBE_SLOW           probe timed out after producing some output
  NO_RECENT_SUCCESS    no successful registry row for the lane inside the window
  BUDGET_EXHAUSTED     a budget check refused, or a probe hit a usage-limit error
  RETIRED_REF          antigravity referenced in dispatch config or dispatched recently
  MCP_CONNECT_FAIL     server exited/closed the connection or HTTP did not answer
  MCP_TIMEOUT          server started but never answered initialize or tools/list in time
  MCP_CONFIG_MISSING_BINARY  configured command or its script does not exist
  MCP_NO_TOOLS         initialize succeeded but tools/list is empty or errors
  MCP_DRIFT            a server the repo .mcp.json defines is absent from an agent's configs
  MCP_LEFTOVER_PROCESS a handshake left a process behind (killed by the sweep)

Usage: sweep-lanes.py [--json] [--report PATH] [--fail-on CLASS,...] [--probe] [--no-mcp] [--repo DIR]
                      [--fixture FILE] [--dump-fixture FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:  # python < 3.11
    tomllib = None

DEFAULT_REPO = Path(__file__).resolve().parents[2]
CLASSES = ("LANE_DOWN", "QUOTA_MODEL", "HANG", "PROBE_SLOW", "NO_RECENT_SUCCESS", "BUDGET_EXHAUSTED", "RETIRED_REF",
           "MCP_CONNECT_FAIL", "MCP_TIMEOUT", "MCP_CONFIG_MISSING_BINARY", "MCP_NO_TOOLS", "MCP_DRIFT",
           "MCP_LEFTOVER_PROCESS")
LANES = ("claude", "codex", "gemini", "local")
WRAPPERS = {"claude": "delegate-to-claude", "codex": "delegate-to-codex", "gemini": "delegate-to-gemini",
            "local": "delegate-to-local"}
CLIS = {"claude": "claude", "codex": "codex", "gemini": "gemini"}
AUTH_FILES = {"claude": "~/.claude/.credentials.json", "codex": "~/.codex/auth.json", "gemini": "~/.gemini/oauth_creds.json"}
REGISTRY_AGENT_LANE = {"claude": "claude", "codex": "codex", "gemini": "gemini", "local-direct": "local",
                       "local-agent": "local", "local-hybrid": "local", "local": "local"}
RECENT_WINDOW_S = 24 * 3600
STUCK_RUNNING_S = 45 * 60
REMOTE_TIMEOUT_S = 60
LOCAL_TIMEOUT_S = 120
MCP_TIMEOUT_S = 20
PROBE_PROMPT = "Reply with the single word OK."
QUOTA_RE = re.compile(r"\b429\b|Individual quota|quota (reached|exceeded)|RESOURCE_EXHAUSTED|Resource has been exhausted", re.I)
USAGE_LIMIT_RE = re.compile(r"usage limit|rate limit|hit your limit|limit reached|credit balance", re.I)
SIDE_EFFECT_CMDS = {"npx", "npm", "pnpm", "yarn", "uvx", "pipx", "docker", "podman", "nix", "nix-shell", "bunx"}
SIDE_EFFECT_WRAPPER_RE = re.compile(r"\b(npx|uvx|pipx run|docker run|nix run|nix-shell|pip install|npm install)\b|aq-event\b|\bcurl\b", re.I)
RETIRED_SCAN_GLOBS = ("scripts/ai/delegate-*", "scripts/ai/aq-delegate*", "config/model-coordinator.json",
                      "config/*dispatch*", "config/*delegat*", "config/*lane*", ".agents/*.json")
MARKER_ENV = "SWEEP_LANES_MARKER"
INIT_PARAMS = {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "sweep-lanes", "version": "1"}}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(text, limit=200):
    """Truncate and mask long token-like strings so stderr/CLI output cannot leak a credential into a report."""
    t = re.sub(r"(?=[A-Za-z0-9_\-+=]*\d)(?=[A-Za-z0-9_\-+=]*[A-Za-z])[A-Za-z0-9_\-+=]{32,}", "<redacted>", text or "")
    t = re.sub(r"(?i)(bearer|token|api[_-]?key|secret)\s*[:=]\s*\S+", r"\1=<redacted>", t)
    return " ".join(t.split())[:limit]


# --------------------------------------------------------------------------------------------- process helpers
def run_group(cmd, timeout, cwd=None, env=None, stdin_text=None):
    """Run cmd in its own process group with a hard timeout; the group is always killed and reaped.
    Returns (returncode|None, stdout, stderr, timed_out, elapsed)."""
    t0 = time.time()
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=env,
                             start_new_session=True)
    except OSError as e:
        return 127, "", str(e), False, 0.0
    timed_out = False
    try:
        out, err = p.communicate(stdin_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(p.pid)
        try:
            out, err = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = "", ""
    kill_group(p.pid)
    return (None if timed_out else p.returncode), out or "", err or "", timed_out, round(time.time() - t0, 1)


def kill_group(pgid):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.15)


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def marked_pids(marker):
    """PIDs of our own processes whose environment carries the marker (catches setsid/daemonised leftovers)."""
    pids = []
    me = os.getpid()
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            if marker.encode() in (d / "environ").read_bytes():
                pids.append(int(d.name))
        except OSError:
            pass
    return pids


def reap_marked(marker):
    left = marked_pids(marker)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in left:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        time.sleep(0.2)
    return left


# --------------------------------------------------------------------------------------------- MCP handshake
def _read_until(fd, buf, deadline, want_id):
    """Read newline-delimited JSON-RPC from fd until a message with id==want_id arrives. Returns (msg, state)."""
    while True:
        while b"\n" in buf[0]:
            line, buf[0] = buf[0].split(b"\n", 1)
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("id") == want_id:
                return m, "ok"
        left = deadline - time.time()
        if left <= 0:
            return None, "timeout"
        r, _, _ = select.select([fd], [], [], min(left, 0.5))
        if r:
            chunk = os.read(fd, 65536)
            if not chunk:
                return None, "eof"
            buf[0] += chunk


def handshake_stdio(command, args, env_extra, timeout=MCP_TIMEOUT_S, cwd=None):
    """initialize + tools/list against a stdio server. Never calls a tool. Always kills the group and verifies."""
    marker = uuid.uuid4().hex
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (env_extra or {}).items()})
    env[MARKER_ENV] = marker
    res = {"transport": "stdio", "state": None, "protocol": None, "server": None, "tools": None, "stderr": "",
           "exit": None, "leftover": [], "elapsed": None}
    t0 = time.time()
    try:
        p = subprocess.Popen([command, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, cwd=cwd, start_new_session=True)
    except OSError as e:
        res.update(state="spawn_error", stderr=scrub(str(e)))
        return res
    try:
        deadline = t0 + timeout
        buf = [b""]
        fd = p.stdout.fileno()

        def send(obj):
            try:
                p.stdin.write((json.dumps(obj) + "\n").encode())
                p.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
                return False

        sent = send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": INIT_PARAMS})
        msg, st = _read_until(fd, buf, deadline, 1) if sent else (None, "eof")
        if msg is None:
            res["state"] = "closed" if st == "eof" else "timeout_init"
        elif "error" in msg:
            res["state"] = "init_error"
            res["stderr"] = scrub(json.dumps(msg["error"]))
        else:
            r = msg.get("result") or {}
            res["protocol"] = r.get("protocolVersion")
            res["server"] = (r.get("serverInfo") or {}).get("name")
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            msg2, st2 = _read_until(fd, buf, deadline, 2)
            if msg2 is None:
                res["state"] = "closed_after_init" if st2 == "eof" else "timeout_tools"
            elif "error" in msg2:
                res["state"] = "tools_error"
                res["tools"] = 0
                res["stderr"] = scrub(json.dumps(msg2["error"]))
            else:
                names = [t.get("name") for t in (msg2.get("result") or {}).get("tools", []) if isinstance(t, dict)]
                res["tools"] = len(names)
                res["state"] = "ok"
        if p.poll() is not None:
            res["exit"] = p.returncode
    finally:
        pgid = p.pid
        try:
            err = b""
            r, _, _ = select.select([p.stderr], [], [], 0.2)
            if r:
                err = os.read(p.stderr.fileno(), 4096)
            res["stderr"] = res["stderr"] or scrub(err.decode("utf-8", "replace"))
        except (OSError, ValueError):
            pass
        for s in (p.stdin, p.stdout, p.stderr):
            try:
                s.close()
            except OSError:
                pass
        kill_group(pgid)
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        left = []
        if group_alive(pgid):
            left.append(f"pgid {pgid}")
        left += [f"pid {x}" for x in reap_marked(marker)]
        res["leftover"] = left
        res["elapsed"] = round(time.time() - t0, 1)
    return res


def handshake_http(url, headers, timeout=MCP_TIMEOUT_S):
    res = {"transport": "http", "state": None, "protocol": None, "server": None, "tools": None, "stderr": "",
           "exit": None, "leftover": [], "elapsed": None}
    t0 = time.time()
    hdr = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    hdr.update(headers or {})

    def post(body, extra=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**hdr, **(extra or {})}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(1 << 20).decode("utf-8", "replace")
            return r.status, r.headers, raw

    def parse(raw):
        for chunk in ([raw] + [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]):
            try:
                return json.loads(chunk)
            except ValueError:
                continue
        return None

    try:
        _, h, raw = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": INIT_PARAMS})
        m = parse(raw)
        if not m or "result" not in m:
            res["state"] = "init_error"
            res["stderr"] = scrub(raw, 120)
        else:
            res["protocol"] = m["result"].get("protocolVersion")
            res["server"] = (m["result"].get("serverInfo") or {}).get("name")
            sid = h.get("Mcp-Session-Id")
            extra = {"Mcp-Session-Id": sid} if sid else {}
            try:
                post({"jsonrpc": "2.0", "method": "notifications/initialized"}, extra)
            except urllib.error.HTTPError:
                pass
            _, _, raw2 = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, extra)
            m2 = parse(raw2)
            if m2 and "result" in m2:
                res["tools"] = len(m2["result"].get("tools", []))
                res["state"] = "ok"
            else:
                res["tools"] = 0
                res["state"] = "tools_error"
    except urllib.error.HTTPError as e:
        res["state"] = "http_error"
        res["stderr"] = f"HTTP {e.code}"
    except TimeoutError:
        res["state"] = "timeout_init"
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        res["state"] = "timeout_init" if "timed out" in str(reason) else "unreachable"
        res["stderr"] = scrub(str(reason), 120)
    res["elapsed"] = round(time.time() - t0, 1)
    return res


# --------------------------------------------------------------------------------------------- MCP config discovery
def _norm_server(name, spec, agent, src):
    s = {"name": name, "agent": agent, "source": src, "command": spec.get("command"), "args": list(spec.get("args") or []),
         "url": spec.get("url") or spec.get("httpUrl"), "env_keys": sorted((spec.get("env") or {}).keys()),
         "disabled": bool(spec.get("disabled")) or spec.get("enabled") is False}
    s["_env"] = dict(spec.get("env") or {})
    s["_headers"] = dict(spec.get("headers") or spec.get("http_headers") or {})
    return s


def _load_json(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def discover(repo):
    """Every MCP server any agent reads. Returns list of normalised entries plus config files seen/missing."""
    home = Path(os.path.expanduser("~"))
    servers, seen, missing = [], [], []

    def take(path, agent, picker):
        p = Path(path)
        if not p.exists():
            missing.append(str(p))
            return
        seen.append(str(p))
        for n, sp in picker(p).items():
            if isinstance(sp, dict):
                servers.append(_norm_server(n, sp, agent, str(p)))

    jpick = lambda p: (_load_json(p) or {}).get("mcpServers") or {}
    take(repo / ".mcp.json", "claude", jpick)
    take(home / ".claude.json", "claude", jpick)
    take(repo / ".claude/settings.json", "claude", jpick)
    take(home / ".claude/settings.json", "claude", jpick)
    take(repo / ".gemini/settings.json", "gemini", jpick)
    take(home / ".gemini/settings.json", "gemini", jpick)
    take(repo / ".agents/mcp_config.json", "antigravity-shared", jpick)

    def codex_pick(p):
        if tomllib is None:
            return {}
        try:
            return tomllib.loads(p.read_text()).get("mcp_servers") or {}
        except (OSError, ValueError):
            return {}
    take(home / ".codex/config.toml", "codex", codex_pick)
    return servers, seen, missing


def fingerprint(s):
    """Identity of a server across agents: the script or binary it runs, ignoring checkout-path differences."""
    if s.get("url"):
        return "url:" + re.sub(r"^https?://", "", s["url"]).rstrip("/")
    cmd = os.path.basename(s.get("command") or "")
    arg0 = next((a for a in s.get("args", []) if not a.startswith("-")), "")
    if cmd in ("python3", "python", "node", "bash", "sh") and arg0:
        b = os.path.basename(arg0)
        if b in ("server.py", "index.js", "main.py"):
            b = os.path.basename(os.path.dirname(arg0)) or b
        return b
    return cmd


def resolve_command(s, repo):
    """Returns (ok, why). Checks the command and, for interpreters, the script argument."""
    cmd = s.get("command") or ""
    path = cmd if "/" in cmd else shutil.which(cmd)
    if not path or not os.path.isfile(path) or not os.access(path, os.X_OK):
        return False, f"command not found or not executable: {cmd}"
    if os.path.basename(cmd) in ("python3", "python", "node", "bash", "sh"):
        arg0 = next((a for a in s.get("args", []) if not a.startswith("-")), "")
        if arg0.startswith("/") and not os.path.exists(arg0):
            return False, f"script argument missing: {arg0}"
    return True, ""


def side_effect_reason(s):
    cmd = os.path.basename(s.get("command") or "")
    if cmd in SIDE_EFFECT_CMDS:
        return f"launcher `{cmd}` can fetch/install at start"
    path = s.get("command") or ""
    if "/" in path and os.path.isfile(path):
        try:
            head = Path(path).read_bytes()[:20000]
            if head.startswith(b"#!") and b"python" not in head.split(b"\n", 1)[0] and b"lean" not in head[:0]:
                m = SIDE_EFFECT_WRAPPER_RE.search(head.decode("utf-8", "replace"))
                if m:
                    return f"wrapper {os.path.basename(path)} contains `{m.group(0).strip()}` (network or event-log side effect at start)"
        except OSError:
            pass
    for a in s.get("args", []):
        if a.startswith("/") and a.endswith((".sh", "")) and os.path.isfile(a) and os.path.basename(cmd) in ("bash", "sh"):
            return "shell script argument not inspected"
    return None


def collect_mcp(repo, start=True):
    servers, seen, missing = discover(Path(repo))
    groups = {}
    for s in servers:
        groups.setdefault(fingerprint(s), []).append(s)
    out = []
    for fp, ss in sorted(groups.items()):
        rep = next((x for x in ss if x["command"] and resolve_command(x, repo)[0]), ss[0])
        rec = {"fingerprint": fp, "configs": [{"agent": x["agent"], "name": x["name"], "source": x["source"],
                                               "disabled": x["disabled"]} for x in ss],
               "command": rep.get("command"), "args": rep.get("args"), "url": rep.get("url"), "env_keys": rep.get("env_keys"),
               "binary_ok": None, "binary_why": "", "unknown_reason": None, "handshake": None}
        if rep.get("url"):
            rec["binary_ok"] = True
        else:
            ok, why = resolve_command(rep, repo)
            rec["binary_ok"], rec["binary_why"] = ok, why
            # every distinct (command,args) pair that fails to resolve is its own missing-binary fact
            rec["unresolved_variants"] = sorted({f"{x['source']}: {resolve_command(x, repo)[1]}" for x in ss
                                                 if x.get("command") and not resolve_command(x, repo)[0]})
        if start and rec["binary_ok"]:
            why = None if rep.get("url") else side_effect_reason(rep)
            if why:
                rec["unknown_reason"] = f"not started: {why}"
            elif all(x["disabled"] for x in ss):
                rec["unknown_reason"] = "not started: disabled in every config"
            elif rep.get("url"):
                rec["handshake"] = handshake_http(rep["url"], rep["_headers"])
            else:
                rec["handshake"] = handshake_stdio(rep["command"], rep["args"], rep["_env"], cwd=str(repo))
        out.append(rec)
    canonical = []
    rp = Path(repo) / ".mcp.json"
    for n, sp in ((_load_json(rp) or {}).get("mcpServers") or {}).items():
        canonical.append(fingerprint(_norm_server(n, sp, "repo", str(rp))))
    return {"servers": out, "config_files": seen, "config_files_absent": missing, "repo_canonical": canonical}


# --------------------------------------------------------------------------------------------- lane collection
def endpoint_defaults(repo):
    """Llama base URL: env first, else the defaults declared in config/service-endpoints.sh (the shell SSOT)."""
    if os.environ.get("LLAMA_CPP_BASE_URL"):
        return os.environ["LLAMA_CPP_BASE_URL"].rstrip("/")
    host, port = os.environ.get("LLAMA_HOST"), os.environ.get("LLAMA_PORT")
    try:
        txt = (Path(repo) / "config/service-endpoints.sh").read_text()
        host = host or (re.search(r'LLAMA_HOST="\$\{LLAMA_HOST:-([^}]+)\}"', txt) or [None, None])[1]
        port = port or (re.search(r'LLAMA_PORT="\$\{LLAMA_PORT:-([^}]+)\}"', txt) or [None, None])[1]
    except OSError:
        pass
    return f"http://{host}:{port}" if host and port else None


def http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(16 << 20).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError):
        return None, ""


def delegation_dir(repo):
    if os.environ.get("AQ_DELEGATION_DIR"):
        return Path(os.environ["AQ_DELEGATION_DIR"])
    rc, out, _, _, _ = run_group(["git", "-C", str(repo), "rev-parse", "--git-common-dir"], 10)
    if rc == 0 and out.strip():
        common = Path(out.strip())
        if not common.is_absolute():
            common = Path(repo) / common
        cand = common.resolve().parent / ".agents/delegation"
        if cand.is_dir():
            return cand
    return Path(repo) / ".agents/delegation"


def parse_ts(v):
    try:
        return int(datetime.strptime(v.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except (ValueError, AttributeError):
        return None


def failure_reason(deleg, repo, row):
    """Best-effort last line from the failed task's output log that explains why; scrubbed, never an env value."""
    of = row.get("output_file") or ""
    for base in (Path(repo), deleg.parent.parent):
        p = Path(of) if of.startswith("/") else base / of
        try:
            tail = p.read_bytes()[-6000:].decode("utf-8", "replace")
        except OSError:
            continue
        for line in reversed(tail.splitlines()):
            if re.search(r"error|fail|quota|429|exhaust|refus|timeout|limit", line, re.I):
                return scrub(line, 160)
        return "log present, no error line"
    return None


def collect_registry(deleg, repo, now):
    reg = deleg / "registry.jsonl"
    out = {"path": str(reg), "present": reg.is_file(), "lanes": {}}
    if not reg.is_file():
        return out
    last = {}
    antigravity = []
    try:
        for line in reg.read_text(errors="replace").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            last[r.get("id")] = r
    except OSError:
        return out
    for r in last.values():
        ag = r.get("agent", "")
        if ag == "antigravity":
            t = parse_ts(r.get("created"))
            if t and now - t < 30 * 86400:
                antigravity.append({"id": r.get("id"), "created": r.get("created"), "status": r.get("status")})
        lane = REGISTRY_AGENT_LANE.get(ag)
        if not lane:
            continue
        t = parse_ts(r.get("created"))
        L = out["lanes"].setdefault(lane, {"rows": 0, "done_total": 0, "done_recent": 0, "failed_recent": 0,
                                           "last_success": None, "last_failure": None, "stuck_running": []})
        L["rows"] += 1
        st = r.get("status")
        if st == "done":
            L["done_total"] += 1
            if t and now - t <= RECENT_WINDOW_S:
                L["done_recent"] += 1
            if t and (not L["last_success"] or t > parse_ts(L["last_success"]["created"])):
                L["last_success"] = {"id": r["id"], "created": r["created"]}
        elif st in ("failed", "timeout", "refused") or r.get("outcome") == "refused":
            if t and now - t <= RECENT_WINDOW_S:
                L["failed_recent"] += 1
            if t and (not L["last_failure"] or t > parse_ts(L["last_failure"]["created"])):
                L["last_failure"] = {"id": r["id"], "created": r["created"], "status": st, "_row": r}
        elif st == "running" and t and now - t > STUCK_RUNNING_S:
            L["stuck_running"].append({"id": r["id"], "age_s": now - t})
    for L in out["lanes"].values():
        lf = L["last_failure"]
        if lf:
            lf["reason"] = failure_reason(deleg, repo, lf.pop("_row"))
    out["antigravity_rows_30d"] = antigravity
    return out


def retired_refs(repo):
    hits = []
    seen = set()
    for pat in RETIRED_SCAN_GLOBS:
        for p in sorted(Path(repo).glob(pat)):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            try:
                for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                    if "antigravity" in line.lower():
                        hits.append({"file": str(p.relative_to(repo)), "line": i, "text": " ".join(line.split())[:110]})
            except OSError:
                pass
    return hits


def collect_lane(lane, repo, deleg_reg):
    f = {"wrapper": None, "wrapper_ok": None, "cli": None, "cli_path": None, "auth_file": None, "auth_present": None,
         "auth_age_days": None, "budget": None}
    w = Path(repo) / "scripts/ai" / WRAPPERS[lane]
    f["wrapper"] = str(w.relative_to(repo))
    f["wrapper_ok"] = w.is_file() and os.access(w, os.X_OK)
    if lane in CLIS:
        path = shutil.which(CLIS[lane])
        f["cli"], f["cli_path"] = CLIS[lane], path
        a = Path(os.path.expanduser(AUTH_FILES[lane]))
        f["auth_file"] = AUTH_FILES[lane]
        try:
            st = a.stat()
            f["auth_present"] = st.st_size > 0
            f["auth_age_days"] = int((time.time() - st.st_mtime) // 86400)
        except OSError:
            f["auth_present"] = False
    if lane in ("codex", "claude") and f["wrapper_ok"]:
        rc, out, err, to, _ = run_group([str(w), "--budget-check-only", "--role", "review"], 30)
        txt = scrub(" | ".join(l for l in (out + "\n" + err).splitlines() if l.strip()), 400)
        f["budget"] = {"exit": rc, "timed_out": to, "text": txt}
    return f


def collect_local(repo):
    base = endpoint_defaults(repo)
    d = {"base_url": base, "health": None, "slots": None}
    if not base:
        return d
    st, body = http_get(base + "/health")
    d["health"] = {"status": st, "body": scrub(body, 80)}
    st, body = http_get(base + "/slots")
    try:
        slots = json.loads(body)
        d["slots"] = {"status": st, "count": len(slots), "busy": sum(1 for s in slots if s.get("is_processing"))}
    except ValueError:
        d["slots"] = {"status": st, "count": None, "busy": None}
    return d


# --------------------------------------------------------------------------------------------- probes (spend tokens)
def classify_probe(rc, out, err, timed_out, model_scoped):
    text = out + "\n" + err
    if timed_out:
        return ("HANG" if not out.strip() and not err.strip() else "PROBE_SLOW"), None
    if rc == 0 and out.strip():
        return "OK", None
    if QUOTA_RE.search(text):
        return ("QUOTA_MODEL" if model_scoped else "BUDGET_EXHAUSTED"), scrub(text, 160)
    if USAGE_LIMIT_RE.search(text):
        return "BUDGET_EXHAUSTED", scrub(text, 160)
    return "LANE_DOWN", scrub(text, 160) or f"exit {rc} with no output"


def claude_tokens(out, err=""):
    """Total tokens from `claude -p --output-format json`; this CLI emits either one object or an event array."""
    try:
        j = json.loads(out)
    except ValueError:
        return None
    for e in (j if isinstance(j, list) else [j]):
        if isinstance(e, dict) and e.get("type") == "result":
            u = e.get("usage") or {}
            return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                                    "cache_read_input_tokens"))
    return None


def probe_tokens(text):
    m = re.search(r"tokens used\s*[:\n]?\s*([\d,]+)", text, re.I)
    return int(m.group(1).replace(",", "")) if m else None


def run_probe(lane, label, cmd, timeout, parse_tokens, model_scoped, cwd):
    rc, out, err, to, el = run_group(cmd, timeout, cwd=cwd)
    verdict, why = classify_probe(rc, out, err, to, model_scoped)
    return {"lane": lane, "model": label, "verdict": verdict, "why": why, "exit": rc, "elapsed_s": el,
            "timeout_s": timeout, "reply": scrub(out, 60) if verdict == "OK" and lane != "claude" else ("OK" if verdict == "OK" else None),
            "tokens": parse_tokens(out, err)}


def gemini_models(repo):
    d = _load_json(Path(repo) / "config/model-coordinator.json") or {}
    g = (d.get("tiers") or {}).get("google") or {}
    return g.get("balanced") or g.get("flagship")


def collect_probes(repo, local_base):
    scratch = tempfile.mkdtemp(prefix="sweep-lanes-probe-")
    probes = []
    try:
        if shutil.which("claude"):
            probes.append(run_probe("claude", "haiku", ["claude", "-p", PROBE_PROMPT, "--model", "haiku", "--output-format", "json",
                                                          "--no-session-persistence", "--disable-slash-commands"],
                                    REMOTE_TIMEOUT_S, claude_tokens, False, scratch))
        if shutil.which("codex"):
            probes.append(run_probe("codex", "cli-default", ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                                                              "-C", scratch, PROBE_PROMPT],
                                    REMOTE_TIMEOUT_S, lambda o, e: probe_tokens(o + "\n" + e), False, scratch))
        if shutil.which("gemini"):
            flash = gemini_models(repo)
            for label, extra in (("cli-default", []), (flash or "flash(unresolved)", ["--model", flash] if flash else None)):
                if extra is None:
                    probes.append({"lane": "gemini", "model": label, "verdict": "UNKNOWN", "why": "no Flash model in config/model-coordinator.json"})
                    continue
                probes.append(run_probe("gemini", label, ["gemini", "-p", PROBE_PROMPT, "--mode", "plan", *extra],
                                        REMOTE_TIMEOUT_S, lambda o, e: None, True, scratch))
        if local_base:
            body = json.dumps({"messages": [{"role": "user", "content": PROBE_PROMPT}], "max_tokens": 8, "temperature": 0,
                               "chat_template_kwargs": {"enable_thinking": False}}).encode()
            t0 = time.time()
            rec = {"lane": "local", "model": "llama.cpp", "timeout_s": LOCAL_TIMEOUT_S, "tokens": None, "reply": None, "why": None,
                   "exit": None}
            try:
                req = urllib.request.Request(local_base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=LOCAL_TIMEOUT_S) as r:
                    j = json.loads(r.read(1 << 20))
                msg = ((j.get("choices") or [{}])[0].get("message") or {})
                text = (msg.get("content") or "").strip()
                rec["tokens"] = (j.get("usage") or {}).get("total_tokens")
                rec["reply"] = scrub(text, 60)
                rec["verdict"] = "OK" if text else "LANE_DOWN"
                rec["why"] = None if text else "empty completion"
            except TimeoutError:
                rec["verdict"], rec["why"] = "HANG", None
            except (urllib.error.URLError, OSError, ValueError) as e:
                reason = getattr(e, "reason", e)
                rec["verdict"] = "HANG" if "timed out" in str(reason) else "LANE_DOWN"
                rec["why"] = scrub(str(reason), 120)
            rec["elapsed_s"] = round(time.time() - t0, 1)
            probes.append(rec)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return probes


def collect(repo, probe=False, mcp=True):
    now = int(time.time())
    deleg = delegation_dir(repo)
    data = {"now": now, "repo": str(repo), "host_has_lanes": (Path(repo) / "scripts/ai/delegate-to-codex").exists(),
            "lanes": {l: collect_lane(l, repo, deleg) for l in LANES}, "local": collect_local(repo),
            "registry": collect_registry(deleg, repo, now), "retired_refs": retired_refs(repo),
            "probes": None, "mcp": None}
    if probe:
        data["probes"] = collect_probes(repo, data["local"]["base_url"])
    if mcp:
        data["mcp"] = collect_mcp(repo)
    return data


# --------------------------------------------------------------------------------------------- analysis
def fmt_age(sec):
    sec = int(sec)
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if sec >= n:
            return f"{sec // n}{unit}"
    return f"{sec}s"


def analyse(data):
    """Pure function over collected facts."""
    findings, unknown, lane_rows = [], [], []
    now = data["now"]

    def add(cls, subject, evidence, sev):
        findings.append({"class": cls, "subject": subject, "severity": sev, "evidence": evidence})

    def unk(subject, what):
        unknown.append({"subject": subject, "what": what})

    reg = data.get("registry") or {}
    for lane in LANES:
        f = (data.get("lanes") or {}).get(lane) or {}
        row = {"lane": lane, "wrapper": "ok" if f.get("wrapper_ok") else "MISSING", "cli": f.get("cli_path") or ("n/a" if lane == "local" else "MISSING"),
               "auth": "n/a", "budget": "n/a", "registry": "no registry", "probe": "not run"}
        if not f.get("wrapper_ok"):
            add("LANE_DOWN", lane, f"wrapper {f.get('wrapper')} missing or not executable", "high")
        if lane in CLIS:
            if not f.get("cli_path"):
                add("LANE_DOWN", lane, f"CLI `{CLIS[lane]}` does not resolve on PATH", "high")
            if f.get("auth_present"):
                row["auth"] = f"present ({f.get('auth_age_days')}d old file)"
            else:
                row["auth"] = "ABSENT"
                add("LANE_DOWN", lane, f"auth file {f.get('auth_file')} missing or empty", "high")
        b = f.get("budget")
        if b:
            if b.get("timed_out"):
                unk(lane, "budget check timed out")
                row["budget"] = "timeout"
            elif b.get("exit") == 3:
                row["budget"] = "EXHAUSTED"
                add("BUDGET_EXHAUSTED", lane, f"{WRAPPERS[lane]} --budget-check-only refused (exit 3): {b['text'][:200]}", "high")
            elif b.get("exit") == 0:
                row["budget"] = "headroom"
            else:
                row["budget"] = f"exit {b.get('exit')}"
                unk(lane, f"budget check exit {b.get('exit')}: {b.get('text', '')[:100]}")
        elif lane in ("gemini", "local"):
            unk(lane, "wrapper has no budget check; quota is only observable by a probe")
        rl = (reg.get("lanes") or {}).get(lane)
        if not reg.get("present"):
            unk(lane, "registry.jsonl not found")
        elif not rl:
            add("NO_RECENT_SUCCESS", lane, "no registry rows at all", "medium")
        else:
            ls = rl.get("last_success")
            age = (now - parse_ts(ls["created"])) if ls and parse_ts(ls["created"]) else None
            row["registry"] = f"{rl['done_recent']} done/24h, last ok {fmt_age(age) + ' ago' if age is not None else 'never'}"
            if rl["done_recent"] == 0:
                add("NO_RECENT_SUCCESS", lane, f"no successful dispatch in the last {fmt_age(RECENT_WINDOW_S)}; last success "
                    f"{fmt_age(age) + ' ago' if age is not None else 'never'}; {rl['failed_recent']} failures in window", "medium")
            for s in rl.get("stuck_running", []):
                add("HANG", lane, f"registry task {s['id']} still `running` after {fmt_age(s['age_s'])}", "high")
            lf = rl.get("last_failure")
            if lf:
                row["registry"] += f"; last failure {lf['created']} ({lf.get('status')}): {lf.get('reason') or 'reason not recorded'}"
        if lane == "local":
            loc = data.get("local") or {}
            if not loc.get("base_url"):
                unk(lane, "local base URL not derivable from env or config/service-endpoints.sh")
            else:
                h = loc.get("health") or {}
                if h.get("status") == 200:
                    s = loc.get("slots") or {}
                    row["probe"] = f"/health ok, slots {s.get('count')} ({s.get('busy')} busy)"
                else:
                    add("LANE_DOWN", lane, f"{loc['base_url']}/health returned {h.get('status')}", "high")
                    row["probe"] = f"/health {h.get('status')}"
        lane_rows.append(row)

    by_lane = {r["lane"]: r for r in lane_rows}
    for p in data.get("probes") or []:
        lane, model, v = p["lane"], p.get("model"), p.get("verdict")
        subject = f"{lane}:{model}"
        tag = f"{v} in {p.get('elapsed_s')}s" + (f", {p['tokens']} tok" if p.get("tokens") else "")
        if lane in by_lane:
            prev = by_lane[lane]["probe"]
            by_lane[lane]["probe"] = f"{model}: {tag}" if prev == "not run" else f"{prev}; {model}: {tag}"
        if v == "OK":
            continue
        if v == "UNKNOWN":
            unk(subject, p.get("why"))
        elif v == "HANG":
            add("HANG", subject, f"no output within {p.get('timeout_s')}s hard timeout", "high")
        elif v == "PROBE_SLOW":
            add("PROBE_SLOW", subject, f"timed out after {p.get('timeout_s')}s with partial output", "medium")
        elif v in ("QUOTA_MODEL", "BUDGET_EXHAUSTED", "LANE_DOWN"):
            add(v, subject, p.get("why") or v, "high")

    by_file = {}
    for r in data.get("retired_refs") or []:
        by_file.setdefault(r["file"], []).append(r)
    for f, rs in sorted(by_file.items()):
        lines = ", ".join(str(r["line"]) for r in rs[:8])
        add("RETIRED_REF", f, f"{len(rs)} antigravity reference(s) at line(s) {lines}; first: {rs[0]['text']}",
            "medium" if f.endswith(".json") else "low")
    ag = reg.get("antigravity_rows_30d", [])
    if ag:
        newest = max(ag, key=lambda r: r["created"])
        add("RETIRED_REF", "registry", f"{len(ag)} antigravity dispatch rows in the last 30 days; newest {newest['created']} "
            f"(status {newest['status']})", "medium")

    mcp = data.get("mcp")
    mcp_rows = []
    if mcp:
        canonical = set(mcp.get("repo_canonical") or [])
        agents_seen = {c["agent"] for s in mcp["servers"] for c in s["configs"]} - {"antigravity-shared"}
        for s in mcp["servers"]:
            fp = s["fingerprint"]
            h = s.get("handshake")
            cfgs = sorted({c["agent"] for c in s["configs"]})
            row = {"server": fp, "agents": ",".join(cfgs), "result": "", "protocol": "-", "tools": "-", "names": sorted({c["name"] for c in s["configs"]})}
            if not s.get("binary_ok"):
                row["result"] = "MISSING BINARY"
                add("MCP_CONFIG_MISSING_BINARY", fp, f"{s.get('binary_why')} (configured in {', '.join(cfgs)})", "high")
            elif s.get("unresolved_variants"):
                for v in s["unresolved_variants"]:
                    add("MCP_CONFIG_MISSING_BINARY", fp, f"another config variant does not resolve: {v}", "medium")
            if s.get("unknown_reason"):
                row["result"] = "unknown"
                unk(fp, s["unknown_reason"])
            if h:
                st = h["state"]
                row["protocol"] = h.get("protocol") or "-"
                row["tools"] = h.get("tools") if h.get("tools") is not None else "-"
                if st == "ok" and h.get("tools"):
                    row["result"] = "ok"
                elif st == "ok" or st == "tools_error":
                    row["result"] = "NO TOOLS"
                    add("MCP_NO_TOOLS", fp, f"initialize ok (protocol {h.get('protocol')}) but tools/list returned {h.get('tools')}"
                        + (f": {h['stderr']}" if h.get("stderr") else ""), "medium")
                elif st in ("timeout_init", "timeout_tools"):
                    row["result"] = "TIMEOUT"
                    add("MCP_TIMEOUT", fp, f"no answer to {'initialize' if st == 'timeout_init' else 'tools/list'} within "
                        f"{MCP_TIMEOUT_S}s" + (f"; stderr: {h['stderr']}" if h.get("stderr") else ""), "high")
                else:
                    row["result"] = "CONNECT FAIL"
                    add("MCP_CONNECT_FAIL", fp, f"{st} (exit {h.get('exit')}); stderr: {h.get('stderr') or 'empty'}", "high")
                for lo in h.get("leftover", []):
                    add("MCP_LEFTOVER_PROCESS", fp, f"process left behind after handshake ({lo}); sweep killed it", "high")
            elif not row["result"]:
                row["result"] = "not started"
            mcp_rows.append(row)
        have = {a: {fingerprint_cfg for fingerprint_cfg in [s["fingerprint"] for s in mcp["servers"]
                                                             if any(c["agent"] == a and not c["disabled"] for c in s["configs"])]}
                for a in agents_seen}
        for a in sorted(agents_seen):
            for fp in sorted(canonical - have[a]):
                add("MCP_DRIFT", f"{fp}@{a}", f"repo .mcp.json defines `{fp}` but no {a} config (user or repo level) has it", "medium")
    else:
        unk("mcp", "MCP sweep not run")

    counts = {c: sum(1 for f in findings if f["class"] == c) for c in CLASSES}
    sev = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (sev.get(f["severity"], 3), CLASSES.index(f["class"]), f["subject"]))
    return {"skipped": False, "now": now, "counts": counts, "findings": findings, "unknown": unknown, "lanes": lane_rows,
            "mcp": mcp_rows, "probed": data.get("probes") is not None, "probes": data.get("probes") or [],
            "mcp_config_files": (mcp or {}).get("config_files", []), "mcp_config_absent": (mcp or {}).get("config_files_absent", [])}


# --------------------------------------------------------------------------------------------- report
def md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_report(res, day, argv, notes):
    L = [f"# {day} sweep-lanes", "", "## Objective",
         "Recovery sweep P2.6 (system-integrity-recovery): each MCP server connects and each agent lane (Claude, Codex, Gemini, "
         "local) dispatches, judged from live state. Report only; no config, tracker or backlog was changed.", "",
         "## Workflow/Session IDs", f"Branch feat/sweep-lanes, date {day}, live host.", "",
         "## Delegation Decision", "Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixtures).", "",
         "## Commands Executed",
         f"- `scripts/governance/sweep-lanes.py {' '.join(argv)}`".rstrip(),
         "- `scripts/ai/delegate-to-codex|claude --budget-check-only --role review` (no model call)",
         "- Registry read: `.agents/delegation/registry.jsonl`; local `GET /health`, `GET /slots`",
         "- MCP: one `initialize` + `tools/list` per unique server, own process group, killed and verified; no tool called",
         "- Probes (only with --probe): one tiny prompt per lane, 60 s remote / 120 s local hard timeout", "",
         "## Validation Evidence", "", "Counts per class:", "", "| Class | Count |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in res["counts"].items()]
    L += ["", f"Total findings: {len(res['findings'])}. Unknown (not counted as pass): {len(res['unknown'])}. "
              f"Probe run: {'yes' if res['probed'] else 'no'}.", "", "Lane status:", "",
          "| Lane | Wrapper | CLI | Auth | Budget | Registry | Probe / health |", "|---|---|---|---|---|---|---|"]
    for r in res["lanes"]:
        L.append(f"| {r['lane']} | {r['wrapper']} | {md(r['cli'])} | {md(r['auth'])} | {r['budget']} | {md(r['registry'])} | {md(r['probe'])} |")
    if res["probes"]:
        L += ["", "Probes:", "", "| Lane | Model | Verdict | Time | Tokens | Detail |", "|---|---|---|---|---|---|"]
        for p in res["probes"]:
            L.append(f"| {p['lane']} | {md(p.get('model'))} | {p['verdict']} | {p.get('elapsed_s', '-')}s | "
                     f"{p.get('tokens') if p.get('tokens') is not None else 'unknown'} | {md(p.get('why') or p.get('reply') or '')} |")
    L += ["", "MCP servers (one handshake per unique server; env values never printed):", "",
          "| Server | Configured for | Result | Protocol | Tools | Config names |", "|---|---|---|---|---|---|"]
    for r in res["mcp"]:
        L.append(f"| `{r['server']}` | {r['agents']} | {r['result']} | {r['protocol']} | {r['tools']} | {md(', '.join(r['names']))} |")
    if not res["mcp"]:
        L.append("| - | - | not run | - | - | - |")
    L += ["", "Config files read: " + (", ".join(f"`{p}`" for p in res["mcp_config_files"]) or "none"),
          "Config files absent: " + (", ".join(f"`{p}`" for p in res["mcp_config_absent"]) or "none"), "",
          "Findings:", "", "| # | Sev | Class | Subject | Evidence |", "|---|---|---|---|---|"]
    for i, f in enumerate(res["findings"], 1):
        L.append(f"| {i} | {f['severity']} | {f['class']} | `{md(f['subject'])}` | {md(f['evidence'])} |")
    if not res["findings"]:
        L.append("| - | - | - | none | - |")
    L += ["", "Unknown / not determinable:", ""]
    L += [f"- `{md(u['subject'])}`: {md(u['what'])}" for u in res["unknown"]] or ["- none"]
    L += ["", "Notes:", ""] + [f"- {n}" for n in notes]
    L += ["", "## Rollback Plan", "Delete this report and the sweep script; nothing else was changed.", ""]
    return "\n".join(L)


def sweep_notes(res):
    n = ["Probes call the CLIs and the llama.cpp HTTP API directly, not the delegate-to-* wrappers, so they add no registry rows.",
         "Gemini quota is per model: the CLI default and the Flash model named in config/model-coordinator.json are probed separately.",
         "Auth is checked by file existence and age only; a present file does not prove the token is still valid (that is what --probe shows).",
         "Registry `success` means status `done`; the wrappers do not record a failure reason, so the reason is the last error-like line of the failed task's log.",
         "MCP drift compares the repo `.mcp.json` against the merged user+repo config of each agent; claude.ai cloud connectors are not file-configured and are out of scope.",
         "A server whose launcher may have side effects at start is reported unknown and not started."]
    if not res["probed"]:
        n.append("Run without --probe: no model tokens were spent.")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", help="write the dated markdown report to this path")
    ap.add_argument("--fail-on", default="", help="comma list of classes that make the exit status non-zero (default: report only)")
    ap.add_argument("--probe", action="store_true", help="send one tiny prompt per lane (spends tokens; never use in CI)")
    ap.add_argument("--no-mcp", action="store_true", help="skip the MCP handshakes")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--fixture", help="analyse captured collector output (JSON) instead of the live host")
    ap.add_argument("--dump-fixture", help="write the collected live facts to this JSON file")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args(argv)
    fail = [c for c in a.fail_on.split(",") if c]
    bad = [c for c in fail if c not in CLASSES]
    if bad:
        ap.error(f"unknown class {bad}; choose from {CLASSES}")
    if a.fixture:
        data = json.loads(Path(a.fixture).read_text())
    elif not (Path(a.repo) / "scripts/ai/delegate-to-codex").exists() or os.environ.get("CI"):
        msg = "sweep-lanes: SKIP: no agent lane wrappers or CI environment (live host only); nothing to sweep, exit 0"
        print(json.dumps({"skipped": True, "reason": "no live host"}) if a.json else msg)
        return 0
    else:
        data = collect(a.repo, probe=a.probe, mcp=not a.no_mcp)
    if a.dump_fixture:
        Path(a.dump_fixture).write_text(json.dumps(data, indent=1))
    res = analyse(data)
    if a.report:
        Path(a.report).write_text(render_report(res, a.date, sys.argv[1:] if argv is None else argv, sweep_notes(res)))
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"sweep-lanes: {len(res['lanes'])} lanes, {len(res['mcp'])} MCP servers, {len(res['unknown'])} unknown, "
              f"probe={'yes' if res['probed'] else 'no'}")
        for k, v in res["counts"].items():
            print(f"  {k:26} {v}")
        for f in res["findings"]:
            print(f"  [{f['class']}] {f['subject']}: {f['evidence']}")
    return 1 if any(res["counts"][c] for c in fail) else 0


if __name__ == "__main__":
    sys.exit(main())
