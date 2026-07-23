#!/usr/bin/env python3
"""
Slice 2a regression tests — ai-stack/local-agents/context_cache.py.

Exercises the embed-backed semantic context cache library WITHOUT a live
embed (:8081) or Qdrant (:6333) server: the http client (httpx.Client) is
monkeypatched with a fake that dispatches on (method, url) to a stubbed
response or an exception, so every branch — success, non-200, and dead
endpoint — is reachable deterministically.

Tests:
  1. embed_text: None on dead endpoint; vector on stubbed 200
  2. cache_evicted: None when embed unavailable (no raise); collection name +
     N upserted points when stubbed
  3. retrieve_ctx: ordered texts on stubbed search; [] on embed failure and
     on search-endpoint error
  4. scratchpad_message: None on empty; one system message containing every
     snippet on non-empty (pure function, no I/O)
  5. delete_collection: never raises on a dead endpoint
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "ai-stack" / "local-agents"))

import context_cache  # noqa: E402


class FakeResponse:
    """Minimal stand-in for httpx.Response — only what context_cache reads."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


class FakeClient:
    """Stand-in for httpx.Client — routes every call through a test-supplied
    dispatcher so tests can assert on exact requests and force any response
    or exception path without a live server."""

    def __init__(self, dispatcher, *args, **kwargs):
        self._dispatcher = dispatcher

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, json=None, params=None):
        return self._dispatcher("POST", url, json, params)

    def get(self, url, params=None):
        return self._dispatcher("GET", url, None, params)

    def put(self, url, json=None, params=None):
        return self._dispatcher("PUT", url, json, params)

    def delete(self, url, params=None):
        return self._dispatcher("DELETE", url, None, params)


def _client_factory(dispatcher):
    """Returns a callable usable as a drop-in replacement for httpx.Client."""
    def _factory(*args, **kwargs):
        return FakeClient(dispatcher)
    return _factory


def _dead_dispatcher(method, url, json, params):
    raise ConnectionError(f"dead endpoint: {method} {url}")


class TestEmbedText(unittest.TestCase):

    def test_none_on_dead_endpoint(self):
        with patch.object(context_cache.httpx, "Client", _client_factory(_dead_dispatcher)):
            self.assertIsNone(context_cache.embed_text("hello"))

    def test_none_on_non_200(self):
        def dispatcher(method, url, json, params):
            return FakeResponse(500, {}, "server error")
        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            self.assertIsNone(context_cache.embed_text("hello"))

    def test_vector_on_stubbed_200(self):
        def dispatcher(method, url, json, params):
            self.assertTrue(url.endswith("/v1/embeddings"))
            self.assertEqual(json["model"], "bge-m3")
            self.assertEqual(json["input"], "hello")
            return FakeResponse(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            self.assertEqual(context_cache.embed_text("hello"), [0.1, 0.2, 0.3])


class TestCacheEvicted(unittest.TestCase):

    def test_none_when_embed_unavailable(self):
        with patch.object(context_cache, "embed_text", return_value=None):
            result = context_cache.cache_evicted("task-1", ["chunk one", "chunk two"])
        self.assertIsNone(result)

    def test_none_on_no_usable_chunks(self):
        # No httpx involved at all — empty/whitespace-only chunks short-circuit.
        result = context_cache.cache_evicted("task-1", ["", "   ", None])
        self.assertIsNone(result)

    def test_collection_and_n_upserts_when_stubbed(self):
        calls = []

        def dispatcher(method, url, json, params):
            calls.append((method, url, json, params))
            if method == "POST" and url.endswith("/v1/embeddings"):
                return FakeResponse(200, {"data": [{"embedding": [0.1, 0.2]}]})
            if method == "GET" and url.endswith("/collections/agent-ctx-task-1"):
                return FakeResponse(404, {}, "not found")
            if method == "PUT" and url.endswith("/collections/agent-ctx-task-1"):
                return FakeResponse(200, {"result": True})
            if method == "PUT" and url.endswith("/collections/agent-ctx-task-1/points"):
                self.assertEqual(params, {"wait": "true"})
                self.assertEqual(len(json["points"]), 2)
                return FakeResponse(200, {"result": {"status": "completed"}})
            return FakeResponse(500, {}, f"unexpected call: {method} {url}")

        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            collection = context_cache.cache_evicted("task-1", ["chunk one", "chunk two"])

        self.assertEqual(collection, "agent-ctx-task-1")
        upsert_calls = [c for c in calls if c[0] == "PUT" and c[1].endswith("/points")]
        self.assertEqual(len(upsert_calls), 1)

    def test_none_on_upsert_failure(self):
        def dispatcher(method, url, json, params):
            if method == "POST" and url.endswith("/v1/embeddings"):
                return FakeResponse(200, {"data": [{"embedding": [0.1]}]})
            if method == "GET":
                return FakeResponse(404, {}, "not found")
            if method == "PUT" and url.endswith("/points"):
                return FakeResponse(500, {}, "upsert failed")
            return FakeResponse(200, {"result": True})

        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            result = context_cache.cache_evicted("task-2", ["chunk one"])
        self.assertIsNone(result)


class TestRetrieveCtx(unittest.TestCase):

    def test_ordered_texts_on_stubbed_search(self):
        def dispatcher(method, url, json, params):
            if method == "POST" and url.endswith("/v1/embeddings"):
                return FakeResponse(200, {"data": [{"embedding": [0.5]}]})
            if method == "POST" and url.endswith("/points/search"):
                return FakeResponse(200, {"result": [
                    {"payload": {"text": "first"}, "score": 0.9},
                    {"payload": {"text": "second"}, "score": 0.8},
                ]})
            return FakeResponse(500, {}, "unexpected")

        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            result = context_cache.retrieve_ctx("agent-ctx-task-1", "query", k=2)
        self.assertEqual(result, ["first", "second"])

    def test_empty_on_dead_endpoint(self):
        with patch.object(context_cache.httpx, "Client", _client_factory(_dead_dispatcher)):
            self.assertEqual(context_cache.retrieve_ctx("agent-ctx-task-1", "query"), [])

    def test_empty_on_search_error(self):
        def dispatcher(method, url, json, params):
            if method == "POST" and url.endswith("/v1/embeddings"):
                return FakeResponse(200, {"data": [{"embedding": [0.5]}]})
            if method == "POST" and url.endswith("/points/search"):
                return FakeResponse(500, {}, "server error")
            return FakeResponse(500, {}, "unexpected")

        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            self.assertEqual(context_cache.retrieve_ctx("agent-ctx-task-1", "query"), [])


class TestScratchpadMessage(unittest.TestCase):

    def test_none_on_empty(self):
        self.assertIsNone(context_cache.scratchpad_message([]))

    def test_one_system_message_with_every_snippet(self):
        retrieved = ["alpha snippet", "beta snippet", "gamma snippet"]
        msg = context_cache.scratchpad_message(retrieved)
        self.assertIsInstance(msg, dict)
        self.assertEqual(msg["role"], "system")
        self.assertIn("## Retrieved context (semantic cache)", msg["content"])
        for snippet in retrieved:
            self.assertIn(snippet, msg["content"])


class TestDeleteCollection(unittest.TestCase):

    def test_never_raises_on_dead_endpoint(self):
        with patch.object(context_cache.httpx, "Client", _client_factory(_dead_dispatcher)):
            result = context_cache.delete_collection("agent-ctx-task-1")
        self.assertIsNone(result)

    def test_returns_none_on_stubbed_200(self):
        def dispatcher(method, url, json, params):
            self.assertEqual(method, "DELETE")
            return FakeResponse(200, {"result": True})
        with patch.object(context_cache.httpx, "Client", _client_factory(dispatcher)):
            result = context_cache.delete_collection("agent-ctx-task-1")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
