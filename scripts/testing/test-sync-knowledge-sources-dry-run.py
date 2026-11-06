#!/usr/bin/env python3
"""Regression: scripts/data/sync-knowledge-sources --dry-run must never POST to AIDB.

A local stub HTTP server stands in for AIDB and records every request. The sources file is a
temp YAML with one enabled url source served by the stub. The dry run must exit 0 with zero POSTs;
the same run without --dry-run must POST at least once, which proves the stub sees imports.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/data/sync-knowledge-sources"
FEED_PATH = "/feed.txt"
FEED_BODY = "Knowledge body served by the stub.\n"


class Stub:
    def __init__(self):
        self.requests = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _record(self, method, body=b""):
                stub.requests.append((method, self.path, body))

            def do_GET(self):
                self._record("GET")
                payload = FEED_BODY.encode("utf-8") if self.path == FEED_PATH else b"not found"
                self.send_response(200 if self.path == FEED_PATH else 404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self._record("POST", self.rfile.read(length))
                payload = json.dumps({"status": "approved"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def count(self, method):
        return sum(1 for m, _, _ in self.requests if m == method)


def run_sync(stub, tmp, sources_file, extra_args):
    key_file = tmp / "aidb_key"
    key_file.write_text("test-key\n")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp),
        "XDG_CACHE_HOME": str(tmp / "cache"),
        "AIDB_URL": stub.url,
        "AIDB_API_KEY_FILE": str(key_file),
        "KNOWLEDGE_SOURCES_FILE": str(sources_file),
        "AIDB_IMPORT_DELAY_MS": "0",
        "AIDB_IMPORT_MAX_RETRIES": "0",
    }
    try:
        return subprocess.run(
            ["bash", str(SCRIPT), *extra_args],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return subprocess.CompletedProcess(e.cmd, 124, out, f"timeout after 60s (args={extra_args})")


def write_sources(tmp, stub):
    sources = tmp / "knowledge-sources.yaml"
    sources.write_text(
        "sources:\n"
        "  - id: dry-run-fixture\n"
        "    type: url\n"
        "    description: stub-served fixture source\n"
        f"    url: {stub.url}{FEED_PATH}\n"
        "    fetch:\n"
        "      - full\n"
        "    enabled: true\n"
    )
    return sources


def main():
    failures = []
    with Stub() as stub, tempfile.TemporaryDirectory(prefix="sync-dry-run-") as d:
        tmp = Path(d)
        sources = write_sources(tmp, stub)

        dry = run_sync(stub, tmp, sources, ["--dry-run"])
        dry_posts = stub.count("POST")
        if dry.returncode != 0:
            failures.append(f"--dry-run exited {dry.returncode}: {dry.stderr.strip()[-500:]}")
        if dry_posts != 0:
            failures.append(f"--dry-run sent {dry_posts} POST(s) to AIDB stub: {stub.requests}")
        if "DRY RUN" not in dry.stdout:
            failures.append(f"--dry-run output lacks 'DRY RUN' marker: {dry.stdout[-500:]}")

        stub.requests.clear()
        live = run_sync(stub, tmp, sources, [])
        live_posts = stub.count("POST")
        if live.returncode != 0:
            failures.append(f"live run exited {live.returncode}: {live.stderr.strip()[-500:]}")
        if live_posts < 1:
            failures.append("live run (no --dry-run) sent no POST; test cannot observe imports")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"PASS: --dry-run sent 0 POSTs (rc=0); live run sent {live_posts} POST(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
