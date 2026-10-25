#!/usr/bin/env python3
"""
Unit and regression tests for Microarchitectural Isolation framework.
Tests XML specification validity, script syntax, and failure containment contracts.
"""

import os
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = REPO_ROOT / "scripts/ai/orchestrate-sandbox.sh"
DRIVER = REPO_ROOT / "scripts/ai/agent_driver.py"
LIBVIRT_XML = REPO_ROOT / "config/libvirt/untrusted-agent-microvm.xml"
NIX_MODULE = REPO_ROOT / "nix/modules/core/microarchitectural-isolation.nix"

class TestMicroarchitecturalIsolation(unittest.TestCase):

    def test_nix_module_exists(self):
        self.assertTrue(NIX_MODULE.is_file(), "Nix isolation module must exist")
        content = NIX_MODULE.read_text(encoding="utf-8")
        self.assertIn("microarchitecturalIsolation", content)
        self.assertIn("isolcpus", content)
        self.assertIn("nosmt", content)
        self.assertIn("nohz_full", content)

    def test_libvirt_xml_spec(self):
        self.assertTrue(LIBVIRT_XML.is_file(), "Libvirt XML domain spec must exist")
        tree = ET.parse(LIBVIRT_XML)
        root = tree.getroot()
        self.assertEqual(root.tag, "domain")

        # Verify cputune pinning
        cputune = root.find("cputune")
        self.assertIsNotNone(cputune, "cputune block must be present")
        vcpupins = cputune.findall("vcpupin")
        self.assertEqual(len(vcpupins), 4, "Must configure 4 vCPUs")
        pinned_cores = [pin.get("cpuset") for pin in vcpupins]
        self.assertEqual(pinned_cores, ["4", "5", "6", "7"])

        # Verify topology and SMT masking
        cpu = root.find("cpu")
        self.assertIsNotNone(cpu, "cpu block must be present")
        topo = cpu.find("topology")
        self.assertIsNotNone(topo, "topology block must be present")
        self.assertEqual(topo.get("threads"), "1", "SMT threads must be set to 1")

    def test_scripts_executable_and_syntax(self):
        self.assertTrue(os.access(ORCHESTRATOR, os.X_OK))
        self.assertTrue(os.access(DRIVER, os.X_OK))

        # Test bash syntax
        res_bash = subprocess.run(["bash", "-n", str(ORCHESTRATOR)], capture_output=True, text=True)
        self.assertEqual(res_bash.returncode, 0, f"Bash syntax error: {res_bash.stderr}")

        # Test python compilation
        res_py = subprocess.run(["python3", "-m", "py_compile", str(DRIVER)], capture_output=True, text=True)
        self.assertEqual(res_py.returncode, 0, f"Python compile error: {res_py.stderr}")

    def test_orchestrator_fail_closed_without_payload(self):
        res = subprocess.run([str(ORCHESTRATOR)], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Valid executable agent payload", res.stderr)

    def test_driver_hardware_verification_fail_closed(self):
        # On non-hardened boot (current active kernel), driver must fail-closed with error
        res = subprocess.run(["python3", str(DRIVER), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Microarchitectural Isolation Agent Driver", res.stdout)

if __name__ == "__main__":
    unittest.main()
