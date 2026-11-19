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

    def _env(self, **kv: str):
        import os

        saved = {k: os.environ.get(k) for k in kv}
        os.environ.update(kv)

        def restore() -> None:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        self.addCleanup(restore)

    def test_env_min_battery_override(self) -> None:
        s = make_sys(self.tmp / "s", ac="0", bat="40")
        self._env(AQ_POWER_GATE_MIN_BATTERY_PCT="30")
        self.assertTrue(self.run_gate(s)["ok"])
        self._env(AQ_POWER_GATE_MIN_BATTERY_PCT="80")
        d = self.run_gate(s)
        self.assertFalse(d["ok"])
        self.assertIn("below 80%", d["reasons"][0])

    def test_env_max_temp_override(self) -> None:
        s = make_sys(self.tmp / "s", temp_mc="85000")
        self._env(AQ_POWER_GATE_MAX_TEMP_C="90")
        self.assertTrue(self.run_gate(s)["ok"])
        self._env(AQ_POWER_GATE_MAX_TEMP_C="60")
        self.assertFalse(self.run_gate(make_sys(self.tmp / "s2", temp_mc="65000"))["ok"])

    def test_bad_env_values_fall_back(self) -> None:
        self._env(AQ_POWER_GATE_MAX_TEMP_C="hot", AQ_POWER_GATE_MIN_BATTERY_PCT="x")
        self.assertEqual(power_gate.max_temp_c(self.tmp), 80.0)
        self.assertEqual(power_gate.min_battery_pct(), 50)

    def test_non_finite_env_values_fail_closed_to_default(self) -> None:
        import contextlib
        import io

        for bad in ("nan", "NaN", "inf", "-inf", "Infinity"):
            self._env(
                AQ_POWER_GATE_MAX_TEMP_C=bad,
                AQ_POWER_GATE_MIN_BATTERY_PCT=bad,
                AQ_POWER_GATE_TEMP_MARGIN_C=bad,
            )
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(power_gate.max_temp_c(self.tmp), 80.0, bad)
                self.assertEqual(power_gate.min_battery_pct(), 50, bad)
            self.assertIn("non-finite", err.getvalue())
        # A hot CPU must still defer (nan used to disable the ceiling).
        self._env(AQ_POWER_GATE_MAX_TEMP_C="nan")
        self.assertFalse(self.run_gate(make_sys(self.tmp / "hot", temp_mc="95000"))["ok"])
        # nan margin must not poison the derived ceiling.
        self._env(AQ_POWER_GATE_TEMP_MARGIN_C="nan")
        s = self.tmp / "d"
        w(s / "class/hwmon/hwmon0/name", "k10temp")
        w(s / "class/hwmon/hwmon0/temp1_crit", "95000")
        self.assertEqual(power_gate.max_temp_c(s), 80.0)

    def test_temp_derived_from_hwmon_crit(self) -> None:
        s = make_sys(self.tmp / "s", temp_mc="72000")
        w(s / "class/hwmon/hwmon5/temp1_crit", "85000")  # fanless: crit 85 -> limit 70
        self.assertEqual(power_gate.max_temp_c(s), 70.0)
        d = self.run_gate(s)
        self.assertFalse(d["ok"])
        self.assertIn("72C >= 70C", d["reasons"][0])

    def test_temp_derived_server_class_cpu_allows_higher(self) -> None:
        s = make_sys(self.tmp / "s", temp_mc="85000")
        w(s / "class/hwmon/hwmon5/temp1_crit", "105000")
        self.assertEqual(power_gate.max_temp_c(s), 90.0)
        self.assertTrue(self.run_gate(s)["ok"])

    def test_temp_derived_from_thermal_zone_trips(self) -> None:
        s = make_sys(self.tmp / "s")
        z = s / "class/thermal/thermal_zone0"
        w(z / "type", "x86_pkg_temp")
        w(z / "trip_point_0_type", "passive")
        w(z / "trip_point_0_temp", "60000")  # passive trip is ignored
        w(z / "trip_point_1_type", "critical")
        w(z / "trip_point_1_temp", "95000")
        self.assertEqual(power_gate.max_temp_c(s), 80.0)
        self._env(AQ_POWER_GATE_TEMP_MARGIN_C="25")
        self.assertEqual(power_gate.max_temp_c(s), 70.0)

    def test_derived_temp_is_clamped(self) -> None:
        s = make_sys(self.tmp / "s")
        w(s / "class/hwmon/hwmon5/temp1_crit", "60000")
        self.assertEqual(power_gate.max_temp_c(s), 50.0)  # floor
        w(s / "class/hwmon/hwmon5/temp1_crit", "130000")
        self.assertEqual(power_gate.max_temp_c(s), 100.0)  # ceiling

    def test_non_cpu_trip_points_ignored(self) -> None:
        s = make_sys(self.tmp / "s")
        w(s / "class/hwmon/hwmon2/name", "acpitz")
        w(s / "class/hwmon/hwmon2/temp1_crit", "60000")
        self.assertEqual(power_gate.max_temp_c(s), 80.0)

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
        self.assertEqual(oct(log.stat().st_mode & 0o777), "0o600")

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
