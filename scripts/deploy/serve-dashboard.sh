#!/usr/bin/env bash
# serve-dashboard.sh — Development dashboard server (Phase 12.4)
#
# Provides a simple HTTP server for the AI Stack Command Center dashboard
# during development or when systemd services are not used.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
PORT="${DASHBOARD_PORT:-8889}"
WEB_ROOT="${SCRIPT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for static dashboard serving" >&2
  exit 1
fi

echo "Starting dashboard server on http://${BIND_ADDRESS}:${PORT}"
echo "Web root: ${WEB_ROOT}"

export DASHBOARD_PORT="${PORT}"
export DASHBOARD_BIND_ADDRESS="${BIND_ADDRESS}"
export WEB_ROOT="${WEB_ROOT}"

exec python3 -c '
import http.server
import socketserver
import json
import os
import subprocess
from pathlib import Path

PORT = int(os.getenv("DASHBOARD_PORT", 8889))
BIND_ADDRESS = os.getenv("DASHBOARD_BIND_ADDRESS", "127.0.0.1")
WEB_ROOT = Path(os.getenv("WEB_ROOT", ".")).resolve()
AQ_QA_PATH = WEB_ROOT / "scripts" / "ai" / "aq-qa"

class LayeredHealthHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/health/layered":
            self.handle_layered_health()
        else:
            # Serve files relative to the web root
            super().do_GET()

    def handle_layered_health(self):
        try:
            # Execute aq-qa script
            result = subprocess.run(
                [str(AQ_QA_PATH), "0", "--json"],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
                cwd=WEB_ROOT
            )
            qa_data = json.loads(result.stdout)

            # Group by layer
            layers = {i: {"status": "online", "checks": []} for i in range(1, 8)}

            for test in qa_data.get("tests", []):
                layer_num = test.get("layer")
                if layer_num and 1 <= layer_num <= 7:
                    layers[layer_num]["checks"].append(test)

            # Determine layer status
            for i in range(1, 8):
                layer_info = layers[i]
                if any(c["status"] == "FAIL" for c in layer_info["checks"]):
                    layer_info["status"] = "error"
                elif any(c["status"] == "SKIP" for c in layer_info["checks"]):
                    layer_info["status"] = "warning"

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(layers).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            error_payload = {"error": "Failed to get layered health", "details": str(e)}
            self.wfile.write(json.dumps(error_payload).encode("utf-8"))

with socketserver.TCPServer((BIND_ADDRESS, PORT), LayeredHealthHandler) as httpd:
    print(f"Serving at http://{BIND_ADDRESS}:{PORT}")
    httpd.serve_forever()
'
