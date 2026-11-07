#!/usr/bin/env python3
"""Tests for scripts/governance/sweep-tests.py: each class is detected on fixture tests, a timeout leaves no process behind."""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sweep_tests", ROOT / "scripts/governance/sweep-tests.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

FAILS = []


def check(name: str, ok: bool, detail: str = ""):
    print(("PASS: " if ok else "FAIL: ") + name + ("" if ok else f" ({detail})"))
    if not ok:
        FAILS.append(name)


FIXTURES = {
    "test-ok.py": "assert 1 + 1 == 2\n",
    "test-bad.py": "import sys\nprint('x')\nraise AssertionError('expected 1 got 2')\n",
    "test-hang.py": ("import subprocess, os, time\n"
                     "subprocess.Popen(['sleep', '300'], start_new_session=True)\n"
                     "time.sleep(300)\n"),
    "test-flaky.py": ("import os, sys\np = '@FLAGFILE@'\n"
                      "if os.path.exists(p):\n    sys.exit(0)\nopen(p, 'w').close()\nraise AssertionError('first run fails')\n"),
    "test-nowfixed.py": "assert True\n",
    "test-stillbroken.py": "from nonexistent_module_xyz import q\n",
    "test-missingfile.py": "open('/definitely/not/here')\n",
    "test-undeclared.py": "assert True\n",
    "test-noassert.py": "print('hello')\n",
    "test-bomb.py": "import datetime\nassert datetime.datetime.now().year < 2100\nEXPIRES = '2099-12-31'\n",
    "test-live.py": "raise SystemExit(1)\n",
    "test-leak.py": "import subprocess\nsubprocess.Popen(['sleep', '300'], start_new_session=True)\n",
}
MANIFEST = {
    "checks": [{"id": "g", "cmd": "x", "tests": ["scripts/testing/test-" + n[5:] for n in
                ("test-ok.py", "test-bad.py", "test-hang.py", "test-flaky.py", "test-nowfixed.py", "test-stillbroken.py",
                 "test-missingfile.py", "test-noassert.py", "test-bomb.py", "test-live.py", "test-leak.py")]}],
    "test_exempt": [
        {"script": "scripts/testing/test-nowfixed.py", "class": "known-failing", "reason": "r"},
        {"script": "scripts/testing/test-stillbroken.py", "class": "known-failing", "reason": "r"},
        {"script": "scripts/testing/test-missingfile.py", "class": "known-failing", "reason": "r"},
        {"script": "scripts/testing/test-live.py", "class": "live-service", "reason": "r"},
    ],
}


def marked_procs(marker: str) -> int:
    n = 0
    needle = f"{st.MARKER_VAR}={marker}".encode()
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if needle in open(f"/proc/{p}/environ", "rb").read().split(b"\0"):
                    n += 1
            except OSError:
                pass
    return n


def make_repo(d: Path) -> Path:
    (d / "scripts/testing").mkdir(parents=True)
    (d / "config").mkdir()
    for n, body in FIXTURES.items():
        (d / "scripts/testing" / n).write_text(body.replace("@FLAGFILE@", str(d.parent / "flaky-seen")))
    (d / "config/ci-checks.json").write_text(json.dumps(MANIFEST))
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "fixtures"]):
        subprocess.run(["git", "-C", str(d), *cmd], check=True, capture_output=True, env=env)
    return d


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sweep-fixture-") as td:
        repo = make_repo(Path(td) / "repo")
        out = Path(td) / "out.json"
        env = dict(os.environ)
        t0 = time.monotonic()
        r = subprocess.run([sys.executable, str(ROOT / "scripts/governance/sweep-tests.py"), "--repo", str(repo),
                            "--sandbox", "none", "--no-watch", "--timeout", "4", "--date", "2026-11-06",
                            "--workdir", str(Path(td) / "work"), "--json", str(out)],
                           capture_output=True, text=True, env=env, timeout=120)
        check("sweep exits 0 (report only)", r.returncode == 0, r.stdout + r.stderr)
        rows = {Path(x["test"]).name: x for x in json.loads(out.read_text())["rows"]}
        cls = lambda n: rows[n]["class"]
        check("PASS detected", cls("test-ok.py") == "PASS", str(cls("test-ok.py")))
        check("FAIL carries the first failure line", cls("test-bad.py") == "FAIL" and "AssertionError" in rows["test-bad.py"]["first_failure"])
        check("FAIL grouped as stale assertion", rows["test-bad.py"]["group"] == "stale assertion", rows["test-bad.py"]["group"])
        check("TIMEOUT detected within the hard limit", cls("test-hang.py") == "TIMEOUT" and time.monotonic() - t0 < 100)
        check("FLAKY: fails then passes on the single re-run", cls("test-flaky.py") == "FLAKY", cls("test-flaky.py"))
        check("EXEMPT_NOW_PASSES detected", cls("test-nowfixed.py") == "EXEMPT_NOW_PASSES")
        check("EXEMPT_STILL_FAILS grouped: missing module", cls("test-stillbroken.py") == "EXEMPT_STILL_FAILS"
              and rows["test-stillbroken.py"]["group"] == "missing module", rows["test-stillbroken.py"]["group"])
        check("EXEMPT_STILL_FAILS grouped: missing file", rows["test-missingfile.py"]["group"] == "missing file")
        check("live-service exemption is NOT_RUN with a reason", cls("test-live.py") == "NOT_RUN" and "live-service" in rows["test-live.py"]["reason"])
        check("UNDECLARED flagged", "UNDECLARED" in rows["test-undeclared.py"]["flags"] and "UNDECLARED" not in rows["test-ok.py"]["flags"])
        check("NO_ASSERTIONS flagged only on the assertion-free test", "NO_ASSERTIONS" in rows["test-noassert.py"]["flags"]
              and "NO_ASSERTIONS" not in rows["test-ok.py"]["flags"])
        check("TIME_BOMB static candidate flagged", "TIME_BOMB" in rows["test-bomb.py"]["flags"] and "TIME_BOMB" not in rows["test-ok.py"]["flags"])
        check("escaped child process is reported as LEFTOVER_PROCS", "LEFTOVER_PROCS" in rows["test-leak.py"]["flags"])
        check("timeout left no marked process behind", rows["test-hang.py"]["leftover_procs"] >= 1)

        # direct: a hung test with an escaped child leaves nothing alive after execute()
        tmp = tempfile.mkdtemp(dir=td)
        run_id = "unit" + str(os.getpid())
        res = st.execute("scripts/testing/test-hang.py", str(repo), tmp, run_id, 2, "none")
        time.sleep(0.3)
        check("execute(): TIMEOUT status", res["status"] == "TIMEOUT")
        check("execute(): no process with the run marker survives", marked_procs(run_id) == 0, str(marked_procs(run_id)))

        # isolation of the child environment
        e = st.build_env(tmp, "x")
        check("env: HOME and TMPDIR inside the temp dir", e["HOME"].startswith(tmp) and e["TMPDIR"].startswith(tmp))
        check("env: service URLs point at the dead port", e["HYBRID_URL"].endswith(st.DEAD) and e["AIDB_URL"].endswith(st.DEAD))
        os.environ["GITHUB_TOKEN"] = "secret"
        check("env: tokens are not inherited", "GITHUB_TOKEN" not in st.build_env(tmp, "x"))
        check("jobs are capped at 2", st.MAX_JOBS == 2)

        # the bwrap guard, when available: a write outside the temp dirs must be refused
        if st.bwrap_usable():
            probe = Path(td) / "repo/scripts/testing/test-probe.py"
            probe.write_text("import socket, sys\nopen('/home/sweep-probe', 'w')\n")
            tmp2 = tempfile.mkdtemp(dir=td)
            res = st.execute("scripts/testing/test-probe.py", str(repo), tmp2, "probe" + str(os.getpid()), 20, "bwrap")
            check("bwrap: a write outside the temp dirs is refused", res["status"] == "FAIL" and "Read-only" in res["output"], res["output"][-200:])
            srv = socket.socket()
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            probe.write_text(f"import socket\ns = socket.socket()\ns.settimeout(3)\ns.connect(('127.0.0.1', {srv.getsockname()[1]}))\n")
            res = st.execute("scripts/testing/test-probe.py", str(repo), tmp2, "probe2" + str(os.getpid()), 20, "bwrap")
            srv.close()
            check("bwrap: a host loopback listener is unreachable", res["status"] == "FAIL", res["output"][-200:])
        else:
            print("SKIP: bwrap not usable here; sandbox guard not exercised")
    print("PASS: sweep-tests" if not FAILS else f"FAILED: {FAILS}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
