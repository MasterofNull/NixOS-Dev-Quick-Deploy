#!/usr/bin/env python3
"""Regression: coordinator restart must flush only bare legacy embedding keys,
never the live e<epoch>:m<slug>: keys (bug: every restart emptied the cache)."""
import asyncio
import ast
import fnmatch
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack/mcp-servers/hybrid-coordinator"
sys.path[:0] = [str(HC / "knowledge"), str(HC)]
import embedding_cache  # noqa: E402


class FakeRedis:
    def __init__(self, keys):
        self.keys = set(keys)

    async def ping(self):
        return True

    async def scan_iter(self, match):
        pattern = match.replace("[^", "[!")  # redis glob negation -> fnmatch
        for k in list(self.keys):
            if fnmatch.fnmatchcase(k, pattern):
                yield k

    async def delete(self, *keys):
        self.keys -= set(keys)
        return len(keys)


async def main() -> int:
    live = embedding_cache.EmbeddingCache(model_name="BAAI/bge-small-en-v1.5", cache_epoch=2)
    current = live._text_to_key("hello")
    keys = [current, "embedding:mold-slug:vA:" + "a" * 64, "embedding:" + "b" * 64, "other:x"]
    fake = FakeRedis(keys)
    with mock.patch.object(embedding_cache.aioredis, "from_url", mock.AsyncMock(return_value=fake)):
        await live.initialize(flush_on_model_change=True)
    assert current in fake.keys, "live key was flushed"
    assert "embedding:mold-slug:vA:" + "a" * 64 in fake.keys
    assert "embedding:" + "b" * 64 not in fake.keys, "bare legacy key survived"
    assert "other:x" in fake.keys

    src = (HC / "extensions/continuous_learning.py").read_text()
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "awatch"]
    assert calls and all(any(k.arg == "recursive" and getattr(k.value, "value", True) is False
                             for k in c.keywords) for c in calls), "awatch must be non-recursive"
    print("PASS: embedding cache keeps live keys; learning watcher non-recursive")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
