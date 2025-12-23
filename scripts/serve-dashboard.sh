#!/run/current-system/sw/bin/bash
# Dashboard HTTP Server
# Serves the system monitoring dashboard and provides API endpoints for JSON data

set -euo pipefail

export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${HOME}/.nix-profile/bin"

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(/run/current-system/sw/bin/dirname "$SCRIPT_PATH")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="${HOME}/.local/share/nixos-system-dashboard"
PORT="${DASHBOARD_PORT:-8888}"

# Bail early if port is already in use to avoid Python traceback.
if command -v ss >/dev/null 2>&1; then
    if ss -ltn "sport = :${PORT}" | /run/current-system/sw/bin/grep -q ":${PORT}"; then
        echo "ERROR: Port ${PORT} is already in use."
        echo "Hint: run 'ss -ltnp \"sport = :${PORT}\"' to see the process, or set DASHBOARD_PORT."
        exit 1
    fi
fi

# Ensure data directory exists
mkdir -p "$DATA_DIR"

# Start Python HTTP server with custom handler
cd "$DASHBOARD_DIR"

echo "🌐 Starting NixOS System Dashboard Server..."
echo "📊 Dashboard: http://localhost:$PORT/dashboard.html"
echo "📁 Data API: http://localhost:$PORT/data/"
echo "🧩 Actions API: http://localhost:$PORT/action"
echo ""
echo "Press Ctrl+C to stop"

# Create a simple Python server with CORS support
python_bin=""
if command -v python3 >/dev/null 2>&1; then
    python_bin="python3"
elif command -v python >/dev/null 2>&1; then
    python_bin="python"
fi

if [[ -z "$python_bin" ]]; then
    echo "ERROR: python not found in PATH. Install python3 or update dashboard-server.service PATH."
    exit 127
fi

"$python_bin" - <<'EOF'
import http.server
import socketserver
import os
import json
import shlex
import subprocess
from pathlib import Path
from urllib.parse import urlparse

PORT = int(os.getenv('DASHBOARD_PORT', '8888'))
DATA_DIR = Path.home() / '.local/share/nixos-system-dashboard'

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path

        # Serve JSON data files
        if clean_path.startswith('/data/'):
            filename = clean_path.replace('/data/', '')
            filepath = DATA_DIR / filename

            if filepath.exists() and filepath.suffix == '.json':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
        elif clean_path.startswith('/.local/share/nixos-system-dashboard/'):
            filename = clean_path.replace('/.local/share/nixos-system-dashboard/', '')
            filepath = DATA_DIR / filename

            if filepath.exists() and filepath.suffix == '.json':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
        elif clean_path.startswith(f'/home/{os.getenv("USER", "hyperd")}/.local/share/nixos-system-dashboard/'):
            filename = clean_path.replace(f'/home/{os.getenv("USER", "hyperd")}/.local/share/nixos-system-dashboard/', '')
            filepath = DATA_DIR / filename

            if filepath.exists() and filepath.suffix == '.json':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
        elif clean_path.count('/') == 1 and clean_path.endswith('.json'):
            filename = clean_path.lstrip('/')
            filepath = DATA_DIR / filename

            if filepath.exists():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return

        # Default file serving
        super().do_GET()

    def do_POST(self):
        if self.path != '/action':
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            payload = json.loads(body) if body else {}
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        label = payload.get('label')
        if not label:
            self.send_response(400)
            self.end_headers()
            return

        config_path = DATA_DIR / 'config.json'
        if not config_path.exists():
            self.send_response(500)
            self.end_headers()
            return

        try:
            config = json.loads(config_path.read_text())
        except Exception:
            self.send_response(500)
            self.end_headers()
            return

        actions = config.get('actions', [])
        selected = next((action for action in actions if action.get('label') == label), None)
        if not selected:
            self.send_response(404)
            self.end_headers()
            return

        if selected.get('mode') != 'run':
            self.send_response(403)
            self.end_headers()
            return

        command = selected.get('command')
        if not command:
            self.send_response(400)
            self.end_headers()
            return

        try:
            result = subprocess.run(
                shlex.split(command),
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                timeout=120
            )
            output = (result.stdout or '') + (result.stderr or '')
            response = {
                'status': 'ok' if result.returncode == 0 else 'error',
                'code': result.returncode,
                'message': f"{label} finished with exit code {result.returncode}",
                'output': output[-4000:]
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except subprocess.TimeoutExpired:
            self.send_response(504)
            self.end_headers()
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        # Cleaner logging
        if not self.path.endswith(('.ico', '.map')):
            print(f"[{self.log_date_time_string()}] {format % args}")

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


with ThreadingHTTPServer(("", PORT), DashboardHandler) as httpd:
    print(f"✅ Server running on port {PORT}")
    httpd.serve_forever()
EOF
