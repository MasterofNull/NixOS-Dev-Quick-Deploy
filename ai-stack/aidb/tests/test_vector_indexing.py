"""
Tests for Phase 3 Vector Indexing System

Tests the interaction and code change indexers.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Note: These are integration tests that require:
# - Qdrant running on localhost:6333
# - Embedding service running on localhost:8081
# Run with: pytest -v test_vector_indexing.py


class TestInteractionIndexer:
    """Test interaction log vectorization."""

    def test_create_interaction_text(self):
        """Test interaction text creation for embedding."""
        from interaction_indexer import InteractionIndexer

        indexer = InteractionIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
        )

        interaction = {
            "query": "How do I configure NixOS modules?",
            "response": "You can configure NixOS modules by...",
            "agent_type": "qwen",
            "outcome": "success",
        }

        text = indexer.create_interaction_text(interaction)

        assert "Query:" in text
        assert "How do I configure NixOS modules?" in text
        assert "Response:" in text
        assert "Agent: qwen" in text
        assert "Outcome: success" in text

    @pytest.mark.asyncio
    async def test_embed_text_fallback(self):
        """Test embedding fallback to zero vector on failure."""
        from interaction_indexer import InteractionIndexer

        # Mock HTTP client that always fails
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Service unavailable")

        indexer = InteractionIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
            embedding_dim=1024,
        )
        indexer.http_client = mock_client

        vector = await indexer.embed_text("test query")

        assert len(vector) == 1024
        assert all(v == 0.0 for v in vector)


class TestCodeChangeIndexer:
    """Test code change vectorization."""

    def test_categorize_change_conventional_commits(self):
        """Test change categorization from conventional commit messages."""
        from code_change_indexer import CodeChangeIndexer

        indexer = CodeChangeIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
            repo_path=".",
        )

        test_cases = [
            ({"subject": "feat: add new feature"}, [], "feature"),
            ({"subject": "fix: resolve bug"}, [], "fix"),
            ({"subject": "refactor: improve code"}, [], "refactor"),
            ({"subject": "docs: update readme"}, [], "documentation"),
            ({"subject": "test: add unit tests"}, [], "test"),
            ({"subject": "chore: update dependencies"}, [], "chore"),
        ]

        for commit, files, expected in test_cases:
            category = indexer.categorize_change(commit, files)
            assert category == expected, f"Failed for {commit['subject']}"

    def test_categorize_change_file_based(self):
        """Test change categorization from file extensions."""
        from code_change_indexer import CodeChangeIndexer

        indexer = CodeChangeIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
            repo_path=".",
        )

        test_cases = [
            ({"subject": "update files"}, ["README.md"], "documentation"),
            ({"subject": "update files"}, ["test_feature.py"], "test"),
            ({"subject": "update files"}, ["config.nix"], "configuration"),
        ]

        for commit, files, expected in test_cases:
            category = indexer.categorize_change(commit, files)
            assert category == expected, f"Failed for files {files}"

    def test_extract_code_context(self):
        """Test code context extraction from diff."""
        from code_change_indexer import CodeChangeIndexer

        indexer = CodeChangeIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
            repo_path=".",
        )

        diff = """
diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -10,7 +10,7 @@ def function():
     # Old code
-    old_line = "value"
+    new_line = "new value"
     # Context
     context_line = "unchanged"
"""

        context = indexer.extract_code_context(diff, max_length=500)

        # Should extract actual code lines
        assert "old_line" in context or "new_line" in context
        assert "context_line" in context
        # Should not include diff headers
        assert "diff --git" not in context
        assert "index abc123" not in context

    def test_create_change_text(self):
        """Test change text creation for embedding."""
        from code_change_indexer import CodeChangeIndexer

        indexer = CodeChangeIndexer(
            qdrant_client=Mock(),
            embedding_service_url="http://localhost:8081",
            repo_path=".",
        )

        commit = {
            "subject": "feat: add authentication",
            "body": "Implements JWT-based authentication",
            "author_name": "Test Author",
        }
        diff = "+  def authenticate(user):\n+    return jwt.encode(user)"
        files = ["auth.py", "middleware.py"]

        text = indexer.create_change_text(commit, diff, files)

        assert "feat: add authentication" in text
        assert "JWT-based authentication" in text
        assert "auth.py" in text
        assert "authenticate" in text


class TestCLITool:
    """Test aq-index CLI tool functionality."""

    def test_cli_help(self):
        """Test CLI help output."""
        import subprocess

        result = subprocess.run(
            ["scripts/ai/aq-index", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Vector Indexing CLI" in result.stdout
        assert "interactions" in result.stdout
        assert "code" in result.stdout
        assert "search" in result.stdout
        assert "stats" in result.stdout


# Integration tests (require services running)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_code_indexing_integration():
    """Integration test for code indexing (requires Qdrant + embedding service)."""
    from code_change_indexer import CodeChangeIndexer
    from qdrant_client import QdrantClient

    qdrant = QdrantClient(url="http://localhost:6333")
    indexer = CodeChangeIndexer(
        qdrant_client=qdrant,
        embedding_service_url="http://localhost:8081",
        repo_path=".",
        collection_name="test-codebase-context",
    )

    try:
        # Ensure collection exists
        await indexer.ensure_collection()

        # Index last commit
        commits = indexer.get_git_commits(since="1 day ago", limit=1)
        if commits:
            result = await indexer.index_commit(commits[0])
            assert result is not None, "Indexing failed"

        # Get stats
        stats = await indexer.get_stats()
        assert stats["total_changes"] >= 0

    finally:
        # Cleanup
        try:
            qdrant.delete_collection("test-codebase-context")
        except:
            pass
        await indexer.close()


if __name__ == "__main__":
    # Run basic unit tests
    pytest.main([__file__, "-v", "-k", "not integration"])
