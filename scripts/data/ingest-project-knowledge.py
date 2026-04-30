#!/usr/bin/env python3
"""
ingest-project-knowledge.py — Project-wide knowledge ingestion for AIDB.

Chunks .md, .nix, .py, .sh files from the repo into 512-token segments and
posts them to AIDB POST /documents with project=nixos-dev-quick-deploy.

Phase 13.4 implementation. Targets >= 1,000 chunks.

Usage:
    python3 scripts/data/ingest-project-knowledge.py
    python3 scripts/data/ingest-project-knowledge.py --dry-run
    python3 scripts/data/ingest-project-knowledge.py --max-docs 200
    python3 scripts/data/ingest-project-knowledge.py --paths docs/ nix/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, List, Tuple

# ---------------------------------------------------------------------------
# Pre-ingestion secrets redaction (mirrors AIDB validator patterns)
# Redact before posting so docs with example/template values still get indexed.
# ---------------------------------------------------------------------------

_PEM_BEGIN = "-----BEGIN "
_PEM_END = " KEY-----"
_SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [  # type: ignore[type-arg]
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("openai_api_key_new", re.compile(r"sk-proj-[A-Za-z0-9]{48}")),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{90,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{40}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("gitlab_token", re.compile(r"glpat-[A-Za-z0-9\-]{20,}")),
    ("private_key_rsa", re.compile(re.escape(f"{_PEM_BEGIN}RSA PRIVATE{_PEM_END}"))),
    ("private_key_openssh", re.compile(re.escape(f"{_PEM_BEGIN}OPENSSH PRIVATE{_PEM_END}"))),
    ("private_key_ec", re.compile(re.escape(f"{_PEM_BEGIN}EC PRIVATE{_PEM_END}"))),
    ("jwt_token", re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    ("password_field", re.compile(r"(?i)password\s*[=:]\s*[^\s]{8,}")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}")),
]


def _pre_redact(text: str) -> Tuple[str, List[str]]:
    """Redact secret patterns from text before ingestion. Returns (redacted, detected_names)."""
    detected = []
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            detected.append(name)
            text = pattern.sub(f"[REDACTED:{name}]", text)
    return text, detected

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

AIDB_URL = os.getenv("AIDB_URL", "http://localhost:8002")
AIDB_KEY_FILE = os.getenv(
    "AIDB_API_KEY_FILE",
    "/run/secrets/aidb_api_key",
)
PROJECT_NAME = "nixos-dev-quick-deploy"

EXTENSIONS = {".md", ".nix", ".py", ".sh"}
CHUNK_TOKENS = 512          # approximate — ~4 chars per token
CHUNK_CHARS = CHUNK_TOKENS * 4   # 2048 chars per chunk
CHUNK_OVERLAP_CHARS = 200   # sliding window overlap

# Paths to skip entirely (relative to repo root)
SKIP_DIRS = {
    ".git",
    ".forks",
    "__pycache__",
    ".claude",
    "docs/archive",
    "docs/archive/deprecated",
    "docs/archive/stale",
    "scripts/data/archive",
    ".agents/plans/archive",
    "node_modules",
    ".npm",
}

# File name patterns to skip
SKIP_FILE_PATTERNS = {
    ".env",
    "secrets",
    "password",
    "credentials",
    "scores.sqlite",
    "*.lock",
    # Actual secret files — never ingest
    # (docs with example password patterns are handled by _pre_redact, not skipped)
}

# Default scan paths (relative to repo root). If empty, scan entire repo.
DEFAULT_PATHS = [
    "docs",
    "nix",
    "ai-stack/mcp-servers/hybrid-coordinator",
    "ai-stack/prompts",
    "ai-stack/data",
    "scripts/ai",
    "scripts/governance",
    "scripts/testing",
    "scripts/automation",
    "config",
    ".agents/plans",
    ".agent",
    ".claude/commands",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    path = Path(AIDB_KEY_FILE)
    if path.exists():
        return path.read_text().strip()
    key = os.getenv("AIDB_API_KEY", "")
    if not key:
        print(f"[WARN] No API key found at {AIDB_KEY_FILE} and AIDB_API_KEY not set", file=sys.stderr)
    return key


def _should_skip_path(rel: Path) -> bool:
    parts = set(rel.parts)
    for skip in SKIP_DIRS:
        if any(p == skip or rel.as_posix().startswith(skip) for p in parts):
            return True
    name_lower = rel.name.lower()
    for pat in SKIP_FILE_PATTERNS:
        if pat.startswith("*"):
            if name_lower.endswith(pat[1:]):
                return True
        elif pat in name_lower:
            return True
    return False


def _iter_files(paths: List[str]) -> Iterator[Path]:
    """Yield absolute file paths for the given scan paths."""
    for p in paths:
        target = REPO_ROOT / p
        if target.is_file():
            if target.suffix in EXTENSIONS:
                rel = target.relative_to(REPO_ROOT)
                if not _should_skip_path(rel):
                    yield target
        elif target.is_dir():
            for f in sorted(target.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix not in EXTENSIONS:
                    continue
                rel = f.relative_to(REPO_ROOT)
                if _should_skip_path(rel):
                    continue
                yield f


def _chunk_text(text: str, path_str: str) -> List[Tuple[str, int]]:
    """Split text into overlapping chunks. Returns list of (chunk, chunk_index)."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        chunk = text[start:end]
        if chunk.strip():
            chunks.append((chunk, idx))
        start += CHUNK_CHARS - CHUNK_OVERLAP_CHARS
        idx += 1
    return chunks


def _post_document(
    api_key: str,
    content: str,
    title: str,
    relative_path: str,
    project: str,
    dry_run: bool,
    max_retries: int = 5,
    cooloff_seconds: int = 65,
) -> bool:
    """POST a single document to AIDB. Returns True on success.

    Retries on HTTP 429 (rate limited) with exponential backoff.
    """
    content, redacted_names = _pre_redact(content)
    if redacted_names:
        print(f"  [redact] {relative_path}: {','.join(redacted_names)}", file=sys.stderr)

    payload = {
        "content": content,
        "project": project,
        "relative_path": relative_path,
        "title": title,
    }
    if dry_run:
        return True

    url = f"{AIDB_URL}/documents"
    data = json.dumps(payload).encode()

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status in (200, 201)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt < max_retries:
                    backoff = 2 ** (attempt + 1)  # 2s, 4s, 8s, 16s, 32s
                    print(
                        f"  [429] rate limited — backing off {backoff}s (attempt {attempt + 1}/{max_retries})",
                        file=sys.stderr,
                    )
                    time.sleep(backoff)
                    continue
                # All retries exhausted — wait for the rate limit window to fully clear
                print(
                    f"  [429] max retries exhausted for {relative_path} — cooling off {cooloff_seconds}s",
                    file=sys.stderr,
                )
                time.sleep(cooloff_seconds)
                return False
            body = e.read().decode(errors="replace")[:200]
            print(f"  [HTTP {e.code}] {relative_path}: {body}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"  [ERR] {relative_path}: {e}", file=sys.stderr)
            return False

    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest project knowledge into AIDB (Phase 13.4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Count chunks without posting to AIDB",
    )
    parser.add_argument(
        "--max-docs", type=int, default=0,
        help="Stop after N documents (0 = unlimited)",
    )
    parser.add_argument(
        "--paths", nargs="+", default=DEFAULT_PATHS,
        help="Repo-relative paths to scan (files or directories)",
    )
    parser.add_argument(
        "--project", default=PROJECT_NAME,
        help=f"AIDB project name (default: {PROJECT_NAME})",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds between posts (throttle, default: 2.0 — AIDB limit is 60 RPM)",
    )
    args = parser.parse_args()

    api_key = "" if args.dry_run else _load_api_key()

    if not args.dry_run:
        # Quick health check
        try:
            req = urllib.request.Request(
                f"{AIDB_URL}/health",
                headers={"X-API-Key": api_key},
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as e:
            print(f"[FATAL] AIDB not reachable at {AIDB_URL}: {e}", file=sys.stderr)
            return 1

    files_seen = 0
    chunks_total = 0
    posted_ok = 0
    posted_fail = 0
    skipped_empty = 0

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Ingesting project knowledge → AIDB {args.project}")
    print(f"Scanning {len(args.paths)} paths from {REPO_ROOT}")
    print()

    for abs_path in _iter_files(args.paths):
        rel = abs_path.relative_to(REPO_ROOT)
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        chunks = _chunk_text(text, str(rel))
        if not chunks:
            skipped_empty += 1
            continue

        files_seen += 1
        for chunk_text, chunk_idx in chunks:
            chunks_total += 1
            if args.max_docs and chunks_total > args.max_docs:
                break

            chunk_rel = f"{rel}" if len(chunks) == 1 else f"{rel}#chunk{chunk_idx}"
            first_line = chunk_text.strip().splitlines()[0][:80].strip("# ").strip() or str(rel)
            title = f"{rel.name}" if len(chunks) == 1 else f"{rel.name} [{chunk_idx+1}/{len(chunks)}]"

            ok = _post_document(
                api_key=api_key,
                content=chunk_text,
                title=title,
                relative_path=chunk_rel,
                project=args.project,
                dry_run=args.dry_run,
            )
            if ok:
                posted_ok += 1
                if posted_ok % 50 == 0:
                    print(f"  ...{posted_ok} chunks ingested ({files_seen} files)", flush=True)
            else:
                posted_fail += 1

            if not args.dry_run and args.delay > 0:
                time.sleep(args.delay)

        if args.max_docs and chunks_total >= args.max_docs:
            print(f"  [max-docs={args.max_docs} reached]")
            break

    print()
    print(f"Results:")
    print(f"  files:  {files_seen}")
    print(f"  chunks: {chunks_total}")
    if args.dry_run:
        print(f"  (dry-run — nothing posted)")
    else:
        print(f"  posted: {posted_ok} ok, {posted_fail} failed")
    if skipped_empty:
        print(f"  skipped (empty): {skipped_empty}")

    if not args.dry_run and chunks_total < 500:
        print(f"\n[WARN] Only {chunks_total} chunks — below 500-doc gate.", file=sys.stderr)
        print("  Try removing --max-docs or adding more --paths.", file=sys.stderr)

    return 0 if posted_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
