#!/usr/bin/env python3
"""Fixture tests for aq-closure-scan summarisation and nix-closure RSI intake mapping."""
import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


class GrypeConfig(unittest.TestCase):
    def test_repository_config_in_both_live_paths(self):
        for triage in (False, True):
            for present in (False, True):
                with self.subTest(triage=triage, present=present), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    config = root / ".grype.yaml"
                    if present:
                        config.write_text("ignore: []\n")
                    calls = []

                    def fake_run(pkg, args, timeout, cwd=None):
                        if pkg == "sbomnix":
                            Path(args[args.index("--cdx") + 1]).write_text(
                                json.dumps({"components": [{"name": "fixture"}]}))
                            if "--csv" in args:
                                Path(args[args.index("--csv") + 1]).write_text("name,version\n")
                        elif pkg == "grype":
                            calls.append(args)
                        return subprocess.CompletedProcess([], 0, '{"matches": []}', "")

                    with patch.object(scan, "REPO_ROOT", root), \
                         patch.object(scan, "_nix_run", side_effect=fake_run), \
                         patch.object(scan.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), \
                         patch.object(scan, "fetch_track_versions", return_value={}):
                        if triage:
                            scan.triage_scan("/fixture", 5)
                        else:
                            scan.scan("/fixture", root / "sbom.json", None, 5, 5)
                    self.assertEqual(len(calls), 1)
                    if present:
                        self.assertIn("-c", calls[0])
                        self.assertEqual(calls[0][calls[0].index("-c") + 1], str(config))
                    else:
                        self.assertNotIn("-c", calls[0])


class Triage(unittest.TestCase):
    """Nix-aware triage classification (offline fixtures; no network, no nix)."""

    GRYPE = {"matches": [
        {"vulnerability": {"id": "CVE-2026-1", "severity": "Critical", "fix": {"versions": ["1.2.4"]}},
         "artifact": {"name": "libfoo", "version": "1.2.3"}},   # patched via sbom csv
        {"vulnerability": {"id": "CVE-2026-2", "severity": "High", "fix": {"versions": []}},
         "artifact": {"name": "libbar", "version": "2.0"}},     # fixed in unstable
        {"vulnerability": {"id": "CVE-2026-3", "severity": "Medium", "fix": {"versions": []}},
         "artifact": {"name": "libbaz", "version": "3.0"}},     # no fix
        {"vulnerability": {"id": "CVE-2026-4", "severity": "Low"},
         "artifact": {"name": "libqux", "version": "4.0"}},     # repology undecided
        {"vulnerability": {"id": "CVE-2026-5", "severity": "High"},
         "artifact": {"name": "libnew", "version": "5.0"}},     # no triage row
        {"vulnerability": {"id": "CVE-2026-2", "severity": "High"},
         "artifact": {"name": "libbar", "version": "2.0"}},     # duplicate
    ]}
    SBOM_CSV = "pname,version,patches\nlibfoo,1.2.3,/nix/store/x-CVE-2026-1.patch other.patch\nlibbar,2.0,\n"
    TRIAGE_CSV = (
        "vuln_id,url,package,severity,version_local,version_nixpkgs,version_upstream,package_repology,classify\n"
        "CVE-2026-2,u,libbar,high,2.0,2.1,2.1,libbar,fix_update_to_version_nixpkgs\n"
        "CVE-2026-3,u,libbaz,medium,3.0,3.0,3.0,libbaz,fix_not_available\n"
        "CVE-2026-4,u,libqux,low,4.0,,,,err_missing_repology_version\n")

    def _run(self, with_triage=True):
        with tempfile.TemporaryDirectory() as tmp:
            g, c, t = Path(tmp) / "g.json", Path(tmp) / "s.csv", Path(tmp) / "t.csv"
            g.write_text(json.dumps(self.GRYPE))
            c.write_text(self.SBOM_CSV)
            t.write_text(self.TRIAGE_CSV)
            return scan.triage_scan("/x", 5, {"grype_json": g, "sbom_csv": c, "triage_csv": t if with_triage else None})

    def test_classes_and_counts(self):
        rep = self._run()
        cls = {f["id"]: f["class"] for f in rep["findings"]}
        self.assertEqual(cls, {"CVE-2026-1": scan.CLASS_PATCHED, "CVE-2026-2": scan.CLASS_FIXED_NIXPKGS,
                               "CVE-2026-3": scan.CLASS_NO_FIX, "CVE-2026-4": scan.CLASS_REVIEW,
                               "CVE-2026-5": scan.CLASS_REVIEW})
        self.assertEqual(rep["total"], 5)  # duplicate collapsed
        self.assertEqual(rep["by_class"][scan.CLASS_PATCHED]["critical"], 1)

    def test_patch_evidence_cites_patch_file(self):
        f = next(f for f in self._run()["findings"] if f["id"] == "CVE-2026-1")
        self.assertIn("CVE-2026-1.patch", f["evidence"])
        self.assertNotIn("other.patch", f["evidence"])

    def test_actionable_groups_exclude_patched_and_sort_by_severity(self):
        groups = self._run()["actionable_groups"]
        self.assertTrue(all(g["class"] != scan.CLASS_PATCHED for g in groups))
        self.assertIn("fast-lane promotion of libbar", groups[0]["root_fix"])
        self.assertEqual(groups[0]["severity"]["high"], 1)

    def test_backend_unavailable_degrades_to_review_not_clean(self):
        rep = self._run(with_triage=False)
        cls = {f["id"]: f["class"] for f in rep["findings"]}
        self.assertEqual(cls["CVE-2026-1"], scan.CLASS_PATCHED)   # patch rule needs no network
        self.assertEqual(cls["CVE-2026-2"], scan.CLASS_REVIEW)

    def test_version_compare_fallback_when_repology_down(self):
        def m(vid, ver, fixes, pkg="libbar", constraint=None):
            out = {"vulnerability": {"id": vid, "severity": "High", "fix": {"versions": fixes}},
                   "artifact": {"name": pkg, "version": ver}}
            if constraint is not None:
                out["matchDetails"] = [{"found": {"versionConstraint": constraint}}]
            return out
        grype = {"matches": [
            m("CVE-A", "2.0", ["2.1"]),                       # only unstable head reaches 2.1
            m("CVE-B", "2.0", ["9.0"]),                       # nobody packages 9.0
            m("CVE-C", "2.0", ["2.0.5"]),                     # stable head already has it
            m("CVE-D", "2.0", []),                            # no fix data -> never auto-classed
            m("CVE-E", "2.0", ["2.0", "1.9"]),                # installed >= every fix -> human decides
            m("CVE-F", "2.0", ["1.9.9", "2.0.8", "2.1.1"]),   # backport list: installed branch (2.0.x) fix wins
            m("CVE-G", "1.0", ["1.0.5"], pkg="libold"),       # closure carries older variant than nixpkgs ships
            m("CVE-H", "2.0", ["2.1"], pkg="libpin"),         # locked unstable already has the fix
            m("CVE-I", "2.0", [], constraint=">= 1.0, <= 2.0 (unknown)"),   # stable head 2.0.9 is newer than last-affected
            m("CVE-J", "2.0", [], constraint="<= 2.1.5 (unknown)"),         # nothing newer than last-affected exists
            m("CVE-K", "2.0", [], constraint="none (unknown)"),             # unbounded CPE
            m("CVE-L", "2.0", [], constraint=">= 1.0 (unknown)"),           # open-ended range
            m("CVE-M", "2.0", [], constraint="<= 1.5b1 (unknown)"),         # installed already newer than last-affected
        ]}
        tv = {"stable_pinned": {"libbar": "2.0", "libold": "3.4", "libpin": "2.0"},
              "stable_head": {"libbar": "2.0.9", "libold": "3.5", "libpin": "2.0"},
              "unstable_pinned": {"libbar": "2.0", "libpin": "2.1"},
              "unstable_head": {"libbar": "2.1.5", "libpin": "2.1.2"}}
        cls = {f["id"]: f for f in scan.classify_findings(grype, {}, None, tv)}
        self.assertEqual(cls["CVE-A"]["cls"], scan.CLASS_FIXED_NIXPKGS)
        self.assertIn("nixpkgs-unstable + fast-lane", cls["CVE-A"]["root_fix"])
        self.assertEqual(cls["CVE-C"]["cls"], scan.CLASS_FIXED_STABLE)
        self.assertEqual(cls["CVE-B"]["cls"], scan.CLASS_FIXED_UPSTREAM)
        self.assertEqual(cls["CVE-D"]["cls"], scan.CLASS_REVIEW)
        self.assertEqual(cls["CVE-E"]["cls"], scan.CLASS_REVIEW)
        self.assertEqual(cls["CVE-F"]["cls"], scan.CLASS_FIXED_STABLE)  # 2.0.8 <= stable head 2.0.9
        self.assertEqual(cls["CVE-G"]["cls"], scan.CLASS_LEGACY)
        self.assertEqual(cls["CVE-H"]["cls"], scan.CLASS_FIXED_NIXPKGS)
        self.assertTrue(cls["CVE-H"]["root_fix"].startswith("fast-lane promotion of libpin"))
        self.assertEqual(cls["CVE-I"]["cls"], scan.CLASS_FIXED_STABLE)
        self.assertEqual(cls["CVE-J"]["cls"], scan.CLASS_NO_FIX)
        self.assertEqual(cls["CVE-K"]["cls"], scan.CLASS_UNBOUNDED)
        self.assertEqual(cls["CVE-L"]["cls"], scan.CLASS_UNBOUNDED)
        self.assertEqual(cls["CVE-M"]["cls"], scan.CLASS_REVIEW)

    def test_version_ge_edges(self):
        self.assertTrue(scan.version_ge("1.10", "1.9"))
        self.assertTrue(scan.version_ge("2.0", "2.0.0"))
        self.assertFalse(scan.version_ge("1.26.11", "1.28"))
        self.assertIsNone(scan.version_ge("unstable", "1.0"))
        self.assertIsNone(scan.version_ge("1.0.10", "2025-09-16"))  # date-stamped fix is not comparable

    def test_patch_names_deduped_and_hash_stripped(self):
        h = "0" * 32
        ev = scan.patch_evidence("CVE-9", f"/nix/store/{h}-CVE-9.patch /nix/store/{h}-CVE-9.patch")
        self.assertEqual(ev, "CVE-9.patch")

    def test_deterministic(self):
        self.assertEqual(json.dumps(self._run(), sort_keys=True), json.dumps(self._run(), sort_keys=True))

    def test_cli_offline_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            g, c, o = Path(tmp) / "g.json", Path(tmp) / "s.csv", Path(tmp) / "out.json"
            g.write_text(json.dumps(self.GRYPE))
            c.write_text(self.SBOM_CSV)
            r = subprocess.run([str(SCAN), "--triage-json", str(o), "--grype-json", str(g), "--sbom-csv", str(c)],
                               capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(o.read_text())["total"], 5)


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
