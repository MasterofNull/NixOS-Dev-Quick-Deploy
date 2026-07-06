#!/usr/bin/env python3
"""Unit tests for a2a_guard — outbound secret-scan + redaction + audit."""
import importlib.util
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("a2a_guard", str(ROOT / "scripts" / "ai" / "lib" / "a2a_guard.py"))
_spec = importlib.util.spec_from_loader("a2a_guard", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def test_detects_secrets():
    text = "here is a key sk-abcdefghij1234567890XYZ and ghp_" + "a" * 36
    f = mod.scan_secrets(text)
    kinds = {x["kind"] for x in f}
    if "openai_key" not in kinds or "github_pat_classic" not in kinds:
        _fail(f"expected openai+github pat, got {kinds}")
    # previews must be redacted (not the raw secret)
    if any("sk-abcdefghij" in x["match_preview"] for x in f):
        _fail("finding preview leaked the secret")
    print("PASS  detects openai + github secrets, previews redacted")


def test_clean_text():
    if mod.scan_secrets("just a normal prompt about caching design"):
        _fail("clean text flagged")
    print("PASS  clean text -> no findings")


def test_redact():
    r = mod.redact("token=SUPERSECRETVALUE123 rest")
    if "SUPERSECRETVALUE123" in r or "[REDACTED-SECRET]" not in r:
        _fail(f"redaction failed: {r}")
    print("PASS  redact replaces secret with marker")


def test_guard_blocks_outbound():
    tmp = Path(tempfile.mkdtemp()) / "audit.log"
    res = mod.guard_outbound("api_key=abcd1234efgh5678", from_agent="claude",
                             to_agent="codex", task_id="t1", block=True)
    if res["ok"]:
        _fail("outbound with secret should be blocked (ok=False)")
    if "[REDACTED-SECRET]" not in res["text"]:
        _fail("blocked outbound text should be redacted")
    print("PASS  guard_outbound blocks + redacts a secret-bearing prompt")


def test_audit_writes():
    tmp = Path(tempfile.mkdtemp()) / "audit.log"
    mod.audit("outbound", "claude", "gemini", "some prompt", [{"kind": "openai_key"}],
              task_id="t2", log_path=str(tmp))
    if not tmp.exists() or "gemini" not in tmp.read_text():
        _fail("audit did not write a record")
    if "some prompt" in tmp.read_text() and "openai_key" not in tmp.read_text():
        _fail("audit should record finding kinds")
    print("PASS  audit writes a redacted record")


def test_audit_summary_redacted():
    # The audit line must NOT leak the raw secret it is flagging.
    tmp = Path(tempfile.mkdtemp()) / "audit.log"
    raw = "auth with api_key=sk-abcdefghij1234567890XYZ now"
    mod.audit("outbound", "claude", "codex", raw, mod.scan_secrets(raw),
              task_id="t3", log_path=str(tmp))
    body = tmp.read_text()
    if "sk-abcdefghij1234567890XYZ" in body:
        _fail("audit summary leaked the raw secret")
    if "[REDACTED-SECRET]" not in body or "openai_key" not in body:
        _fail("audit summary should be redacted but retain finding kinds")
    print("PASS  audit summary redacted (no raw secret on disk)")


if __name__ == "__main__":
    test_detects_secrets()
    test_clean_text()
    test_redact()
    test_guard_blocks_outbound()
    test_audit_writes()
    test_audit_summary_redacted()
    print("\n6/6 a2a-guard tests passed")
