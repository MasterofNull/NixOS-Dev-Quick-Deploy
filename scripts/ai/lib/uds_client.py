"""
UDS and HTTP Client for Agent Auth (AUTH-S7).

Provides request_http_or_uds for transparent HTTP-over-UDS or TCP communication.
Automatically renders guided deny error bodies when coordinator rejects a scope.
"""

from typing import Dict, Any, Optional
import http.client
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request


class UDSHTTPConnection(http.client.HTTPConnection):
    """HTTP Connection targeting a Unix Domain Socket."""

    def __init__(self, socket_path: str, timeout: int = 30):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(self.socket_path)
            self.sock = sock
        except Exception:
            sock.close()
            raise


def split_uds_url(url: str) -> tuple[str, str]:
    """
    Parse a UDS URL into (socket_path, request_path).
    Supports:
      - unix:///run/ai-hybrid/agent.sock:/hints?q=test -> (/run/ai-hybrid/agent.sock, /hints?q=test)
      - unix:///run/ai-hybrid/agent.sock/hints?q=test  -> (/run/ai-hybrid/agent.sock, /hints?q=test)
    """
    raw = url[len("unix://"):]
    if ":" in raw:
        sock_path, req_path = raw.split(":", 1)
    elif ".sock" in raw:
        idx = raw.find(".sock") + 5
        sock_path = raw[:idx]
        req_path = raw[idx:] or "/"
    else:
        sock_path = raw
        req_path = "/"

    if not req_path.startswith("/"):
        req_path = "/" + req_path
    return sock_path, req_path


def request_http_or_uds(
    url: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    tcp_fallback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute an HTTP request over UDS or standard TCP HTTP.
    If UDS fails with connection error and tcp_fallback_url is supplied, falls back to TCP.
    """
    hdrs = dict(headers or {})

    if url.startswith("unix://"):
        sock_path, req_path = split_uds_url(url)
        conn = None
        try:
            conn = UDSHTTPConnection(sock_path, timeout=timeout)
            conn.request(method, req_path, body=data, headers=hdrs)
            resp = conn.getresponse()
            resp_body = resp.read()

            if resp.status >= 400:
                try:
                    err_body = json.loads(resp_body)
                    return {
                        "error": err_body.get("reason", resp.reason),
                        "status": resp.status,
                        "guided_deny": err_body.get("guided_deny") or err_body.get("guidance"),
                        "body": err_body,
                    }
                except Exception:
                    return {
                        "error": resp.reason,
                        "status": resp.status,
                        "raw": resp_body.decode(errors="replace"),
                    }

            return json.loads(resp_body)
        except (OSError, socket.error) as e:
            if tcp_fallback_url:
                fallback_target = f"{tcp_fallback_url.rstrip('/')}{req_path}"
                return request_http_or_uds(fallback_target, method=method, data=data, headers=hdrs, timeout=timeout)
            return {"error": str(e), "uds_error": True}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    else:
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
                return {
                    "error": err_body.get("reason", e.reason),
                    "status": e.code,
                    "guided_deny": err_body.get("guided_deny") or err_body.get("guidance"),
                    "body": err_body,
                }
            except Exception:
                return {"error": e.reason, "status": e.code}
        except Exception as e:
            return {"error": str(e)}
