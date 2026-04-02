#!/usr/bin/env python3
"""
Workspace Isolation - Per-Agent Sandboxed Execution Environments

Provides isolated workspace management for parallel agent execution with:
- Temporary directory creation per agent/session
- Git worktree isolation for concurrent modifications
- File conflict detection and resolution
- Resource cleanup on completion

Part of Phase 4.2: Multi-Agent Orchestration Enhancements
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class IsolationMode(str, Enum):
    """Workspace isolation strategy."""
    TEMP_DIR = "temp_dir"       # Simple temp directory
    GIT_WORKTREE = "worktree"   # Git worktree for version control
    OVERLAY = "overlay"         # Overlay filesystem (requires root)
    COPY = "copy"               # Full copy of source directory


class ConflictStrategy(str, Enum):
    """Strategy for resolving concurrent file modifications."""
    FAIL = "fail"               # Fail on any conflict
    LATEST_WINS = "latest"      # Most recent modification wins
    MERGE = "merge"             # Attempt git merge
    MANUAL = "manual"           # Flag for manual resolution


@dataclass
class FileModification:
    """Track file modification for conflict detection."""
    path: str
    agent_id: str
    workspace_id: str
    operation: str  # create, modify, delete
    timestamp: float
    content_hash: Optional[str] = None
    original_hash: Optional[str] = None


@dataclass
class Workspace:
    """Isolated agent workspace."""
    workspace_id: str
    agent_id: str
    session_id: str
    mode: IsolationMode
    root_path: Path
    source_path: Optional[Path] = None
    branch: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    modifications: List[FileModification] = field(default_factory=list)
    mounted_volumes: Dict[str, Path] = field(default_factory=dict)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "mode": self.mode.value,
            "root_path": str(self.root_path),
            "source_path": str(self.source_path) if self.source_path else None,
            "branch": self.branch,
            "created_at": self.created_at,
            "modification_count": len(self.modifications),
            "mounted_volumes": {k: str(v) for k, v in self.mounted_volumes.items()},
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


@dataclass
class ConflictReport:
    """Report of detected file conflicts."""
    file_path: str
    conflicting_agents: List[str]
    modifications: List[FileModification]
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None


class WorkspaceManager:
    """
    Manages isolated workspaces for parallel agent execution.

    Provides sandboxed environments with file tracking, conflict
    detection, and cleanup capabilities.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        default_mode: IsolationMode = IsolationMode.TEMP_DIR,
        conflict_strategy: ConflictStrategy = ConflictStrategy.FAIL,
    ) -> None:
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "agent-workspaces"
        self.default_mode = default_mode
        self.conflict_strategy = conflict_strategy
        self.workspaces: Dict[str, Workspace] = {}
        self._modification_log: List[FileModification] = []
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _generate_workspace_id(self, agent_id: str, session_id: str) -> str:
        timestamp = str(int(time.time() * 1000))
        raw = f"{agent_id}-{session_id}-{timestamp}"
        return f"ws-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    def _hash_file(self, path: Path) -> Optional[str]:
        if not path.exists() or not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    # -------------------------------------------------------------------------
    # Workspace Lifecycle
    # -------------------------------------------------------------------------

    async def create_workspace(
        self,
        agent_id: str,
        session_id: str,
        source_path: Optional[Path] = None,
        mode: Optional[IsolationMode] = None,
        branch: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Workspace:
        """Create an isolated workspace for an agent."""
        workspace_id = self._generate_workspace_id(agent_id, session_id)
        isolation_mode = mode or self.default_mode

        workspace_root = self.base_dir / workspace_id
        workspace_root.mkdir(parents=True, exist_ok=True)

        workspace = Workspace(
            workspace_id=workspace_id,
            agent_id=agent_id,
            session_id=session_id,
            mode=isolation_mode,
            root_path=workspace_root,
            source_path=source_path,
            branch=branch,
            metadata=metadata or {},
        )

        # Initialize based on mode
        if isolation_mode == IsolationMode.TEMP_DIR:
            await self._init_temp_workspace(workspace)
        elif isolation_mode == IsolationMode.GIT_WORKTREE:
            await self._init_git_worktree(workspace)
        elif isolation_mode == IsolationMode.COPY:
            await self._init_copy_workspace(workspace)

        self.workspaces[workspace_id] = workspace
        logger.info("Created workspace %s for agent %s", workspace_id, agent_id)
        return workspace

    async def _init_temp_workspace(self, workspace: Workspace) -> None:
        """Initialize simple temp directory workspace."""
        if workspace.source_path and workspace.source_path.exists():
            # Copy essential files if source provided
            for item in workspace.source_path.iterdir():
                if item.name.startswith("."):
                    continue
                dest = workspace.root_path / item.name
                if item.is_file():
                    shutil.copy2(item, dest)

    async def _init_git_worktree(self, workspace: Workspace) -> None:
        """Initialize git worktree for isolated version control."""
        if not workspace.source_path:
            logger.warning("Git worktree requires source_path with git repo")
            return

        branch = workspace.branch or f"agent-{workspace.agent_id}-{int(time.time())}"

        try:
            # Create new branch from current HEAD
            subprocess.run(
                ["git", "branch", branch],
                cwd=workspace.source_path,
                check=True,
                capture_output=True,
            )

            # Create worktree
            subprocess.run(
                ["git", "worktree", "add", str(workspace.root_path), branch],
                cwd=workspace.source_path,
                check=True,
                capture_output=True,
            )
            workspace.branch = branch
            logger.info("Created git worktree at %s on branch %s", workspace.root_path, branch)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create git worktree: %s", e.stderr.decode() if e.stderr else str(e))

    async def _init_copy_workspace(self, workspace: Workspace) -> None:
        """Initialize full copy workspace."""
        if workspace.source_path and workspace.source_path.exists():
            shutil.copytree(
                workspace.source_path,
                workspace.root_path,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules"),
            )

    async def cleanup_workspace(self, workspace_id: str, force: bool = False) -> bool:
        """Clean up and remove a workspace."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False

        if workspace.is_active and not force:
            logger.warning("Cannot cleanup active workspace %s without force=True", workspace_id)
            return False

        workspace.is_active = False

        # Handle git worktree cleanup
        if workspace.mode == IsolationMode.GIT_WORKTREE and workspace.source_path:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", str(workspace.root_path), "--force"],
                    cwd=workspace.source_path,
                    check=True,
                    capture_output=True,
                )
                if workspace.branch:
                    subprocess.run(
                        ["git", "branch", "-D", workspace.branch],
                        cwd=workspace.source_path,
                        check=False,
                        capture_output=True,
                    )
            except subprocess.CalledProcessError as e:
                logger.warning("Git worktree cleanup warning: %s", e)

        # Remove workspace directory
        if workspace.root_path.exists():
            shutil.rmtree(workspace.root_path, ignore_errors=True)

        del self.workspaces[workspace_id]
        logger.info("Cleaned up workspace %s", workspace_id)
        return True

    async def cleanup_session_workspaces(self, session_id: str) -> int:
        """Clean up all workspaces for a session."""
        to_cleanup = [
            ws_id for ws_id, ws in self.workspaces.items()
            if ws.session_id == session_id
        ]
        count = 0
        for ws_id in to_cleanup:
            if await self.cleanup_workspace(ws_id, force=True):
                count += 1
        return count

    # -------------------------------------------------------------------------
    # File Operations with Tracking
    # -------------------------------------------------------------------------

    def track_modification(
        self,
        workspace_id: str,
        file_path: str,
        operation: str,
    ) -> Optional[FileModification]:
        """Track a file modification for conflict detection."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return None

        full_path = workspace.root_path / file_path
        content_hash = self._hash_file(full_path) if full_path.exists() else None

        mod = FileModification(
            path=file_path,
            agent_id=workspace.agent_id,
            workspace_id=workspace_id,
            operation=operation,
            timestamp=time.time(),
            content_hash=content_hash,
        )
        workspace.modifications.append(mod)
        self._modification_log.append(mod)
        return mod

    def get_workspace_files(self, workspace_id: str) -> List[str]:
        """List all files in a workspace."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace or not workspace.root_path.exists():
            return []

        files = []
        for path in workspace.root_path.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(workspace.root_path)
                files.append(str(rel_path))
        return sorted(files)

    def read_file(self, workspace_id: str, file_path: str) -> Optional[str]:
        """Read a file from workspace."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return None

        full_path = workspace.root_path / file_path
        if not full_path.exists():
            return None

        return full_path.read_text(encoding="utf-8")

    def write_file(
        self,
        workspace_id: str,
        file_path: str,
        content: str,
    ) -> bool:
        """Write a file to workspace with tracking."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False

        full_path = workspace.root_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        operation = "modify" if full_path.exists() else "create"
        full_path.write_text(content, encoding="utf-8")

        self.track_modification(workspace_id, file_path, operation)
        return True

    def delete_file(self, workspace_id: str, file_path: str) -> bool:
        """Delete a file from workspace with tracking."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False

        full_path = workspace.root_path / file_path
        if not full_path.exists():
            return False

        full_path.unlink()
        self.track_modification(workspace_id, file_path, "delete")
        return True

    # -------------------------------------------------------------------------
    # Conflict Detection
    # -------------------------------------------------------------------------

    def detect_conflicts(self, session_id: str) -> List[ConflictReport]:
        """Detect file conflicts across all workspaces in a session."""
        # Group modifications by file path
        session_workspaces = [
            ws for ws in self.workspaces.values()
            if ws.session_id == session_id
        ]

        file_modifications: Dict[str, List[FileModification]] = {}
        for ws in session_workspaces:
            for mod in ws.modifications:
                file_modifications.setdefault(mod.path, []).append(mod)

        conflicts = []
        for file_path, mods in file_modifications.items():
            # Check if multiple agents modified the same file
            agents = set(m.agent_id for m in mods)
            if len(agents) > 1:
                conflicts.append(ConflictReport(
                    file_path=file_path,
                    conflicting_agents=list(agents),
                    modifications=mods,
                ))

        return conflicts

    async def resolve_conflicts(
        self,
        conflicts: List[ConflictReport],
        strategy: Optional[ConflictStrategy] = None,
    ) -> List[ConflictReport]:
        """Resolve file conflicts using specified strategy."""
        resolution_strategy = strategy or self.conflict_strategy
        resolved = []

        for conflict in conflicts:
            if resolution_strategy == ConflictStrategy.FAIL:
                conflict.resolution = "failed"
                continue

            if resolution_strategy == ConflictStrategy.LATEST_WINS:
                latest = max(conflict.modifications, key=lambda m: m.timestamp)
                conflict.resolution = "latest_wins"
                conflict.resolved_by = latest.agent_id
                resolved.append(conflict)

            elif resolution_strategy == ConflictStrategy.MERGE:
                # Attempt git merge if in worktree mode
                conflict.resolution = "merge_attempted"
                resolved.append(conflict)

            elif resolution_strategy == ConflictStrategy.MANUAL:
                conflict.resolution = "manual_required"

        return resolved

    # -------------------------------------------------------------------------
    # Merge & Sync
    # -------------------------------------------------------------------------

    async def merge_to_source(
        self,
        workspace_id: str,
        commit_message: Optional[str] = None,
    ) -> bool:
        """Merge workspace changes back to source."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace or not workspace.source_path:
            return False

        if workspace.mode == IsolationMode.GIT_WORKTREE:
            return await self._merge_worktree(workspace, commit_message)
        else:
            return await self._copy_back_changes(workspace)

    async def _merge_worktree(
        self,
        workspace: Workspace,
        commit_message: Optional[str] = None,
    ) -> bool:
        """Merge git worktree back to main branch."""
        if not workspace.branch:
            return False

        try:
            # Commit changes in worktree
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace.root_path,
                check=True,
                capture_output=True,
            )

            msg = commit_message or f"Agent {workspace.agent_id} changes"
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=workspace.root_path,
                check=False,
                capture_output=True,
            )

            if result.returncode != 0 and b"nothing to commit" not in result.stdout:
                logger.warning("Commit in worktree failed: %s", result.stderr.decode())
                return False

            # Merge to main
            main_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workspace.source_path,
                check=True,
                capture_output=True,
            ).stdout.decode().strip()

            subprocess.run(
                ["git", "checkout", main_branch],
                cwd=workspace.source_path,
                check=True,
                capture_output=True,
            )

            subprocess.run(
                ["git", "merge", workspace.branch, "--no-ff", "-m", f"Merge {workspace.branch}"],
                cwd=workspace.source_path,
                check=True,
                capture_output=True,
            )

            logger.info("Merged workspace %s branch %s to %s", workspace.workspace_id, workspace.branch, main_branch)
            return True

        except subprocess.CalledProcessError as e:
            logger.error("Merge failed: %s", e.stderr.decode() if e.stderr else str(e))
            return False

    async def _copy_back_changes(self, workspace: Workspace) -> bool:
        """Copy modified files back to source."""
        if not workspace.source_path:
            return False

        for mod in workspace.modifications:
            src = workspace.root_path / mod.path
            dest = workspace.source_path / mod.path

            if mod.operation == "delete":
                if dest.exists():
                    dest.unlink()
            elif src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        logger.info("Copied %d modifications back to source", len(workspace.modifications))
        return True

    # -------------------------------------------------------------------------
    # Status & Monitoring
    # -------------------------------------------------------------------------

    def get_workspace_status(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed workspace status."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return None

        files = self.get_workspace_files(workspace_id)
        return {
            **workspace.to_dict(),
            "file_count": len(files),
            "modification_count": len(workspace.modifications),
            "disk_usage_bytes": sum(
                (workspace.root_path / f).stat().st_size
                for f in files
                if (workspace.root_path / f).exists()
            ),
        }

    def list_workspaces(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Workspace]:
        """List workspaces with optional filters."""
        workspaces = list(self.workspaces.values())

        if session_id:
            workspaces = [w for w in workspaces if w.session_id == session_id]
        if agent_id:
            workspaces = [w for w in workspaces if w.agent_id == agent_id]

        return sorted(workspaces, key=lambda w: w.created_at, reverse=True)

    def get_modification_timeline(
        self,
        session_id: Optional[str] = None,
    ) -> List[FileModification]:
        """Get modification timeline for analysis."""
        mods = self._modification_log

        if session_id:
            session_workspaces = {
                ws.workspace_id for ws in self.workspaces.values()
                if ws.session_id == session_id
            }
            mods = [m for m in mods if m.workspace_id in session_workspaces]

        return sorted(mods, key=lambda m: m.timestamp)
