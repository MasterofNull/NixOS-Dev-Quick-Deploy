#!/usr/bin/env python3
"""Fixture tests for aq-closure-scan summarisation and nix-closure RSI intake mapping."""
import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "scripts" / "security" / "aq-closure-scan"
INTAKE = ROOT / "scripts" / "security" / "rsi-intake-code-scanning.py"

loader = importlib.machinery.SourceFileLoader("aq_closure_scan", str(SCAN))
spec = importlib.util.spec_from_loader("aq_closure_scan", loader)
scan = importlib.util.module_from_spec(spec)
loader.exec_module(scan)


def _match(vid, name, ver, sev):
    return {"vulnerability": {"id": vid, "severity": sev}, "artifact": {"name": name, "version": ver}}


class Summarize(unittest.TestCase):
    def test_counts_dedup_and_ranking(self):
        doc = {"matches": [
            _match("CVE-1", "openssl", "3.0", "Critical"),
            _match("CVE-1", "openssl", "3.0", "Critical"),  # duplicate id/pkg
            _match("CVE-2", "openssl", "3.0", "High"),
            _match("CVE-3", "zlib", "1.2", "Medium"),
            _match("CVE-4", "curl", "8.0", "Low"),
            _match("CVE-5", "curl", "8.0", "Negligible"),
        ]}
        out = scan.summarize(doc, top=2)
        self.assertEqual((out["critical"], out["high"], out["medium"], out["low"]), (1, 1, 1, 1))
        self.assertEqual(out["unknown"], 1)
        self.assertEqual(out["total"], 5)
        self.assertEqual(out["top_packages"][0]["package"], "openssl 3.0")
        self.assertEqual(len(out["top_packages"]), 2)

    def test_empty(self):
        out = scan.summarize({}, top=5)
        self.assertEqual(out["total"], 0)

    def test_sarif_results_get_non_empty_artifact_location(self):
        # grype emits uri "" for SBOM inputs; GitHub code scanning rejects that upload.
        doc = {"runs": [{"results": [
            {"ruleId": "CVE-1-redis", "locations": [{"physicalLocation": {"artifactLocation": {"uri": ""}}}]},
            {"ruleId": "CVE-2-zlib"},
            {"ruleId": "CVE-3-curl", "locations": [{"physicalLocation": {"artifactLocation": {"uri": "keep.txt"}}}]},
        ]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.sarif"
            path.write_text(json.dumps(doc))
            self.assertEqual(scan.anchor_sarif(path), 2)
            for res in json.loads(path.read_text())["runs"][0]["results"]:
                self.assertTrue(res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"])
            self.assertEqual(json.loads(path.read_text())["runs"][0]["results"][2]["locations"][0]
                             ["physicalLocation"]["artifactLocation"]["uri"], "keep.txt")

    def test_scanner_crash_is_error_not_clean(self):
        def boom(*a, **k):
            raise scan.ScanError("grype exited 1")
        orig = scan._nix_run
        scan._nix_run = boom
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(scan.ScanError):
                    scan.scan("/nonexistent", Path(tmp) / "s.cdx.json", None, 5, 5)
        finally:
            scan._nix_run = orig

    def test_empty_sbom_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            sbom = Path(tmp) / "s.cdx.json"

            def fake(pkg, args, timeout, cwd=None):
                sbom.write_text(json.dumps({"components": []}))
            orig = scan._nix_run
            scan._nix_run = fake
            try:
                with self.assertRaises(scan.ScanError):
                    scan.scan("/x", sbom, None, 5, 5)
            finally:
                scan._nix_run = orig


class IntakeMapping(unittest.TestCase):
    def _plan(self, category):
        alert = {"state": "open",
                 "most_recent_instance": {"category": category, "message": {"text":
                     "Package: openssl\nInstalled Version: 3.0.1\nFixed Version: 3.0.9"}},
                 "rule": {"security_severity_level": "high"}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump([alert], fh)
        try:
            r = subprocess.run([str(INTAKE), "--alerts", fh.name, "--dry-run"],
                               capture_output=True, text=True, check=False)
        finally:
            Path(fh.name).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout.strip().split("\n")[-2])[0]

    def test_nix_closure_maps_to_nix_flake_update(self):
        inc = self._plan("nix-closure")
        self.assertEqual(inc["manifest"], "nix/")
        self.assertIn("nix flake update / fast-lane promotion", inc["root_fix"])
        self.assertIn("flake.lock", inc["root_fix"])
        self.assertNotIn("Dockerfile", inc["root_fix"])

    def test_grype_sarif_message_format_parsed(self):
        alert = {"state": "open",
                 "most_recent_instance": {"category": "nix-closure", "message": {"text":
                     "A critical vulnerability in nix package: redis, version 8.8.3 was found "}},
                 "rule": {"security_severity_level": "critical"}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump([alert], fh)
        try:
            r = subprocess.run([str(INTAKE), "--alerts", fh.name, "--dry-run"],
                               capture_output=True, text=True, check=False)
        finally:
            Path(fh.name).unlink(missing_ok=True)
        inc = json.loads(r.stdout.strip().split("\n")[-2])[0]
        self.assertEqual((inc["package"], inc["installed"]), ("redis", "8.8.3"))

    def test_legacy_category_still_maps_to_manifest(self):
        inc = self._plan("trivy-custom-nixos-docs")
        self.assertTrue(inc["manifest"].endswith("requirements.txt") or inc["manifest"].endswith("security.yml"))
        self.assertIn("raise the minimum-version floor", inc["root_fix"])


if __name__ == "__main__":
    unittest.main()
