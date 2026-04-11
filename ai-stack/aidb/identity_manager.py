#!/usr/bin/env python3
"""
Identity Management System

Phase 1.5 Slice 1.7: Agent identity and profile management for L0 layer.

Manages agent identities, profiles, and core context that should always
be loaded into memory (L0 layer - 50 tokens).

Usage:
    from aidb.identity_manager import IdentityManager

    identity_mgr = IdentityManager()

    # Get current identity
    identity = identity_mgr.get_identity()

    # Update identity
    identity_mgr.set_identity(
        name="Claude",
        role="AI Coordinator",
        system="NixOS on hyperd's desktop",
        focus="local-first AI, cost optimization"
    )
"""

from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, asdict
import json
from datetime import datetime, timezone


@dataclass
class AgentIdentity:
    """
    Agent identity configuration.

    Represents the core identity of an AI agent in the harness.
    Should be compact enough to fit in 50 tokens.
    """
    name: str
    role: str
    system: str
    focus: str
    created_at: str
    updated_at: str

    def to_text(self, max_chars: int = 200) -> str:
        """
        Convert identity to compact text format.

        Args:
            max_chars: Maximum characters (approximately 50 tokens)

        Returns:
            Formatted identity text
        """
        lines = [
            f"I am {self.name}, {self.role} for NixOS-Dev-Quick-Deploy.",
            f"System: {self.system}.",
            f"Focus: {self.focus}."
        ]
        text = " ".join(lines)

        if len(text) > max_chars:
            text = text[:max_chars-3] + "..."

        return text

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentIdentity':
        """Create from dictionary"""
        return cls(**data)


class IdentityManager:
    """
    Manages agent identities and profiles.

    Handles loading, saving, and formatting of agent identities
    for use in the L0 memory layer.
    """

    DEFAULT_IDENTITY = {
        "name": "AI Agent",
        "role": "orchestrator and coordinator",
        "system": "NixOS on local machine",
        "focus": "local-first AI, declarative infrastructure, cost optimization",
    }

    def __init__(
        self,
        identity_file: str = "~/.aidb/identity.json",
        identity_text_file: str = "~/.aidb/identity.txt"
    ):
        """
        Initialize identity manager.

        Args:
            identity_file: Path to identity JSON file
            identity_text_file: Path to identity text file (for quick loading)
        """
        self.identity_file = Path(identity_file).expanduser()
        self.identity_text_file = Path(identity_text_file).expanduser()
        self._identity: Optional[AgentIdentity] = None

    def get_identity(self) -> AgentIdentity:
        """
        Get current agent identity.

        Returns:
            AgentIdentity object
        """
        if self._identity is None:
            self._load()

        return self._identity

    def get_identity_text(self, max_chars: int = 200) -> str:
        """
        Get identity as formatted text (for L0 layer).

        Args:
            max_chars: Maximum characters (~50 tokens)

        Returns:
            Formatted identity text
        """
        # Try to load from text file first (faster)
        if self.identity_text_file.exists():
            with open(self.identity_text_file, 'r') as f:
                text = f.read().strip()
                if len(text) > max_chars:
                    text = text[:max_chars-3] + "..."
                return text

        # Fall back to generating from identity object
        identity = self.get_identity()
        return identity.to_text(max_chars)

    def set_identity(
        self,
        name: str,
        role: str,
        system: str,
        focus: str
    ):
        """
        Set agent identity.

        Args:
            name: Agent name
            role: Agent role
            system: System description
            focus: Focus areas
        """
        now = datetime.now(timezone.utc).isoformat()

        # Create new identity
        self._identity = AgentIdentity(
            name=name,
            role=role,
            system=system,
            focus=focus,
            created_at=self._identity.created_at if self._identity else now,
            updated_at=now
        )

        # Save both JSON and text versions
        self._save()

    def update_identity(self, **kwargs):
        """
        Update specific fields of identity.

        Args:
            **kwargs: Fields to update (name, role, system, focus)
        """
        identity = self.get_identity()

        # Update fields
        for key, value in kwargs.items():
            if hasattr(identity, key) and key not in ['created_at', 'updated_at']:
                setattr(identity, key, value)

        # Update timestamp
        identity.updated_at = datetime.now(timezone.utc).isoformat()

        self._identity = identity
        self._save()

    def _load(self):
        """Load identity from file"""
        if self.identity_file.exists():
            try:
                with open(self.identity_file, 'r') as f:
                    data = json.load(f)
                    self._identity = AgentIdentity.from_dict(data)
                return
            except Exception as e:
                print(f"Warning: Could not load identity from {self.identity_file}: {e}")

        # Create default identity
        now = datetime.now(timezone.utc).isoformat()
        self._identity = AgentIdentity(
            **self.DEFAULT_IDENTITY,
            created_at=now,
            updated_at=now
        )
        self._save()

    def _save(self):
        """Save identity to files"""
        if self._identity is None:
            return

        # Ensure directory exists
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON
        with open(self.identity_file, 'w') as f:
            json.dump(self._identity.to_dict(), f, indent=2)

        # Save text version for fast loading
        with open(self.identity_text_file, 'w') as f:
            f.write(self._identity.to_text())

    def reset_to_default(self):
        """Reset identity to default values"""
        now = datetime.now(timezone.utc).isoformat()
        self._identity = AgentIdentity(
            **self.DEFAULT_IDENTITY,
            created_at=now,
            updated_at=now
        )
        self._save()


if __name__ == "__main__":
    # Demo usage
    print("=== Identity Manager Demo ===\n")

    manager = IdentityManager()

    # Set identity
    manager.set_identity(
        name="Claude",
        role="AI Coordinator",
        system="NixOS on hyperd's desktop with 32GB RAM, RTX 3090",
        focus="local-first AI, declarative infrastructure, cost optimization"
    )

    # Get identity text
    identity_text = manager.get_identity_text()
    print("Identity Text (L0 layer):")
    print(identity_text)
    print(f"\nLength: {len(identity_text)} chars (~{len(identity_text)//4} tokens)")

    # Get full identity
    print("\nFull Identity:")
    identity = manager.get_identity()
    print(json.dumps(identity.to_dict(), indent=2))
