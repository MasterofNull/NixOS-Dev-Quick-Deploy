#!/usr/bin/env python3
"""
Container Engine MCP Server
Provides tools for Docker/Podman container management, best practices, and pattern learning
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import structlog

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.podman_api_client import PodmanAPIClient, ContainerNotFoundError
from shared.auth_middleware import get_api_key_dependency

logger = structlog.get_logger()

# Global Podman API client
podman_client: Optional[PodmanAPIClient] = None

# Load API key from secret file
def load_api_key() -> Optional[str]:
    """Load API key from Docker secret file"""
    secret_file = os.environ.get("CONTAINER_ENGINE_API_KEY_FILE", "/run/secrets/container_engine_api_key")
    if Path(secret_file).exists():
        return Path(secret_file).read_text().strip()
    # Fallback to environment variable for development
    return os.environ.get("CONTAINER_ENGINE_API_KEY")

# Initialize authentication dependency
api_key = load_api_key()
require_auth = get_api_key_dependency(
    service_name="container-engine",
    expected_key=api_key,
    optional=not api_key  # If no key configured, allow unauthenticated (dev mode)
)

app = FastAPI(
    title="Container Engine MCP Server",
    description="MCP server for Docker/Podman container management and best practices",
    version="1.0.0"
)


@app.on_event("startup")
async def startup():
    """Initialize Podman API client on startup"""
    global podman_client
    podman_client = PodmanAPIClient(
        service_name="container-engine",
        allowed_operations=["list", "inspect", "logs"],  # Read-only operations
        audit_enabled=True
    )
    await podman_client.__aenter__()
    auth_status = "enabled" if api_key else "disabled (development mode)"
    logger.info("container_engine_started", allowed_operations=["list", "inspect", "logs"], auth=auth_status)


@app.on_event("shutdown")
async def shutdown():
    """Clean up Podman API client on shutdown"""
    global podman_client
    if podman_client:
        await podman_client.__aexit__(None, None, None)
    logger.info("container_engine_stopped")


class ContainerInspectRequest(BaseModel):
    container_id: str


class NetworkInspectRequest(BaseModel):
    network_name: str


class BestPracticeRequest(BaseModel):
    context: str
    service_type: Optional[str] = None


class ContainerActionRequest(BaseModel):
    container_id: str


# Container engine detection
CONTAINER_ENGINE = "podman"  # Can be "docker" or "podman"


@app.get("/health")
async def health():
    """Health check endpoint"""
    # Check if API client is initialized
    if not podman_client:
        return {
            "status": "degraded",
            "container_engine": CONTAINER_ENGINE,
            "engine_available": False,
            "error": "API client not initialized"
        }

    try:
        # Test API connectivity by listing containers
        await podman_client.list_containers()
        return {
            "status": "healthy",
            "container_engine": CONTAINER_ENGINE,
            "engine_available": True
        }
    except Exception as e:
        return {
            "status": "degraded",
            "container_engine": CONTAINER_ENGINE,
            "engine_available": False,
            "error": str(e)
        }


@app.get("/containers")
async def containers_list(auth: str = Depends(require_auth)):
    """List containers using the container engine."""
    return await list_containers()


@app.post("/containers/{container_id}/start")
async def containers_start(container_id: str, auth: str = Depends(require_auth)):
    """Start a container."""
    return await start_container(container_id)


@app.post("/containers/{container_id}/stop")
async def containers_stop(container_id: str, auth: str = Depends(require_auth)):
    """Stop a container."""
    return await stop_container(container_id)


@app.post("/containers/{container_id}/restart")
async def containers_restart(container_id: str, auth: str = Depends(require_auth)):
    """Restart a container."""
    return await restart_container(container_id)


@app.get("/containers/{container_id}/logs")
async def containers_logs(container_id: str, tail: int = 100, auth: str = Depends(require_auth)):
    """Get container logs."""
    return await get_container_logs(container_id, tail=tail)


@app.get("/tools/list")
async def list_tools(auth: str = Depends(require_auth)):
    """List available MCP tools"""
    return {
        "tools": [
            {
                "name": "inspect_container",
                "description": "Get detailed information about a container including networking, volumes, environment",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "container_id": {"type": "string", "description": "Container name or ID"}
                    },
                    "required": ["container_id"]
                }
            },
            {
                "name": "inspect_network",
                "description": "Get network configuration and connected containers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "network_name": {"type": "string", "description": "Network name"}
                    },
                    "required": ["network_name"]
                }
            },
            {
                "name": "list_containers",
                "description": "List all containers with status and networking info",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "check_connectivity",
                "description": "Check if two containers can communicate on the network",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source_container": {"type": "string"},
                        "target_host": {"type": "string"},
                        "target_port": {"type": "integer"}
                    },
                    "required": ["source_container", "target_host"]
                }
            },
            {
                "name": "get_best_practices",
                "description": "Get Docker/Podman best practices for specific scenarios",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "context": {"type": "string", "description": "Context: networking, volumes, security, performance"},
                        "service_type": {"type": "string", "description": "Optional: api, database, worker, etc."}
                    },
                    "required": ["context"]
                }
            },
            {
                "name": "validate_dockerfile",
                "description": "Validate Dockerfile against best practices",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dockerfile_path": {"type": "string"}
                    },
                    "required": ["dockerfile_path"]
                }
            },
            {
                "name": "get_container_logs",
                "description": "Get recent logs from a container",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "container_id": {"type": "string"},
                        "tail": {"type": "integer", "default": 100}
                    },
                    "required": ["container_id"]
                }
            }
        ]
    }


@app.post("/tools/call")
async def call_tool(tool_name: str, arguments: Dict[str, Any], auth: str = Depends(require_auth)):
    """Execute an MCP tool"""
    logger.info("tool_called", tool=tool_name, arguments=arguments)

    if tool_name == "inspect_container":
        return await inspect_container(arguments.get("container_id"))
    elif tool_name == "inspect_network":
        return await inspect_network(arguments.get("network_name"))
    elif tool_name == "list_containers":
        return await list_containers()
    elif tool_name == "check_connectivity":
        return await check_connectivity(
            arguments.get("source_container"),
            arguments.get("target_host"),
            arguments.get("target_port")
        )
    elif tool_name == "get_best_practices":
        return await get_best_practices(
            arguments.get("context"),
            arguments.get("service_type")
        )
    elif tool_name == "validate_dockerfile":
        return await validate_dockerfile(arguments.get("dockerfile_path"))
    elif tool_name == "get_container_logs":
        return await get_container_logs(
            arguments.get("container_id"),
            arguments.get("tail", 100)
        )
    elif tool_name == "start_container":
        return await start_container(arguments.get("container_id"))
    elif tool_name == "stop_container":
        return await stop_container(arguments.get("container_id"))
    elif tool_name == "restart_container":
        return await restart_container(arguments.get("container_id"))
    else:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")


async def inspect_container(container_id: str) -> Dict[str, Any]:
    """Inspect container configuration"""
    try:
        inspect_data = await podman_client.get_container(container_id)

        # Extract key networking information
        network_settings = inspect_data.get("NetworkSettings", {})
        networks = network_settings.get("Networks", {})

        network_info = {}
        for net_name, net_data in networks.items():
            network_info[net_name] = {
                "ip_address": net_data.get("IPAddress"),
                "gateway": net_data.get("Gateway"),
                "network_id": net_data.get("NetworkID")
            }

        return {
            "container_id": container_id,
            "name": inspect_data.get("Name", "").lstrip("/"),
            "image": inspect_data.get("Config", {}).get("Image"),
            "status": inspect_data.get("State", {}).get("Status"),
            "networks": network_info,
            "ports": inspect_data.get("NetworkSettings", {}).get("Ports", {}),
            "environment": inspect_data.get("Config", {}).get("Env", []),
            "volumes": inspect_data.get("Mounts", []),
            "hostname": inspect_data.get("Config", {}).get("Hostname"),
            "command": inspect_data.get("Config", {}).get("Cmd"),
            "created": inspect_data.get("Created"),
            "platform": inspect_data.get("Platform")
        }
    except ContainerNotFoundError:
        return {"error": "Container not found", "container_id": container_id}
    except Exception as e:
        logger.error("inspect_parse_error", error=str(e))
        return {"error": f"Failed to inspect container: {e}"}


async def inspect_network(network_name: str) -> Dict[str, Any]:
    """Inspect network configuration"""
    try:
        # Network inspection via API
        network_data = await podman_client._api_request(
            "GET",
            f"/networks/{network_name}/json"
        )

        containers = {}
        for container_id, container_data in network_data.get("Containers", {}).items():
            containers[container_data.get("Name", container_id[:12])] = {
                "ip_address": container_data.get("IPv4Address", "").split("/")[0],
                "mac_address": container_data.get("MacAddress")
            }

        return {
            "network_name": network_name,
            "driver": network_data.get("Driver"),
            "scope": network_data.get("Scope"),
            "subnet": network_data.get("IPAM", {}).get("Config", [{}])[0].get("Subnet"),
            "gateway": network_data.get("IPAM", {}).get("Config", [{}])[0].get("Gateway"),
            "containers": containers,
            "options": network_data.get("Options", {})
        }
    except Exception as e:
        logger.error("network_inspect_parse_error", error=str(e))
        return {"error": f"Failed to inspect network: {e}", "network_name": network_name}


async def list_containers() -> Dict[str, Any]:
    """List all containers"""
    try:
        containers_data = await podman_client.list_containers(all_containers=True)

        containers = []
        for container in containers_data:
            containers.append({
                "id": container.get("Id", "")[:12],
                "name": container.get("Names", [""])[0] if isinstance(container.get("Names"), list) else container.get("Names", ""),
                "image": container.get("Image"),
                "status": container.get("State"),
                "ports": container.get("Ports"),
                "networks": container.get("Networks")
            })

        return {"containers": containers, "count": len(containers)}
    except Exception as e:
        logger.error("list_parse_error", error=str(e))
        return {"error": f"Failed to list containers: {e}"}


async def check_connectivity(source_container: str, target_host: str, target_port: Optional[int] = None) -> Dict[str, Any]:
    """Check network connectivity between containers"""
    # Note: Container exec is not available via API client (security restriction)
    # This function is deprecated and should not be used
    return {
        "source": source_container,
        "target": f"{target_host}:{target_port}" if target_port else target_host,
        "reachable": False,
        "error": "Container exec operations are disabled for security reasons",
        "recommendation": "Use container logs or inspect network settings instead",
        "tested_at": datetime.utcnow().isoformat()
    }


async def get_best_practices(context: str, service_type: Optional[str] = None) -> Dict[str, Any]:
    """Get containerization best practices"""
    practices = {
        "networking": {
            "practices": [
                "Use container names instead of localhost for inter-container communication",
                "Services in same Docker network can resolve by container name (DNS)",
                "Avoid using host network mode unless absolutely necessary",
                "Use bridge networks for isolated container groups",
                "Publish ports with 127.0.0.1:HOST_PORT:CONTAINER_PORT for security",
                "Container's localhost != Host's localhost",
                "Use environment variables for service discovery endpoints"
            ],
            "common_errors": [
                "Using localhost when container needs to reach another container",
                "Not specifying network for containers that need to communicate",
                "Publishing to 0.0.0.0 instead of 127.0.0.1 exposing services publicly"
            ],
            "examples": {
                "correct": "http://service-name:8080",
                "incorrect": "http://localhost:8080 (from inside container)"
            }
        },
        "volumes": {
            "practices": [
                "Use named volumes for persistent data",
                "Bind mounts for configuration files",
                "Use :Z flag for SELinux systems",
                "Never store secrets in volumes without encryption",
                "Set proper permissions on mounted directories"
            ]
        },
        "security": {
            "practices": [
                "Run containers as non-root user",
                "Use minimal base images (alpine, distroless)",
                "Scan images for vulnerabilities",
                "Set resource limits (memory, CPU)",
                "Use read-only root filesystem when possible",
                "Drop unnecessary capabilities",
                "Enable user namespace remapping"
            ]
        },
        "performance": {
            "practices": [
                "Use multi-stage builds to reduce image size",
                "Leverage build cache with proper layer ordering",
                "Use .dockerignore to exclude unnecessary files",
                "Set resource limits to prevent resource exhaustion",
                "Use connection pooling for database connections",
                "Implement health checks for proper orchestration"
            ]
        }
    }

    result = practices.get(context.lower(), {})

    if service_type:
        # Add service-specific recommendations
        service_recommendations = {
            "api": {
                "health_check": "Implement /health endpoint",
                "logging": "Use structured logging (JSON)",
                "graceful_shutdown": "Handle SIGTERM for graceful shutdown",
                "connection_management": "Use connection pooling, reuse HTTP sessions"
            },
            "database": {
                "persistence": "Always use named volumes for data",
                "backups": "Implement regular backup strategy",
                "connection_limits": "Configure max_connections appropriately"
            },
            "worker": {
                "queue_management": "Implement backpressure handling",
                "retry_logic": "Use exponential backoff for retries",
                "monitoring": "Expose metrics endpoint for monitoring"
            }
        }

        if service_type in service_recommendations:
            result["service_specific"] = service_recommendations[service_type]

    result["context"] = context
    result["service_type"] = service_type

    return result


async def start_container(container_id: str) -> Dict[str, Any]:
    """Start a container - DISABLED FOR SECURITY"""
    logger.warning("operation_not_allowed", operation="start", service="container-engine")
    return {
        "container": container_id,
        "action": "start",
        "success": False,
        "error": "Container start operations are not allowed for container-engine service",
        "recommendation": "Use health-monitor service for container lifecycle management"
    }


async def stop_container(container_id: str) -> Dict[str, Any]:
    """Stop a container - DISABLED FOR SECURITY"""
    logger.warning("operation_not_allowed", operation="stop", service="container-engine")
    return {
        "container": container_id,
        "action": "stop",
        "success": False,
        "error": "Container stop operations are not allowed for container-engine service",
        "recommendation": "Use health-monitor service for container lifecycle management"
    }


async def restart_container(container_id: str) -> Dict[str, Any]:
    """Restart a container - DISABLED FOR SECURITY"""
    logger.warning("operation_not_allowed", operation="restart", service="container-engine")
    return {
        "container": container_id,
        "action": "restart",
        "success": False,
        "error": "Container restart operations are not allowed for container-engine service",
        "recommendation": "Use health-monitor service for container lifecycle management"
    }


async def validate_dockerfile(dockerfile_path: str) -> Dict[str, Any]:
    """Validate Dockerfile against best practices"""
    try:
        with open(dockerfile_path, "r") as f:
            content = f.read()

        issues = []
        warnings = []
        recommendations = []

        lines = content.split("\n")

        # Check for best practices
        if "FROM" not in content:
            issues.append("Missing FROM instruction")

        if ":latest" in content:
            warnings.append("Using :latest tag - specify exact version for reproducibility")

        if "apt-get update" in content and "rm -rf /var/lib/apt/lists/*" not in content:
            warnings.append("apt-get update without cleanup - increases image size")

        if "COPY . ." in content:
            recommendations.append("Consider using .dockerignore to exclude unnecessary files")

        if "USER" not in content:
            warnings.append("No USER instruction - container will run as root")

        if "HEALTHCHECK" not in content:
            recommendations.append("Add HEALTHCHECK instruction for better orchestration")

        # Count layers
        layer_count = sum(1 for line in lines if line.strip().startswith(("RUN", "COPY", "ADD")))

        return {
            "dockerfile": dockerfile_path,
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "stats": {
                "total_lines": len(lines),
                "layer_count": layer_count
            }
        }
    except Exception as e:
        return {"error": str(e), "dockerfile": dockerfile_path}


async def get_container_logs(container_id: str, tail: int = 100) -> Dict[str, Any]:
    """Get container logs"""
    try:
        logs = await podman_client.get_container_logs(
            container_id,
            tail=tail,
            timestamps=False
        )
        return {
            "container_id": container_id,
            "logs": logs,
            "success": True,
            "tail": tail
        }
    except ContainerNotFoundError:
        return {
            "container_id": container_id,
            "logs": "",
            "success": False,
            "error": "Container not found",
            "tail": tail
        }
    except Exception as e:
        logger.error("get_logs_failed", container=container_id, error=str(e))
        return {
            "container_id": container_id,
            "logs": "",
            "success": False,
            "error": str(e),
            "tail": tail
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8095)
