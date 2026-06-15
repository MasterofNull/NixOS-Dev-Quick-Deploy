#!/usr/bin/env python3
"""
scripts/data/index-codebase.py

Walk the repository and upsert file chunks into the `codebase-context` Qdrant
collection so that local agents can query_aidb for code context.

Only re-indexes files that have changed since the last run (mtime checkpoint).
Designed to be invoked from a git post-commit hook or manually.

Usage:
  python3 scripts/data/index-codebase.py [--full] [--dry-run] [--path PATH]

  --full      Force re-index of all files regardless of checkpoint
  --dry-run   Print what would be indexed without writing to Qdrant
  --path      Restrict indexing to a specific subdirectory (relative to repo root)

Env:
  LLAMA_EMBED_URL   embedding server (default http://127.0.0.1:8081)
  QDRANT_URL        Qdrant (default http://127.0.0.1:6333)
  REPO_ROOT         Repo root (default: parent of this script's parent dir)
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMBED_URL = os.environ.get("LLAMA_EMBED_URL", "http://127.0.0.1:8081")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = "codebase-context"
EMBED_MODEL = "bge-m3"

_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(os.environ.get("REPO_ROOT", str(_SCRIPT_DIR.parent.parent)))

CHECKPOINT_FILE = REPO_ROOT / ".agent" / "codebase-index-checkpoint.json"

# Extensions to index
INCLUDE_EXTS = {".py", ".nix", ".sh", ".yaml", ".yml", ".md", ".json", ".toml"}

# Directories to skip entirely
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".agents/delegation/outputs", "result", ".direnv",
    "archive", ".agent/archive",
    ".forks",   # forked repos — 45k+ files, not harness-authored
    ".reports",  # generated reports
}

# Max file size to index (bytes)
MAX_FILE_BYTES = 80_000

# Chunk size (characters) — embed server ubatch-size=2048 tokens (post-rebuild); 2000 chars ≈ 700 tokens, well within limit
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

# Batch size for embedding requests
EMBED_BATCH = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_skip_dir(rel: Path) -> bool:
    parts = set(rel.parts)
    return bool(parts & SKIP_DIRS)


def _file_id(rel_path: str, chunk_idx: int) -> str:
    h = hashlib.md5(f"{rel_path}:{chunk_idx}".encode()).hexdigest()
    return h


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    """Embed a batch of texts via llama-embed. Returns list of vectors or None."""
    payload = json.dumps({
        "model": EMBED_MODEL,
        "input": texts,
    }).encode()
    req = urllib.request.Request(
        f"{EMBED_URL}/v1/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        return [item["embedding"] for item in data.get("data", [])]
    except Exception as e:
        print(f"  [embed error] {e}", file=sys.stderr)
        return None


def _upsert_points(points: list[dict]) -> bool:
    """Upsert points into Qdrant."""
    payload = json.dumps({"points": points}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=false",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return data.get("status") == "ok" or data.get("result", {}).get("status") == "acknowledged"
    except Exception as e:
        print(f"  [qdrant error] {e}", file=sys.stderr)
        return False


def _load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_checkpoint(data: dict) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Main indexer
# ---------------------------------------------------------------------------

def collect_files(root: Path, subpath: str | None = None) -> list[Path]:
    """Walk repo and return files eligible for indexing."""
    search_root = root / subpath if subpath else root
    files = []
    for p in search_root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _should_skip_dir(rel):
            continue
        if p.suffix not in INCLUDE_EXTS:
            continue
        if p.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(p)
    return files


def index_files(
    files: list[Path],
    repo_root: Path,
    checkpoint: dict,
    dry_run: bool = False,
    full: bool = False,
) -> dict:
    """Index files, return updated checkpoint."""
    stats = {"indexed": 0, "skipped": 0, "errors": 0, "chunks": 0}

    # Accumulate (file, chunk_idx, chunk_text, rel_path, mtime) for batching
    pending: list[tuple[str, int, str, float]] = []

    def flush_batch(batch_pending):
        if not batch_pending:
            return
        texts = [t for _, _, t, _ in batch_pending]
        vectors = _embed_batch(texts)
        if vectors is None:
            stats["errors"] += len(batch_pending)
            return
        points = []
        for (fid, cidx, text, mtime), vec in zip(batch_pending, vectors):
            points.append({
                "id": _file_id(fid, cidx),
                "vector": vec,
                "payload": {
                    "file": fid,
                    "chunk": cidx,
                    "content": text,
                    "indexed_at": int(time.time()),
                    "source": "codebase-index",
                },
            })
        if not dry_run:
            ok = _upsert_points(points)
            if not ok:
                stats["errors"] += len(points)
                return
        stats["chunks"] += len(points)

    batch: list[tuple[str, int, str, float]] = []

    for filepath in files:
        rel = str(filepath.relative_to(repo_root))
        mtime = filepath.stat().st_mtime

        # Skip if unchanged (unless --full)
        if not full and checkpoint.get(rel) == mtime:
            stats["skipped"] += 1
            continue

        try:
            text = filepath.read_text(errors="replace")
        except OSError as e:
            print(f"  [read error] {rel}: {e}", file=sys.stderr)
            stats["errors"] += 1
            continue

        chunks = _chunk_text(text)
        print(f"  indexing {rel} ({len(chunks)} chunks)")

        for i, chunk in enumerate(chunks):
            # Prefix chunk with file path for retrieval quality
            tagged = f"# {rel} (chunk {i+1}/{len(chunks)})\n{chunk}"
            batch.append((rel, i, tagged, mtime))
            if len(batch) >= EMBED_BATCH:
                flush_batch(batch)
                batch.clear()

        checkpoint[rel] = mtime
        stats["indexed"] += 1

    flush_batch(batch)
    return stats


def main():
    parser = argparse.ArgumentParser(description="Index repo codebase into Qdrant codebase-context")
    parser.add_argument("--full", action="store_true", help="Re-index all files")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    parser.add_argument("--path", default=None, help="Restrict to subdirectory")
    args = parser.parse_args()

    print(f"Repo root: {REPO_ROOT}")
    print(f"Collection: {COLLECTION}")
    print(f"Mode: {'full' if args.full else 'incremental'}{' (dry-run)' if args.dry_run else ''}")

    checkpoint = {} if args.full else _load_checkpoint()

    files = collect_files(REPO_ROOT, subpath=args.path)
    print(f"Found {len(files)} eligible files")

    stats = index_files(files, REPO_ROOT, checkpoint, dry_run=args.dry_run, full=args.full)

    if not args.dry_run:
        _save_checkpoint(checkpoint)

    print(
        f"\nDone — indexed={stats['indexed']} skipped={stats['skipped']} "
        f"chunks={stats['chunks']} errors={stats['errors']}"
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
