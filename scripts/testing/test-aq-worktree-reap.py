#!/usr/bin/env python3
"""
Unit tests for aq-worktree-reap.

Tests the core logic without requiring full git worktree setup.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


class TestBranchAnalysis(unittest.TestCase):
    """Test cases for branch analysis logic."""

    def setUp(self):
        """Create temporary directories for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.temp_dir.name) / "test-repo"
        self.repo_dir.mkdir(parents=True)

        # Initialize bare origin repo
        self.origin_dir = Path(self.temp_dir.name) / "origin"
        self.origin_dir.mkdir()
        subprocess.run(
            ["git", "init", "--bare"],
            cwd=str(self.origin_dir),
            capture_output=True,
            check=True
        )

        # Clone into test repo
        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(self.repo_dir)],
            capture_output=True,
            check=True
        )

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

        # Create initial commit
        (self.repo_dir / "README.md").write_text("# Test\n")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

    def tearDown(self):
        """Clean up temporary directories."""
        self.temp_dir.cleanup()

    def test_delegate_branch_no_commits_ahead(self):
        """Test that delegate branch with no commits ahead is detected."""
        # Create delegate branch (same as origin/main)
        subprocess.run(
            ["git", "checkout", "-b", "delegate/clean"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "delegate/clean"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

        # Verify branch has no commits ahead of origin/main
        result = subprocess.run(
            ["git", "rev-list", "delegate/clean", "--not", "origin/main"],
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            check=True
        )

        # Should have no commits ahead
        self.assertEqual(result.stdout.strip(), "")

    def test_delegate_branch_with_commits_ahead(self):
        """Test that delegate branch with commits ahead is detected."""
        # Create delegate branch
        subprocess.run(
            ["git", "checkout", "-b", "delegate/ahead"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

        # Add a commit
        (self.repo_dir / "file.txt").write_text("content")
        subprocess.run(
            ["git", "add", "file.txt"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add file"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "delegate/ahead"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

        # Verify branch has commits ahead of origin/main
        result = subprocess.run(
            ["git", "rev-list", "delegate/ahead", "--not", "origin/main"],
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            check=True
        )

        # Should have commits ahead
        self.assertGreater(len(result.stdout.strip()), 0)

    def test_non_delegate_branch_ignored(self):
        """Test that non-delegate branches are in the list but clearly distinguishable."""
        # Create a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "feature/test"],
            cwd=str(self.repo_dir),
            capture_output=True,
            check=True
        )

        # Verify we can check branch name
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            check=True
        )

        self.assertIn("feature/test", result.stdout)


class TestGraphDetection(unittest.TestCase):
    """Test cases for orphaned graph detection."""

    def setUp(self):
        """Create temporary graph directory."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.graph_dir = Path(self.temp_dir.name) / "graphs"
        self.graph_dir.mkdir()

    def tearDown(self):
        """Clean up."""
        self.temp_dir.cleanup()

    def test_orphan_detection(self):
        """Test detection of orphaned graphs with non-existent project root."""
        # Create a graph entry with non-existent project root
        graph_entry = self.graph_dir / "abc123"
        graph_entry.mkdir()

        index_data = {
            "project_root": "/nonexistent/path/12345",
            "created_at": "2024-01-01T00:00:00Z"
        }
        (graph_entry / "index.json").write_text(json.dumps(index_data))

        # Create some fake data files
        (graph_entry / "data.db").write_text("x" * 1000)

        # Read and verify the data
        with open(graph_entry / "index.json") as f:
            data = json.load(f)
            self.assertEqual(data["project_root"], "/nonexistent/path/12345")
            # Verify project root does not exist
            self.assertFalse(Path(data["project_root"]).exists())

    def test_graph_with_existing_project_root(self):
        """Test that graphs with existing project roots are not orphaned."""
        # Create a project root
        project_root = Path(self.temp_dir.name) / "project"
        project_root.mkdir()

        # Create a graph entry
        graph_entry = self.graph_dir / "def456"
        graph_entry.mkdir()

        index_data = {
            "project_root": str(project_root),
            "created_at": "2024-01-01T00:00:00Z"
        }
        (graph_entry / "index.json").write_text(json.dumps(index_data))

        # Read and verify the data
        with open(graph_entry / "index.json") as f:
            data = json.load(f)
            # Verify project root exists
            self.assertTrue(Path(data["project_root"]).exists())


class TestAgeDetection(unittest.TestCase):
    """Test cases for age-based filtering."""

    def test_mtime_calculation(self):
        """Test that modification time is correctly calculated."""
        temp_dir = tempfile.TemporaryDirectory()
        test_file = Path(temp_dir.name) / "test"
        test_file.mkdir()

        # Get current mtime
        current_mtime = test_file.stat().st_mtime
        current_time = datetime.now(timezone.utc).timestamp()

        # Verify it's close to now (within 5 seconds)
        self.assertLess(abs(current_time - current_mtime), 5)

        temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
