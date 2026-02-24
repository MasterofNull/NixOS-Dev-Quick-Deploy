#!/usr/bin/env python3
"""
Claude API Proxy - Intercepts Claude Code API calls and routes through local AI stack

This proxy server:
1. Listens on SERVICE_HOST:ANTHROPIC_PROXY_PORT mimicking Anthropic API
2. Receives requests from Claude Code CLI
3. Routes simple queries to local LLM via hybrid coordinator
4. Routes complex queries to real Anthropic API
5. Logs all usage to telemetry system
6. Tracks token savings

Usage:
    # Start proxy server
    python3 scripts/claude-api-proxy.py

    # In another terminal, set environment variable before launching Claude
    export ANTHROPIC_BASE_URL=http://<service-host>:${ANTHROPIC_PROXY_PORT}
    claude

Environment Variables:
    ANTHROPIC_API_KEY - Real API key for remote routing
    ANTHROPIC_BASE_URL - Set to proxy URL to use local routing
    HYBRID_COORDINATOR_URL - Override coordinator URL (default: HYBRID_URL)
    AIDB_MCP_URL - Override AIDB URL (default: AIDB_URL)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

# Service endpoints
SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
HYBRID_COORDINATOR = os.getenv("HYBRID_COORDINATOR_URL", os.getenv("HYBRID_URL", "http://localhost"))
AIDB_MCP = os.getenv("AIDB_MCP_URL", os.getenv("AIDB_URL", "http://localhost"))
REAL_ANTHROPIC_API = "https://api.anthropic.com"
TELEMETRY_DIR = os.path.expanduser("~/.local/share/nixos-ai-stack/telemetry")

# Token thresholds for routing decisions
SIMPLE_QUERY_TOKENS = 100  # Queries under this use local LLM
COMPLEX_QUERY_TOKENS = 3000  # Queries over this use remote API

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(TELEMETRY_DIR, "proxy.log"))
    ]
)
logger = logging.getLogger(__name__)


class ClaudeAPIProxy(BaseHTTPRequestHandler):
    """Proxy handler that intercepts Claude API requests"""

    def do_POST(self):
        """Handle POST requests to /v1/messages endpoint"""

        if self.path.startswith("/v1/messages"):
            self._handle_messages_request()
        else:
            self._proxy_to_real_api("POST")

    def do_GET(self):
        """Handle GET requests (rate limits, etc.)"""
        self._proxy_to_real_api("GET")

    def _handle_messages_request(self):
        """Route messages through local AI stack or remote API"""

        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))

            # Extract query details
            messages = request_data.get("messages", [])
            max_tokens = request_data.get("max_tokens", 1024)

            # Estimate complexity (simple heuristic)
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            estimated_tokens = total_chars // 4  # Rough approximation

            # Routing decision
            use_local = self._should_use_local(estimated_tokens, max_tokens, request_data)

            if use_local:
                logger.info(f"📍 Routing to LOCAL (tokens ~{estimated_tokens})")
                response = self._route_to_local(request_data)
            else:
                logger.info(f"📍 Routing to REMOTE (tokens ~{estimated_tokens})")
                response = self._route_to_remote(request_data)

            # Log telemetry
            self._log_telemetry(request_data, response, use_local, estimated_tokens)

            # Send response back to Claude CLI
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            logger.error(f"❌ Proxy error: {e}")
            self._send_error_response(str(e))

    def _should_use_local(self, estimated_tokens: int, max_tokens: int, request: Dict) -> bool:
        """Decide whether to route locally or remotely"""

        # Always use remote for very complex queries
        if estimated_tokens > COMPLEX_QUERY_TOKENS or max_tokens > 2000:
            return False

        # Always use local for simple queries
        if estimated_tokens < SIMPLE_QUERY_TOKENS:
            return True

        # Medium complexity - check if local models are available
        try:
            health_check = urllib.request.urlopen(f"{HYBRID_COORDINATOR}/health", timeout=2)
            if health_check.status == 200:
                return True
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Hybrid coordinator health check failed: %s", e)

        return False

    def _route_to_local(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route request through hybrid coordinator"""

        try:
            # Extract user query
            messages = request_data.get("messages", [])
            if not messages:
                raise ValueError("No messages in request")

            last_message = messages[-1]
            query = last_message.get("content", "")

            # Get RAG context from AIDB
            context = self._get_rag_context(query)

            # Route through hybrid coordinator
            payload = {
                "query": query,
                "context": context,
                "force_local": True,
                "timestamp": datetime.now().isoformat()
            }

            req = urllib.request.Request(
                f"{HYBRID_COORDINATOR}/query",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            # Convert to Anthropic API format
            return self._format_as_anthropic_response(result, "local")

        except Exception as e:
            logger.error(f"❌ Local routing failed: {e}")
            # Fallback to remote
            return self._route_to_remote(request_data)

    def _route_to_remote(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route request to real Anthropic API"""

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        req = urllib.request.Request(
            f"{REAL_ANTHROPIC_API}/v1/messages",
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            }
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))

    def _get_rag_context(self, query: str) -> Dict[str, Any]:
        """Retrieve RAG context from AIDB"""

        try:
            req = urllib.request.Request(
                f"{AIDB_MCP}/documents?search={urllib.parse.quote(query)}&limit=3",
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.warning(f"⚠️ RAG retrieval failed: {e}")
            return {"documents": []}

    def _format_as_anthropic_response(self, local_result: Dict, source: str) -> Dict[str, Any]:
        """Convert local response to Anthropic API format"""

        return {
            "id": f"msg_{int(time.time())}_{source}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": local_result.get("response", local_result.get("answer", ""))
                }
            ],
            "model": local_result.get("model", "local-llm"),
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": local_result.get("tokens_used", 0),
                "output_tokens": local_result.get("tokens_generated", 0)
            }
        }

    def _log_telemetry(self, request: Dict, response: Dict, used_local: bool, estimated_tokens: int):
        """Log usage telemetry for metrics"""

        try:
            os.makedirs(TELEMETRY_DIR, exist_ok=True)

            telemetry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": "api_query_routed",
                "source": "claude_api_proxy",
                "metadata": {
                    "routing_decision": "local" if used_local else "remote",
                    "estimated_tokens": estimated_tokens,
                    "tokens_saved": estimated_tokens if used_local else 0,
                    "model": request.get("model", "unknown"),
                    "success": "error" not in response
                }
            }

            telemetry_file = os.path.join(TELEMETRY_DIR, f"events-{datetime.now().strftime('%Y-%m-%d')}.jsonl")
            with open(telemetry_file, 'a') as f:
                f.write(json.dumps(telemetry) + '\n')

            logger.info(f"📊 Telemetry logged: {telemetry['metadata']['routing_decision']}")

        except Exception as e:
            logger.error(f"⚠️ Telemetry logging failed: {e}")

    def _proxy_to_real_api(self, method: str):
        """Forward request directly to real Anthropic API"""

        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                self._send_error_response("ANTHROPIC_API_KEY not set")
                return

            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b''

            # Forward to real API
            req = urllib.request.Request(
                f"{REAL_ANTHROPIC_API}{self.path}",
                data=body if body else None,
                method=method,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                }
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                self.send_response(response.status)
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())

        except Exception as e:
            logger.error(f"❌ Proxy forwarding failed: {e}")
            self._send_error_response(str(e))

    def _send_error_response(self, error_msg: str):
        """Send error response to client"""

        error_response = {
            "type": "error",
            "error": {
                "type": "proxy_error",
                "message": error_msg
            }
        }

        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.debug(format % args)


def start_proxy(host=os.getenv("SERVICE_HOST", "127.0.0.1"), port=None):
    """Start the Claude API proxy server"""
    if port is None:
        port = int(os.getenv("ANTHROPIC_PROXY_PORT", "0"))

    # Ensure telemetry directory exists
    os.makedirs(TELEMETRY_DIR, exist_ok=True)

    logger.info("=" * 70)
    logger.info("CLAUDE API PROXY - Starting")
    logger.info("=" * 70)
    logger.info(f"📡 Listening on: {host}:{port}")
    logger.info(f"🔀 Hybrid Coordinator: {HYBRID_COORDINATOR}")
    logger.info(f"📚 AIDB MCP Server: {AIDB_MCP}")
    logger.info(f"📊 Telemetry Directory: {TELEMETRY_DIR}")
    logger.info("")
    logger.info("⚙️  Configuration:")
    logger.info(f"   Simple queries (<{SIMPLE_QUERY_TOKENS} tokens) → LOCAL")
    logger.info(f"   Complex queries (>{COMPLEX_QUERY_TOKENS} tokens) → REMOTE")
    logger.info("")
    logger.info("🚀 To use this proxy, set in your shell:")
    logger.info(f"   export ANTHROPIC_BASE_URL=http://{host}:{port}")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    server = HTTPServer((host, port), ClaudeAPIProxy)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n🛑 Proxy server stopped")
        server.shutdown()


if __name__ == "__main__":
    start_proxy()
