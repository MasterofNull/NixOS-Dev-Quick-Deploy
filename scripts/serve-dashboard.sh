#!/run/current-system/sw/bin/bash
# Dashboard HTTP Server
# Serves the system monitoring dashboard and provides API endpoints for JSON data

set -euo pipefail

export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${HOME}/.nix-profile/bin:${HOME}/.local/state/nix/profiles/home-manager/bin"

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(/run/current-system/sw/bin/dirname "$SCRIPT_PATH")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="${HOME}/.local/share/nixos-system-dashboard"
PORT="${DASHBOARD_PORT:-8888}"
export DASHBOARD_BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS}"

# Source centralized service endpoints (optional)
# shellcheck source=config/service-endpoints.sh
if [[ -f "${DASHBOARD_DIR}/config/service-endpoints.sh" ]]; then
    source "${DASHBOARD_DIR}/config/service-endpoints.sh"
fi

# Export endpoint vars for the embedded Python server
export SERVICE_HOST
export AIDB_URL
export HYBRID_URL
export DASHBOARD_API_URL
export NGINX_HTTPS_URL

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
echo "📊 Dashboard: http://${SERVICE_HOST:-localhost}:$PORT/dashboard.html"
echo "📁 Data API: http://${SERVICE_HOST:-localhost}:$PORT/data/"
echo "🧩 Actions API: http://${SERVICE_HOST:-localhost}:$PORT/action"
echo "🔒 Bind address: ${BIND_ADDRESS}"
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
from collections import defaultdict
from datetime import datetime, timedelta
import threading

PORT = int(os.getenv('DASHBOARD_PORT', '8888'))
BIND_ADDRESS = os.getenv('DASHBOARD_BIND_ADDRESS', '127.0.0.1')
DATA_DIR = Path.home() / '.local/share/nixos-system-dashboard'
HOME_DASHBOARD_PREFIX = f"{DATA_DIR}/"
SERVICE_HOST = os.getenv('SERVICE_HOST', 'localhost')
HYBRID_URL = os.getenv('HYBRID_URL', f'http://{SERVICE_HOST}:8092')
AIDB_URL = os.getenv('AIDB_URL', f'http://{SERVICE_HOST}:8091')
NGINX_HTTPS_URL = os.getenv('NGINX_HTTPS_URL', f'https://{SERVICE_HOST}:8443')

def is_k8s_mode() -> bool:
    explicit = os.getenv('DASHBOARD_MODE', '').lower()
    if explicit in ('k8s', 'kubernetes'):
        return True
    if os.getenv('KUBECONFIG') or os.path.exists('/etc/rancher/k3s/k3s.yaml'):
        return True
    return False

def restart_service_k8s(service_name: str) -> bool:
    try:
        result = subprocess.run(
            ['kubectl', 'rollout', 'restart', f'deployment/{service_name}', '-n', os.getenv('AI_STACK_NAMESPACE', 'ai-stack')],
            capture_output=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False

class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.
    P1-SEC-002: Prevent DoS attacks via rate limiting.
    """
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is within rate limit"""
        with self.lock:
            now = datetime.now()
            cutoff = now - self.window

            # Clean old requests
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if req_time > cutoff
            ]

            # Check limit
            if len(self.requests[client_ip]) >= self.max_requests:
                return False

            # Record request
            self.requests[client_ip].append(now)
            return True

    def get_retry_after(self, client_ip: str) -> int:
        """Get retry-after seconds for rate-limited client"""
        with self.lock:
            if client_ip not in self.requests or not self.requests[client_ip]:
                return 0
            oldest = self.requests[client_ip][0]
            retry_time = oldest + self.window
            return int((retry_time - datetime.now()).total_seconds())

# Global rate limiter instance
# Increased from 60 to 150 req/min to handle dashboard initial load (loads ~16 JSON files)
# Dashboard needs burst capacity for initial page load without triggering 429 errors
rate_limiter = RateLimiter(max_requests=150, window_seconds=60)

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        # P1-SEC-002: Rate limiting check
        client_ip = self.client_address[0]
        # Whitelist localhost for development (but still apply rate limits)
        is_localhost = client_ip in ('127.0.0.1', '::1', 'localhost')
        if not is_localhost and not rate_limiter.is_allowed(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip)
            self.send_response(429)
            self.send_header('Content-type', 'application/json')
            self.send_header('Retry-After', str(retry_after))
            self.end_headers()
            error_msg = json.dumps({
                "error": "Rate limit exceeded",
                "retry_after_seconds": retry_after
            })
            self.wfile.write(error_msg.encode('utf-8'))
            return

        parsed = urlparse(self.path)
        clean_path = parsed.path

        # API: Get current configuration
        if clean_path == '/api/config':
            try:
                import yaml
                config_file = Path.home() / '.local/share/nixos-ai-stack/config/config.yaml'
                if not config_file.exists():
                    # Return defaults if file doesn't exist
                    default_config = {
                        "rate_limit": 60,
                        "checkpoint_interval": 100,
                        "backpressure_threshold_mb": 100,
                        "log_level": "INFO"
                    }
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(default_config).encode('utf-8'))
                    return

                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)

                # Extract relevant settings
                response = {
                    "rate_limit": config_data.get('rate_limiting', {}).get('requests_per_minute', 60),
                    "checkpoint_interval": config_data.get('continuous_learning', {}).get('checkpoint_interval', 100),
                    "backpressure_threshold_mb": config_data.get('continuous_learning', {}).get('backpressure_threshold_mb', 100),
                    "log_level": config_data.get('logging', {}).get('level', 'INFO')
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": f"Failed to read config: {str(e)}"})
                self.wfile.write(error_msg.encode('utf-8'))
                return

        # API: Get learning stats
        if clean_path == '/api/stats/learning':
            try:
                import urllib.request
                import urllib.error
                # Fetch from hybrid coordinator learning stats endpoint
                stats_url = f'{HYBRID_URL}/learning/stats'
                req = urllib.request.Request(stats_url, headers={'User-Agent': 'Dashboard/1.0'})

                with urllib.request.urlopen(req, timeout=5) as response:
                    content = response.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(content)
                    return
            except Exception as e:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": "Learning stats not available"})
                self.wfile.write(error_msg.encode('utf-8'))
                return

        # API: Get circuit breaker stats
        if clean_path == '/api/stats/circuit-breakers':
            try:
                import urllib.request
                import urllib.error
                # Fetch from hybrid coordinator health endpoint
                health_url = f'{HYBRID_URL}/health'
                req = urllib.request.Request(health_url, headers={'User-Agent': 'Dashboard/1.0'})

                with urllib.request.urlopen(req, timeout=5) as response:
                    content = response.read()
                    health_data = json.loads(content)
                    breakers = health_data.get('circuit_breakers', {})

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(breakers).encode('utf-8'))
                    return
            except Exception as e:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": "Circuit breaker stats not available"})
                self.wfile.write(error_msg.encode('utf-8'))
                return

        # Proxy AIDB health check requests to container network
        if clean_path.startswith('/aidb/'):
            try:
                import urllib.request
                import urllib.error
                # Validate and sanitize path to prevent injection
                aidb_path = clean_path.replace('/aidb/', '')
                # Whitelist allowed endpoints
                allowed_endpoints = ['health', 'health/live', 'health/ready', 'health/startup', 'health/detailed']
                if not any(aidb_path.startswith(ep) for ep in allowed_endpoints):
                    self.send_response(403)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    error_msg = json.dumps({"error": "Endpoint not allowed"})
                    self.wfile.write(error_msg.encode('utf-8'))
                    return

                # Use HTTP client to access AIDB via nginx (no subprocess)
                container_url = f'{NGINX_HTTPS_URL}/aidb/{aidb_path}'

                # Create request with timeout
                req = urllib.request.Request(container_url, headers={'User-Agent': 'Dashboard/1.0'})
                context = __import__('ssl').create_default_context()
                context.check_hostname = False
                context.verify_mode = __import__('ssl').CERT_NONE

                with urllib.request.urlopen(req, timeout=5, context=context) as response:
                    content = response.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(content)
                    return

            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": f"AIDB returned {e.code}"})
                self.wfile.write(error_msg.encode('utf-8'))
                return
            except urllib.error.URLError as e:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": "AIDB not accessible"})
                self.wfile.write(error_msg.encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": "Internal server error"})
                self.wfile.write(error_msg.encode('utf-8'))
                return

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
        elif clean_path.startswith(HOME_DASHBOARD_PREFIX):
            filename = clean_path.replace(HOME_DASHBOARD_PREFIX, '')
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
        # P1-SEC-002: Rate limiting check
        client_ip = self.client_address[0]
        # Whitelist localhost for development (but still apply rate limits)
        is_localhost = client_ip in ('127.0.0.1', '::1', 'localhost')
        if not is_localhost and not rate_limiter.is_allowed(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip)
            self.send_response(429)
            self.send_header('Content-type', 'application/json')
            self.send_header('Retry-After', str(retry_after))
            self.end_headers()
            error_msg = json.dumps({
                "error": "Rate limit exceeded",
                "retry_after_seconds": retry_after
            })
            self.wfile.write(error_msg.encode('utf-8'))
            return

        # API: Update configuration
        if self.path == '/api/config':
            try:
                import yaml
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                new_config = json.loads(body) if body else {}

                config_file = Path.home() / '.local/share/nixos-ai-stack/config/config.yaml'

                # Read existing config or create new one
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config_data = yaml.safe_load(f)
                else:
                    config_file.parent.mkdir(parents=True, exist_ok=True)
                    config_data = {}

                # Update configuration sections
                if 'rate_limiting' not in config_data:
                    config_data['rate_limiting'] = {}
                if 'continuous_learning' not in config_data:
                    config_data['continuous_learning'] = {}
                if 'logging' not in config_data:
                    config_data['logging'] = {}

                # Apply updates
                if 'rate_limit' in new_config:
                    config_data['rate_limiting']['requests_per_minute'] = new_config['rate_limit']
                if 'checkpoint_interval' in new_config:
                    config_data['continuous_learning']['checkpoint_interval'] = new_config['checkpoint_interval']
                if 'backpressure_threshold_mb' in new_config:
                    config_data['continuous_learning']['backpressure_threshold_mb'] = new_config['backpressure_threshold_mb']
                if 'log_level' in new_config:
                    config_data['logging']['level'] = new_config['log_level']

                # Write updated config
                with open(config_file, 'w') as f:
                    yaml.dump(config_data, f, default_flow_style=False)

                # Restart affected services (hybrid-coordinator and aidb)
                restarted = []
                if is_k8s_mode():
                    if restart_service_k8s('hybrid-coordinator'):
                        restarted.append('hybrid-coordinator')
                    if restart_service_k8s('aidb'):
                        restarted.append('aidb')
                else:
                    try:
                        result = subprocess.run(
                            ['podman', 'restart', 'local-ai-hybrid-coordinator'],
                            capture_output=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            restarted.append('hybrid-coordinator')
                    except Exception:
                        pass

                    try:
                        result = subprocess.run(
                            ['podman', 'restart', 'local-ai-aidb'],
                            capture_output=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            restarted.append('aidb')
                    except Exception:
                        pass

                response = {
                    "status": "success",
                    "message": "Configuration updated",
                    "restarted": restarted
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_msg = json.dumps({"error": f"Failed to update config: {str(e)}"})
                self.wfile.write(error_msg.encode('utf-8'))
                return

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


with ThreadingHTTPServer((BIND_ADDRESS, PORT), DashboardHandler) as httpd:
    print(f"✅ Server running on {BIND_ADDRESS}:{PORT}")
    httpd.serve_forever()
EOF
