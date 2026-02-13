#!/usr/bin/env python3
"""
AI Stack Health Check Script v2

Purpose: Comprehensive health checking with smart container detection
Following: docs/agent-guides/02-SERVICE-STATUS.md
"""

import sys
import json
import os
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from urllib import request as urllib_request
from urllib import error as urllib_error

try:
    import requests  # type: ignore
    REQUEST_ERROR = requests.exceptions.RequestException
except Exception:  # pragma: no cover - fallback when requests is absent
    requests = None  # type: ignore

    class REQUEST_ERROR(Exception):
        """Fallback request error when requests is unavailable."""

SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
LOCAL_HOST = os.getenv("LOCAL_HOST", "127.0.0.1")


@dataclass
class ServiceCheck:
    """Health check result for a service"""
    name: str
    status: str  # "ok" | "warning" | "error" | "not_installed"
    message: str
    details: Dict = field(default_factory=dict)


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_kubectl(args: List[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def k8s_namespace_available(namespace: str) -> bool:
    if not command_exists("kubectl"):
        return False
    try:
        result = run_kubectl(["get", "namespace", namespace])
        return result.returncode == 0
    except Exception:
        return False


def get_k8s_deployments(namespace: str) -> Dict[str, Dict]:
    result = run_kubectl(["get", "deploy", "-n", namespace, "-o", "json"], timeout=10)
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return {item.get("metadata", {}).get("name", ""): item for item in data.get("items", []) if item.get("metadata")}


def deployment_replica_status(deploy: Dict) -> Tuple[int, int]:
    spec = deploy.get("spec", {})
    status = deploy.get("status", {})
    desired = spec.get("replicas", 1) or 0
    ready = status.get("readyReplicas", 0) or 0
    return desired, ready


def find_exec_target(namespace: str) -> Optional[str]:
    result = run_kubectl(
        ["get", "pod", "-n", namespace, "-l", "io.kompose.service=nginx", "-o", "json"],
        timeout=10,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for item in data.get("items", []):
        conditions = {c.get("type"): c.get("status") for c in item.get("status", {}).get("conditions", [])}
        if conditions.get("Ready") == "True":
            name = item.get("metadata", {}).get("name")
            if name:
                return f"pod/{name}"
    return None


def kubectl_exec(namespace: str, target: str, command: List[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return run_kubectl(["exec", "-n", namespace, target, "--"] + command, timeout=timeout)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def port_forward(namespace: str, service: str, remote_port: int, local_port: Optional[int] = None):
    if local_port is None:
        local_port = find_free_port()
    cmd = [
        "kubectl",
        "port-forward",
        "-n",
        namespace,
        f"svc/{service}",
        f"{local_port}:{remote_port}",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(1.0)
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"port-forward failed: {stderr.strip()}")
        yield local_port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def k8s_http_request(
    namespace: str,
    service: str,
    port: int,
    path: str,
    exec_target: Optional[str],
    timeout: int = 5,
) -> Tuple[int, str]:
    url = f"http://{service}:{port}{path}"
    if exec_target:
        result = kubectl_exec(
            namespace,
            exec_target,
            ["curl", "-sS", "--max-time", str(timeout), url],
            timeout=timeout + 2,
        )
        if result.returncode == 0:
            return 200, result.stdout.strip()
    with port_forward(namespace, service, port) as local_port:
        response = http_get(f"http://{LOCAL_HOST}:{local_port}{path}", timeout=timeout)
        return response.status_code, response.text.strip()


class SimpleResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self):
        return json.loads(self.text)


def http_get(url: str, timeout: int = 5) -> SimpleResponse:
    if requests is not None:
        resp = requests.get(url, timeout=timeout)
        return SimpleResponse(resp.status_code, resp.text)
    try:
        with urllib_request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode()
            return SimpleResponse(resp.getcode() or 0, body)
    except urllib_error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        return SimpleResponse(exc.code or 0, body)
    except Exception as exc:
        raise REQUEST_ERROR(str(exc)) from exc


def response_json(resp: SimpleResponse) -> Optional[Dict]:
    try:
        return resp.json()
    except Exception:
        return None

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
        response = http_get(f"http://{SERVICE_HOST}:6333/healthz", timeout=timeout)

        if response.status_code == 200:
            check = ServiceCheck(
                name="Qdrant",
                status="ok",
                message="Qdrant is healthy"
            )

            # Check collections
            try:
                coll_response = http_get(f"http://{SERVICE_HOST}:6333/collections", timeout=timeout)
                if coll_response.status_code == 200:
                    data = response_json(coll_response) or {}
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

    except REQUEST_ERROR:
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


def check_llama_cpp(timeout: int = 5) -> ServiceCheck:
    """Check llama.cpp GGUF inference"""
    try:
        response = http_get(f"http://{SERVICE_HOST}:8080/health", timeout=timeout)

        if response.status_code == 200:
            check = ServiceCheck(
                name="llama.cpp",
                status="ok",
                message="llama.cpp is healthy"
            )

            # Try to get models
            try:
                models_response = http_get(f"http://{SERVICE_HOST}:8080/v1/models", timeout=timeout)
                if models_response.status_code == 200:
                    data = response_json(models_response) or {}
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
                name="llama.cpp",
                status="error",
                message=f"Unhealthy (HTTP {response.status_code})"
            )

    except REQUEST_ERROR:
        return ServiceCheck(
            name="llama.cpp",
            status="error",
            message="Not reachable",
            details={"suggestion": "podman start local-ai-llama-cpp"}
        )
    except Exception as e:
        return ServiceCheck(
            name="llama.cpp",
            status="error",
            message=f"Check failed: {str(e)[:50]}"
        )


def check_open_webui(timeout: int = 5) -> ServiceCheck:
    """Check Open WebUI (try multiple ports)"""
    ports = [3001, 3000, 8080, 8081]  # Common ports

    for port in ports:
        try:
            response = http_get(f"http://{SERVICE_HOST}:{port}", timeout=timeout)
            if response.status_code == 200:
                return ServiceCheck(
                    name="Open WebUI",
                    status="ok",
                    message=f"Open WebUI is healthy (port {port})",
                    details={"port": port}
                )
        except REQUEST_ERROR:
            continue
        except Exception:
            continue

    return ServiceCheck(
        name="Open WebUI",
        status="warning",
        message="Not reachable on common ports (3001, 3000, 8080, 8081)",
        details={"suggestion": "podman-ai-stack up (or podman start local-ai-open-webui)"}
    )


def check_aidb(timeout: int = 5) -> ServiceCheck:
    """Check AIDB MCP server"""
    try:
        response = http_get(f"http://{SERVICE_HOST}:8091/health", timeout=timeout)

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

    except REQUEST_ERROR:
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
        response = http_get(f"http://{SERVICE_HOST}:47334", timeout=timeout)
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
    except REQUEST_ERROR:
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


def k8s_check_http_service(
    name: str,
    deployment: str,
    service: str,
    port: int,
    path: str,
    deployments: Dict[str, Dict],
    namespace: str,
    exec_target: Optional[str],
    optional: bool = False,
) -> ServiceCheck:
    deploy = deployments.get(deployment)
    if not deploy:
        status = "not_installed" if optional else "error"
        return ServiceCheck(name=name, status=status, message="Deployment not found")

    desired, ready = deployment_replica_status(deploy)
    if desired == 0:
        return ServiceCheck(
            name=name,
            status="not_installed" if optional else "warning",
            message="Deployment scaled to 0",
            details={"desired": desired, "ready": ready},
        )
    if ready < desired:
        return ServiceCheck(
            name=name,
            status="error",
            message=f"Deployment not ready ({ready}/{desired})",
            details={"desired": desired, "ready": ready},
        )

    try:
        status_code, body = k8s_http_request(namespace, service, port, path, exec_target)
    except Exception as exc:
        return ServiceCheck(
            name=name,
            status="error",
            message=f"Not reachable ({str(exc)[:50]})",
        )

    if status_code == 200:
        return ServiceCheck(name=name, status="ok", message=f"{name} is healthy")

    return ServiceCheck(
        name=name,
        status="warning" if optional else "error",
        message=f"Unexpected status (HTTP {status_code})",
        details={"response": body[:200]},
    )


def k8s_check_exec_service(
    name: str,
    deployment: str,
    command: List[str],
    expected_substring: str,
    deployments: Dict[str, Dict],
    namespace: str,
    optional: bool = False,
) -> ServiceCheck:
    deploy = deployments.get(deployment)
    if not deploy:
        status = "not_installed" if optional else "error"
        return ServiceCheck(name=name, status=status, message="Deployment not found")

    desired, ready = deployment_replica_status(deploy)
    if desired == 0:
        return ServiceCheck(
            name=name,
            status="not_installed" if optional else "warning",
            message="Deployment scaled to 0",
            details={"desired": desired, "ready": ready},
        )
    if ready < desired:
        return ServiceCheck(
            name=name,
            status="error",
            message=f"Deployment not ready ({ready}/{desired})",
            details={"desired": desired, "ready": ready},
        )

    result = kubectl_exec(namespace, f"deploy/{deployment}", command, timeout=8)
    if result.returncode == 0 and expected_substring in result.stdout:
        return ServiceCheck(name=name, status="ok", message=f"{name} is healthy")

    message = result.stderr.strip()[:80] if result.stderr else result.stdout.strip()[:80]
    return ServiceCheck(
        name=name,
        status="warning" if optional else "error",
        message=f"Check failed: {message}" if message else "Check failed",
    )


def run_k8s_checks(namespace: str, verbose: bool) -> List[ServiceCheck]:
    deployments = get_k8s_deployments(namespace)
    exec_target = find_exec_target(namespace)
    results: List[ServiceCheck] = []

    results.append(
        k8s_check_http_service(
            name="Qdrant",
            deployment="qdrant",
            service="qdrant",
            port=6333,
            path="/healthz",
            deployments=deployments,
            namespace=namespace,
            exec_target=exec_target,
        )
    )
    results.append(
        k8s_check_http_service(
            name="llama.cpp",
            deployment="llama-cpp",
            service="llama-cpp",
            port=8080,
            path="/health",
            deployments=deployments,
            namespace=namespace,
            exec_target=exec_target,
        )
    )
    results.append(
        k8s_check_http_service(
            name="Open WebUI",
            deployment="open-webui",
            service="open-webui",
            port=3001,
            path="/",
            deployments=deployments,
            namespace=namespace,
            exec_target=exec_target,
            optional=True,
        )
    )
    results.append(
        k8s_check_http_service(
            name="AIDB MCP",
            deployment="aidb",
            service="aidb",
            port=8091,
            path="/health",
            deployments=deployments,
            namespace=namespace,
            exec_target=exec_target,
        )
    )
    results.append(
        k8s_check_http_service(
            name="MindsDB",
            deployment="mindsdb",
            service="mindsdb",
            port=47334,
            path="/",
            deployments=deployments,
            namespace=namespace,
            exec_target=exec_target,
            optional=True,
        )
    )
    results.append(
        k8s_check_exec_service(
            name="PostgreSQL",
            deployment="postgres",
            command=["pg_isready", "-U", "mcp"],
            expected_substring="accepting connections",
            deployments=deployments,
            namespace=namespace,
        )
    )
    results.append(
        k8s_check_exec_service(
            name="Redis",
            deployment="redis",
            command=["sh", "-c", "redis-cli -a $(cat /run/secrets/redis-password) ping"],
            expected_substring="PONG",
            deployments=deployments,
            namespace=namespace,
        )
    )

    if verbose and exec_target:
        results.append(
            ServiceCheck(
                name="Probe Pod",
                status="ok",
                message=f"Using {exec_target} for in-cluster HTTP checks",
            )
        )

    return results


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Stack Health Check v2")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-j", "--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--mode",
        choices=["auto", "k8s", "podman"],
        default="auto",
        help="Force runtime mode (auto, k8s, podman)",
    )
    args = parser.parse_args()

    print("=== AI Stack Health Check ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    namespace = os.environ.get("AI_STACK_NAMESPACE", "ai-stack")
    mode = args.mode
    if mode == "auto":
        mode = "k8s" if k8s_namespace_available(namespace) else "podman"

    if mode == "k8s":
        print(f"Mode: k8s (namespace: {namespace})")
        print()
        results = run_k8s_checks(namespace, args.verbose)
    else:
        print("Mode: podman")
        print()
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
        results.append(check_llama_cpp())
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
