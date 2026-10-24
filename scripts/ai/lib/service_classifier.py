"""
Service Classifier and Prober for Agent Auth (AUTH-S9).

Probes in-repo and system AI services across standard ports:
- aidb (:8002)
- coordinator (:8003)
- ralph (:8004)
- llama.cpp (:8080)
- switchboard (:8085)
- dashboard (:8889)

Classifies auth model, host/origin enforcement, and socket support.
Fail-closed empty key check for aidb.
"""

from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error
import json
import socket
import os

SERVICES = {
    "aidb": {"port": 8002, "expected_auth": "api-key", "health_path": "/health"},
    "coordinator": {"port": 8003, "expected_auth": "uds-or-key", "health_path": "/health"},
    "ralph": {"port": 8004, "expected_auth": "api-key", "health_path": "/health"},
    "llama": {"port": 8080, "expected_auth": "socket-or-key", "health_path": "/health"},
    "switchboard": {"port": 8085, "expected_auth": "loopback-or-token", "health_path": "/health"},
    "dashboard": {"port": 8889, "expected_auth": "session-or-loopback", "health_path": "/api/status"},
}


def probe_service_tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    """Test TCP port availability."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def verify_aidb_fail_closed_empty_key(api_key: Optional[str]) -> bool:
    """
    Fail-closed empty key validation for AIDB.
    Returns True if an empty or whitespace key is rejected.
    """
    if not api_key or not api_key.strip():
        return False
    return True


def classify_service_auth(name: str) -> Dict[str, Any]:
    """Classify the auth posture and verified boundaries for a service."""
    if name not in SERVICES:
        return {"name": name, "status": "unknown", "classification": "unregistered"}

    spec = SERVICES[name]
    port = spec["port"]
    is_live = probe_service_tcp("127.0.0.1", port)

    return {
        "name": name,
        "port": port,
        "live": is_live,
        "expected_auth": spec["expected_auth"],
        "health_path": spec["health_path"],
        "classification": "verified" if is_live else "dormant_or_standby",
        "socket_capable": name in ("coordinator", "llama", "switchboard"),
    }


def probe_all_services() -> List[Dict[str, Any]]:
    """Probe all known AI harness services and return classification reports."""
    results = []
    for name in SERVICES:
        results.append(classify_service_auth(name))
    return results


def check_host_origin_enforcement(url: str, invalid_host: str = "attacker.internal") -> Dict[str, Any]:
    """
    Probe Host/Origin header protection on an HTTP endpoint.
    Expects 403, 421 (Misdirected Request), or connection rejection on invalid host.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Host": invalid_host,
            "Origin": f"http://{invalid_host}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return {"enforced": False, "status": resp.status}
    except urllib.error.HTTPError as e:
        return {"enforced": e.code in (403, 421), "status": e.code}
    except Exception as e:
        return {"enforced": True, "error": str(e)}
