#!/usr/bin/env python3
"""sweep-tests: execute every test file once, isolated, and produce a dated red list.

Recovery sweep P2.1 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Report only: no test is
fixed and no exemption in config/ci-checks.json is edited. Re-runnable; the dated report becomes a standing check
(scripts/testing/test-sweep-tests.py proves each class on fixtures; the full sweep is run on demand, not in CI).

Test inventory: scripts/testing/test-* plus every `tests` entry of config/ci-checks.json and every check whose cmd is
exactly one scripts/testing script. Exemptions come from `test_exempt` in the same manifest.

Isolation (every test, no exceptions):
  - bwrap: whole filesystem read-only except a per-test temp dir and a private clone of the repo, no network
    namespace access, private pid/ipc/uts, /run/user, /run/dbus and /run/systemd masked (no zellij, no systemctl, no
    docker socket), no_new_privs (sudo cannot work). --sandbox none falls back to env-only isolation (fixtures).
  - env whitelist (no tokens/keys); HOME and XDG dirs, TMPDIR, state-dir vars point at the temp dir; every service URL
    points at a dead port; GIT_CONFIG_GLOBAL=/dev/null.
  - own session + process group, hard timeout, SIGKILL of the group, then a /proc sweep for any process still carrying
    the run marker (a leftover is reported, never tolerated).
  - nice 19 / ionice idle, at most 2 workers, a wall-clock budget after which the sweep stops and can be resumed.
  - after each test: `git status` of the repo clone (TREE_MUTATION: it wrote inside the tree, harmless, reported) and
    an mtime snapshot of live state paths (LIVE_MUTATION: that family stops, loudly).

Classes (raw result, then exemption-aware):
  PASS FAIL TIMEOUT NOT_RUN FLAKY EXEMPT_NOW_PASSES EXEMPT_STILL_FAILS
Flags on any record: UNDECLARED NO_ASSERTIONS TIME_BOMB(static; --faketime-* adds an exercised second run)
  TREE_MUTATION LIVE_MUTATION LEFTOVER_PROCS RO_BLOCKED
Heuristic limits are stated in the report; nothing undeterminable is counted as a pass.

Usage: sweep-tests.py [--repo DIR] [--date YYYY-MM-DD] [--report PATH] [--json PATH] [--state FILE] [--jobs 1|2]
                      [--timeout S] [--budget-min N] [--sandbox bwrap|none] [--include-live] [--only GLOB ...]
                      [--no-watch] [--no-rerun] [--faketime-lib SO --faketime-date 'YYYY-MM-DD HH:MM:SS'] [--fail-on CLASS,...]
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from queue import Queue

DEFAULT_REPO = Path(__file__).resolve().parents[2]
DEAD = "127.0.0.1:9"
MAX_JOBS = 2
MARKER_VAR = "AQ_SWEEP_RUN_ID"
KEEP_ENV = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "LOCALE_ARCHIVE", "SSL_CERT_FILE", "NIX_SSL_CERT_FILE",
            "LD_LIBRARY_PATH", "PYTHONHASHSEED")
URL_VARS = ("HYBRID_URL", "DASHBOARD_URL", "LLAMA_URL", "AIDB_URL", "SWITCHBOARD_URL", "DASHBOARD_API_URL",
            "LLAMA_CPP_URL", "QDRANT_URL", "HYBRID_COORDINATOR_URL", "REDIS_URL", "LLAMA_BASE_URL",
            "LLAMA_CPP_BASE_URL", "HYBRID_COORDINATOR_ENDPOINT", "AIDB_ENDPOINT", "AQ_AUTO_UPDATE_LLAMA_URL",
            "AQ_AUTO_UPDATE_COORDINATOR_URL", "OLLAMA_URL", "EMBEDDINGS_URL")
PORT_VARS = ("HYBRID_COORDINATOR_PORT", "SWITCHBOARD_PORT", "LLAMA_PORT", "AIDB_PORT", "DASHBOARD_PORT", "QDRANT_PORT")
HOST_VARS = ("HYBRID_HOST", "AIDB_HOST", "LLAMA_HOST", "SWITCHBOARD_HOST", "DASHBOARD_HOST")
FLAGS = ("UNDECLARED", "NO_ASSERTIONS", "TIME_BOMB", "TREE_MUTATION", "LIVE_MUTATION", "LEFTOVER_PROCS", "RO_BLOCKED")
CLASS_ORDER = ("PASS", "FAIL", "TIMEOUT", "NOT_RUN", "FLAKY", "EXEMPT_NOW_PASSES", "EXEMPT_STILL_FAILS")

# Root-cause grouping: regexes over the failure window, first match wins (order = precedence).
GROUPS = (
    ("missing module", re.compile(r"ModuleNotFoundError|No module named|ImportError|cannot import name|command not found|: not found$|executable file not found", re.M)),
    ("missing file", re.compile(r"FileNotFoundError|No such file or directory|missing file|does not exist|not a git repository|cannot open", re.I)),
    ("environment", re.compile(r"Connection refused|ConnectionError|URLError|Errno 111|Errno 101|Network is unreachable|Temporary failure in name|name resolution|Permission denied|PermissionError|Read-only file system|EROFS|bwrap|systemctl|Failed to connect|not installed|GITHUB_TOKEN|API[_ ]KEY|requires a? ?(running|live)|live (stack|service)|unreachable|OSError|timed out|Operation not permitted", re.I)),
    ("real product bug (suspect)", re.compile(r"\b(TypeError|KeyError|AttributeError|NameError|ValueError|IndexError|UnboundLocalError|RuntimeError|ZeroDivisionError|RecursionError|JSONDecodeError)\b")),
    ("stale assertion", re.compile(r"AssertionError|\bFAIL\b|assert|expected|mismatch|not equal|!=|should|does not contain|missing from|not found in", re.I)),
)
FAIL_LINE = re.compile(r"\bFAIL(?:ED)?\b|\bnot ok\b|Traceback|Error\b|\berror:|\bERROR\b|AssertionError|\u2717|\u2718", re.I)
PY_ASSERT = re.compile(r"\bassert\w*\b|\braise\b|sys\.exit\(|\bexit\(|\bunittest\b|\bpytest\b|\.fail\(|def (?:check|ok|expect|fail|assert|require|verify)\w*|\bcheck\(|\bexpect\(|SystemExit|os\._exit")
SH_ASSERT = re.compile(r"\bexit\s+(?:[1-9]|\$)|\breturn\s+[1-9]|\|\|\s*(?:fail|die|exit|return|echo)|\b(?:fail|die|assert\w*|expect\w*|check\w*|require\w*)\b|\[\[?\s|\bgrep\s+-\w*q|\btest\s+-|\bdiff\b|\bset\s+-\w*e")
JS_ASSERT = re.compile(r"\bassert\b|process\.exit|throw\b|expect\(")
CLOCK = re.compile(r"datetime\.(?:now|utcnow|today)|date\.today|time\.time\(|time\.localtime|time\.gmtime|\bdate\s+[+-]|\$\(date|Date\.now|new Date\(\)|fromtimestamp|utcnow|\bnow\(\)", re.I)
DATE_LIT = re.compile(r"\b(20[2-9]\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")


# ---------------------------------------------------------------- inventory

def load_manifest(repo: Path) -> dict:
    p = Path(os.environ.get("CI_CHECKS_MANIFEST") or repo / "config/ci-checks.json")
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {"checks": [], "test_exempt": []}


def inventory(repo: Path, manifest: dict) -> tuple[list[str], set[str], dict[str, dict]]:
    """(sorted test paths, declared-by-a-check set, {script: exempt entry})."""
    declared: set[str] = set()
    for c in manifest.get("checks", []):
        declared.update(t for t in c.get("tests", []))
        cmd = (c.get("cmd") or "").strip()
        m = re.fullmatch(r"(scripts/testing/[\w./-]+\.(?:py|sh|js))", cmd)
        if m:
            declared.add(m.group(1))
        # test-*.{py,sh} named anywhere in a cmd (the rule tier0.d/check-ci-test-coverage.sh applies)
        declared.update(re.findall(r"scripts/testing/test-[\w.-]+\.(?:py|sh)", cmd))
    exempt = {e["script"]: e for e in manifest.get("test_exempt", []) if e.get("script")}
    found = {os.path.relpath(p, repo) for p in glob.glob(str(repo / "scripts/testing/test-*")) if os.path.isfile(p)}
    found |= {t for t in declared if (repo / t).is_file()}
    found |= {t for t in exempt if (repo / t).is_file()}
    return sorted(found), declared, exempt


# ---------------------------------------------------------------- process isolation

def build_env(tmp: str, run_id: str, faketime: tuple[str, str] | None = None) -> dict:
    env = {k: os.environ[k] for k in KEEP_ENV if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin")
    home = f"{tmp}/home"
    env.update({
        "HOME": home, "XDG_CONFIG_HOME": f"{home}/.config", "XDG_DATA_HOME": f"{home}/.local/share",
        "XDG_CACHE_HOME": f"{home}/.cache", "XDG_STATE_HOME": f"{home}/.local/state", "XDG_RUNTIME_DIR": f"{tmp}/run",
        "TMPDIR": f"{tmp}/tmp", "TERM": "dumb", "CI": "1", MARKER_VAR: run_id,
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "sweep", "GIT_AUTHOR_EMAIL": "sweep@invalid", "GIT_COMMITTER_NAME": "sweep",
        "GIT_COMMITTER_EMAIL": "sweep@invalid", "NO_PROXY": "*", "no_proxy": "*", "PYTHONDONTWRITEBYTECODE": "1",
        # state dirs, as in scripts/testing/run-test-group.py
        "AQ_DELEGATION_DIR": f"{tmp}/delegation", "DASHBOARD_DATA_DIR": f"{tmp}/dashboard",
        "RSI_RUNTIME_DIR": f"{tmp}/rsi", "RSI_BACKLOG_FILE": f"{tmp}/issues-backlog.md",
        "PRSI_INCIDENTS_FILE": f"{tmp}/rsi/rsi-incidents.json", "AQ_ONCALL_STATE_DIR": f"{tmp}/oncall",
        "AQ_TRIAGE_STATE_DIR": f"{tmp}/triage", "PULSE_LOG_PATH": f"{tmp}/PULSE.log",
        "RESUME_JSON_PATH": f"{tmp}/RESUME.json",
    })
    for v in URL_VARS:
        env[v] = f"http://{DEAD}"
    for v in PORT_VARS:
        env[v] = "9"
    for v in HOST_VARS:
        env[v] = "127.0.0.1"
    for d in ("home", "run", "tmp", "delegation", "dashboard", "rsi", "oncall", "triage"):
        Path(tmp, d).mkdir(parents=True, exist_ok=True)
    if faketime:
        env["LD_PRELOAD"] = faketime[0]
        env["FAKETIME"] = f"@{faketime[1]}"
        env["FAKETIME_DONT_RESET"] = "1"
    return env


def bwrap_usable() -> bool:
    if not shutil.which("bwrap"):
        return False
    try:
        return subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-net", "--unshare-pid", "true"],
                              capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def bwrap_argv(repo_copy: str, tmp: str, inner: list[str]) -> list[str]:
    a = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
         "--unshare-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session"]
    for masked in ("/run/user", "/run/dbus", "/run/systemd", "/run/docker", "/run/containerd"):
        if os.path.isdir(masked):
            a += ["--tmpfs", masked]
    for sock in ("/run/docker.sock", "/run/podman/podman.sock"):
        if os.path.exists(sock):
            a += ["--ro-bind", "/dev/null", sock]
    # the repo clone and the temp dir are the only writable places; both live under /tmp, a fresh tmpfs in here
    a += ["--bind", tmp, tmp, "--bind", repo_copy, repo_copy, "--chdir", repo_copy]
    return a + inner


def kill_marked(run_id: str) -> int:
    """SIGKILL every process whose environment carries this run's marker (escaped setsid/daemonised children)."""
    needle = f"{MARKER_VAR}={run_id}".encode()
    me = os.getpid()
    n = 0
    for p in os.listdir("/proc"):
        if not p.isdigit() or int(p) == me:
            continue
        try:
            with open(f"/proc/{p}/environ", "rb") as f:
                blob = f.read()
        except OSError:
            continue
        if needle in blob.split(b"\0"):
            try:
                os.kill(int(p), signal.SIGKILL)
                n += 1
            except OSError:
                pass
    return n


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 << 20, 512 << 20))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def interpreter(test: str) -> list[str]:
    return ["node"] if test.endswith(".js") else ["python3"] if test.endswith(".py") else ["bash"]


def execute(test: str, repo_copy: str, tmp: str, run_id: str, timeout: int, sandbox: str,
            faketime: tuple[str, str] | None = None) -> dict:
    env = build_env(tmp, run_id, faketime)
    argv = interpreter(test) + [test]
    if sandbox == "bwrap":
        argv = bwrap_argv(repo_copy, tmp, ["env", "-i"] + [f"{k}={v}" for k, v in env.items()] + argv)
        popen_env = {"PATH": env["PATH"]}
    else:
        popen_env = env
    out_path = Path(tmp) / "out.txt"
    t0 = time.monotonic()
    status, rc = "FAIL", -1
    with open(out_path, "wb") as out:
        proc = subprocess.Popen(argv, cwd=repo_copy, env=popen_env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=_limits)
        try:
            rc = proc.wait(timeout=timeout)
            status = "PASS" if rc == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            status, rc = "TIMEOUT", 124
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.kill()
            proc.wait()
    leftovers = kill_marked(run_id)
    secs = round(time.monotonic() - t0, 1)
    text = out_path.read_bytes()[-65536:].decode("utf-8", "replace")
    return {"status": status, "rc": rc, "secs": secs, "output": text, "leftover_procs": leftovers}


# ---------------------------------------------------------------- analysis

def first_failure(text: str) -> tuple[str, str]:
    """(first failure line, window of text around it used for grouping)."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "(no output)", ""
    tb = [i for i, l in enumerate(lines) if l.startswith("Traceback (most recent call last)")]
    if tb:
        # the exception line closing the LAST traceback: first non-indented line after its frames
        i = tb[-1] + 1
        while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("Traceback")):
            i += 1
        i = min(i, len(lines) - 1)
        return lines[i][:200], "\n".join(lines[max(0, i - 3): i + 3])
    for i, l in enumerate(lines):
        if FAIL_LINE.search(l):
            return l[:200], "\n".join(lines[max(0, i - 2): i + 3])
    return lines[-1][:200], "\n".join(lines[-4:])


def root_cause_group(status: str, window: str) -> str:
    if status == "TIMEOUT":
        return "timeout"
    for name, rx in GROUPS:
        if rx.search(window):
            return name
    return "unclassified"


def static_flags(repo: Path, test: str, today: date) -> dict:
    src = (repo / test).read_text(encoding="utf-8", errors="replace") if (repo / test).is_file() else ""
    rx = PY_ASSERT if test.endswith(".py") else JS_ASSERT if test.endswith(".js") else SH_ASSERT
    future = set()
    for m in DATE_LIT.finditer(src):
        try:
            if date.fromisoformat(m.group(0)) >= today and int(m.group(1)) < 2100:
                future.add(m.group(0))
        except ValueError:  # e.g. 2026-02-30 in a fixture
            pass
    future = sorted(future)
    return {"no_assertions": not rx.search(src), "clock": bool(CLOCK.search(src)),
            "dates": bool(DATE_LIT.search(src)), "future_dates": future}


def family(test: str) -> str:
    stem = Path(test).name
    stem = stem[5:] if stem.startswith("test-") else stem
    return stem.split("-")[0].split(".")[0]


class Sweep:
    def __init__(self, a):
        self.a = a
        self.repo = Path(a.repo).resolve()
        self.today = date.fromisoformat(a.date)
        self.manifest = load_manifest(self.repo)
        self.tests, self.declared, self.exempt = inventory(self.repo, self.manifest)
        self.sandbox = a.sandbox
        self.run_dir = Path(a.workdir or tempfile.mkdtemp(prefix="aq-sweep-tests-", dir="/tmp"))
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state = Path(a.state) if a.state else self.run_dir / "state.jsonl"
        self.lock = threading.Lock()
        self.records: dict[str, dict] = {}
        self.stopped_families: dict[str, str] = {}
        self.deadline = time.monotonic() + a.budget_min * 60
        self.watch: dict[str, float] = {}
        self.noisy: list[str] = []
        self.clones: list[str] = []
        self.ft_mode = False

    # ---- state / resume
    def load_state(self):
        if self.state.is_file():
            for line in self.state.read_text().splitlines():
                try:
                    r = json.loads(line)
                    self.records[r["test"]] = r
                except ValueError:
                    pass

    def save(self, rec: dict):
        with self.lock:
            self.records[rec["test"]] = rec
            with open(self.state, "a") as f:
                f.write(json.dumps(rec) + "\n")

    # ---- live-state watch (belt and braces; the bwrap mount is the actual guard)
    def watch_paths(self) -> list[str]:
        if self.a.no_watch:
            return []
        h = Path(os.path.expanduser("~"))
        main = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"
        cands = [f"{main}/.agent/collaboration/PULSE.log", f"{main}/.agent/collaboration/RESUME.json",
                 f"{main}/.agent/memory/issues-backlog.md", str(h / ".local/share/nixos-ai-stack"),
                 str(h / ".config/zellij"), f"/run/user/{os.getuid()}/zellij", "/var/lib/ai-stack", *self.a.watch]
        return [c for c in cands if os.path.exists(c)]

    @staticmethod
    def stamp(path: str) -> float:
        """max mtime over the path and its first two directory levels."""
        try:
            m = os.stat(path).st_mtime
            if os.path.isdir(path):
                for e in os.scandir(path):
                    m = max(m, e.stat(follow_symlinks=False).st_mtime)
                    if e.is_dir(follow_symlinks=False):
                        try:
                            for e2 in os.scandir(e.path):
                                m = max(m, e2.stat(follow_symlinks=False).st_mtime)
                        except OSError:
                            pass
            return m
        except OSError:
            return 0.0

    def prime_watch(self):
        paths = self.watch_paths()
        first = {p: self.stamp(p) for p in paths}
        if paths:
            time.sleep(3)
        self.watch = {p: first[p] for p in paths if self.stamp(p) == first[p]}
        self.noisy = [p for p in paths if p not in self.watch]

    def watch_changed(self) -> list[str]:
        return [p for p, m in self.watch.items() if self.stamp(p) != m]

    # ---- repo clones (one per worker, reset after a mutating test)
    def make_clone(self, slot: int) -> str:
        dest = str(self.run_dir / f"w{slot}" / "repo")
        shutil.rmtree(dest, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "--shared", str(self.repo), dest], check=True, capture_output=True,
                       env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"})
        return dest

    @staticmethod
    def git(clone: str, *args) -> str:
        r = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", clone, *args],
                           capture_output=True, text=True, timeout=120,
                           env={"PATH": os.environ.get("PATH", "/usr/bin"), "GIT_CONFIG_GLOBAL": "/dev/null",
                                "HOME": "/nonexistent"})
        return r.stdout

    def tree_dirty(self, clone: str) -> list[str]:
        return [l[3:] for l in self.git(clone, "status", "--porcelain", "--untracked-files=all").splitlines()]

    def reset_clone(self, clone: str):
        self.git(clone, "reset", "--hard", "-q")
        self.git(clone, "clean", "-fdxq")

    # ---- one test
    def run_test(self, test: str, slot_q: Queue) -> dict:
        fam = family(test)
        if fam in self.stopped_families:
            return self.not_run(test, f"family '{fam}' stopped: {self.stopped_families[fam]}")
        if time.monotonic() > self.deadline:
            return self.not_run(test, "budget: wall-clock limit reached; re-run with the same --state to resume")
        slot = slot_q.get()
        try:
            clone = self.clones[slot]
            run_id = uuid.uuid4().hex
            tmp = tempfile.mkdtemp(prefix=f"t{slot}-", dir=str(self.run_dir))
            try:
                ft = (self.a.faketime_lib, self.a.faketime_date) if (self.a.faketime_lib and self.ft_mode) else None
                res = execute(test, clone, tmp, run_id, self.a.timeout, self.sandbox, ft)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            rec = {"test": test, **{k: res[k] for k in ("status", "rc", "secs", "leftover_procs")}}
            if res["status"] != "PASS":
                rec["first_failure"], window = first_failure(res["output"])
                rec["group"] = root_cause_group(res["status"], window)
            else:
                rec["first_failure"], rec["group"] = "", ""
            rec["tail"] = "\n".join(res["output"].strip().splitlines()[-6:])[:600]
            rec["ro_blocked"] = bool(re.search(r"Read-only file system|EROFS", res["output"]))
            dirty = self.tree_dirty(clone)
            rec["tree_mutation"] = dirty[:10]
            if dirty:
                self.reset_clone(clone)
            changed = self.watch_changed()
            if changed:
                rec["live_mutation"] = changed
                with self.lock:
                    self.stopped_families[fam] = f"LIVE_MUTATION suspected during {test}: {', '.join(changed)}"
                    # re-baseline so one event does not stop every later family
                    self.watch = {p: self.stamp(p) for p in self.watch}
            return rec
        finally:
            slot_q.put(slot)

    @staticmethod
    def not_run(test: str, why: str) -> dict:
        return {"test": test, "status": "NOT_RUN", "rc": None, "secs": 0, "reason": why, "first_failure": "", "group": ""}

    def pre_skip(self, test: str) -> str | None:
        e = self.exempt.get(test)
        if e and e.get("class") == "live-service" and not self.a.include_live:
            return "live-service: exempt as needing the live stack; not run (use --include-live to run it isolated)"
        if not test.endswith((".py", ".sh", ".js")):
            return "unsupported extension"
        if test.endswith(".js") and not shutil.which("node"):
            return "node not on PATH"
        return None

    def _pool_run(self, fn, items):
        jobs = max(1, min(self.a.jobs, MAX_JOBS))
        self.clones = [self.make_clone(i) for i in range(jobs)]
        slot_q: Queue = Queue()
        for i in range(jobs):
            slot_q.put(i)
        try:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for rec in pool.map(lambda x: fn(x, slot_q), items):
                    self.save(rec)
        finally:
            for c in self.clones:
                shutil.rmtree(Path(c).parent, ignore_errors=True)

    def run_all(self):
        self.load_state()
        todo = [t for t in self.tests if (not self.a.only or any(fnmatch.fnmatch(t, g) for g in self.a.only))]
        pending = []
        for t in todo:
            if t in self.records and self.records[t]["status"] != "NOT_RUN":
                continue
            why = self.pre_skip(t)
            if why:
                self.save(self.not_run(t, why))
            else:
                pending.append(t)
        if not pending:
            return
        self.prime_watch()
        self._pool_run(self.run_test, pending)
        if not self.a.no_rerun:
            # A single re-run of FAIL results (not TIMEOUT: too slow to repeat); a differing outcome marks FLAKY.
            fails = [t for t in pending if self.records[t]["status"] == "FAIL" and "rerun" not in self.records[t]]
            def again(t, slot_q):
                first = self.records[t]
                if time.monotonic() > self.deadline:
                    return first
                second = self.run_test(t, slot_q)
                if second["status"] == "NOT_RUN":
                    return first
                return {**first, "rerun": {"status": second["status"], "first_failure": second.get("first_failure", "")}}
            self._pool_run(again, fails)

    # ---- faketime second run: only passing tests that mention dates/clocks
    def faketime_pass(self):
        if not self.a.faketime_lib:
            return
        self.ft_mode = True
        try:
            cands = [t for t, r in self.records.items() if r["status"] == "PASS" and "faketime" not in r
                     and (lambda s: s["dates"] or s["clock"])(static_flags(self.repo, t, self.today))]
            def go(t, slot_q):
                second = self.run_test(t, slot_q)
                return {**self.records[t], "faketime": {"date": self.a.faketime_date, "status": second["status"],
                                                        "first_failure": second.get("first_failure", "")}}
            self._pool_run(go, cands)
        finally:
            self.ft_mode = False

    # ---- classification
    def classify(self) -> list[dict]:
        out = []
        for t in self.tests:
            r = dict(self.records.get(t) or self.not_run(t, "not reached"))
            ex = self.exempt.get(t)
            raw = r["status"]
            r["exempt_class"] = ex.get("class") if ex else None
            r["exempt_reason"] = ex.get("reason") if ex else None
            cls = raw
            if raw == "FAIL" and r.get("rerun", {}).get("status") == "PASS":
                cls = "FLAKY"
            if ex and ex.get("class") == "known-failing":
                if raw == "PASS":
                    cls = "EXEMPT_NOW_PASSES"
                elif raw in ("FAIL", "TIMEOUT") and cls != "FLAKY":
                    cls = "EXEMPT_STILL_FAILS"
            r["class"] = cls
            f = static_flags(self.repo, t, self.today)
            flags = []
            if t not in self.declared and t not in self.exempt:
                flags.append("UNDECLARED")
            if raw == "PASS" and f["no_assertions"]:
                flags.append("NO_ASSERTIONS")
            ft = r.get("faketime")
            if f["future_dates"] and f["clock"]:
                flags.append("TIME_BOMB")
                r["time_bomb"] = "static: future date literal(s) " + ",".join(f["future_dates"][:3]) + " beside a wall-clock call"
            if ft and ft["status"] != "PASS":
                if "TIME_BOMB" not in flags:
                    flags.append("TIME_BOMB")
                r["time_bomb"] = f"exercised: passes now, {ft['status']} at {ft['date']}: {ft['first_failure']}"
            if r.get("tree_mutation"):
                flags.append("TREE_MUTATION")
            if r.get("live_mutation"):
                flags.append("LIVE_MUTATION")
            if r.get("leftover_procs"):
                flags.append("LEFTOVER_PROCS")
            if r.get("ro_blocked"):
                flags.append("RO_BLOCKED")
            r["flags"] = flags
            out.append(r)
        return out


# ---------------------------------------------------------------- report

def summarize(rows: list[dict]) -> dict:
    counts = {c: sum(1 for r in rows if r["class"] == c) for c in CLASS_ORDER}
    flags = {f: sum(1 for r in rows if f in r["flags"]) for f in FLAGS}
    groups: dict[str, int] = {}
    for r in rows:
        if r["class"] in ("EXEMPT_STILL_FAILS", "FAIL", "TIMEOUT") and r.get("group"):
            groups[r["group"]] = groups.get(r["group"], 0) + 1
    return {"total": len(rows), "counts": counts, "flags": flags,
            "groups": dict(sorted(groups.items(), key=lambda kv: -kv[1]))}


def md_cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")[:160]


def render(sw: Sweep, rows: list[dict], runtime_s: float, argv: list[str]) -> str:
    s = summarize(rows)
    L = [f"# Recovery sweep P2.1: every test file executed ({sw.today})", ""]
    L += ["## Objective", "Execute every test file once, isolated, and produce a dated red list (P2.1, system-integrity-recovery). "
          "Report only: no test and no exemption was changed.", ""]
    L += ["## Workflow/Session IDs", f"Branch feat/sweep-tests, worktree `.agents/delegation/worktrees/p21-tests-sweep`. Date {sw.today}. "
          "Tool: `scripts/governance/sweep-tests.py`; its unit test is `scripts/testing/test-sweep-tests.py`.", ""]
    L += ["## Delegation Decision", "Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17: bounded script, test and report).", ""]
    L += ["## Commands Executed", "```", " ".join(argv), "```",
          f"Isolation: sandbox={sw.sandbox} (read-only filesystem except a per-test temp dir and a private repo clone, no network, "
          f"private pid/ipc/uts, /run/user /run/dbus /run/systemd masked), env whitelist, HOME/XDG/TMPDIR redirected, every service URL "
          f"-> http://{DEAD}, own process group + hard timeout {sw.a.timeout}s + marker sweep, nice 19, {min(sw.a.jobs, MAX_JOBS)} worker(s).", ""]
    ran = [r for r in rows if r["status"] != "NOT_RUN"]
    L += ["## Validation Evidence", f"Runtime of this invocation {runtime_s / 60:.1f} min wall; {len(ran)} of {s['total']} test files executed "
          "(resumed runs accumulate in the state file).", "",
          "### Counts per class", "", "| class | count |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in s["counts"].items()]
    L += ["", "Flags (orthogonal, a test can carry several):", "", "| flag | count |", "|---|---|"]
    L += [f"| {f} | {n} |" for f, n in s["flags"].items()]
    if s["groups"]:
        L += ["", "### Root-cause groups (FAIL, TIMEOUT, EXEMPT_STILL_FAILS)", "", "| group | count |", "|---|---|"]
        L += [f"| {g} | {n} |" for g, n in s["groups"].items()]
    nowpass = [r for r in rows if r["class"] == "EXEMPT_NOW_PASSES"]
    L += ["", f"### EXEMPT_NOW_PASSES ({len(nowpass)}): known-failing exemptions whose test passed; each exemption can be removed", ""]
    L += [f"- `{r['test']}` ({r['secs']}s)" for r in nowpass] or ["- none"]
    other = [r for r in rows if r["class"] == "PASS" and r["exempt_class"]]
    L += ["", f"### Passed here but exempt for another class ({len(other)}); NOT evidence the exemption can go (this run has no live stack)", ""]
    L += [f"- `{r['test']}` [{r['exempt_class']}]" for r in other] or ["- none"]
    L += ["", "### Findings table (everything not a plain PASS)", "",
          "| test | class | exempt | group | first failure / note | flags |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["class"] == "PASS" and not r["flags"]:
            continue
        note = r.get("first_failure") or r.get("reason") or r.get("time_bomb") or ""
        if r["class"] == "FLAKY":
            note = f"1st: {r.get('first_failure', '')} | rerun: {r.get('rerun', {}).get('status')}"
        L.append(f"| `{Path(r['test']).name}` | {r['class']} | {r['exempt_class'] or ''} | {md_cell(r.get('group', ''))} | "
                 f"{md_cell(note)} | {', '.join(r['flags'])} |")
    L += ["", "## Rollback Plan", "Delete this report, the sweep script and its test; nothing else was changed.", ""]
    L += ["## Residual Risk and heuristic limits",
          "- Root-cause groups come from regexes over the text around the first failure line (the exception line of the last traceback, or the first "
          "FAIL/Error line, with 2 to 3 lines of context). 'stale assertion' and 'real product bug (suspect)' cannot be told apart "
          "without reading the test: an AssertionError may be either. A traceback ending in a non-assertion exception is labelled "
          "'real product bug (suspect)'. A test failing for an earlier reason can be filed under a later group, and 'environment' "
          "also catches failures caused by this sweep's own isolation (no network, read-only filesystem, mapped uid).",
          "- NO_ASSERTIONS is a textual check on source (no assert/raise/sys.exit/check-helper tokens for .py; no exit/fail/test/grep -q "
          "tokens or `set -e` for .sh); a test that delegates asserting to a library or subprocess is a false positive, and one with a "
          "decorative `assert True` is a false negative. Only tests that exited 0 are checked.",
          "- TIME_BOMB (static) means a future date literal sits in a test that also reads the wall clock: a candidate, not proof. "
          "The exercised second run (libfaketime) covers only passing tests that mention dates or clocks and only when `--faketime-lib` is given.",
          "- FLAKY is one re-run of FAIL results only; TIMEOUT results are not re-run. A test that fails 1 in 10 and passes both times is not detected.",
          "- Tests marked live-service in the exemption list are NOT_RUN unless `--include-live`. A pass in this sandbox (no network, "
          "read-only filesystem) is not proof a test passes on the host.",
          "- LIVE_MUTATION is detected by mtime of watched live paths during a test window, which only catches writes to them; the read-only "
          "mount is the real guard (an attempted write shows as RO_BLOCKED). TREE_MUTATION means the test wrote inside its private repo clone, which is discarded.", ""]
    nr = [r for r in rows if r["class"] == "NOT_RUN"]
    if nr:
        by: dict[str, int] = {}
        for r in nr:
            k = (r.get("reason") or "").split(":")[0]
            by[k] = by.get(k, 0) + 1
        L += ["### NOT_RUN reasons", ""] + [f"- {k}: {n}" for k, n in sorted(by.items())] + [""]
    if sw.noisy:
        L += ["### Live-state paths excluded from the mutation watch (changed during the idle baseline)", ""] + [f"- `{p}`" for p in sw.noisy] + [""]
    lm = [r for r in rows if "LIVE_MUTATION" in r["flags"]]
    L += ["### LIVE_MUTATION", ""] + ([f"- `{r['test']}`: {', '.join(r['live_mutation'])}" for r in lm] or ["- none observed"]) + [""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--report")
    ap.add_argument("--json")
    ap.add_argument("--state", help="JSONL results file; an existing one is resumed")
    ap.add_argument("--workdir", help="scratch dir (default: new dir under /tmp)")
    ap.add_argument("--jobs", type=int, default=2, help=f"workers, capped at {MAX_JOBS}")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--budget-min", type=float, default=45)
    ap.add_argument("--sandbox", choices=("bwrap", "none"), default="bwrap")
    ap.add_argument("--include-live", action="store_true")
    ap.add_argument("--only", action="append", help="glob of test paths relative to the repo (repeatable)")
    ap.add_argument("--no-watch", action="store_true")
    ap.add_argument("--watch", action="append", default=[], help="extra live path to watch")
    ap.add_argument("--no-rerun", action="store_true")
    ap.add_argument("--faketime-lib")
    ap.add_argument("--faketime-date", default="2027-03-01 12:00:00")
    ap.add_argument("--fail-on", default="")
    a = ap.parse_args(argv)
    if a.sandbox == "bwrap" and not bwrap_usable():
        print("sweep-tests: bwrap is not usable here; refusing to run unisolated (use --sandbox none for fixtures only)", file=sys.stderr)
        return 2
    try:
        os.nice(19)
    except OSError:
        pass
    if shutil.which("ionice"):
        subprocess.run(["ionice", "-c3", "-p", str(os.getpid())], capture_output=True)
    sw = Sweep(a)
    t0 = time.monotonic()
    try:
        sw.run_all()
        sw.faketime_pass()
    finally:
        for p in glob.glob(str(sw.run_dir / "t*-*")):
            shutil.rmtree(p, ignore_errors=True)
    rows = sw.classify()
    runtime = time.monotonic() - t0
    summ = summarize(rows)
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(render(sw, rows, runtime, [Path(sys.argv[0]).name] + (argv if argv is not None else sys.argv[1:])))
    if a.json:
        Path(a.json).write_text(json.dumps({"date": a.date, "summary": summ, "rows": rows}, indent=1))
    print("sweep-tests: " + ", ".join(f"{k}={v}" for k, v in summ["counts"].items()) + f" of {summ['total']} in {runtime / 60:.1f} min")
    print("flags: " + ", ".join(f"{k}={v}" for k, v in summ["flags"].items() if v))
    want = {x for x in a.fail_on.split(",") if x}
    return 1 if any(summ["counts"].get(c) or summ["flags"].get(c) for c in want) else 0


if __name__ == "__main__":
    sys.exit(main())
