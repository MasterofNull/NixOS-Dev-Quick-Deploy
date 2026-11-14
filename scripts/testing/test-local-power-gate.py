#!/usr/bin/env python3
"""Tests for scripts/ai/lib/power_gate.py using injected fake sysfs roots."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts/ai/lib"
sys.path.insert(0, str(LIB))
import power_gate  # noqa: E402


def w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text + "\n")


def make_sys(
    root: Path,
    ac: str | None = "1",
    bat: str | None = "90",
    temp_mc: str | None = "50000",
) -> Path:
    ps = root / "class/power_supply"
    ps.mkdir(parents=True, exist_ok=True)
    if ac is not None:
        w(ps / "AC/type", "Mains")
        w(ps / "AC/online", ac)
    if bat is not None:
        w(ps / "BAT0/type", "Battery")
        w(ps / "BAT0/capacity", bat)
    (root / "class/thermal").mkdir(parents=True, exist_ok=True)
    if temp_mc is not None:
        w(root / "class/hwmon/hwmon5/name", "k10temp")
        w(root / "class/hwmon/hwmon5/temp1_input", temp_mc)
    else:
        w(root / "class/hwmon/hwmon2/name", "acpitz")  # non-CPU sensor must not count
        w(root / "class/hwmon/hwmon2/temp1_input", "40000")
    return root


class PowerGate(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.load = self.tmp / "loadavg"
        self.set_load(0.5)

    def tearDown(self) -> None:
        self._td.cleanup()

    def set_load(self, v: float) -> None:
        w(self.load, f"0.1 {v} 0.3 1/100 999")

    def run_gate(self, sysroot: Path, state: Path | None = None) -> dict:
        return power_gate.evaluate(sysroot, self.load, ncpu=10, state_file=state)

    def test_ac_ok(self) -> None:
        d = self.run_gate(make_sys(self.tmp / "s", ac="1", bat="10"))
        self.assertTrue(d["ok"], d)

    def test_battery_low_defers(self) -> None:
        d = self.run_gate(make_sys(self.tmp / "s", ac="0", bat="40"))
        self.assertFalse(d["ok"])
        self.assertIn("battery", d["reasons"][0])

    def test_battery_ok_at_50(self) -> None:
        self.assertTrue(self.run_gate(make_sys(self.tmp / "s", ac="0", bat="50"))["ok"])

    def test_hot_defers(self) -> None:
        d = self.run_gate(make_sys(self.tmp / "s", temp_mc="85000"))
        self.assertFalse(d["ok"])
        self.assertIn("85C", d["reasons"][0])

    def test_unreadable_temp_defers(self) -> None:
        d = self.run_gate(make_sys(self.tmp / "s", temp_mc=None))
        self.assertFalse(d["ok"])
        self.assertIn("temp unreadable", d["reasons"][0])

    def test_unreadable_power_defers(self) -> None:
        d = self.run_gate(make_sys(self.tmp / "s", ac=None, bat=None))
        self.assertFalse(d["ok"])
        self.assertIn("power state unreadable", d["reasons"][0])

    def test_unreadable_load_defers(self) -> None:
        self.load.unlink()
        self.assertFalse(self.run_gate(make_sys(self.tmp / "s"))["ok"])

    def test_hysteresis(self) -> None:
        s = make_sys(self.tmp / "s")
        st = self.tmp / "state" / "power-gate.state"
        self.set_load(0.72 * 10)
        self.assertFalse(self.run_gate(s, st)["ok"])  # enters busy
        self.set_load(0.60 * 10)
        self.assertFalse(self.run_gate(s, st)["ok"])  # still busy
        self.set_load(0.50 * 10)
        self.assertTrue(self.run_gate(s, st)["ok"])  # cleared
        self.set_load(0.60 * 10)
        self.assertTrue(self.run_gate(s, st)["ok"])  # clear state: 0.60 < enter

    def _cli(
        self, sysroot: Path, *extra: str, env: dict | None = None
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(LIB / "power_gate.py"),
                "--sys-root",
                str(sysroot),
                "--proc-loadavg",
                str(self.load),
                *extra,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_cli_defer_exit_and_log(self) -> None:
        log = self.tmp / "d" / "deferred.jsonl"
        r = self._cli(
            make_sys(self.tmp / "s", temp_mc="90000"),
            "--defer-log",
            str(log),
            "--task",
            "t",
        )
        self.assertEqual(r.returncode, 5)
        self.assertIn("DEFER", r.stdout)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        self.assertIn('"task": "t"', log.read_text())

    def _delegate(
        self, *extra: str, env_extra: dict | None = None
    ) -> subprocess.CompletedProcess:
        import os

        hot = make_sys(self.tmp / "hot", temp_mc="90000")
        env = {
            **os.environ,
            "AQ_POWER_GATE_SYS": str(hot),
            "AQ_POWER_GATE_LOADAVG": str(self.load),
            "AQ_DELEGATION_DIR": str(self.tmp / "deleg"),
            "AQ_NO_CONSULT": "1",
            "LLAMA_PORT": "1",
            **(env_extra or {}),
        }
        return subprocess.run(
            [
                str(REPO / "scripts/ai/delegate-to-local"),
                "--prompt",
                "x",
                "--mode",
                "direct",
                *extra,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=240,
            check=False,
        )

    def test_delegate_defers_with_exit_5_and_override_bypasses(self) -> None:
        r = self._delegate()
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("power-gate: DEFER", r.stdout)
        self.assertTrue((self.tmp / "deleg/power-gate-deferred.jsonl").exists())
        for kw in (
            {"extra": ("--ignore-power-gate",)},
            {"env_extra": {"AQ_LOCAL_POWER_GATE": "0"}},
        ):
            r2 = self._delegate(*kw.get("extra", ()), env_extra=kw.get("env_extra"))  # type: ignore[arg-type]
            self.assertIn(
                r2.returncode, (3, 4), r2.stdout + r2.stderr
            )  # passed the gate, refused by preflight (no llama on port 1)
            self.assertNotIn("power-gate: DEFER", r2.stdout)


if __name__ == "__main__":
    unittest.main()
