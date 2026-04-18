"""
Code Change Vectorization System

This module provides indexing of code changes from git history into vector
embeddings for semantic search. It processes git commits and creates searchable
vectors for code modifications, enabling semantic code search and change analysis.

Phase 3.1 Completion - Code Change Vector Embeddings
"""

import asyncio
import hashlib
import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

logger = logging.getLogger(__name__)

_STOPWORD_HINTS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then",
    "feat", "fix", "docs", "chore", "refactor", "test", "perf", "build", "ci",
}
_DOC_PATH_MARKERS = (
    ".agent/",
    ".agents/",
    "docs/",
    "readme.md",
    "primer",
    "workflow",
    "roadmap",
)
_VALIDATION_NOISE_HINTS = {
    "py_compile",
    "pytest",
    "pre-commit",
    "pre-deploy",
    "tier0-validation-gate",
    "repo-structure-lint",
    "nix-instantiate",
    "bash -n",
    "aq-qa",
    "validation",
}
_ROUTE_STACK_OWNER_PATHS = (
    "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
    "ai-stack/mcp-servers/hybrid-coordinator/search_router.py",
    "ai-stack/mcp-servers/hybrid-coordinator/semantic_cache.py",
    "nix/modules/services/switchboard.nix",
)
_SUBSYSTEM_PATH_HINTS = (
    ("route-stack", _ROUTE_STACK_OWNER_PATHS),
    ("switchboard", ("nix/modules/services/switchboard.nix", "ai-stack/mcp-servers/hybrid-coordinator/llm_client.py")),
    ("orchestration", ("ai-stack/mcp-servers/ralph-wiggum/orchestrator.py", "ai-stack/offloading/agent_pool_manager.py")),
)
_ROUTE_STACK_HINT_TOKENS = (
    "route-stack",
    "route_handler",
    "search_router",
    "semantic_cache",
    "prompt_cache",
    "retrieval_context",
    "switchboard",
)


class CodeChangeIndexer:
    """Indexes code changes from git history into vector embeddings."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_service_url: str,
        repo_path: str = ".",
        collection_name: str = "codebase-context",
        embedding_dim: int = 1024,
    ):
        """
        Initialize the code change indexer.

        Args:
            qdrant_client: Qdrant client for vector storage
            embedding_service_url: URL of the embedding service
            repo_path: Path to the git repository
            collection_name: Name of the Qdrant collection
            embedding_dim: Dimension of embedding vectors
        """
        self.qdrant = qdrant_client
        self.embedding_url = embedding_service_url
        self.repo_path = Path(repo_path).resolve()
        self.collection = collection_name
        self.embedding_dim = embedding_dim
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def ensure_collection(self) -> None:
        """Ensure the Qdrant collection exists with proper configuration."""
        try:
            self.qdrant.get_collection(self.collection)
            logger.info(f"Collection {self.collection} already exists")
        except Exception:
            logger.info(f"Creating collection {self.collection}")
            self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    def truncate_text(self, text: str, max_tokens: int = 1800) -> str:
        """
        Truncate text to stay within token limit.

        Uses a rough approximation: 1 token ≈ 4 characters.
        Max tokens is set below the batch size to ensure safe margin.

        Args:
            text: Text to truncate
            max_tokens: Maximum token count (default: 1800, well below 2048 batch size)

        Returns:
            Truncated text
        """
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]
        logger.warning(
            f"Text truncated from {len(text)} to {max_chars} chars "
            f"(~{max_tokens} tokens) to fit batch size"
        )
        return truncated

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text using the embedding service.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Truncate text to prevent exceeding batch size
        text = self.truncate_text(text)

        try:
            response = await self.http_client.post(
                f"{self.embedding_url}/v1/embeddings",
                json={"input": text},
            )
            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            if "data" in data:
                return data["data"][0]["embedding"]
            elif "embeddings" in data:
                return data["embeddings"][0]
            else:
                logger.error(f"Unexpected embedding response format: {data.keys()}")
                return [0.0] * self.embedding_dim

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * self.embedding_dim

    def get_git_commits(
        self,
        since: Optional[str] = None,
        limit: int = 100,
        path_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get git commits with metadata.

        Args:
            since: Get commits since this date (e.g., "30 days ago")
            limit: Maximum number of commits
            path_filter: Filter commits by file path pattern

        Returns:
            List of commit dictionaries
        """
        cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "log",
            f"-{limit}",
            "--format=%H%n%an%n%ae%n%aI%n%s%n%b%n---END---",
        ]

        if since:
            cmd.append(f"--since={since}")

        if path_filter:
            cmd.extend(["--", path_filter])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            commits = []
            commit_texts = result.stdout.split("---END---\n")

            for commit_text in commit_texts:
                if not commit_text.strip():
                    continue

                lines = commit_text.strip().split("\n")
                if len(lines) < 5:
                    continue

                commit = {
                    "hash": lines[0],
                    "author_name": lines[1],
                    "author_email": lines[2],
                    "date": lines[3],
                    "subject": lines[4],
                    "body": "\n".join(lines[5:]) if len(lines) > 5 else "",
                }
                commits.append(commit)

            logger.info(f"Retrieved {len(commits)} git commits")
            return commits

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git commits: {e}")
            return []

    def get_commit_diff(self, commit_hash: str) -> str:
        """
        Get the diff for a specific commit.

        Args:
            commit_hash: Git commit hash

        Returns:
            Commit diff as string
        """
        cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "show",
            "--format=",
            "--unified=3",
            commit_hash,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit diff for {commit_hash}: {e}")
            return ""

    def get_commit_files(self, commit_hash: str) -> List[str]:
        """
        Get list of files changed in a commit.

        Args:
            commit_hash: Git commit hash

        Returns:
            List of changed file paths
        """
        cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "show",
            "--name-only",
            "--format=",
            commit_hash,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            files = [f for f in result.stdout.split("\n") if f.strip()]
            return files
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit files for {commit_hash}: {e}")
            return []

    def extract_code_context(self, diff: str, max_length: int = 2000) -> str:
        """
        Extract meaningful code context from a diff.

        Args:
            diff: Git diff text
            max_length: Maximum length of extracted context

        Returns:
            Extracted code context
        """
        # Remove diff headers and metadata
        lines = diff.split("\n")
        code_lines = []

        for line in lines:
            # Keep added/removed lines and context
            if line.startswith(("+", "-", " ")):
                # Strip diff markers but keep the code
                cleaned = line[1:] if line else ""
                code_lines.append(cleaned)

        context = "\n".join(code_lines)

        # Truncate if too long
        if len(context) > max_length:
            context = context[:max_length] + "\n... (truncated)"

        return context

    def categorize_change(self, commit: Dict[str, Any], files: List[str]) -> str:
        """
        Categorize the type of code change.

        Args:
            commit: Commit metadata
            files: List of changed files

        Returns:
            Change category (feature, fix, refactor, docs, etc.)
        """
        subject = commit["subject"].lower()

        # Check conventional commit prefixes
        if subject.startswith("feat"):
            return "feature"
        elif subject.startswith("fix"):
            return "fix"
        elif subject.startswith("refactor"):
            return "refactor"
        elif subject.startswith("docs"):
            return "documentation"
        elif subject.startswith("test"):
            return "test"
        elif subject.startswith("chore"):
            return "chore"
        elif subject.startswith("perf"):
            return "performance"

        # Infer from file types
        if any(f.endswith((".md", ".txt", ".rst")) for f in files):
            return "documentation"
        elif any(f.startswith("test") or "test" in f for f in files):
            return "test"
        elif any(f.endswith((".sh", ".nix", ".yaml", ".yml")) for f in files):
            return "configuration"

        return "other"

    def build_keyword_hints(self, commit: Dict[str, Any], files: List[str], diff: str) -> List[str]:
        """Build compact lexical hints to improve later keyword ranking."""
        hints: List[str] = []
        for file_path in files[:8]:
            path = str(file_path).strip()
            if not path:
                continue
            hints.append(path)
            lowered_path = path.lower()
            if any(marker in lowered_path for marker in _DOC_PATH_MARKERS):
                continue
            hints.extend(part for part in re.split(r"[/_.-]+", lowered_path) if len(part) >= 3)

        subject = " ".join(str(commit.get("subject", "")).lower().split())
        body = " ".join(str(commit.get("body", "")).lower().split())
        diff_preview = " ".join(str(diff or "").lower().split())[:600]
        for source in (subject, body, diff_preview):
            for token in re.findall(r"[a-z0-9_/-]{3,}", source):
                if token in _STOPWORD_HINTS or token in _VALIDATION_NOISE_HINTS:
                    continue
                if any(marker in token for marker in _DOC_PATH_MARKERS):
                    continue
                hints.append(token)

        deduped: List[str] = []
        for hint in hints:
            normalized = hint.strip()
            if not normalized or normalized in deduped:
                continue
            deduped.append(normalized)
        return deduped[:40]

    def build_owner_paths(self, files: List[str]) -> List[str]:
        """Return direct owner paths that should outrank mixed roadmap/runtime commits."""
        owners: List[str] = []
        for file_path in files:
            normalized = str(file_path).strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if any(owner in lowered for owner in _ROUTE_STACK_OWNER_PATHS):
                owners.append(normalized)
        deduped: List[str] = []
        for owner in owners:
            if owner not in deduped:
                deduped.append(owner)
        return deduped

    def build_subsystem_tags(self, files: List[str], commit: Dict[str, Any], diff: str) -> List[str]:
        """Tag commits by subsystem so retrieval can prefer direct ownership lanes."""
        tags: List[str] = []
        normalized_files = [str(file_path).strip().lower() for file_path in files if str(file_path).strip()]
        merged_text = " ".join(
            part for part in (
                str(commit.get("subject", "")).lower(),
                str(commit.get("body", "")).lower(),
                str(diff or "").lower(),
            ) if part
        )
        for tag, path_hints in _SUBSYSTEM_PATH_HINTS:
            if any(hint in merged_text for hint in (tag.replace("-", " "), tag.replace("-", "_"))):
                tags.append(tag)
                continue
            if any(any(path_hint in file_path for path_hint in path_hints) for file_path in normalized_files):
                tags.append(tag)
        deduped: List[str] = []
        for tag in tags:
            if tag not in deduped:
                deduped.append(tag)
        return deduped

    def build_route_stack_hints(self, commit: Dict[str, Any], files: List[str], diff: str) -> List[str]:
        """Build explicit route-stack retrieval hints for codebase-context payloads."""
        owner_paths = self.build_owner_paths(files)
        merged_text = " ".join(
            part for part in (
                str(commit.get("subject", "")).lower(),
                str(commit.get("body", "")).lower(),
                str(diff or "").lower(),
            ) if part
        )
        hints: List[str] = []
        if owner_paths:
            hints.extend(_ROUTE_STACK_HINT_TOKENS)
        if "route stack" in merged_text:
            hints.append("route-stack")
        if "prompt cache" in merged_text:
            hints.append("prompt_cache")
        if "retrieval context" in merged_text:
            hints.append("retrieval_context")
        if "switchboard" in merged_text:
            hints.append("switchboard")
        deduped: List[str] = []
        for hint in hints:
            if hint not in deduped:
                deduped.append(hint)
        return deduped

    def build_payload(self, commit: Dict[str, Any], diff: str, files: List[str]) -> Dict[str, Any]:
        """Build Qdrant payload for a code change entry."""
        return {
            "commit_hash": commit["hash"],
            "commit_subject": commit["subject"],
            "commit_body": commit.get("body", "")[:500],
            "author_name": commit["author_name"],
            "author_email": commit["author_email"],
            "date": commit["date"],
            "files_changed": files,
            "num_files": len(files),
            "category": self.categorize_change(commit, files),
            "diff_preview": diff[:500],
            "keyword_hints": self.build_keyword_hints(commit, files, diff),
            "owner_paths": self.build_owner_paths(files),
            "subsystem_tags": self.build_subsystem_tags(files, commit, diff),
            "route_stack_hints": self.build_route_stack_hints(commit, files, diff),
        }

    def create_change_text(self, commit: Dict[str, Any], diff: str, files: List[str]) -> str:
        """
        Create searchable text from code change data.

        Args:
            commit: Commit metadata
            diff: Commit diff
            files: Changed files

        Returns:
            Combined text for embedding
        """
        parts = []

        # Commit message (most important for search)
        parts.append(f"Commit: {commit['subject']}")

        if commit.get("body"):
            body = commit["body"][:300]  # Limit body length
            parts.append(f"Description: {body}")

        # Changed files context
        if files:
            files_text = ", ".join(files[:10])  # Limit file list
            parts.append(f"Files: {files_text}")
        owner_paths = self.build_owner_paths(files)
        if owner_paths:
            parts.append(f"Owner Paths: {', '.join(owner_paths[:4])}")
        subsystem_tags = self.build_subsystem_tags(files, commit, diff)
        if subsystem_tags:
            parts.append(f"Subsystems: {', '.join(subsystem_tags[:6])}")
        route_stack_hints = self.build_route_stack_hints(commit, files, diff)
        if route_stack_hints:
            parts.append(f"Retrieval Hints: {', '.join(route_stack_hints[:8])}")

        # Code context
        code_context = self.extract_code_context(diff, max_length=1000)
        if code_context:
            parts.append(f"Code:\n{code_context}")

        return "\n\n".join(parts)

    async def index_commit(self, commit: Dict[str, Any]) -> Optional[str]:
        """
        Index a single commit into the vector database.

        Args:
            commit: Commit metadata

        Returns:
            Change ID if successful, None otherwise
        """
        commit_hash = commit["hash"]
        # Generate a UUID for Qdrant compatibility
        change_id = str(uuid4())

        # Get commit diff and files
        diff = self.get_commit_diff(commit_hash)
        files = self.get_commit_files(commit_hash)

        if not diff and not files:
            logger.warning(f"No changes found for commit {commit_hash}")
            return None

        # Create searchable text
        text = self.create_change_text(commit, diff, files)

        # Generate embedding
        vector = await self.embed_text(text)

        if not vector or len(vector) != self.embedding_dim:
            logger.error(f"Invalid embedding vector for commit {commit_hash}")
            return None

        payload = self.build_payload(commit, diff, files)
        await self.delete_existing_commit_points(commit_hash)

        # Store in Qdrant
        try:
            self.qdrant.upsert(
                collection_name=self.collection,
                points=[PointStruct(id=change_id, vector=vector, payload=payload)],
            )
            logger.debug(f"Indexed commit {commit_hash[:12]}")
            return change_id
        except Exception as e:
            logger.error(f"Failed to index commit {commit_hash}: {e}")
            return None

    async def delete_existing_commit_points(self, commit_hash: str) -> int:
        """Delete any existing vectors for the same commit hash before reindexing."""
        try:
            points, _ = self.qdrant.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="commit_hash", match=MatchValue(value=commit_hash))]
                ),
                limit=256,
                with_payload=False,
                with_vectors=False,
            )
        except Exception as exc:
            logger.warning("existing_commit_lookup_failed commit=%s error=%s", commit_hash, exc)
            return 0

        existing_ids = [point.id for point in points if getattr(point, "id", None) is not None]
        if not existing_ids:
            return 0
        self.qdrant.delete(collection_name=self.collection, points_selector=existing_ids)
        return len(existing_ids)

    async def index_commits(
        self,
        since: str = "30 days ago",
        limit: int = 100,
        path_filter: Optional[str] = None,
        batch_size: int = 10,
    ) -> Tuple[int, int]:
        """
        Index commits from git history.

        Args:
            since: Index commits since this date
            limit: Maximum number of commits to index
            path_filter: Filter commits by file path
            batch_size: Number of commits to process at once

        Returns:
            Tuple of (successful_count, failed_count)
        """
        commits = self.get_git_commits(since=since, limit=limit, path_filter=path_filter)

        if not commits:
            logger.info("No commits found to index")
            return 0, 0

        successful = 0
        failed = 0

        for i in range(0, len(commits), batch_size):
            batch = commits[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} commits)")

            for commit in batch:
                result = await self.index_commit(commit)
                if result:
                    successful += 1
                else:
                    failed += 1

            # Small delay between batches
            if i + batch_size < len(commits):
                await asyncio.sleep(0.5)

        logger.info(f"Commit indexing complete: {successful} successful, {failed} failed")
        return successful, failed

    async def search_code_changes(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search code changes by semantic similarity.

        Args:
            query: Search query
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            category_filter: Filter by change category

        Returns:
            List of matching code changes with scores
        """
        # Generate query embedding
        query_vector = await self.embed_text(query)

        if not query_vector or len(query_vector) != self.embedding_dim:
            logger.error("Failed to generate query embedding")
            return []

        # Build filter if provided
        qdrant_filter = None
        if category_filter:
            # TODO: Convert category filter to Qdrant filter format
            pass

        # Search in Qdrant
        try:
            results = self.qdrant.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
            ).points

            changes = []
            for hit in results:
                change = hit.payload.copy()
                change["id"] = hit.id
                change["score"] = hit.score
                changes.append(change)

            logger.info(f"Found {len(changes)} matching code changes")
            return changes

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the indexed code changes.

        Returns:
            Dictionary with collection stats
        """
        try:
            info = self.qdrant.get_collection(self.collection)
            return {
                "collection": self.collection,
                "total_changes": info.points_count,
                "status": info.status.value if hasattr(info.status, 'value') else str(info.status),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    async def close(self) -> None:
        """Close HTTP client connections."""
        await self.http_client.aclose()


# Standalone functions for CLI usage

async def index_recent_commits(
    repo_path: str = ".",
    qdrant_url: str = "http://localhost:6333",
    embedding_url: str = "http://localhost:8081",
    since: str = "30 days ago",
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Index recent commits from git history.

    Args:
        repo_path: Path to git repository
        qdrant_url: Qdrant server URL
        embedding_url: Embedding service URL
        since: Index commits since this date
        limit: Maximum commits to index

    Returns:
        Indexing results
    """
    qdrant = QdrantClient(url=qdrant_url)
    indexer = CodeChangeIndexer(
        qdrant_client=qdrant,
        embedding_service_url=embedding_url,
        repo_path=repo_path,
    )

    await indexer.ensure_collection()
    successful, failed = await indexer.index_commits(since=since, limit=limit)
    stats = await indexer.get_stats()
    await indexer.close()

    return {
        "indexed": successful,
        "failed": failed,
        "total": successful + failed,
        "stats": stats,
    }


if __name__ == "__main__":
    # Simple CLI test
    import sys

    async def main():
        repo_path = sys.argv[1] if len(sys.argv) > 1 else "."

        qdrant = QdrantClient(url="http://localhost:6333")
        indexer = CodeChangeIndexer(
            qdrant_client=qdrant,
            embedding_service_url="http://localhost:8081",
            repo_path=repo_path,
        )

        await indexer.ensure_collection()

        # Index recent commits
        print("Indexing recent commits...")
        successful, failed = await indexer.index_commits(since="7 days ago", limit=50)
        print(f"Indexed {successful} commits ({failed} failed)")

        # Show stats
        stats = await indexer.get_stats()
        print(f"Collection stats: {json.dumps(stats, indent=2)}")

        await indexer.close()

    asyncio.run(main())
