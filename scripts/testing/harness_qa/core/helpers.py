"""Low-level check primitives used by phase modules."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError


def cmd_ok(*args: str, cwd: str | None = None, env: dict | None = None, timeout: int = 15) -> bool:
    """Return True if the command exits with code 0."""
    try:
        r = subprocess.run(
            list(args),
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def cmd_output(*args: str, cwd: str | None = None, env: dict | None = None, timeout: int = 15) -> str:
    """Run a command and return its combined stdout+stderr, or '' on error."""
    try:
        r = subprocess.run(
            list(args),
            capture_output=True, text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        return r.stdout + r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


_SANDBOX_DENIED_RE = re.compile(
    r"operation not permitted|permission denied|failed to connect to bus|"
    r"cannot connect to socket.*daemon-socket|read-only file system",
    re.IGNORECASE,
)


def is_sandbox_denied(text: str | None) -> bool:
    """Return True when probe output represents sandbox/permission denial."""
    return bool(text and _SANDBOX_DENIED_RE.search(text))


def host_observer_url(path: str = "/api/health/services/all") -> str:
    """Return the declared dashboard host-observer URL for agent-safe probes."""
    base = os.environ.get("AQ_HOST_OBSERVER_URL", "").strip()
    if not base:
        dashboard = os.environ.get("DASHBOARD_API_URL", "http://127.0.0.1:8889").rstrip("/")
        base = dashboard
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def host_observer_services(timeout: int = 5) -> dict[str, Any] | None:
    """Return service health map from the declared host observer, if available."""
    artifact_path = os.environ.get(
        "AQ_HOST_OBSERVER_FILE",
        "/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json",
    )
    try:
        with open(artifact_path, encoding="utf-8") as fh:
            artifact = json.load(fh)
        services = artifact.get("services")
        if isinstance(services, list):
            mapped = {}
            for service in services:
                if not isinstance(service, dict) or not service.get("name"):
                    continue
                status = service.get("status")
                mapped[str(service["name"])] = {
                    **service,
                    "status": "healthy" if status == "active" else status,
                    "systemd": {
                        "active": status == "active",
                        "status": status,
                        "sub_state": service.get("sub_state"),
                    },
                }
            if mapped:
                return mapped
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    data = http_json(host_observer_url(), timeout=timeout)
    if not isinstance(data, dict):
        return None
    services = data.get("services")
    return services if isinstance(services, dict) else None


def host_observer_service_status(service_id: str, timeout: int = 5) -> dict[str, Any] | None:
    """Return one service health record from the declared host observer."""
    services = host_observer_services(timeout=timeout)
    if not services:
        return None
    value = services.get(service_id)
    return value if isinstance(value, dict) else None


def output_matches(pattern: str, *args: str, timeout: int = 15) -> bool:
    """Return True if command output matches the regex pattern."""
    out = cmd_output(*args, timeout=timeout)
    return bool(re.search(pattern, out))


def port_bound(port: int, retries: int = 4, delay: float = 1.0) -> bool:
    """Check if a TCP port is listening (resilient check)."""
    import socket
    dashboard_safe = os.environ.get("AQ_QA_DASHBOARD_SAFE", "0").strip().lower() in {"1", "true", "yes", "on"}
    for attempt in range(retries):
        # Primary: socket connection check (most reliable across environments)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception:
            pass

        if dashboard_safe:
            if attempt < retries - 1:
                time.sleep(delay)
            continue

        # Secondary: ss command (fallback for detailed diagnostic if needed)
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=5,
            )
            if f":{port} " in result.stdout:
                return True
        except Exception:
            pass

        if attempt < retries - 1:
            time.sleep(delay)
    return False


def http_get(url: str, timeout: int = 5, headers: dict | None = None) -> tuple[int, str]:
    """Return (status_code, body) for a GET request, or (-1, '') on error."""
    try:
        req = Request(url, headers=headers or {})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        code = getattr(getattr(e, "code", None), "__int__", lambda: -1)()
        return code if isinstance(code, int) and code > 0 else -1, ""
    except Exception:
        return -1, ""


def http_health_ok(url: str, timeout: int = 5) -> bool:
    """Return True if GET url returns JSON with status='ok' or 'no slot available'."""
    _, body = http_get(url, timeout=timeout)
    try:
        d = json.loads(body)
        return d.get("status") in ("ok", "no slot available")
    except Exception:
        return False


def http_json(url: str, timeout: int = 5, headers: dict | None = None) -> Any:
    """Return parsed JSON from GET url, or None on error."""
    _, body = http_get(url, timeout=timeout, headers=headers)
    try:
        return json.loads(body)
    except Exception:
        return None


def http_post_json(
    url: str,
    payload: dict,
    headers: dict | None = None,
    timeout: int = 10,
) -> tuple[int, Any]:
    """Return (status_code, parsed_json_or_none) for a POST request."""
    import urllib.request
    data = json.dumps(payload).encode()
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception:
        return -1, None


def file_exists(path: str) -> bool:
    from pathlib import Path
    try:
        return Path(path).exists()
    except (OSError, PermissionError):
        return False


def file_readable(path: str) -> bool:
    from pathlib import Path
    try:
        p = Path(path)
        return p.exists() and p.stat().st_size > 0
    except (OSError, PermissionError):
        return False


def json_valid(path: str) -> bool:
    from pathlib import Path
    try:
        json.loads(Path(path).read_text())
        return True
    except Exception:
        return False
