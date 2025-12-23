#!/usr/bin/env python3
"""
AI Stack Manager
Provides tool-friendly functions for interacting with the local Podman AI stack.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

import podman
import requests
from dotenv import load_dotenv

load_dotenv()


def _default_podman_socket() -> str:
    uid = os.getuid()
    return f"unix:///run/user/{uid}/podman/podman.sock"


class PodmanManager:
    """A manager for the AI Podman stack."""

    def __init__(self) -> None:
        base_url = os.getenv("PODMAN_HOST", _default_podman_socket())
        try:
            self.client = podman.PodmanClient(base_url=base_url)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to connect to Podman at {base_url}. Is Podman running? Error: {exc}"
            ) from exc

    def get_all_containers(self):
        """Returns a list of all containers."""
        return self.client.containers.list(all=True)

    def get_container_by_name(self, name: str):
        """Returns a container by name."""
        for container in self.get_all_containers():
            if name in container.name:
                return container
        return None

    def start_container(self, name: str) -> Dict[str, str]:
        """Starts a container by name."""
        container = self.get_container_by_name(name)
        if container:
            if container.status != "running":
                container.start()
                return {"status": "success", "message": f"Container {name} started."}
            return {"status": "success", "message": f"Container {name} is already running."}
        return {"status": "error", "message": f"Container {name} not found."}

    def stop_container(self, name: str) -> Dict[str, str]:
        """Stops a container by name."""
        container = self.get_container_by_name(name)
        if container:
            if container.status == "running":
                container.stop()
                return {"status": "success", "message": f"Container {name} stopped."}
            return {"status": "success", "message": f"Container {name} is not running."}
        return {"status": "error", "message": f"Container {name} not found."}

    def get_container_status(self, name: str) -> Dict[str, str]:
        """Gets the status of a container by name."""
        container = self.get_container_by_name(name)
        if container:
            return {"name": container.name, "status": container.status}
        return {"name": name, "status": "not found"}

    def get_container_logs(self, name: str, tail: int = 100) -> str:
        """Gets the logs of a container by name."""
        container = self.get_container_by_name(name)
        if container:
            return container.logs(tail=tail).decode("utf-8", errors="ignore")
        return f"Container {name} not found."


def get_ai_stack_status() -> List[Dict[str, str]]:
    """
    Gets the status of all services in the AI Podman stack.

    :return: A list of dictionaries, where each dictionary represents a service and its status.
    """
    manager = PodmanManager()
    all_containers = manager.get_all_containers()
    return [{"name": c.name, "status": c.status} for c in all_containers]


def start_ai_service(service_name: str) -> Dict[str, str]:
    """
    Starts a specific service in the AI Podman stack.

    :param service_name: The name of the service to start (e.g., 'ollama', 'qdrant').
    :return: A dictionary with the status of the operation.
    """
    manager = PodmanManager()
    return manager.start_container(service_name)


def stop_ai_service(service_name: str) -> Dict[str, str]:
    """
    Stops a specific service in the AI Podman stack.

    :param service_name: The name of the service to stop.
    :return: A dictionary with the status of the operation.
    """
    manager = PodmanManager()
    return manager.stop_container(service_name)


def get_ai_service_logs(service_name: str, tail: int = 100) -> str:
    """
    Gets the logs of a specific service in the AI Podman stack.

    :param service_name: The name of the service to get the logs from.
    :param tail: The number of lines to return from the end of the logs.
    :return: The logs as a string.
    """
    manager = PodmanManager()
    return manager.get_container_logs(service_name, tail)


def check_service_health(service_name: str) -> Dict[str, str]:
    """
    Checks the health of a specific service by making a request to its health endpoint.

    :param service_name: The name of the service to check.
    :return: A dictionary with the health status.
    """
    health_endpoints = {
        "llama-cpp": "http://localhost:8080/health",
        "aidb": "http://localhost:8091/health",
        "hybrid-coordinator": "http://localhost:8092/health",
        "qdrant": "http://localhost:6333/healthz",
        "open-webui": "http://localhost:3001/health",
    }

    if service_name not in health_endpoints:
        return {"status": "error", "message": f"No health endpoint defined for service: {service_name}"}

    try:
        response = requests.get(health_endpoints[service_name], timeout=5)
        response.raise_for_status()
        return {"status": "success", "message": f"{service_name} is healthy."}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Failed to connect to {service_name}: {exc}"}


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP bridge for tool-based access (JSON in/out)."""

    def _send_json(self, payload: Dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _read_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        data = self.rfile.read(length).decode("utf-8")
        return json.loads(data) if data else {}

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send_json({"status": "ok"})
        if parsed.path == "/status":
            return self._send_json({"services": get_ai_stack_status()})
        if parsed.path == "/logs":
            params = parse_qs(parsed.query)
            service = (params.get("service") or [""])[0]
            tail = int((params.get("tail") or [100])[0])
            return self._send_json({"service": service, "logs": get_ai_service_logs(service, tail)})
        if parsed.path == "/service-health":
            params = parse_qs(parsed.query)
            service = (params.get("service") or [""])[0]
            return self._send_json(check_service_health(service))
        return self._send_json({"status": "error", "message": "Unknown endpoint"}, status=404)

    def do_POST(self):  # noqa: N802
        if self.path == "/start":
            payload = self._read_body()
            return self._send_json(start_ai_service(payload.get("service", "")))
        if self.path == "/stop":
            payload = self._read_body()
            return self._send_json(stop_ai_service(payload.get("service", "")))
        return self._send_json({"status": "error", "message": "Unknown endpoint"}, status=404)


def run_bridge_server(host: str = "127.0.0.1", port: int = 8095) -> None:
    server = HTTPServer((host, port), BridgeHandler)
    print(f"AI stack bridge listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI stack manager bridge")
    parser.add_argument("--serve", action="store_true", help="Run the HTTP bridge server")
    parser.add_argument("--host", default="127.0.0.1", help="Bridge bind host")
    parser.add_argument("--port", type=int, default=8095, help="Bridge bind port")
    args = parser.parse_args()

    if args.serve:
        run_bridge_server(args.host, args.port)
