#!/usr/bin/env python3
"""
AI Stack Health Check Script v2

Purpose: Comprehensive health checking with smart container detection
Following: docs/agent-guides/02-SERVICE-STATUS.md
"""

import sys
import json
import subprocess
import requests
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ServiceCheck:
    """Health check result for a service"""
    name: str
    status: str  # "ok" | "warning" | "error" | "not_installed"
    message: str
    details: Dict = field(default_factory=dict)


def get_running_containers() -> List[str]:
    """Get list of running AI stack containers"""
    try:
        result = subprocess.run(
            ["podman", "ps", "--filter", "label=nixos.quick-deploy.ai-stack=true",
             "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        containers = [c.strip() for c in result.stdout.strip().split('\n') if c.strip()]
        return containers
    except Exception:
        return []


def check_qdrant(timeout: int = 5) -> ServiceCheck:
    """Check Qdrant vector database"""
    try:
        # Healthz check (returns plain text)
        response = requests.get("http://localhost:6333/healthz", timeout=timeout)

        if response.status_code == 200:
            check = ServiceCheck(
                name="Qdrant",
                status="ok",
                message="Qdrant is healthy"
            )

            # Check collections
            try:
                coll_response = requests.get("http://localhost:6333/collections", timeout=timeout)
                if coll_response.status_code == 200:
                    data = coll_response.json()
                    collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
                    check.details["collections"] = collections
                    check.details["collection_count"] = len(collections)

                    expected = ["codebase-context", "skills-patterns", "error-solutions",
                               "best-practices", "interaction-history"]
                    missing = set(expected) - set(collections)

                    if missing:
                        check.status = "warning"
                        check.message += f" (missing {len(missing)} collections)"
                        check.details["missing_collections"] = list(missing)
            except Exception as e:
                check.status = "warning"
                check.message += f" (couldn't verify collections: {str(e)[:30]})"

            return check
        else:
            return ServiceCheck(
                name="Qdrant",
                status="error",
                message=f"Unhealthy (HTTP {response.status_code})",
                details={"status_code": response.status_code}
            )

    except requests.exceptions.ConnectionError:
        return ServiceCheck(
            name="Qdrant",
            status="error",
            message="Not reachable (connection refused)",
            details={"suggestion": "podman start local-ai-qdrant"}
        )
    except Exception as e:
        return ServiceCheck(
            name="Qdrant",
            status="error",
            message=f"Check failed: {str(e)[:50]}",
            details={"error": str(e)}
        )


def check_lemonade(timeout: int = 5) -> ServiceCheck:
    """Check Lemonade GGUF inference"""
    try:
        response = requests.get("http://localhost:8080/health", timeout=timeout)

        if response.status_code == 200:
            check = ServiceCheck(
                name="Lemonade",
                status="ok",
                message="Lemonade is healthy"
            )

            # Try to get models
            try:
                models_response = requests.get("http://localhost:8080/v1/models", timeout=timeout)
                if models_response.status_code == 200:
                    data = models_response.json()
                    models = data.get("data", [])
                    if models:
                        check.details["models"] = [m.get("id") for m in models]
                        check.details["model_loaded"] = True
                    else:
                        check.status = "warning"
                        check.message += " (no models loaded - may be downloading)"
                        check.details["model_loaded"] = False
            except Exception:
                check.status = "warning"
                check.message += " (couldn't verify models)"

            return check
        else:
            return ServiceCheck(
                name="Lemonade",
                status="error",
                message=f"Unhealthy (HTTP {response.status_code})"
            )

    except requests.exceptions.ConnectionError:
        return ServiceCheck(
            name="Lemonade",
            status="error",
            message="Not reachable",
            details={"suggestion": "podman start local-ai-lemonade"}
        )
    except Exception as e:
        return ServiceCheck(
            name="Lemonade",
            status="error",
            message=f"Check failed: {str(e)[:50]}"
        )


def check_open_webui(timeout: int = 5) -> ServiceCheck:
    """Check Open WebUI (try multiple ports)"""
    ports = [3001, 3000, 8080, 8081]  # Common ports

    for port in ports:
        try:
            response = requests.get(f"http://localhost:{port}", timeout=timeout)
            if response.status_code == 200:
                return ServiceCheck(
                    name="Open WebUI",
                    status="ok",
                    message=f"Open WebUI is healthy (port {port})",
                    details={"port": port}
                )
        except requests.exceptions.ConnectionError:
            continue
        except Exception:
            continue

    return ServiceCheck(
        name="Open WebUI",
        status="error",
        message="Not reachable on common ports (3000, 8080, 8081)",
        details={"suggestion": "podman start local-ai-open-webui"}
    )


def check_aidb(timeout: int = 5) -> ServiceCheck:
    """Check AIDB MCP server"""
    try:
        response = requests.get("http://localhost:8091/health", timeout=timeout)

        if response.status_code == 200:
            check = ServiceCheck(
                name="AIDB MCP",
                status="ok",
                message="AIDB is healthy"
            )

            try:
                data = response.json()
                services = data.get("services", {})
                if services:
                    check.details["services"] = services
            except Exception:
                pass

            return check

        return ServiceCheck(
            name="AIDB MCP",
            status="error",
            message=f"Unhealthy (HTTP {response.status_code})"
        )

    except requests.exceptions.ConnectionError:
        return ServiceCheck(
            name="AIDB MCP",
            status="error",
            message="Not reachable",
            details={"suggestion": "podman start local-ai-aidb"}
        )
    except Exception as e:
        return ServiceCheck(
            name="AIDB MCP",
            status="error",
            message=f"Check failed: {str(e)[:50]}"
        )


def check_mindsdb(timeout: int = 5) -> ServiceCheck:
    """Check MindsDB analytics (optional)"""
    try:
        response = requests.get("http://localhost:47334", timeout=timeout)
        if response.status_code in (200, 302, 401):
            return ServiceCheck(
                name="MindsDB",
                status="ok",
                message="MindsDB is reachable"
            )
        return ServiceCheck(
            name="MindsDB",
            status="warning",
            message=f"Unexpected response (HTTP {response.status_code})"
        )
    except requests.exceptions.ConnectionError:
        return ServiceCheck(
            name="MindsDB",
            status="not_installed",
            message="Not reachable (optional service)",
            details={"suggestion": "podman start local-ai-mindsdb"}
        )
    except Exception as e:
        return ServiceCheck(
            name="MindsDB",
            status="warning",
            message=f"Check failed: {str(e)[:50]}"
        )


def check_container_service(container_name: str, display_name: str, check_command: List[str]) -> ServiceCheck:
    """Check service via container command"""
    try:
        result = subprocess.run(
            ["podman", "exec", container_name] + check_command,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return ServiceCheck(
                name=display_name,
                status="ok",
                message=f"{display_name} is healthy",
                details={"output": result.stdout.strip()[:100]}
            )
        else:
            return ServiceCheck(
                name=display_name,
                status="error",
                message=f"Check failed: {result.stderr.strip()[:50]}",
                details={"returncode": result.returncode}
            )

    except subprocess.CalledProcessError as e:
        return ServiceCheck(
            name=display_name,
            status="error",
            message=f"Container command failed: {str(e)[:50]}"
        )
    except FileNotFoundError:
        return ServiceCheck(
            name=display_name,
            status="not_installed",
            message="Container {container_name} not found",
            details={"suggestion": f"Container may not be running"}
        )
    except Exception as e:
        return ServiceCheck(
            name=display_name,
            status="error",
            message=f"Check failed: {str(e)[:50]}"
        )


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Stack Health Check v2")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-j", "--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    print("=== AI Stack Health Check ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Get running containers
    containers = get_running_containers()

    if args.verbose:
        print(f"Running containers: {len(containers)}")
        for container in containers:
            print(f"  - {container}")
        print()

    # Run checks
    results = []

    # Always check HTTP services
    results.append(check_qdrant())
    results.append(check_lemonade())
    results.append(check_open_webui())
    results.append(check_aidb())
    results.append(check_mindsdb())

    # Only check container services if they're running
    if "local-ai-postgres" in containers:
        results.append(check_container_service(
            "local-ai-postgres",
            "PostgreSQL",
            ["pg_isready", "-U", "mcp"]
        ))
    else:
        results.append(ServiceCheck(
            name="PostgreSQL",
            status="not_installed",
            message="Container not running (optional service)",
            details={"suggestion": "./scripts/hybrid-ai-stack.sh up"}
        ))

    if "local-ai-redis" in containers:
        results.append(check_container_service(
            "local-ai-redis",
            "Redis",
            ["redis-cli", "ping"]
        ))
    else:
        results.append(ServiceCheck(
            name="Redis",
            status="not_installed",
            message="Container not running (optional service)",
            details={"suggestion": "./scripts/hybrid-ai-stack.sh up"}
        ))

    if "local-ai-ollama" in containers:
        # Note: Ollama doesn't seem to be running currently
        pass

    # Print results
    status_icons = {
        "ok": "✓",
        "warning": "⚠",
        "error": "✗",
        "not_installed": "○"
    }

    for result in results:
        icon = status_icons.get(result.status, "?")
        print(f"{icon} {result.name:20s}: {result.message}")

        if args.verbose and result.details:
            for key, value in result.details.items():
                if isinstance(value, list) and len(value) > 3:
                    print(f"   {key}: {value[:3]} ... ({len(value)} total)")
                else:
                    print(f"   {key}: {value}")

    # Summary
    print()
    print("=== Summary ===")
    total = len(results)
    ok = sum(1 for r in results if r.status == "ok")
    warnings = sum(1 for r in results if r.status == "warning")
    errors = sum(1 for r in results if r.status == "error")
    not_installed = sum(1 for r in results if r.status == "not_installed")

    print(f"Total: {total} | OK: {ok} | Warnings: {warnings} | Errors: {errors} | Not Running: {not_installed}")

    # Recommendations
    if errors > 0:
        print()
        print("=== Issues Found ===")
        for result in results:
            if result.status == "error":
                print(f"\n{result.name}:")
                print(f"  {result.message}")
                if "suggestion" in result.details:
                    print(f"  Suggestion: {result.details['suggestion']}")

    print()

    # Exit code: 0 if OK, 1 if warnings or errors
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
