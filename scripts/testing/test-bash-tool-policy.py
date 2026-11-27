#!/usr/bin/env python3
"""Hermetic test for bash_tool_policy + aq-bash-tool-policy-hook."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("bash_tool_policy", f"{ROOT}/scripts/ai/lib/bash_tool_policy.py")
assert spec is not None and spec.loader is not None
pol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pol)
os.environ.pop("AQ_BASH_POLICY", None)

CASES = [
    ("cat foo.py", "deny"),
    ("cd x && ls -la", "deny"),
    ("find . -name y", "deny"),
    ("grep -rn z .", "deny"),
    ("echo a; cat b", "deny"),
    ("cat > f <<'EOF'\ncat foo\nEOF", "allow"),
    ("cat <<EOF > f\nx\nEOF", "allow"),
    ("cat a >> f", "allow"),
    ("rg x | head", "allow"),
    ("git log | grep y", "allow"),
    ("git grep z", "allow"),
    ("sed -n 1,5p f", "allow"),
    ("fd y", "allow"),
    ("echo 'a && cat b'", "allow"),
    ("git log |\n grep fix", "allow"),
    ("git log | \n\n grep fix", "allow"),
    ("git log \\\n | grep fix", "allow"),
    ("echo a \\\n && cat foo.py", "deny"),
    ("git log |\n cat foo.py", "allow"),
    ("cat <<EOF\ntext\nEOF\nls", "deny"),
    ("cat <<EOF\ntext\nEOF\nrg x", "allow"),
    ("cat <<'EOF'\nls\nEOF\nrg x", "allow"),
    ('cat <<"EOF"\nls\nEOF\nls', "deny"),
    ("cat <<-EOF\n\tgrep x\n\tEOF\nrg x", "allow"),
    ("cat <<-EOF\n\tgrep x\n\tEOF\ngrep x f", "deny"),
    ("AQ_BASH_POLICY=0 cat foo.py", "deny"),
    ("cat <<\\EOF\nls\nEOF\nrg x", "allow"),
    ("cat <<\\EOF\nbody\nEOF\nls", "deny"),
    ("cat <<-\\EOF\n\tls\n\tEOF\nrg x", "allow"),
    ("cat foo.py 2>/dev/null", "allow"),
    ("cat foo.py > out.txt", "allow"),
    ("cat foo.py 2>&1 | rg x", "allow"),
    ("cat a 1>out", "allow"),
    ("cat a &>out", "allow"),
    ("cat >&2 >out.txt", "allow"),
    ("cat 2>2 >out.txt", "allow"),
    ("cat 2>&1", "allow"),
    ("cat - 2>&1", "allow"),
    ("cat 1>&2", "allow"),
    ("cat 0<&3", "allow"),
    # gemini r3 / shlex rebuild
    ("rg '<<EOF' scripts/\ncat foo.py", "deny"),
    ("echo a\\; cat b", "allow"),
    ("echo don\\'t && ls", "deny"),
    ('echo \\" && cat foo.py', "deny"),
    ("# comment with ' quote\ncat foo.py", "deny"),
    ("cat a>out", "allow"),
    ("cat a >| out", "allow"),
    ("echo ';' && ls", "deny"),
    ("echo 'a;ls'", "allow"),
    ("cat", "allow"),
    ("cat -", "allow"),
    ("cat <<< hi", "allow"),
    ("echo 'unbalanced && cat foo", "allow"),  # ambiguous: shlex fails -> allow
    ("echo \"multi\nline\" \n cat foo.py", "deny"),
    ("echo \"multi\ncat x\"", "allow"),
    ("git log |\n cat foo.py && ls", "deny"),
    ("/bin/cat foo.py", "allow"),  # contract: first word exactly `cat`
]
fails = []
for cmd, want in CASES:
    got, reason = pol.evaluate(cmd)
    if got != want:
        fails.append(f"{cmd!r}: want {want} got {got} ({reason})")
os.environ["AQ_BASH_POLICY"] = "0"
if pol.evaluate("cat foo.py")[0] != "allow":
    fails.append("kill switch failed")
del os.environ["AQ_BASH_POLICY"]

hook = f"{ROOT}/scripts/ai/aq-bash-tool-policy-hook"
with tempfile.TemporaryDirectory() as td:
    log = f"{td}/t/log.jsonl"
    env = dict(os.environ, AQ_BASH_POLICY_LOG=log)

    def run(cmd):
        return subprocess.run([sys.executable, hook], input=json.dumps({"tool_input": {"command": cmd}}),
                              capture_output=True, text=True, env=env)

    r = run("cat secret-token-file.txt")
    if r.returncode != 2 or "ctx_read" not in r.stderr:
        fails.append(f"hook deny: rc={r.returncode} err={r.stderr!r}")
    if run("rg x").returncode != 0:
        fails.append("hook allow rc")
    bad = subprocess.run([sys.executable, hook], input="not json", capture_output=True, text=True, env=env)
    if bad.returncode != 0:
        fails.append("hook not fail-open")
    lines = open(log).read().splitlines()
    if len(lines) != 3 or any("secret-token-file" in ln for ln in lines):
        fails.append(f"telemetry wrong: {lines}")
    else:
        d = json.loads(lines[0])
        if d["decision"] != "deny" or d["token"] != "cat":
            fails.append(f"telemetry fields: {d}")
    run("cd x && ls -la")
    d2 = json.loads(open(log).read().splitlines()[-1])
    if d2["rule"] != "bare-ls" or d2["token"] != "ls":
        fails.append(f"telemetry offender: {d2}")

with tempfile.TemporaryDirectory() as td:
    r = subprocess.run([sys.executable, hook], input=json.dumps({"tool_input": {"command": "rg x"}}),
                       capture_output=True, text=True, cwd=td, env=dict(os.environ, AQ_BASH_POLICY_LOG="bare.jsonl"))
    if r.returncode != 0 or not os.path.exists(f"{td}/bare.jsonl") or len(open(f"{td}/bare.jsonl").read().splitlines()) != 1:
        fails.append("bare-filename log path not written")

if fails:
    print("FAIL\n" + "\n".join(fails))
    sys.exit(1)
print(f"PASS ({len(CASES)} policy cases + kill switch + hook + bare log path)")
