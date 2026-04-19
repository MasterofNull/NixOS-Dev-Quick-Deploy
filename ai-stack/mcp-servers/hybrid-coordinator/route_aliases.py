"""
Route alias resolution system for Layer 1 Front-Door Routing.

This module provides a RouteAliasResolver that maps OpenClaude-style route names
(e.g., "Explore", "Plan", "Implementation") to existing harness profiles
(e.g., "default", "remote-coding", "remote-reasoning").

Purpose:
    - Provide stable front-door routing for all human-to-LLM requests
    - Map user-facing route names to internal profile names
    - Maintain backward compatibility with existing routes
    - Enable deterministic and auditable route selection

Performance Target: < 10ms overhead per alias resolution

Phase: Phase 0 Slice 0.1
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class RouteAliasResolver:
    """
    Resolves route aliases to harness profiles.

    Loads alias mappings from config/route-aliases.json and provides
    fast, cached resolution with validation and error handling.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the route alias resolver.

        Args:
            config_path: Path to route-aliases.json. If None, uses default location.
        """
        self._config_path = config_path
        self._aliases: Dict[str, str] = {}
        self._allowed_profiles: Set[str] = set()
        self._config_mtime: float = 0.0
        self._load_attempts: int = 0
        self._last_error: Optional[str] = None

        # Load aliases on initialization
        self.load_aliases()

    def _get_default_config_path(self) -> Path:
        """Get the default path to route-aliases.json."""
        # Determine repo root (hybrid-coordinator is in ai-stack/mcp-servers/hybrid-coordinator)
        current_file = Path(__file__).resolve()
        repo_root = current_file.parent.parent.parent.parent
        return repo_root / "config" / "route-aliases.json"

    def load_aliases(self) -> bool:
        """
        Load route aliases from configuration file.

        Returns:
            bool: True if loading succeeded, False otherwise.
        """
        self._load_attempts += 1

        try:
            config_path = Path(self._config_path) if self._config_path else self._get_default_config_path()

            if not config_path.exists():
                self._last_error = f"Config file not found: {config_path}"
                # Provide safe defaults if config doesn't exist
                self._set_default_aliases()
                return False

            # Check if file has been modified
            current_mtime = config_path.stat().st_mtime
            if current_mtime == self._config_mtime and self._aliases:
                # Already loaded and up to date
                return True

            # Load configuration
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Validate structure
            if not isinstance(config, dict):
                self._last_error = "Config must be a JSON object"
                self._set_default_aliases()
                return False

            # Extract aliases
            aliases = config.get("aliases", {})
            if not isinstance(aliases, dict):
                self._last_error = "Config 'aliases' must be an object"
                self._set_default_aliases()
                return False

            # Extract allowed profiles for validation
            validation = config.get("validation", {})
            allowed_profiles = set(validation.get("allowed_profiles", []))

            # Validate all alias targets are in allowed profiles
            invalid_targets = []
            for alias, target in aliases.items():
                if allowed_profiles and target not in allowed_profiles:
                    invalid_targets.append((alias, target))

            if invalid_targets:
                self._last_error = f"Invalid alias targets: {invalid_targets[:3]}"
                self._set_default_aliases()
                return False

            # Update internal state
            self._aliases = {k.lower(): v for k, v in aliases.items()}
            self._allowed_profiles = allowed_profiles
            self._config_mtime = current_mtime
            self._last_error = None

            return True

        except json.JSONDecodeError as e:
            self._last_error = f"JSON parse error: {e}"
            self._set_default_aliases()
            return False
        except Exception as e:
            self._last_error = f"Error loading aliases: {e}"
            self._set_default_aliases()
            return False

    def _set_default_aliases(self) -> None:
        """Set safe default aliases when config cannot be loaded."""
        self._aliases = {
            "default": "default",
            "explore": "default",
            "plan": "default",
            "implementation": "remote-coding",
            "reasoning": "remote-reasoning",
            "toolcalling": "local-tool-calling",
            "continuation": "default",
        }
        self._allowed_profiles = {
            "default",
            "local-tool-calling",
            "embedded-assist",
            "remote-gemini",
            "remote-free",
            "remote-coding",
            "remote-reasoning",
            "remote-tool-calling",
        }

    def resolve_alias(self, alias: str) -> str:
        """
        Resolve a route alias to a harness profile.

        Args:
            alias: The route alias to resolve (case-insensitive)

        Returns:
            str: The resolved profile name. Returns "default" if alias is unknown.

        Performance: < 10ms target

        Examples:
            >>> resolver = RouteAliasResolver()
            >>> resolver.resolve_alias("Explore")
            'default'
            >>> resolver.resolve_alias("Implementation")
            'remote-coding'
            >>> resolver.resolve_alias("unknown")
            'default'
        """
        if not alias:
            return "default"

        # Normalize alias (lowercase)
        normalized = alias.strip().lower()

        # Direct lookup
        profile = self._aliases.get(normalized)

        if profile:
            return profile

        # Fallback to default
        return "default"

    def get_all_aliases(self) -> Dict[str, str]:
        """
        Get all configured route aliases.

        Returns:
            Dict[str, str]: Mapping of aliases to profiles.
        """
        return dict(self._aliases)

    def is_valid_alias(self, alias: str) -> bool:
        """
        Check if an alias is defined in the configuration.

        Args:
            alias: The alias to check (case-insensitive)

        Returns:
            bool: True if alias is defined, False otherwise.
        """
        if not alias:
            return False
        return alias.strip().lower() in self._aliases

    def is_valid_profile(self, profile: str) -> bool:
        """
        Check if a profile is in the allowed profiles list.

        Args:
            profile: The profile name to validate

        Returns:
            bool: True if profile is allowed, False otherwise.
        """
        if not profile or not self._allowed_profiles:
            return True  # No validation if allowed_profiles is empty
        return profile in self._allowed_profiles

    def get_stats(self) -> Dict[str, Any]:
        """
        Get resolver statistics and status.

        Returns:
            Dict with stats including load attempts, error status, and alias count.
        """
        return {
            "load_attempts": self._load_attempts,
            "last_error": self._last_error,
            "alias_count": len(self._aliases),
            "allowed_profile_count": len(self._allowed_profiles),
            "config_mtime": self._config_mtime,
            "config_path": str(self._config_path) if self._config_path else str(self._get_default_config_path()),
        }

    def reload(self) -> bool:
        """
        Force reload of aliases from configuration file.

        Returns:
            bool: True if reload succeeded, False otherwise.
        """
        self._config_mtime = 0.0  # Force reload
        return self.load_aliases()


# Global singleton instance
_resolver: Optional[RouteAliasResolver] = None


def get_resolver() -> RouteAliasResolver:
    """
    Get the global RouteAliasResolver instance.

    Returns:
        RouteAliasResolver: The singleton resolver instance.
    """
    global _resolver
    if _resolver is None:
        _resolver = RouteAliasResolver()
    return _resolver


def resolve_route_alias(alias: str) -> str:
    """
    Convenience function to resolve a route alias.

    Args:
        alias: The route alias to resolve

    Returns:
        str: The resolved profile name.
    """
    return get_resolver().resolve_alias(alias)
