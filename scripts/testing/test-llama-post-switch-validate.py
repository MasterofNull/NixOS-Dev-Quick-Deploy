#!/usr/bin/env python3
"""llama-post-switch-validate.sh against a stub llama server: pass path, MTP zero-acceptance and slow paths."""
import json
import os
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "llama-post-switch-validate.sh"


def make_handler(gen, drafted, accepted, health="ok"):
    class H(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send({"status": health})
            else:
                self.send_response(200)
                self.end_headers()

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if "response_format" in req:
                content = json.dumps({"fruit": "apple", "colour": "red"})
            else:
                content = "one, two, three"
            self._send({"choices": [{"message": {"content": content}}],
                        "timings": {"predicted_per_second": gen, "prompt_per_second": 6.0,
                                    "draft_n": drafted, "draft_n_accepted": accepted}})
    return H


def run(**kw):
    srv = HTTPServer(("127.0.0.1", 0), make_handler(**kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, LLAMA_URL=f"http://127.0.0.1:{srv.server_port}", AQ_VALIDATE_TIMEOUT_S="20")
    try:
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    finally:
        srv.shutdown()
        srv.server_close()


class Validate(unittest.TestCase):
    def test_pass(self):
        r = run(gen=4.5, drafted=10, accepted=6)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("RESULT: PASS", r.stdout)

    def test_zero_acceptance_fails_with_rollback(self):
        r = run(gen=4.5, drafted=10, accepted=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nixos-rebuild switch --rollback", r.stderr)

    def test_slow_fails(self):
        r = run(gen=1.0, drafted=10, accepted=5)
        self.assertEqual(r.returncode, 1)
        self.assertIn("tok/s below", r.stderr)

    def test_unhealthy_fails(self):
        r = run(gen=4.5, drafted=10, accepted=5, health="loading")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ROLLBACK", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
