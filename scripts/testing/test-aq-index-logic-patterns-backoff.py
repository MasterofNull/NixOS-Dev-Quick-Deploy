#!/usr/bin/env python3
"""aq-index-logic-patterns: 429 is retried with backoff, and a partial ingest exits non-zero."""
import importlib.machinery
import importlib.util
import io
import sys
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "aq-index-logic-patterns"
loader = importlib.machinery.SourceFileLoader("aq_index_logic_patterns", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = mod
loader.exec_module(mod)


class Resp:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_429():
    return urllib.error.HTTPError("http://aidb/documents", 429, "Too Many", {}, io.BytesIO(b""))


DOC = mod.PatternDoc(path=ROOT / "x.py", line=1, pattern_type="t", title="doc", content="c")


def main() -> int:
    calls = []

    def flaky(req, timeout=10):
        calls.append(1)
        if len(calls) <= 2:
            raise http_429()
        return Resp()

    with mock.patch("urllib.request.urlopen", side_effect=flaky), mock.patch.object(mod.time, "sleep") as slp:
        assert mod._ingest(DOC, "k", False) is True, "429 then success must ingest"
    assert len(calls) == 3, f"expected 3 attempts, got {len(calls)}"
    assert [c.args[0] for c in slp.call_args_list] == [2, 4], slp.call_args_list

    with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: (_ for _ in ()).throw(http_429())), \
            mock.patch.object(mod.time, "sleep"):
        assert mod._ingest(DOC, "k", False) is False, "persistent 429 must fail"

    results = iter([True, False])
    with mock.patch.object(mod, "scan_repo", return_value=[DOC, DOC]), \
            mock.patch.object(mod, "_aidb_key", return_value="k"), \
            mock.patch.object(mod, "_ingest", side_effect=lambda *a: next(results)), \
            mock.patch.object(mod.time, "sleep"), mock.patch.object(sys, "argv", ["x"]):
        assert mod.main() == 1, "partial ingest must exit non-zero"
    print("PASS: aq-index-logic-patterns 429 backoff + partial-ingest exit code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
