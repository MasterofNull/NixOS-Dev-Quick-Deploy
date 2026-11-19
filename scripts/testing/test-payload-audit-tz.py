#!/usr/bin/env python3
"""Regression: aq-payload-audit 6b severity logic is timezone-independent (CI runs in UTC, dev in local TZ)."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TZS = ("UTC", "America/Los_Angeles", "Asia/Kolkata", "Pacific/Kiritimati")
CHILD = (
    "import os,sys,time,importlib.util;"
    "os.environ['TZ']=sys.argv[1];time.tzset();"
    "spec=importlib.util.spec_from_file_location('t',sys.argv[2]);m=importlib.util.module_from_spec(spec);"
    "sys.modules['t']=m;spec.loader.exec_module(m);m.test_6b_reset_severity();print('ok')"
)


def main() -> int:
    rc = 0
    for tz in TZS:
        r = subprocess.run([sys.executable, "-c", CHILD, tz, str(HERE / "test-payload-audit-routine.py")],
                           capture_output=True, text=True)
        ok = r.returncode == 0 and "ok" in r.stdout
        print(f"{'PASS' if ok else 'FAIL'} test_6b_reset_severity TZ={tz}")
        if not ok:
            print(r.stdout + r.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
