#!/usr/bin/env python3
"""
Local Context Supply Chain — Slice 0.1: the assembler.

Problem (see .agents/plans/local-context-supply-chain/DESIGN.md): Qwen on the
APU re-prefills fully every call and is single-slot. Reading raw files and
discovering fixes/patterns via in-loop tool calls (query_aidb, get_hint) pays
an extra slow prefill per call, and the anti-stagnation guard can abort a task
for making them without an interleaved action. So local starts most tasks
cold, re-deriving fixes the knowledge base already holds.

Fix: assemble a task's context ONCE at dispatch time — embed the task text,
search the harness's populated Qdrant collections (codebase-context history,
error-solutions, best-practices, skills-patterns, wiki-sections, agent
semantic memory), token-budget the results, and hand the caller one small,
labeled, front-loaded block to prepend to the prompt. In-loop retrieval stays
available as a bounded fallback, not the primary path.

Reuses ai-stack/local-agents/context_cache.py's embed_text() (bge-m3 @ :8081)
and its EMBED_URL/QDRANT_URL env-var + fail-open conventions — this module
adds only the multi-collection search/merge/budget/format layer on top; it
does not reimplement embedding or the base httpx client pattern.

Fail-open (HARD, mirrors context_cache.py): any embed/Qdrant/collection error
skips that source and never raises. A totally-down backend, an absent
collection, or empty task_text all return an empty-but-valid AssembledContext
(never None, never an exception) — the assembler must never break a dispatch.

Two retrieval paths, tiered by budget priority (live-verified 2026-08-17):
`codebase-context` (25,980 pts) does NOT reliably index every file — the
scripts/ai/ shebang scripts (no .py extension) are unindexed, so a task
naming e.g. "scripts/ai/aq-role-route" gets thematically-similar neighbors
back from semantic search, never the file itself. Relying on codebase-context
alone would front-load the WRONG file for most named-file backlog tasks.

  Tier 0 — FILE-TARGETED (primary, authoritative, cap ~1500 tok): parse file
  paths the task names (an explicit "File: <path>" line, or inline
  slash-delimited tokens) and keep only ones that exist on disk. Read, chunk
  line-aware, embed the chunks into an ephemeral collection (reusing
  context_cache.cache_evicted + retrieve_ctx — no new embed/Qdrant code path)
  and pull the top-k chunks relevant to the task, each carrying a real
  `[path:start-end]` citation. Torn down immediately after retrieval.

  Tier 1 — prior fixes (error-solutions, skills-patterns, best-practices):
  semantic search, greedy-filled into whatever budget Tier 0 left.

  Tier 2 — supplementary (codebase-context, wiki-sections,
  agent-memory-semantic): semantic search, greedy-filled into what remains.

If a task names no file (or none resolve on disk), Tier 0 contributes
nothing and Tiers 1/2 behave as pure semantic search over the full budget.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent  # ai-stack/local-agents/../.. = repo root
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    import context_cache  # noqa: E402  (same dir: ai-stack/local-agents/)
    import httpx  # noqa: E402  (context_cache's own dependency; reused here)
except Exception:  # noqa: BLE001 — an unavailable dependency degrades to fail-open, never a crash
    context_cache = None  # type: ignore
    httpx = None  # type: ignore

QDRANT_URL = getattr(context_cache, "QDRANT_URL", "http://127.0.0.1:6333")

# Tier 1 / Tier 2 ranked sources with per-source caps (search top-k), so no
# single source can dominate its tier. Order also drives subsection order in
# the formatted output. DEFAULT_SOURCES is the flat union, kept for reference
# / as the plan used when a caller passes an explicit `collections` override.
PRIOR_FIX_SOURCES: list = [
    ("error-solutions", 3),
    ("skills-patterns", 2),
    ("best-practices", 2),
]
SUPPLEMENTARY_SOURCES: list = [
    ("codebase-context", 4),
    ("wiki-sections", 2),
    ("agent-memory-semantic", 2),
]
DEFAULT_SOURCES: list = PRIOR_FIX_SOURCES + SUPPLEMENTARY_SOURCES
_OVERRIDE_K = 2  # per-collection cap used when caller passes an explicit `collections` list

MAX_EXCERPT_CHARS = 320  # per-item text cap so no single semantic hit dominates the budget either

# Tier 0 (file-targeted) tuning.
FILE_TARGETED_CAP_TOKENS = 1500  # soft sub-budget — never lets Tier 0 crowd out Tiers 1/2
FILE_CHUNK_LINES = 40            # line-aware chunk size for the ephemeral embed
FILE_TARGETED_K = 4              # top-k chunks pulled per named file
FILE_TARGETED_MAX_FILES = 3      # bound worst-case embed cost if a task names many paths
FILE_TARGETED_EXCERPT_CHARS = 2400  # byte-safety net for verbatim code (was 600 under the old
# excerpt-collapse path; verbatim keeps newlines/indentation so needs more headroom per char of
# real content — rarely hit anyway since a span is already line-bounded to FILE_CHUNK_LINES)

_FILE_LINE_RE = re.compile(r"(?im)^\s*file:\s*(\S+)")
_INLINE_PATH_RE = re.compile(r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+")
_CHUNK_CITATION_RE = re.compile(r"^\[(?P<citation>[^\]]+)\]\n(?P<body>.*)$", re.DOTALL)


@dataclass
class AssembledContext:
    text: str
    sources: list  # [{collection, score, citation}, ...] in the order they appear in .text
    tokens: int  # est. ~chars/4 of .text
    stats: dict = field(default_factory=dict)


def _empty(reason: str, task_id: Optional[str] = None) -> AssembledContext:
    return AssembledContext(
        text="",
        sources=[],
        tokens=0,
        stats={
            "task_id": task_id,
            "embed_ok": False,
            "reason": reason,
            "collections_queried": 0,
            "collections_hit": 0,
            "items_total": 0,
            "items_used": 0,
        },
    )


def _estimate_tokens(text: str) -> int:
    return max(0, len(text) // 4)


def _excerpt(text: str, limit: int = MAX_EXCERPT_CHARS) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


def _verbatim(text: str, max_lines: int = FILE_CHUNK_LINES, max_chars: int = FILE_TARGETED_EXCERPT_CHARS) -> str:
    """Return `text` byte-exact — no whitespace collapsing — truncated only at
    a LINE boundary, never mid-line/mid-indentation.

    This is the property `_excerpt` (whitespace-collapse) destroys: an
    `edit_file` old_string an agent builds from front-loaded text must
    byte-match the real file, which only holds if newlines and indentation
    survive the round-trip. Used for CODE spans only (Tier 0 file-targeted) —
    prose/semantic hits (Tiers 1/2) keep `_excerpt`; they're never edit
    targets, so collapsing them is harmless and saves budget.
    """
    if not text:
        return ""
    lines = text.splitlines()
    if max_lines > 0:
        lines = lines[:max_lines]
    body = "\n".join(lines)
    while len(body) > max_chars and lines:
        lines = lines[:-1]
        body = "\n".join(lines)
    return body


def _extract(collection: str, point: dict):
    """Return (text, citation) for one Qdrant hit, or None if unusable.

    Field names differ per collection (verified against the live schemas at
    authoring time) — each branch below maps that collection's payload shape
    to a short excerpt + a citation an agent can act on without re-fetching.
    Unknown/custom collections fall back to generic content/title fields.
    """
    payload = point.get("payload") or {}
    pid = point.get("id", "")
    try:
        if collection == "codebase-context":
            subject = payload.get("commit_subject") or ""
            body = payload.get("commit_body") or ""
            text = f"{subject} — {body}" if body else subject
            files = payload.get("files_changed") or []
            first_file = files[0] if isinstance(files, list) and files else ""
            chash = (payload.get("commit_hash") or "")[:8]
            citation = f"{chash}:{first_file}" if (chash and first_file) else (chash or str(pid))
        elif collection in ("error-solutions", "best-practices"):
            title = payload.get("title") or ""
            content = payload.get("content") or ""
            text = f"{title}: {content}" if title else content
            citation = title or str(pid)
        elif collection == "skills-patterns":
            prompt = payload.get("prompt") or ""
            response = payload.get("response") or ""
            text = f"Q: {prompt} A: {response}"
            citation = payload.get("pattern_id") or str(pid)
        elif collection == "wiki-sections":
            text = payload.get("content") or payload.get("description") or ""
            citation = payload.get("relative_path") or payload.get("title") or str(pid)
        elif collection == "agent-memory-semantic":
            text = payload.get("summary") or payload.get("content") or ""
            citation = payload.get("memory_id") or str(pid)
        else:
            text = payload.get("content") or payload.get("text") or payload.get("summary") or ""
            citation = payload.get("title") or payload.get("id") or str(pid)
        text = _excerpt(text)
        if not text:
            return None
        return text, citation
    except Exception:
        return None


def _search_collection(client, collection: str, vector: list, k: int, timeout: float) -> list:
    """Return [{collection,score,text,citation}, ...] for one collection's
    top-k hits. [] on any error (missing collection, dead Qdrant, malformed
    response, bad payload) — fail-open, never raises."""
    try:
        resp = client.post(
            f"{QDRANT_URL}/collections/{collection}/points/search",
            json={"vector": vector, "limit": k, "with_payload": True},
        )
        if resp.status_code != 200:
            return []
        hits = (resp.json() or {}).get("result", []) or []
        items = []
        for hit in hits:
            extracted = _extract(collection, hit)
            if extracted is None:
                continue
            text, citation = extracted
            items.append({
                "collection": collection,
                "score": hit.get("score", 0.0),
                "text": text,
                "citation": citation,
            })
        return items
    except Exception:
        return []


def _extract_named_paths(task_text: str, repo_root: Path) -> list:
    """Repo-relative paths named in `task_text` that exist on disk.

    Matches an explicit 'File: <path>' line and inline slash-delimited
    tokens. Existence-on-disk is the real filter, not the regex shape — a
    false-positive token like "either/or" simply won't resolve to a file, so
    the path pattern doesn't need to be exact."""
    candidates: list = []
    for m in _FILE_LINE_RE.finditer(task_text or ""):
        candidates.append(m.group(1))
    for m in _INLINE_PATH_RE.finditer(task_text or ""):
        candidates.append(m.group(0))

    resolved: list = []
    seen: set = set()
    for raw in candidates:
        cand = raw.strip().strip("`'\",;:()[]{}.")
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            if (repo_root / cand).is_file():
                resolved.append(cand)
        except OSError:
            continue
        if len(resolved) >= FILE_TARGETED_MAX_FILES:
            break
    return resolved


def _chunk_file(text: str, rel_path: str, lines_per_chunk: int = FILE_CHUNK_LINES) -> list:
    """Split file text into line-aware chunks, each prefixed with a
    '[path:start-end]' citation baked into the chunk string itself — this is
    how the citation survives the cache_evicted/retrieve_ctx round-trip
    without needing a new payload field in context_cache's schema."""
    lines = text.splitlines()
    if not lines:
        return []
    chunks = []
    for start in range(0, len(lines), lines_per_chunk):
        end = min(start + lines_per_chunk, len(lines))
        body = "\n".join(lines[start:end])
        if not body.strip():
            continue
        citation = f"{rel_path}:{start + 1}-{end}"
        chunks.append(f"[{citation}]\n{body}")
    return chunks


def _parse_chunk_citation(raw: str):
    """Reverse _chunk_file's '[citation]\\nbody' framing. None if malformed."""
    m = _CHUNK_CITATION_RE.match(raw or "")
    if not m:
        return None
    return m.group("citation"), m.group("body")


def _file_targeted_items(task_text: str, task_id: str, repo_root: Path, timeout: float):
    """Tier 0: read+chunk+embed+retrieve task-named files that exist on disk.

    Reuses context_cache.cache_evicted (embed+upsert each chunk to an
    ephemeral per-file collection) then context_cache.retrieve_ctx (embed
    task_text once more, semantic search within that one file's chunks) —
    no new embed/Qdrant code path, per the DESIGN's reuse mandate. The
    ephemeral collection is torn down immediately after retrieval.

    Returns (items, files_used) — files_used lists only paths that actually
    contributed >=1 selected chunk, for .stats observability ("prove Tier 0
    fired"). Best-effort per file: one file's failure never blocks another's;
    total failure (bad regex match, disk error, dead embed) returns ([], []).
    Never raises.
    """
    resolved_paths = _extract_named_paths(task_text, repo_root)
    if not resolved_paths:
        return [], []

    items: list = []
    files_used: list = []
    for rel_path in resolved_paths:
        collection = None
        try:
            abs_path = repo_root / rel_path
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            chunks = _chunk_file(text, rel_path)
            if not chunks:
                continue
            ephemeral_id = f"{task_id}-ft-{abs(hash(rel_path)) % 1_000_000}"
            collection = context_cache.cache_evicted(ephemeral_id, chunks, timeout=timeout)
            if not collection:
                continue
            retrieved = context_cache.retrieve_ctx(
                collection, task_text, k=FILE_TARGETED_K, timeout=timeout,
            )
            file_hit = False
            for raw in retrieved:
                parsed = _parse_chunk_citation(raw)
                if parsed is None:
                    continue
                citation, body = parsed
                body = _verbatim(body, max_lines=FILE_CHUNK_LINES, max_chars=FILE_TARGETED_EXCERPT_CHARS)
                if not body:
                    continue
                items.append({
                    "collection": "file-targeted",
                    "score": 1.0,  # authoritative — Tier 0 fills before any semantic score comparison
                    "text": body,
                    "citation": citation,
                })
                file_hit = True
            if file_hit:
                files_used.append(rel_path)
        except Exception:
            continue
        finally:
            if collection:
                try:
                    context_cache.delete_collection(collection, timeout=timeout)
                except Exception:
                    pass
    return items, files_used


def _greedy_fill(items: list, budget: int) -> tuple:
    """Add items (already in priority order) while the running token cost
    stays within `budget`. Skips (doesn't stop on) an oversized item so a
    smaller lower-priority item later still gets a chance. Returns
    (selected, tokens_used)."""
    selected: list = []
    used = 0
    for item in items:
        cost = _estimate_tokens(item["text"]) + 2  # +2 for the "- [] " line overhead
        if used + cost > budget:
            continue
        used += cost
        selected.append(item)
    return selected, used


def assemble_context(
    task_text: str,
    *,
    task_id: str,
    token_budget: int = 3500,
    collections: Optional[list] = None,
    timeout: float = 8.0,
) -> AssembledContext:
    """Front-load prior knowledge for a local task — two tiered retrieval
    paths (see module docstring for the full rationale):

      Tier 0 (file-targeted, authoritative, cap ~1500 tok): task-named files
      that exist on disk, read+chunked+embedded+retrieved directly — always
      wins the file-identity question that codebase-context semantic search
      cannot reliably answer for unindexed files.

      Tiers 1/2 (semantic, supplementary): the ranked Qdrant collections,
      searched with `task_text`'s embedding, greedy-filled into whatever
      budget Tier 0 left.

    `collections`: optional override list of collection names (each searched
    at a flat k=2 cap, as a single tier) in place of PRIOR_FIX_SOURCES +
    SUPPLEMENTARY_SOURCES — Tier 0 (file-targeted) still runs regardless,
    since it's an orthogonal disk-read path, not a Qdrant collection choice.
    `task_id` is carried into `.stats` and used only to derive a disposable
    ephemeral-collection name for Tier 0 chunks (never a persistent one).

    Fail-open everywhere: dead embed endpoint, dead/partially-dead Qdrant, an
    absent collection, an unreadable named file, or empty task_text all
    degrade gracefully; a totally-down backend returns an empty-but-valid
    AssembledContext. Never raises.
    """
    start = time.monotonic()
    if not task_text or not task_text.strip():
        return _empty("empty-task-text", task_id)
    if context_cache is None or httpx is None:
        return _empty("context_cache-unavailable", task_id)

    try:
        vector = context_cache.embed_text(task_text, timeout=timeout)
    except Exception:
        vector = None
    if vector is None:
        return _empty("embed-unavailable", task_id)

    selected: list = []
    used_tokens = 0

    # ── Tier 0: file-targeted (authoritative) ───────────────────────────
    try:
        file_items, files_used = _file_targeted_items(task_text, task_id, _REPO_ROOT, timeout)
    except Exception:
        file_items, files_used = [], []
    if file_items:
        tier0_budget = min(FILE_TARGETED_CAP_TOKENS, token_budget - used_tokens)
        tier0_selected, tier0_used = _greedy_fill(file_items, max(tier0_budget, 0))
        selected.extend(tier0_selected)
        used_tokens += tier0_used

    # ── Tiers 1/2: semantic search, greedy-filled into what's left ──────
    tiers = (
        [(PRIOR_FIX_SOURCES, "tier1-prior-fix"), (SUPPLEMENTARY_SOURCES, "tier2-supplementary")]
        if not collections
        else [([(name, _OVERRIDE_K) for name in collections], "tier1-custom")]
    )

    semantic_items_total = 0
    collections_queried = 0
    collections_hit = 0
    order: list = [name for tier_sources, _ in tiers for name, _ in tier_sources]

    try:
        with httpx.Client(timeout=timeout) as client:
            for tier_sources, _tier_label in tiers:
                tier_items: list = []
                for name, k in tier_sources:
                    collections_queried += 1
                    items = _search_collection(client, name, vector, k, timeout)
                    if items:
                        collections_hit += 1
                    tier_items.extend(items)
                semantic_items_total += len(tier_items)
                tier_items.sort(key=lambda it: it.get("score", 0.0), reverse=True)
                tier_selected, tier_used = _greedy_fill(tier_items, max(token_budget - used_tokens, 0))
                selected.extend(tier_selected)
                used_tokens += tier_used
    except Exception:
        pass  # fail-open: keep whatever Tier 0 + whatever partial tier fill succeeded

    if not selected:
        return AssembledContext(
            text="",
            sources=[],
            tokens=0,
            stats={
                "task_id": task_id,
                "embed_ok": True,
                "collections_queried": collections_queried,
                "collections_hit": collections_hit,
                "items_total": len(file_items) + semantic_items_total,
                "items_used": 0,
                "file_targeted_hit": False,
                "file_targeted_files": [],
                "elapsed_ms": round((time.monotonic() - start) * 1000, 1),
            },
        )

    # Preserve tier/rank order for the formatted block: file-targeted first
    # (if present), then each semantic collection in its tier's rank order.
    by_source: dict = {}
    for item in selected:
        by_source.setdefault(item["collection"], []).append(item)

    lines = ["## Relevant prior knowledge (front-loaded — do NOT re-fetch)"]
    sources_out: list = []
    seen_sources: set = set()
    ordered_names = (["file-targeted"] if file_items else []) + order
    for name in ordered_names:
        if name in seen_sources:
            continue
        seen_sources.add(name)
        items = by_source.get(name) or []
        if not items:
            continue
        label = f"{name} (task-named files)" if name == "file-targeted" else name
        lines.append(f"\n### {label}")
        for item in items:
            if name == "file-targeted":
                # Fenced, verbatim — an agent must be able to lift this text
                # straight into an edit_file old_string and have it byte-match
                # the real file. A "- [] text" one-liner (semantic hits' shape)
                # would re-flow the code onto one line and break that.
                lines.append(f"[{item['citation']}]")
                lines.append("```")
                lines.append(item["text"])
                lines.append("```")
            else:
                lines.append(f"- [{item['citation']}] {item['text']}")
            sources_out.append({
                "collection": item["collection"],
                "score": round(float(item.get("score", 0.0)), 4),
                "citation": item["citation"],
            })

    chunk_sources = sorted({
        "file-targeted" if s["collection"] == "file-targeted" else "semantic"
        for s in sources_out
    })
    text = "\n".join(lines) if sources_out else ""
    return AssembledContext(
        text=text,
        sources=sources_out,
        tokens=_estimate_tokens(text),
        stats={
            "task_id": task_id,
            "embed_ok": True,
            "collections_queried": collections_queried,
            "collections_hit": collections_hit,
            "items_total": len(file_items) + semantic_items_total,
            "items_used": len(selected),
            "file_targeted_hit": bool(files_used),
            "file_targeted_files": files_used,
            "chunk_sources": chunk_sources,
            "elapsed_ms": round((time.monotonic() - start) * 1000, 1),
        },
    )
