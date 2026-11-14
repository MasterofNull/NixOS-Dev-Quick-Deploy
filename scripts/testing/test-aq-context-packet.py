#!/usr/bin/env python3
"""aq-context-packet: cap, determinism, latency, degrade, refuse on real repo files."""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = str(REPO / "scripts/ai/aq-context-packet")
CASES = [  # (file, symbol)
    ("scripts/ai/aq-graph-query", "emit"),
    ("scripts/ai/lib/understand_graph.py", "neighbors"),
    ("scripts/testing/run-test-group.py", "tree_state"),
]
LATENCY_MS_LIMIT = 500  # generous for CI; target is <200 ms, real numbers are printed
fails = []


def run(args):
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, cwd=REPO)
    return p, (time.perf_counter() - t0) * 1000


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


for f, sym in CASES:
    a, ms_a = run([f, "-s", sym, "--json"])
    b, ms_b = run([f, "-s", sym, "--json"])
    check(a.returncode == 0, f"{f}:{sym} exit 0")
    if a.returncode:
        print(a.stderr)
        continue
    pk = json.loads(a.stdout)
    est = pk["header"]["token_estimate"]
    check(est <= 2500, f"{f}:{sym} under cap ({est} est tokens)")
    check(a.stdout == b.stdout, f"{f}:{sym} byte-identical across runs")
    best = min(ms_a, ms_b)
    print(f"INFO {f}:{sym} latency {ms_a:.0f} ms / {ms_b:.0f} ms")
    check(best < LATENCY_MS_LIMIT, f"{f}:{sym} latency {best:.0f} ms < {LATENCY_MS_LIMIT} ms")

f, sym = CASES[1]
p, _ = run([f, "-s", sym, "--max-tokens", "120", "--json"])
d = json.loads(p.stdout) if p.returncode == 0 else {}
check(p.returncode == 0 and d.get("header", {}).get("degraded") is True,
      "tiny cap degrades (degraded=true)")
check(all(t["body"] is None for e in d.get("files", []) for t in e["targets"]) and d != {},
      "degraded packet carries signatures only for targets")
p, _ = run([f, "-s", sym, "--max-tokens", "5"])
check(p.returncode != 0 and "refused" in p.stderr, "target dropped -> nonzero exit")
p, _ = run([f, "-s", "no_such_symbol_xyz"])
check(p.returncode != 0, "unknown symbol -> nonzero exit")

sys.exit(1 if fails else 0)
