"""aq_usage — usage telemetry for DIRECT aq-* Python entrypoints (producer side).

Each executable aq-<name> Python script carries a small `# aq-usage-hook` block
that loads this module by path and calls record(__file__, __name__). One JSON
line per invocation is appended (O_APPEND, single write, no flock needed):
  {"ts","command","script","source","tool","argv0","cwd","agent","lane"}  (prefix order kept for legacy greps)
Argument values are never logged. Non-fatal; kill switch AQ_USAGE_TELEMETRY=0.
Schema parity with lib/aq-shim.sh.
"""
import os
import re
import sys
import time

_SAFE = re.compile(r"[^A-Za-z0-9._:@-]")


def _djb2(s):
    h = 5381
    for ch in s:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return h


def record(path, modname="__main__"):
    try:
        if modname != "__main__" or os.environ.get("AQ_USAGE_TELEMETRY", "1") == "0":
            return
        if os.environ.get("AQ_VIA_ROUTER"):
            return
        real = os.path.realpath(path)
        self_name = os.path.basename(path)
        name = re.sub(r"(\.py|\.sh)$", "", self_name)
        name = name[3:] if name.startswith("aq-") else name
        repo = os.path.dirname(os.path.dirname(os.path.dirname(real)))
        ledger = os.environ.get("AQ_USAGE_LEDGER") or os.path.join(
            repo, ".agents", "telemetry", "aq-usage.jsonl")
        agent = (os.environ.get("AQ_AGENT_NAME") or os.environ.get("AQ_AGENT")
                 or os.environ.get("AGENT_NAME") or ("claude" if os.environ.get("CLAUDECODE") else ""))
        lane = os.environ.get("AQ_LANE") or os.environ.get("AQ_AGENT_ROLE") or ""
        line = ('{"ts":%d,"command":"%s","script":"%s","source":"direct","tool":"%s","argv0":"%s",'
                '"cwd":"%08x","agent":"%s","lane":"%s"}\n') % (
            int(time.time()), _SAFE.sub("", name), _SAFE.sub("", self_name), _SAFE.sub("", self_name),
            _SAFE.sub("", self_name), _djb2(os.getcwd()), _SAFE.sub("", agent), _SAFE.sub("", lane))
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode())
        finally:
            os.close(fd)
    except Exception:
        pass
