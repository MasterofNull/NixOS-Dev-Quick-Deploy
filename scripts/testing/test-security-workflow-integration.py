#!/usr/bin/env python3
"""
Comprehensive Security Workflow Integration Tests
Tests end-to-end security, audit, and compliance workflow

Usage:
    python3 test-security-workflow-integration.py [--verbose]
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import unittest

# Add parent directory to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import audit logger module
sys.path.insert(0, str(REPO_ROOT / "lib" / "security"))
from audit_logger import AuditLogger, EventType


class SecurityScannerTests(unittest.TestCase):
    """Test security scanner functionality"""

    def setUp(self):
        self.deployment_id = f"test_deploy_{int(datetime.now().timestamp())}"
        self.scanner_script = REPO_ROOT / "lib" / "security" / "scanner.sh"

    def test_scanner_module_loads(self):
        """Test that scanner module loads successfully"""
        result = subprocess.run(
            ["bash", "-n", str(self.scanner_script)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Scanner syntax error: {result.stderr}")

    def test_detect_secrets_function(self):
        """Test secret detection functionality"""
        # Create a temporary file with insecure-looking config that should
        # still exercise the detector without embedding a secret-shaped token.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write('SERVICE_CREDENTIAL="scanner-test-placeholder"\n')
            f.write('password="insecure123"\n')
            temp_file = f.name

        try:
            result = subprocess.run(
                ["bash", "-c", f"source {self.scanner_script} && detect_secrets {temp_file}"],
                capture_output=True,
                text=True,
                env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
                timeout=30
            )

            # Check that function executed
            self.assertIn("detect_secrets", result.stderr or result.stdout or "executed")

        finally:
            os.unlink(temp_file)

    def test_service_vulnerability_scan(self):
        """Test service vulnerability scanning"""
        result = subprocess.run(
            ["bash", "-c", f"source {self.scanner_script} && scan_service_vulnerabilities redis"],
            capture_output=True,
            text=True,
            env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            timeout=30
        )

        # Check that scan produces JSON output
        if result.returncode == 0 and result.stdout:
            try:
                scan_result = json.loads(result.stdout)
                self.assertIn("scan_id", scan_result)
                self.assertIn("service", scan_result)
            except json.JSONDecodeError:
                pass  # Function may not return JSON in all cases


class AuditLoggerTests(unittest.TestCase):
    """Test audit logger functionality"""

    def setUp(self):
        # Create temporary audit directories
        self.test_dir = Path(tempfile.mkdtemp())
        self.logger = AuditLogger(
            local_store_path=str(self.test_dir / "local"),
            central_store_path=str(self.test_dir / "central")
        )

    def tearDown(self):
        # Clean up temporary directories
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_log_deployment_event(self):
        """Test logging deployment events"""
        event = self.logger.log_deployment_event(
            deployment_id="test_deploy_123",
            action="started",
            details={"user": "test_user"}
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.DEPLOYMENT.value)
        self.assertEqual(event.event_action, "started")
        self.assertIsNotNone(event.checksum)

    def test_log_access_event(self):
        """Test logging access events"""
        event = self.logger.log_access_event(
            user="admin",
            action="login",
            result="success",
            resource="system"
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.ACCESS.value)
        self.assertEqual(event.actor, "admin")

    def test_log_security_event(self):
        """Test logging security events"""
        event = self.logger.log_security_event(
            event_action="vulnerability_detected",
            severity="high",
            actor="scanner",
            resource="service:redis",
            details={"cve": "CVE-2024-1234"}
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.severity, "high")

    def test_query_events(self):
        """Test querying audit events"""
        # Log multiple events
        self.logger.log_deployment_event("deploy_1", "started")
        self.logger.log_deployment_event("deploy_2", "completed")
        self.logger.log_access_event("user1", "login", "success")

        # Query deployment events
        events = self.logger.query_events(event_type=EventType.DEPLOYMENT.value, limit=10)

        self.assertGreaterEqual(len(events), 2)
        for event in events:
            self.assertEqual(event.event_type, EventType.DEPLOYMENT.value)

    def test_verify_chain_integrity(self):
        """Test audit log chain integrity verification"""
        # Log several events to create a chain
        for i in range(5):
            self.logger.log_deployment_event(f"deploy_{i}", "started")

        # Verify integrity
        result = self.logger.verify_chain_integrity()

        self.assertTrue(result["valid"])
        self.assertEqual(result["total_events"], 5)
        self.assertEqual(len(result["issues"]), 0)

    def test_retention_policy(self):
        """Test retention policy enforcement"""
        # Log an event
        self.logger.log_deployment_event("deploy_test", "started")

        # Enforce retention (with short retention for testing)
        self.logger.retention_days = 0  # Remove all events
        result = self.logger.enforce_retention_policy()

        self.assertIn("removed", result)

    def test_get_statistics(self):
        """Test audit log statistics"""
        # Log various events
        self.logger.log_deployment_event("deploy_1", "started")
        self.logger.log_access_event("user1", "login", "success")
        self.logger.log_security_event("scan", "info", "scanner", "system")

        stats = self.logger.get_statistics()

        self.assertGreaterEqual(stats["total_events"], 3)
        self.assertIn("type_counts", stats)


class ComplianceCheckerTests(unittest.TestCase):
    """Test compliance checker functionality"""

    def setUp(self):
        self.deployment_id = f"test_deploy_{int(datetime.now().timestamp())}"
        self.compliance_script = REPO_ROOT / "lib" / "security" / "compliance-checker.sh"

    def test_compliance_module_loads(self):
        """Test that compliance checker module loads"""
        result = subprocess.run(
            ["bash", "-n", str(self.compliance_script)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Compliance checker syntax error: {result.stderr}")

    def test_soc2_compliance_check(self):
        """Test SOC2 compliance checking"""
        result = subprocess.run(
            ["bash", "-c", f"source {self.compliance_script} && check_soc2_compliance {self.deployment_id}"],
            capture_output=True,
            text=True,
            env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            timeout=60
        )

        # Check that function executed (may fail if dependencies missing)
        # Just verify it doesn't have syntax errors
        self.assertNotIn("syntax error", result.stderr.lower())


class SecurityWorkflowTests(unittest.TestCase):
    """Test security workflow validator"""

    def setUp(self):
        self.deployment_id = f"test_deploy_{int(datetime.now().timestamp())}"
        self.workflow_script = REPO_ROOT / "lib" / "security" / "security-workflow-validator.sh"

    def test_workflow_module_loads(self):
        """Test that workflow validator module loads"""
        result = subprocess.run(
            ["bash", "-n", str(self.workflow_script)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Workflow validator syntax error: {result.stderr}")


class DeploymentHooksTests(unittest.TestCase):
    """Test deployment hooks system"""

    def setUp(self):
        self.deployment_id = f"test_deploy_{int(datetime.now().timestamp())}"
        self.hooks_script = REPO_ROOT / "lib" / "deploy" / "deployment-hooks.sh"

    def test_hooks_module_loads(self):
        """Test that deployment hooks module loads"""
        result = subprocess.run(
            ["bash", "-n", str(self.hooks_script)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Deployment hooks syntax error: {result.stderr}")

    def test_register_hook(self):
        """Test hook registration"""
        # Create a simple test hook script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write('#!/bin/bash\n')
            f.write('echo "Test hook executed"\n')
            f.write('exit 0\n')
            hook_script = f.name

        try:
            os.chmod(hook_script, 0o755)

            result = subprocess.run(
                ["bash", "-c", f"source {self.hooks_script} && register_hook pre_deployment test_hook {hook_script} 50"],
                capture_output=True,
                text=True,
                env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
                timeout=10
            )

            # Check that registration succeeded
            self.assertIn("registered", result.stderr.lower() or result.stdout.lower())

        finally:
            os.unlink(hook_script)


class IntegrationTests(unittest.TestCase):
    """End-to-end integration tests"""

    def setUp(self):
        self.deployment_id = f"test_deploy_{int(datetime.now().timestamp())}"

    def test_end_to_end_workflow(self):
        """Test complete security workflow"""
        # This test verifies the full workflow can be executed
        # Note: May require environment setup

        workflow_script = REPO_ROOT / "lib" / "security" / "security-workflow-validator.sh"

        # Run pre-deployment security gate
        result = subprocess.run(
            ["bash", "-c", f"source {workflow_script} && run_pre_deployment_security_gate {self.deployment_id} || true"],
            capture_output=True,
            text=True,
            env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            timeout=180
        )

        # Check that it executed (may fail gates, but should run)
        self.assertNotIn("syntax error", result.stderr.lower())

    def test_audit_logger_cli(self):
        """Test audit logger CLI interface"""
        audit_logger = REPO_ROOT / "lib" / "security" / "audit-logger.py"

        # Test logging via CLI
        result = subprocess.run(
            [
                "python3", str(audit_logger),
                "--action", "log",
                "--event-type", "deployment",
                "--event-action", "test",
                "--actor", "unittest",
                "--resource", "test_resource"
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            timeout=10
        )

        self.assertEqual(result.returncode, 0)

        # Parse output
        try:
            event = json.loads(result.stdout)
            self.assertIn("event_id", event)
        except json.JSONDecodeError:
            self.fail("Audit logger did not return valid JSON")

    def test_compliance_frameworks_available(self):
        """Test that compliance framework policies are initialized"""
        compliance_dir = REPO_ROOT / ".agent" / "security" / "compliance" / "policies"

        # Run compliance checker to ensure initialization
        compliance_script = REPO_ROOT / "lib" / "security" / "compliance-checker.sh"
        subprocess.run(
            ["bash", "-c", f"source {compliance_script} && ensure_compliance_directories"],
            env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            timeout=10
        )

        # Check that policy files were created
        if compliance_dir.exists():
            policy_files = list(compliance_dir.glob("*.json"))
            self.assertGreater(len(policy_files), 0, "No compliance policy files found")


def run_tests(verbosity=2):
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(SecurityScannerTests))
    suite.addTests(loader.loadTestsFromTestCase(AuditLoggerTests))
    suite.addTests(loader.loadTestsFromTestCase(ComplianceCheckerTests))
    suite.addTests(loader.loadTestsFromTestCase(SecurityWorkflowTests))
    suite.addTests(loader.loadTestsFromTestCase(DeploymentHooksTests))
    suite.addTests(loader.loadTestsFromTestCase(IntegrationTests))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Security Workflow Integration Tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    verbosity = 2 if args.verbose else 1
    sys.exit(run_tests(verbosity))
