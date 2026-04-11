#!/usr/bin/env python3
"""
Agent-Specific Memory Diaries

Phase 1.5 Slice 1.8: Private memory spaces for individual agents.

Each agent (qwen, codex, claude, gemini) maintains a private diary of their
work, learnings, and discoveries. This enables expertise accumulation over time
and provides isolated memory spaces.

Usage:
    from aidb.agent_diary import AgentDiary

    # Agent writes to their diary
    diary = AgentDiary("qwen")
    diary.write(
        "Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.",
        topic="auth",
        tags=["jwt", "security", "bcrypt"]
    )

    # Agent reads from their diary
    auth_entries = diary.read(topic="auth", since_days=7)

    # Agent searches their diary
    results = diary.search("JWT implementation")

    # Orchestrator can read (but not write) to agent diaries
    qwen_work = AgentDiary.read_as_observer("qwen", topic="auth")
"""

from pathlib import Path
from typing import List, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import json

from aidb.temporal_facts import TemporalFact


@dataclass
class DiaryEntry:
    """A single diary entry from an agent"""
    entry_id: str
    agent: str
    content: str
    topic: str
    tags: List[str]
    timestamp: str
    fact_id: Optional[str] = None  # Link to corresponding TemporalFact

    def to_dict(self):
        return {
            "entry_id": self.entry_id,
            "agent": self.agent,
            "content": self.content,
            "topic": self.topic,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "fact_id": self.fact_id,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class AgentDiary:
    """
    Private memory diary for an AI agent.

    Each agent has an isolated diary for recording work, learnings,
    and discoveries. This enables:
    - Expertise accumulation over time
    - Memory isolation between agents
    - Work history and context continuity
    """

    VALID_AGENTS = {"qwen", "codex", "claude", "gemini", "remote"}

    def __init__(
        self,
        agent_name: str,
        diary_dir: str = "~/.aidb/diaries",
        fact_store=None
    ):
        """
        Initialize agent diary.

        Args:
            agent_name: Name of the agent (qwen, codex, claude, gemini)
            diary_dir: Directory for diary files
            fact_store: Optional fact store for creating TemporalFacts
        """
        if agent_name not in self.VALID_AGENTS:
            raise ValueError(
                f"Invalid agent name: {agent_name}. "
                f"Must be one of: {', '.join(self.VALID_AGENTS)}"
            )

        self.agent = agent_name
        self.diary_dir = Path(diary_dir).expanduser()
        self.diary_file = self.diary_dir / f"{agent_name}_diary.json"
        self.fact_store = fact_store

        # Ensure diary directory exists
        self.diary_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        content: str,
        topic: str = "general",
        tags: Optional[List[str]] = None,
        create_fact: bool = True
    ) -> str:
        """
        Write entry to agent's diary.

        Args:
            content: Entry content
            topic: Topic category
            tags: Optional tags
            create_fact: Whether to also create a TemporalFact

        Returns:
            Entry ID
        """
        # Generate entry ID
        timestamp = datetime.now(timezone.utc)
        entry_id = f"{self.agent}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Create fact if store is available and requested
        fact_id = None
        if create_fact and self.fact_store:
            fact = TemporalFact(
                content=content,
                project=f"agent-{self.agent}",
                topic=topic,
                type="discovery",
                tags=tags or [],
                valid_from=timestamp,
                agent_owner=self.agent,
                confidence=0.8
            )
            fact_id = self.fact_store.add(fact)

        # Create diary entry
        entry = DiaryEntry(
            entry_id=entry_id,
            agent=self.agent,
            content=content,
            topic=topic,
            tags=tags or [],
            timestamp=timestamp.isoformat(),
            fact_id=fact_id
        )

        # Append to diary file
        entries = self._load_entries()
        entries.append(entry)
        self._save_entries(entries)

        return entry_id

    def read(
        self,
        topic: Optional[str] = None,
        since_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[DiaryEntry]:
        """
        Read from agent's diary with filters.

        Args:
            topic: Filter by topic
            since_days: Only entries from last N days
            tags: Filter by tags (match any)
            limit: Maximum entries to return

        Returns:
            List of diary entries
        """
        entries = self._load_entries()

        # Apply filters
        filtered = entries

        if topic:
            filtered = [e for e in filtered if e.topic == topic]

        if since_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            filtered = [
                e for e in filtered
                if datetime.fromisoformat(e.timestamp) >= cutoff
            ]

        if tags:
            tag_set = set(tags)
            filtered = [
                e for e in filtered
                if any(t in tag_set for t in e.tags)
            ]

        # Sort by timestamp (newest first)
        filtered.sort(key=lambda e: e.timestamp, reverse=True)

        return filtered[:limit]

    def search(self, query: str, limit: int = 20) -> List[DiaryEntry]:
        """
        Search diary entries.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching entries
        """
        entries = self._load_entries()

        query_lower = query.lower()
        matches = []

        for entry in entries:
            # Simple text search
            if query_lower in entry.content.lower():
                matches.append(entry)
            elif any(query_lower in tag.lower() for tag in entry.tags):
                matches.append(entry)

        # Sort by timestamp (newest first)
        matches.sort(key=lambda e: e.timestamp, reverse=True)

        return matches[:limit]

    def get_topics(self) -> Set[str]:
        """
        Get all topics in this agent's diary.

        Returns:
            Set of topic names
        """
        entries = self._load_entries()
        return {e.topic for e in entries}

    def get_tags(self) -> Set[str]:
        """
        Get all tags in this agent's diary.

        Returns:
            Set of tags
        """
        entries = self._load_entries()
        tags = set()
        for entry in entries:
            tags.update(entry.tags)
        return tags

    def get_stats(self) -> dict:
        """
        Get statistics about this diary.

        Returns:
            Dictionary with stats
        """
        entries = self._load_entries()

        if not entries:
            return {
                "total_entries": 0,
                "topics": [],
                "tags": [],
                "oldest_entry": None,
                "newest_entry": None,
            }

        timestamps = [datetime.fromisoformat(e.timestamp) for e in entries]

        return {
            "total_entries": len(entries),
            "topics": sorted(self.get_topics()),
            "tags": sorted(self.get_tags()),
            "oldest_entry": min(timestamps).isoformat(),
            "newest_entry": max(timestamps).isoformat(),
        }

    def _load_entries(self) -> List[DiaryEntry]:
        """Load entries from diary file"""
        if not self.diary_file.exists():
            return []

        try:
            with open(self.diary_file, 'r') as f:
                data = json.load(f)
                return [DiaryEntry.from_dict(item) for item in data]
        except Exception as e:
            print(f"Warning: Could not load diary from {self.diary_file}: {e}")
            return []

    def _save_entries(self, entries: List[DiaryEntry]):
        """Save entries to diary file"""
        try:
            with open(self.diary_file, 'w') as f:
                data = [e.to_dict() for e in entries]
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error: Could not save diary to {self.diary_file}: {e}")

    @classmethod
    def read_as_observer(
        cls,
        agent_name: str,
        topic: Optional[str] = None,
        limit: int = 20,
        diary_dir: str = "~/.aidb/diaries"
    ) -> List[DiaryEntry]:
        """
        Read another agent's diary (observer mode - read-only).

        This allows orchestrators or reviewers to see what an agent
        has been working on, without modifying their diary.

        Args:
            agent_name: Agent whose diary to read
            topic: Filter by topic
            limit: Maximum entries

        Returns:
            List of diary entries
        """
        diary = cls(agent_name, diary_dir=diary_dir)
        return diary.read(topic=topic, limit=limit)

    @classmethod
    def list_all_diaries(cls, diary_dir: str = "~/.aidb/diaries") -> List[str]:
        """
        List all available agent diaries.

        Args:
            diary_dir: Directory containing diaries

        Returns:
            List of agent names with diaries
        """
        diary_path = Path(diary_dir).expanduser()
        if not diary_path.exists():
            return []

        agents = []
        for file in diary_path.glob("*_diary.json"):
            agent_name = file.stem.replace("_diary", "")
            if agent_name in cls.VALID_AGENTS:
                agents.append(agent_name)

        return sorted(agents)


def format_diary_entries(entries: List[DiaryEntry]) -> str:
    """
    Format diary entries as readable text.

    Args:
        entries: List of diary entries

    Returns:
        Formatted text
    """
    if not entries:
        return "No diary entries found."

    lines = []
    for i, entry in enumerate(entries, 1):
        timestamp = datetime.fromisoformat(entry.timestamp)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")

        tags_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""

        lines.append(
            f"{i}. [{timestamp_str}] [{entry.topic}]{tags_str}\n"
            f"   {entry.content}"
        )

    return "\n\n".join(lines)


if __name__ == "__main__":
    # Demo usage
    print("=== Agent Diary Demo ===\n")

    # Qwen writes to diary
    qwen_diary = AgentDiary("qwen")

    qwen_diary.write(
        "Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.",
        topic="auth",
        tags=["jwt", "security", "bcrypt"],
        create_fact=False  # No fact store in demo
    )

    qwen_diary.write(
        "Refactored temporal_facts.py to improve performance. Added caching.",
        topic="optimization",
        tags=["performance", "caching"],
        create_fact=False
    )

    qwen_diary.write(
        "Discovered bug in metadata filtering. Query returns stale facts.",
        topic="bugs",
        tags=["bug", "metadata", "filtering"],
        create_fact=False
    )

    # Read diary
    print("All entries:")
    all_entries = qwen_diary.read(limit=10)
    print(format_diary_entries(all_entries))

    print("\n" + "="*50 + "\n")

    # Filter by topic
    print("Auth-related entries:")
    auth_entries = qwen_diary.read(topic="auth")
    print(format_diary_entries(auth_entries))

    print("\n" + "="*50 + "\n")

    # Search
    print("Search for 'JWT':")
    search_results = qwen_diary.search("JWT")
    print(format_diary_entries(search_results))

    print("\n" + "="*50 + "\n")

    # Stats
    print("Diary Statistics:")
    stats = qwen_diary.get_stats()
    print(json.dumps(stats, indent=2))

    print("\n" + "="*50 + "\n")

    # Observer mode (e.g., codex reading qwen's diary)
    print("Codex reading qwen's diary (observer mode):")
    qwen_work = AgentDiary.read_as_observer("qwen", limit=5)
    print(format_diary_entries(qwen_work))
