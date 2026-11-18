#!/usr/bin/env python3
"""Regression test: json_schema-constrained decoding for machine-read local output.

Covers the helper in shared/llm_config.py and the reviewer path of
scripts/ai/lib/dispatch.py DirectRunner, against a stub llama.cpp HTTP server
(no real inference):
  1. a schema is attached as response_format json_schema
  2. ignore_eos is dropped alongside grammar/json_schema (llama.cpp b12489 = 400)
  3. AQ_LOCAL_JSON_SCHEMA=0 sends the old free-text payload
  4. the reviewer output file still carries Reviewed-head-sha / Review-Disposition lines
  5. no source file combines ignore_eos with grammar/json_schema
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "shared"))
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
os.environ["SLOT_QUEUE"] = "0"

import llm_config as L  # noqa: E402

SHA = "a" * 40
VERDICT = {"notes": "Looks fine.", "reviewed_head_sha": SHA, "disposition": "PASS_WITH_FOLLOWUPS"}
SEEN: list[dict] = []


class Stub(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        body = json.dumps([{"id": 0, "is_processing": False}]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        SEEN.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        text = json.dumps(VERDICT) if "response_format" in SEEN[-1] else "free text\nReview-Disposition: PASS"
        chunks = [{"choices": [{"delta": {"content": text}, "finish_reason": None}]},
                  {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                  {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


def run_reviewer(url: str, outdir: Path, name: str) -> str:
    import dispatch
    from task_config import TaskConfig

    cfg = TaskConfig(mode="direct", role="reviewer", max_tokens=900, timeout_secs=20,
                     llama_url=url, hybrid_url=url, ralph_url=url, task_type="structured")
    out = outdir / f"{name}.log"
    assert dispatch.DirectRunner().run(cfg, "review this", out, task_id=name), "runner failed"
    return out.read_text()


def main() -> int:
    # helper unit checks
    p = L.attach_json_schema({"ignore_eos": True, "messages": []}, L.REVIEW_VERDICT_SCHEMA, "v")
    assert p["response_format"]["json_schema"]["schema"] is L.REVIEW_VERDICT_SCHEMA
    assert "ignore_eos" not in p, "ignore_eos must be stripped alongside a schema"
    assert L.attach_json_schema({"a": 1}, None) == {"a": 1}
    for extra in ({"grammar": "root ::= x"}, {"json_schema": {"type": "object"}},
                  {"response_format": {"type": "json_schema", "json_schema": {}}}):
        assert "ignore_eos" not in L.build_llama_payload([{"role": "user", "content": "x"}], ignore_eos=True, **extra), extra
    assert L.build_llama_payload([{"role": "user", "content": "x"}], ignore_eos=True)["ignore_eos"] is True
    os.environ["AQ_LOCAL_JSON_SCHEMA"] = "0"
    assert "response_format" not in L.attach_json_schema({}, L.REVIEW_VERDICT_SCHEMA)
    os.environ.pop("AQ_LOCAL_JSON_SCHEMA")
    assert L.render_review_verdict("not json") is None
    assert L.render_review_verdict(json.dumps({**VERDICT, "disposition": "MAYBE"})) is None

    # end-to-end against the stub
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}"
    with tempfile.TemporaryDirectory() as td:
        outdir = Path(td)
        text = run_reviewer(url, outdir, "on")
        rf = SEEN[-1]["response_format"]
        assert rf["type"] == "json_schema" and rf["json_schema"]["schema"]["required"], rf
        assert "ignore_eos" not in SEEN[-1]
        assert re.search(rf"^Reviewed-head-sha: {SHA}$", text, re.M), text
        assert re.search(r"^Review-Disposition: PASS_WITH_FOLLOWUPS$", text, re.M), text
        assert json.loads((outdir / "on.log.verdict.json").read_text()) == VERDICT

        os.environ["AQ_LOCAL_JSON_SCHEMA"] = "0"
        text = run_reviewer(url, outdir, "off")
        assert "response_format" not in SEEN[-1], "kill switch must send the free-text payload"
        assert "Review-Disposition: PASS" in text
    srv.shutdown()

    # no source combines ignore_eos with grammar/json_schema
    hits = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "ignore_eos", "--", "*.py", "*.sh", "*.nix",
                           ":!scripts/testing/test-constrained-decoding.py"],
                          capture_output=True, text=True).stdout.split()
    for f in hits:
        src = (ROOT / f).read_text(errors="replace")
        if f != "ai-stack/mcp-servers/shared/llm_config.py":
            assert not re.search(r"grammar|json_schema", src), f"{f} mixes ignore_eos with grammar/json_schema"
    print("PASS test-constrained-decoding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
