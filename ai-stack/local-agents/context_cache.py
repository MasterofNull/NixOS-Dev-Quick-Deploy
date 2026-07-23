#!/usr/bin/env python3
"""
Embed-backed semantic context cache — Slice 2a library.

Replaces the lossy 600-char prune digest (agent_executor._store_prune_checkpoint)
with a real cache: on prune, embed the FULL evicted chunks into a per-task Qdrant
collection; before a call, retrieve the most relevant evicted chunks by semantic
similarity to the current objective.

Pattern mirrors ai_coordination.py's _query_qdrant_direct: embed via bge-m3 at
AI_STACK_EMBED_ENDPOINT (:8081), then talk to Qdrant directly (:6333) — no AIDB
pgvector involved (these are ephemeral per-task collections, not harness patterns).

Fail-open (HARD, all functions): any embed/Qdrant error, timeout, or non-200
response is swallowed and the function returns its documented empty/None result.
The cache is a nice-to-have recall path, never a dependency on the agent's
critical path — a dead :8081/:6333 must degrade silently to "no cache" behavior.

KV-safe by construction: scratchpad_message() is a pure formatter with no I/O and
no knowledge of where its output is placed. The DESIGN.md KV-cache rule (never
re-order/mutate the stable pinned prefix — dynamic semantic content invalidates
llama.cpp prefix-cache reuse) is a caller-side placement contract: whoever
inserts this message into the message list MUST insert it AFTER the stable
pinned prefix, as its own appended block, never spliced into or reordering the
prefix itself. This module does not perform that insertion.

This is Slice 2a: a standalone, importable, dependency-light library only.
Wiring it into agent_executor.py's prune path is Slice 2b (deferred — that file
is hash-frozen in scripts/testing/fixtures/local-delegation-reliability-golden.json
and requires a freeze-aware reconciliation, not a silent edit).
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional

import httpx

EMBED_URL = os.environ.get("AI_STACK_EMBED_ENDPOINT", "http://127.0.0.1:8081")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
EMBED_MODEL = "bge-m3"

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _collection_name(task_id: str) -> str:
    """Derive a Qdrant-safe collection name from an arbitrary task id."""
    sanitized = _SANITIZE_RE.sub("-", str(task_id or "").strip()) or "unknown"
    return f"agent-ctx-{sanitized}"


def embed_text(text: str, timeout: float = 8.0) -> Optional[list]:
    """Embed one string via the bge-m3 endpoint. None on any error (fail-open)."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{EMBED_URL}/v1/embeddings",
                json={"model": EMBED_MODEL, "input": text},
            )
            if resp.status_code != 200:
                return None
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


def _ensure_collection(client: httpx.Client, name: str, vector_size: int) -> None:
    """Create the collection if it doesn't already exist. Best-effort — a create
    failure here is not fatal; the subsequent upsert call surfaces the real error."""
    try:
        get_resp = client.get(f"{QDRANT_URL}/collections/{name}")
        if get_resp.status_code == 200:
            return
    except Exception:
        pass
    try:
        client.put(
            f"{QDRANT_URL}/collections/{name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
    except Exception:
        pass


def cache_evicted(task_id: str, chunks: list, timeout: float = 8.0) -> Optional[str]:
    """Embed + upsert each non-empty chunk to a per-task collection.

    Returns the collection name, or None if nothing could be cached (no usable
    chunks, or embed/Qdrant unreachable). Never raises.
    """
    try:
        non_empty = [c for c in (chunks or []) if isinstance(c, str) and c.strip()]
        if not non_empty:
            return None

        embedded = []  # [(chunk, vector), ...] — only successfully embedded chunks
        for chunk in non_empty:
            vector = embed_text(chunk, timeout=timeout)
            if vector is not None:
                embedded.append((chunk, vector))
        if not embedded:
            return None

        collection = _collection_name(task_id)
        vector_size = len(embedded[0][1])
        with httpx.Client(timeout=timeout) as client:
            _ensure_collection(client, collection, vector_size)
            points = [
                {
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {"text": chunk, "idx": idx},
                }
                for idx, (chunk, vector) in enumerate(embedded)
            ]
            resp = client.put(
                f"{QDRANT_URL}/collections/{collection}/points",
                params={"wait": "true"},
                json={"points": points},
            )
            if resp.status_code not in (200, 201):
                return None
        return collection
    except Exception:
        return None


def retrieve_ctx(collection: str, query: str, k: int = 6, timeout: float = 8.0) -> list:
    """Embed the query, search the collection, return payload.text in score order.
    [] on any error (dead endpoint, missing collection, bad response) — fail-open."""
    vector = embed_text(query, timeout=timeout)
    if vector is None:
        return []
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{QDRANT_URL}/collections/{collection}/points/search",
                json={"vector": vector, "limit": k, "with_payload": True},
            )
            if resp.status_code != 200:
                return []
            hits = resp.json().get("result", [])
            return [
                h.get("payload", {}).get("text", "")
                for h in hits
                if h.get("payload", {}).get("text")
            ]
    except Exception:
        return []


def scratchpad_message(retrieved: list) -> Optional[dict]:
    """Pure formatter — no I/O. None if retrieved is empty, else a single system
    message enumerating every snippet. Caller places this AFTER the stable pinned
    prefix (see module docstring) — this function has no say in placement."""
    if not retrieved:
        return None
    lines = ["## Retrieved context (semantic cache)"]
    for idx, snippet in enumerate(retrieved, 1):
        lines.append(f"{idx}. {snippet}")
    return {"role": "system", "content": "\n".join(lines)}


def delete_collection(collection: str, timeout: float = 8.0) -> None:
    """Best-effort collection teardown for Slice 2b task-end cleanup. Never raises."""
    try:
        with httpx.Client(timeout=timeout) as client:
            client.delete(f"{QDRANT_URL}/collections/{collection}")
    except Exception:
        pass
    return None
