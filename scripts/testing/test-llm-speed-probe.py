#!/usr/bin/env python3
"""Tests for scripts/ai/aq-llm-speed-probe: stub llama server + stubbed /sys,/proc inputs."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "scripts" / "ai" / "aq-llm-speed-probe"
STATE = {"gen": 5.0, "busy": False}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send([{"id": 0, "is_processing": STATE["busy"]}])

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._send({"choices": [{"message": {"content": "one"}}],
                    "timings": {"predicted_per_second": STATE["gen"], "prompt_per_second": 9.0}})


def run(tmp, *, gen, ac, profile, mem_kb, busy=False):
    STATE.update(gen=gen, busy=busy)
    sysfs = Path(tmp, "sys")
    ps = sysfs / "class/power_supply/AC"
    ps.mkdir(parents=True, exist_ok=True)
    (ps / "type").write_text("Mains\n")
    (ps / "online").write_text("1\n" if ac else "0\n")
    Path(tmp, "cpuinfo").write_text("cpu MHz\t\t: 1400.0\ncpu MHz\t\t: 2100.5\n")
    Path(tmp, "meminfo").write_text(f"MemTotal: 28000000 kB\nMemAvailable: {mem_kb} kB\n")
    Path(tmp, "vmstat").write_text("pgmajfault 10\n")
    tel = Path(tmp, "tel")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(LLAMA_URL=f"http://127.0.0.1:{SRV.server_port}", AQ_TELEMETRY_DIR=str(tel),
               AQ_PROBE_SYSFS_ROOT=str(sysfs), AQ_PROBE_CPUINFO=str(Path(tmp, "cpuinfo")),
               AQ_PROBE_MEMINFO=str(Path(tmp, "meminfo")), AQ_PROBE_VMSTAT=str(Path(tmp, "vmstat")),
               AQ_PROBE_POWER_PROFILE=profile, AQ_PROBE_NO_PGREP="1")
    p = subprocess.run([sys.executable, str(PROBE)], env=env, capture_output=True, text=True, timeout=60)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1]), tel / "llm-speed-probe.jsonl"


SRV = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
GOOD_MEM = 25 * 1024 * 1024
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f" {detail}"))
    if not cond:
        fails.append(name)


with tempfile.TemporaryDirectory() as t:
    rc, r, f = run(t, gen=5.0, ac=True, profile="performance", mem_kb=GOOD_MEM)
    check("fast -> ok", rc == 0 and r["status"] == "ok" and r["max_cpu_mhz"] == 2100.5 and f.exists(), (rc, r))
    rc, r, _ = run(t, gen=1.8, ac=False, profile="power-saver", mem_kb=GOOD_MEM)
    check("slow battery -> POWER", rc == 1 and r["status"] == "slow" and r["cause"] == "POWER", (rc, r))
    rc, r, _ = run(t, gen=1.8, ac=True, profile="performance", mem_kb=2 * 1024 * 1024)
    check("slow low mem -> MEMORY", rc == 1 and r["cause"] == "MEMORY", (rc, r))
    rc, r, _ = run(t, gen=1.8, ac=True, profile="performance", mem_kb=GOOD_MEM)
    check("slow otherwise -> UNKNOWN", rc == 1 and r["cause"] == "UNKNOWN", (rc, r))
with tempfile.TemporaryDirectory() as t:
    rc, r, f = run(t, gen=5.0, ac=True, profile="performance", mem_kb=GOOD_MEM, busy=True)
    check("busy -> skipped, exit 0, nothing written", rc == 0 and r["status"] == "skipped" and not f.exists(), (rc, r))

# Ordering-cycle guard: power-profiles-daemon is After=multi-user.target, so a unit that is both
# After= the daemon and WantedBy=multi-user.target makes the transaction cyclic (nixos switch exit 4).
import re  # noqa: E402

_nix = (REPO / "nix/modules/core/power-policy.nix").read_text()
_m = re.search(r"power-policy-apply = \{.*?wantedBy = \[([^\]]*)\];", _nix, re.S)
check("power-policy-apply has wantedBy", bool(_m))
if _m:
    check("power-policy-apply not WantedBy multi-user.target (ordering cycle)", "multi-user.target" not in _m.group(1), _m.group(1))
    check("power-policy-apply WantedBy graphical.target", "graphical.target" in _m.group(1), _m.group(1))

SRV.shutdown()
sys.exit(1 if fails else 0)
