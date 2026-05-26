"""
dag_manager.py — Tree-based session DAG manager with JSONL persistence.
                  Supports parent-child linked turns, branching, and formal handoffs.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("dag-manager")

class AgentHandoff(BaseModel):
    """Formal handoff schema between agents (ASLA compliant)."""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    handoff_count: int = Field(default=0, ge=0, le=10)
    reason: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DAGEntry(BaseModel):
    """A single entry in the session DAG."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    type: str  # message, tool_call, tool_result, compaction, system, handoff
    role: Optional[str] = None  # user, assistant, system
    content: Optional[Union[str, Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DAGSessionManager:
    """
    Manages session DAGs stored in JSONL format.
    Enables branching history and formal agent handoffs.
    """

    def __init__(self, session_dir: Union[str, Path]):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.jsonl"

    def create_entry(
        self,
        session_id: str,
        entry_type: str,
        parent_id: Optional[str] = None,
        role: Optional[str] = None,
        content: Optional[Union[str, Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DAGEntry:
        """Create and persist a new entry in the session DAG."""
        entry = DAGEntry(
            parent_id=parent_id,
            type=entry_type,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        session_path = self._get_session_path(session_id)
        with open(session_path, "a") as f:
            f.write(entry.model_dump_json() + "\n")
            
        return entry

    def load_session(self, session_id: str) -> List[DAGEntry]:
        """Load all entries for a given session."""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return []
            
        entries = []
        with open(session_path, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(DAGEntry.model_validate_json(line))
        return entries

    def get_history_branch(self, session_id: str, leaf_id: str) -> List[DAGEntry]:
        """Traverse upwards from a leaf ID to the root to reconstruct a specific history branch."""
        all_entries = {e.id: e for e in self.load_session(session_id)}
        branch = []
        current_id = leaf_id
        
        while current_id and current_id in all_entries:
            entry = all_entries[current_id]
            branch.append(entry)
            current_id = entry.parent_id
            
        return list(reversed(branch))

    def branch_session(self, session_id: str, fork_id: str, new_session_id: Optional[str] = None) -> str:
        """Create a new session ID branched from a specific turn in an existing session."""
        new_session_id = new_session_id or str(uuid.uuid4())
        history = self.get_history_branch(session_id, fork_id)
        
        new_path = self._get_session_path(new_session_id)
        with open(new_path, "w") as f:
            for entry in history:
                f.write(entry.model_dump_json() + "\n")
                
        return new_session_id

    def record_handoff(self, session_id: str, handoff: AgentHandoff, parent_id: Optional[str] = None) -> DAGEntry:
        """Record a formal agent handoff in the DAG."""
        return self.create_entry(
            session_id=session_id,
            entry_type="handoff",
            parent_id=parent_id,
            content=handoff.model_dump(),
            metadata={"trace_id": handoff.trace_id}
        )
