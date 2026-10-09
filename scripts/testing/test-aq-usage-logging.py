#!/usr/bin/env python3
"""aq-* usage logging: every direct invocation appends one JSON line (ci-1).

Covers the producer hooks (bash lib/aq-shim.sh, python lib/aq_usage.py), the
no-argument-values rule, kill switch, non-fatal behaviour, coverage of every
executable scripts/ai/aq-* entrypoint, and the audit's ledger preference.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "scripts" / "ai"
sys.path.insert(0, str(AI / "lib"))
SECRET = "SECRET-TOKEN-xyz123"


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def hook_lines(path):
    src = path.read_text().splitlines(keepends=True)
    if "python" in src[0]:
        i = next(n for n, l in enumerate(src) if "aq-usage-hook" in l)
        j = next(n for n in range(i, len(src)) if src[n].startswith("    pass"))
        return "".join(src[i:j + 1])
    return next(l for l in src if "aq-usage-hook" in l)


def run(script, ledger, extra_env=None, args=()):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AQ_") and k != "CLAUDECODE"}
    env["AQ_USAGE_LEDGER"] = str(ledger)
    env.update(extra_env or {})
    return subprocess.run([str(script), *args], env=env, capture_output=True, text=True, timeout=30)


def read(ledger):
    return [json.loads(l) for l in Path(ledger).read_text().splitlines()] if Path(ledger).exists() else []


def main():
    real_sh = next(p for p in sorted(AI.glob("aq-*")) if os.access(p, os.X_OK)
                   and p.read_text().startswith("#!/usr/bin/env bash") and "aq-usage-hook" in p.read_text())
    real_py = AI / "aq-capability-audit"
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "scripts" / "ai" / "lib").mkdir(parents=True)
        for f in ("aq-shim.sh", "aq_usage.py"):
            shutil.copy(AI / "lib" / f, tdp / "scripts" / "ai" / "lib" / f)
        sh = tdp / "scripts" / "ai" / "aq-fakesh"
        sh.write_text("#!/usr/bin/env bash\n" + hook_lines(real_sh) + "echo ran \"$@\"\nexit ${FAKE_RC:-0}\n")
        py = tdp / "scripts" / "ai" / "aq-fakepy"
        py.write_text('#!/usr/bin/env python3\n"""fake."""\n' + hook_lines(real_py) +
                      "import sys\nprint('ran', sys.argv[1:])\nsys.exit(int(__import__('os').environ.get('FAKE_RC', '0')))\n")
        sh.chmod(0o755)
        py.chmod(0o755)

        led = tdp / "led" / "aq-usage.jsonl"
        for script, name in ((sh, "aq-fakesh"), (py, "aq-fakepy")):
            r = run(script, led, {"AQ_AGENT_NAME": "codex", "AQ_AGENT_ROLE": "impl\"x"}, args=("--token", SECRET))
            check(r.returncode == 0 and "ran" in r.stdout, f"{name} must still run: {r.stderr}")
        rows = read(led)
        check(len(rows) == 2, f"expected 2 lines, got {rows}")
        for row, name in zip(rows, ("aq-fakesh", "aq-fakepy")):
            for k in ("ts", "command", "script", "tool", "argv0", "cwd", "agent", "lane", "source"):
                check(k in row, f"{name}: missing key {k}: {row}")
            check(row["tool"] == name and row["command"] == name[3:], f"{name}: bad identity {row}")
            check(abs(row["ts"] - time.time()) < 60, "ts not current")
            check(row["agent"] == "codex" and row["lane"] == "implx", f"agent/lane from env + sanitised: {row}")
            check(row["cwd"] != str(tdp) and len(row["cwd"]) == 8, "cwd must be a hash, not a path")
        check(SECRET not in led.read_text(), "argument values must never be logged")

        # kill switch / router double-log guard
        for env in ({"AQ_USAGE_TELEMETRY": "0"}, {"AQ_VIA_ROUTER": "1"}):
            led2 = tdp / "k" / "u.jsonl"
            run(sh, led2, env), run(py, led2, env)
            check(read(led2) == [], f"no logging expected with {env}")

        # non-fatal: unwritable ledger and non-zero host exit code preserved
        bad = Path("/proc/nonexistent/aq-usage.jsonl")
        for script in (sh, py):
            r = run(script, bad)
            check(r.returncode == 0, f"{script.name}: unwritable ledger must not fail the host")
            r = run(script, tdp / "rc.jsonl", {"FAKE_RC": "7"})
            check(r.returncode == 7, f"{script.name}: host exit code must be preserved")

        # hot path: one invocation stays cheap
        t = time.time()
        for _ in range(5):
            run(sh, tdp / "perf.jsonl")
        check((time.time() - t) / 5 < 1.0, "bash hook too slow")

    # coverage: every executable aq-* entrypoint carries the hook
    missing = [p.name for p in sorted(AI.glob("aq-*"))
               if p.is_file() and os.access(p, os.X_OK)
               and "aq-usage-hook" not in p.read_text(errors="ignore") and "aq-shim" not in p.read_text(errors="ignore")]
    check(not missing, f"aq-* entrypoints without the usage hook: {missing}")

    # real script end-to-end (read-only --check)
    with tempfile.TemporaryDirectory() as td:
        led = Path(td) / "u.jsonl"
        run(AI / "aq-capability-index", led, args=("--check",))
        rows = read(led)
        check(len(rows) == 1 and rows[0]["tool"] == "aq-capability-index", f"real script not logged: {rows}")

    # audit prefers the exact ledger once it covers enough distinct tools
    import capability_audit as ca
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / "aq-usage.jsonl"
        now = time.time()
        lp.write_text("".join(json.dumps({"ts": now, "script": f"aq-t{i}"}) + "\n" for i in range(12)))
        check(ca.aq_usage_distinct_tools(lp, cutoff=now - 60) >= ca.AQ_USAGE_PREFER_MIN_TOOLS, "distinct tools miscounted")
        lp.write_text(json.dumps({"ts": now, "script": "aq-qa"}) + "\n")
        check(ca.aq_usage_distinct_tools(lp, cutoff=now - 60) < ca.AQ_USAGE_PREFER_MIN_TOOLS, "single tool must not be 'preferred'")
        check(ca.aq_usage_distinct_tools(Path(td) / "missing", cutoff=0) == 0, "missing ledger -> 0")
    print("PASS: aq-* usage logging (hooks, schema, no arg values, kill switch, non-fatal, coverage, audit preference)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
