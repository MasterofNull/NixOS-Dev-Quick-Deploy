#!/usr/bin/env python3
"""Guard the nix-closure-vuln-scan job in security.yml (replaces container Trivy jobs).

Fail-open scanning would silently drop security coverage, so assert the job
builds the closure, scans it without error suppression, uploads SARIF under
category nix-closure, and that no container-image scan jobs creep back in.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "security.yml").read_text())
JOB = WORKFLOW["jobs"]["nix-closure-vuln-scan"]
STEPS = JOB["steps"]


def _index(pred):
    for i, step in enumerate(STEPS):
        if pred(step):
            return i
    raise AssertionError("step not found")


class NixClosureScanJob(unittest.TestCase):
    def test_no_container_image_jobs(self):
        for name in ("trivy-scan-core", "trivy-scan-custom", "dockerfile-lint"):
            self.assertNotIn(name, WORKFLOW["jobs"])

    def test_builds_system_toplevel(self):
        run = "\n".join(s.get("run", "") for s in STEPS)
        self.assertIn("nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel", run)

    def test_scanner_failure_fails_job(self):
        for step in STEPS:
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("|| true", step.get("run", ""))
        scan = STEPS[_index(lambda s: "aq-closure-scan" in s.get("run", ""))]
        self.assertIn("pipefail", scan["run"])

    def test_sarif_upload_after_scan_with_category(self):
        scan_i = _index(lambda s: "aq-closure-scan" in s.get("run", ""))
        up_i = _index(lambda s: "codeql-action/upload-sarif" in s.get("uses", ""))
        self.assertLess(scan_i, up_i)
        with_ = STEPS[up_i]["with"]
        self.assertEqual(with_["category"], "nix-closure")
        self.assertTrue(with_["sarif_file"].endswith(".sarif"))
        self.assertIn("security-events", JOB["permissions"])

    def test_summary_depends_on_job(self):
        self.assertIn("nix-closure-vuln-scan", WORKFLOW["jobs"]["security-summary"]["needs"])

    def test_closure_changes_gate(self):
        self.assertIn("closure-changes", JOB["needs"])
        self.assertEqual(JOB["if"], "needs.closure-changes.outputs.scan == 'true'")
        run = _step_run(WORKFLOW["jobs"]["closure-changes"]["steps"], "Decide")
        self.assertIn("--no-renames", run)
        # push, schedule and workflow_dispatch must scan unconditionally
        self.assertIn('[ "$EVENT" != "pull_request" ]', run)
        self.assertIn('echo "scan=true" >> "$GITHUB_OUTPUT"', run.split("exit 0")[0])

    def test_closure_changes_path_filter(self):
        run = _step_run(WORKFLOW["jobs"]["closure-changes"]["steps"], "Decide")
        match = re.search(r"pattern='([^']+)'", run)
        self.assertIsNotNone(match, "Decide step must define pattern='...'")
        assert match is not None
        pattern = re.compile(match.group(1))
        for path in ("nix/x.nix", "flake.lock", "Cargo.lock", "config/x",
                     ".grype.yaml", "scripts/security/aq-closure-scan"):
            self.assertRegex(path, pattern)
        for path in ("docs/x.md", "tests/x.py"):
            self.assertNotRegex(path, pattern)


def _step_run(steps, prefix):
    return next(s["run"] for s in steps if s["name"].startswith(prefix))


if __name__ == "__main__":
    unittest.main()
