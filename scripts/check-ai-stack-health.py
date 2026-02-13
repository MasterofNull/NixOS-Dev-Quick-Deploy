#!/usr/bin/env python3
"""
AI Stack Health Check Script (v1 - DEPRECATED)

DEPRECATED: Use check-ai-stack-health-v2.py instead, which supports K3s (kubectl exec)
and provides better service discovery.

Purpose: Comprehensive health checking for all AI stack services
Following: docs/agent-guides/02-SERVICE-STATUS.md
"""

import os
import sys
import json
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")


@dataclass
class ServiceCheck:
    """Health check result for a service"""
    name: str
    status: str  # "ok" | "warning" | "error" | "unknown"
    message: str
    details: Dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AIStackHealthChecker:
    """Health checker for all AI stack services"""

    def __init__(self, verbose: bool = False, timeout: int = 5):
        self.verbose = verbose
        self.timeout = timeout
        self.results: List[ServiceCheck] = []

    def check_service(self, name: str, url: str, expected_key: str = None) -> ServiceCheck:
        """Generic HTTP service health check"""
        try:
            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 200:
                if expected_key:
                    data = response.json()
                    if expected_key in str(data):
                        return ServiceCheck(
                            name=name,
                            status="ok",
                            message=f"{name} is healthy",
                            details={"status_code": 200, "response_time": response.elapsed.total_seconds()}
                        )
                    else:
                        return ServiceCheck(
                            name=name,
                            status="warning",
                            message=f"{name} responded but unexpected format",
                            details={"response": data}
                        )
                else:
                    return ServiceCheck(
                        name=name,
                        status="ok",
                        message=f"{name} is healthy",
                        details={"status_code": 200}
                    )
            else:
                return ServiceCheck(
                    name=name,
                    status="error",
                    message=f"{name} returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )

        except requests.exceptions.ConnectionError:
            return ServiceCheck(
                name=name,
                status="error",
                message=f"{name} is not reachable (connection refused)",
                details={"error": "connection_refused"}
            )
        except requests.exceptions.Timeout:
            return ServiceCheck(
                name=name,
                status="error",
                message=f"{name} timed out after {self.timeout}s",
                details={"error": "timeout"}
            )
        except Exception as e:
            return ServiceCheck(
                name=name,
                status="error",
                message=f"{name} check failed: {str(e)}",
                details={"error": str(e)}
            )

    def check_qdrant(self) -> ServiceCheck:
        """Check Qdrant vector database"""
        check = self.check_service("Qdrant", f"http://{SERVICE_HOST}:6333/healthz", "healthz")

        if check.status == "ok":
            # Also check collections
            try:
                response = requests.get(f"http://{SERVICE_HOST}:6333/collections", timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
                    check.details["collections"] = collections
                    check.details["collection_count"] = len(collections)

                    # Expected collections
                    expected = ["codebase-context", "skills-patterns", "error-solutions",
                               "best-practices", "interaction-history"]
                    missing = set(expected) - set(collections)

                    if missing:
                        check.status = "warning"
                        check.message += f" (missing collections: {', '.join(missing)})"
                        check.details["missing_collections"] = list(missing)

            except Exception as e:
                check.status = "warning"
                check.message += f" (couldn't check collections: {e})"

        return check

    def check_llama_cpp(self) -> ServiceCheck:
        """Check llama.cpp inference service"""
        check = self.check_service("llama.cpp", f"http://{SERVICE_HOST}:8080/health")

        if check.status == "ok":
            # Try to get model info
            try:
                response = requests.get(f"http://{SERVICE_HOST}:8080/v1/models", timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    if models:
                        check.details["model_loaded"] = True
                        check.details["models"] = [m.get("id") for m in models]
                    else:
                        check.status = "warning"
                        check.message += " (no models loaded yet - may be downloading)"
                        check.details["model_loaded"] = False

            except Exception as e:
                check.status = "warning"
                check.message += f" (couldn't check models: {e})"

        return check

    def check_open_webui(self) -> ServiceCheck:
        """Check Open WebUI"""
        return self.check_service("Open WebUI", f"http://{SERVICE_HOST}:3001")

    def _detect_exec_cmd(self, k8s_label: str, container_name: str):
        """Return (cmd_prefix, runtime) for executing inside a container.
        Prefers kubectl (K3s), falls back to podman/docker."""
        import shutil
        if shutil.which("kubectl"):
            return ["kubectl", "exec", "-n", "ai-stack", f"deploy/{k8s_label}", "--"], "k3s"
        if shutil.which("podman"):
            return ["podman", "exec", container_name], "podman"
        if shutil.which("docker"):
            return ["docker", "exec", container_name], "docker"
        return None, None

    def check_postgres(self) -> ServiceCheck:
        """Check PostgreSQL database"""
        import subprocess

        exec_prefix, runtime = self._detect_exec_cmd("postgres", "local-ai-postgres")
        if exec_prefix is None:
            return ServiceCheck(
                name="PostgreSQL",
                status="error",
                message="No container runtime found (kubectl, podman, or docker)",
                details={"error": "no_runtime"}
            )

        try:
            result = subprocess.run(
                exec_prefix + ["pg_isready", "-U", "mcp"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                return ServiceCheck(
                    name="PostgreSQL",
                    status="ok",
                    message=f"PostgreSQL is accepting connections (via {runtime})",
                    details={"output": result.stdout.strip(), "runtime": runtime}
                )
            else:
                return ServiceCheck(
                    name="PostgreSQL",
                    status="error",
                    message=f"PostgreSQL is not ready: {result.stderr.strip()}",
                    details={"returncode": result.returncode}
                )

        except FileNotFoundError:
            return ServiceCheck(
                name="PostgreSQL",
                status="error",
                message=f"{runtime} command not found",
                details={"error": f"{runtime}_not_found"}
            )
        except subprocess.TimeoutExpired:
            return ServiceCheck(
                name="PostgreSQL",
                status="error",
                message=f"PostgreSQL check timed out after {self.timeout}s",
                details={"error": "timeout"}
            )
        except Exception as e:
            return ServiceCheck(
                name="PostgreSQL",
                status="error",
                message=f"PostgreSQL check failed: {str(e)}",
                details={"error": str(e)}
            )

    def check_redis(self) -> ServiceCheck:
        """Check Redis cache"""
        import subprocess

        exec_prefix, runtime = self._detect_exec_cmd("redis", "local-ai-redis")
        if exec_prefix is None:
            return ServiceCheck(
                name="Redis",
                status="error",
                message="No container runtime found (kubectl, podman, or docker)",
                details={"error": "no_runtime"}
            )

        try:
            result = subprocess.run(
                exec_prefix + ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0 and "PONG" in result.stdout:
                return ServiceCheck(
                    name="Redis",
                    status="ok",
                    message=f"Redis is responding (via {runtime})",
                    details={"output": result.stdout.strip(), "runtime": runtime}
                )
            else:
                return ServiceCheck(
                    name="Redis",
                    status="error",
                    message=f"Redis check failed: {result.stderr.strip()}",
                    details={"returncode": result.returncode}
                )

        except Exception as e:
            return ServiceCheck(
                name="Redis",
                status="error",
                message=f"Redis check failed: {str(e)}",
                details={"error": str(e)}
            )

    def run_all_checks(self) -> List[ServiceCheck]:
        """Run all health checks"""
        print("=== AI Stack Health Check ===")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        checks = [
            ("Qdrant Vector DB", self.check_qdrant),
            ("llama.cpp Inference", self.check_llama_cpp),
            ("Open WebUI", self.check_open_webui),
            ("PostgreSQL", self.check_postgres),
            ("Redis Cache", self.check_redis),
        ]

        results = []

        for name, check_func in checks:
            if self.verbose:
                print(f"Checking {name}...", end=" ", flush=True)

            result = check_func()
            results.append(result)

            # Print result
            status_icons = {
                "ok": "✓",
                "warning": "⚠",
                "error": "✗",
                "unknown": "?"
            }

            icon = status_icons.get(result.status, "?")

            if self.verbose:
                print(f"{icon} {result.message}")
            else:
                print(f"{icon} {result.name:20s}: {result.message}")

            # Print details if verbose
            if self.verbose and result.details:
                for key, value in result.details.items():
                    if key not in ["error", "output"]:  # Skip redundant info
                        print(f"   {key}: {value}")

        print()
        return results

    def get_summary(self, results: List[ServiceCheck]) -> Dict:
        """Get summary of health check results"""
        total = len(results)
        ok_count = sum(1 for r in results if r.status == "ok")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")

        return {
            "total_services": total,
            "healthy": ok_count,
            "warnings": warning_count,
            "errors": error_count,
            "overall_status": "ok" if error_count == 0 else "error",
            "timestamp": datetime.now().isoformat()
        }

    def print_summary(self, results: List[ServiceCheck]):
        """Print summary and recommendations"""
        summary = self.get_summary(results)

        print("=== Summary ===")
        print(f"Total Services: {summary['total_services']}")
        print(f"Healthy: {summary['healthy']}")
        print(f"Warnings: {summary['warnings']}")
        print(f"Errors: {summary['errors']}")
        print()

        # Print recommendations for issues
        if summary['warnings'] > 0 or summary['errors'] > 0:
            print("=== Recommendations ===")

            for result in results:
                if result.status in ["warning", "error"]:
                    print(f"\n{result.name}:")
                    print(f"  Issue: {result.message}")

                    # Specific recommendations (K3s-aware)
                    svc_slug = result.name.lower().replace(' ', '-')
                    if "connection refused" in result.message.lower():
                        print(f"  Fix: Check the deployment is running:")
                        print(f"       kubectl get deploy -n ai-stack {svc_slug}")
                        print(f"       kubectl rollout restart deploy/{svc_slug} -n ai-stack")

                    elif "timeout" in result.message.lower():
                        print(f"  Fix: Check service logs:")
                        print(f"       kubectl logs -n ai-stack deploy/{svc_slug}")

                    elif "missing collections" in result.message.lower():
                        print(f"  Fix: Re-initialize Qdrant collections:")
                        print(f"       ./scripts/setup-hybrid-learning-auto.sh")

                    elif "model not found" in result.message.lower() or "no models loaded" in result.message.lower():
                        print(f"  Fix: Wait for model download or check logs:")
                        print(f"       kubectl logs -n ai-stack deploy/{svc_slug} -f")

        print()

        # Exit code
        return 0 if summary['errors'] == 0 else 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Stack Health Check - Verify all services are running correctly"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with detailed information"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=5,
        help="Timeout for each check in seconds (default: 5)"
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    print("WARNING: This script (v1) is deprecated. Use check-ai-stack-health-v2.py instead.", file=sys.stderr)
    print(file=sys.stderr)

    checker = AIStackHealthChecker(verbose=args.verbose, timeout=args.timeout)
    results = checker.run_all_checks()

    if args.json:
        # JSON output
        output = {
            "timestamp": datetime.now().isoformat(),
            "summary": checker.get_summary(results),
            "services": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "details": r.details
                }
                for r in results
            ]
        }
        print(json.dumps(output, indent=2))
        return 0 if output["summary"]["errors"] == 0 else 1
    else:
        # Human-readable output
        return checker.print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
