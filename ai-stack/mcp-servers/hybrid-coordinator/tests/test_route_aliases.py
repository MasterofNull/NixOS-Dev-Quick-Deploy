"""
Unit tests for route alias resolution system.

Tests cover:
- Alias resolution (standard aliases)
- Case-insensitive resolution
- Unknown alias handling (fallback to default)
- Configuration loading and validation
- Error handling (missing config, invalid JSON)
- Performance validation (< 10ms resolution)
- Backward compatibility

Phase: Phase 0 Slice 0.1
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from typing import Dict

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from route_aliases import RouteAliasResolver, get_resolver, resolve_route_alias


class TestRouteAliasResolver:
    """Test suite for RouteAliasResolver."""

    def test_default_config_loading(self):
        """Test loading from default config location."""
        resolver = RouteAliasResolver()
        assert resolver is not None
        stats = resolver.get_stats()
        assert stats["alias_count"] > 0
        assert stats["load_attempts"] >= 1

    def test_standard_alias_resolution(self):
        """Test resolution of standard aliases."""
        resolver = RouteAliasResolver()

        # Test all standard aliases
        assert resolver.resolve_alias("default") == "default"
        assert resolver.resolve_alias("Explore") == "default"
        assert resolver.resolve_alias("Plan") == "default"
        assert resolver.resolve_alias("Implementation") == "remote-coding"
        assert resolver.resolve_alias("Reasoning") == "remote-reasoning"
        assert resolver.resolve_alias("ToolCalling") == "local-tool-calling"
        assert resolver.resolve_alias("Continuation") == "default"

    def test_case_insensitive_resolution(self):
        """Test that alias resolution is case-insensitive."""
        resolver = RouteAliasResolver()

        # Test various case combinations
        assert resolver.resolve_alias("explore") == "default"
        assert resolver.resolve_alias("EXPLORE") == "default"
        assert resolver.resolve_alias("ExPlOrE") == "default"

        assert resolver.resolve_alias("implementation") == "remote-coding"
        assert resolver.resolve_alias("IMPLEMENTATION") == "remote-coding"

    def test_unknown_alias_fallback(self):
        """Test that unknown aliases fall back to 'default'."""
        resolver = RouteAliasResolver()

        assert resolver.resolve_alias("unknown") == "default"
        assert resolver.resolve_alias("nonexistent") == "default"
        assert resolver.resolve_alias("") == "default"
        assert resolver.resolve_alias("   ") == "default"

    def test_is_valid_alias(self):
        """Test alias validation."""
        resolver = RouteAliasResolver()

        assert resolver.is_valid_alias("Explore") is True
        assert resolver.is_valid_alias("explore") is True
        assert resolver.is_valid_alias("Implementation") is True

        assert resolver.is_valid_alias("unknown") is False
        assert resolver.is_valid_alias("") is False
        assert resolver.is_valid_alias("   ") is False

    def test_is_valid_profile(self):
        """Test profile validation."""
        resolver = RouteAliasResolver()

        # Valid profiles
        assert resolver.is_valid_profile("default") is True
        assert resolver.is_valid_profile("remote-coding") is True
        assert resolver.is_valid_profile("remote-reasoning") is True
        assert resolver.is_valid_profile("local-tool-calling") is True

    def test_get_all_aliases(self):
        """Test retrieving all aliases."""
        resolver = RouteAliasResolver()
        aliases = resolver.get_all_aliases()

        assert isinstance(aliases, dict)
        assert len(aliases) > 0

        # Check expected aliases are present
        assert "default" in aliases
        assert "explore" in aliases  # normalized to lowercase
        assert "implementation" in aliases

    def test_custom_config_loading(self):
        """Test loading from a custom config file."""
        # Create temporary config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "version": "1.0.0",
                "aliases": {
                    "test_alias": "test-profile",
                    "another": "default"
                },
                "validation": {
                    "allowed_profiles": ["default", "test-profile"]
                }
            }
            json.dump(config, f)
            config_path = f.name

        try:
            resolver = RouteAliasResolver(config_path=config_path)

            assert resolver.resolve_alias("test_alias") == "test-profile"
            assert resolver.resolve_alias("another") == "default"
            assert resolver.resolve_alias("unknown") == "default"

            aliases = resolver.get_all_aliases()
            assert "test_alias" in aliases
            assert "another" in aliases

        finally:
            Path(config_path).unlink()

    def test_missing_config_fallback(self):
        """Test behavior when config file is missing."""
        resolver = RouteAliasResolver(config_path="/nonexistent/path/config.json")

        # Should fall back to defaults
        assert resolver.resolve_alias("Explore") == "default"
        assert resolver.resolve_alias("Implementation") == "remote-coding"

        stats = resolver.get_stats()
        assert stats["last_error"] is not None
        assert "not found" in stats["last_error"]

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            resolver = RouteAliasResolver(config_path=config_path)

            # Should fall back to defaults
            assert resolver.resolve_alias("Explore") == "default"

            stats = resolver.get_stats()
            assert stats["last_error"] is not None
            assert "JSON" in stats["last_error"]

        finally:
            Path(config_path).unlink()

    def test_invalid_alias_target(self):
        """Test handling of invalid alias targets."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "version": "1.0.0",
                "aliases": {
                    "test": "invalid-profile"
                },
                "validation": {
                    "allowed_profiles": ["default", "remote-coding"]
                }
            }
            json.dump(config, f)
            config_path = f.name

        try:
            resolver = RouteAliasResolver(config_path=config_path)

            # Should fall back to defaults due to validation failure
            stats = resolver.get_stats()
            assert stats["last_error"] is not None
            assert "Invalid alias targets" in stats["last_error"]

        finally:
            Path(config_path).unlink()

    def test_performance_resolution(self):
        """Test that alias resolution meets performance target (< 10ms)."""
        resolver = RouteAliasResolver()

        # Warm up
        resolver.resolve_alias("Explore")

        # Test resolution performance
        iterations = 1000
        start_time = time.time()

        for _ in range(iterations):
            resolver.resolve_alias("Explore")
            resolver.resolve_alias("Implementation")
            resolver.resolve_alias("Reasoning")

        end_time = time.time()
        avg_time_ms = ((end_time - start_time) / (iterations * 3)) * 1000

        # Should be well under 10ms per resolution (typically < 0.01ms)
        assert avg_time_ms < 10, f"Average resolution time {avg_time_ms:.3f}ms exceeds 10ms target"

    def test_reload_functionality(self):
        """Test config reload functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "version": "1.0.0",
                "aliases": {
                    "test": "default"
                },
                "validation": {
                    "allowed_profiles": ["default"]
                }
            }
            json.dump(config, f)
            config_path = f.name

        try:
            resolver = RouteAliasResolver(config_path=config_path)
            assert resolver.resolve_alias("test") == "default"
            assert resolver.is_valid_alias("test2") is False

            # Update config
            with open(config_path, 'w') as f:
                config["aliases"]["test2"] = "default"
                json.dump(config, f)

            # Reload
            assert resolver.reload() is True
            assert resolver.is_valid_alias("test2") is True
            assert resolver.resolve_alias("test2") == "default"

        finally:
            Path(config_path).unlink()

    def test_get_stats(self):
        """Test stats reporting."""
        resolver = RouteAliasResolver()
        stats = resolver.get_stats()

        assert "load_attempts" in stats
        assert "last_error" in stats
        assert "alias_count" in stats
        assert "allowed_profile_count" in stats
        assert "config_mtime" in stats
        assert "config_path" in stats

        assert isinstance(stats["load_attempts"], int)
        assert stats["load_attempts"] > 0
        assert stats["alias_count"] > 0


class TestGlobalResolver:
    """Test suite for global resolver functions."""

    def test_get_resolver_singleton(self):
        """Test that get_resolver returns a singleton."""
        resolver1 = get_resolver()
        resolver2 = get_resolver()

        assert resolver1 is resolver2

    def test_resolve_route_alias_function(self):
        """Test convenience function for alias resolution."""
        assert resolve_route_alias("Explore") == "default"
        assert resolve_route_alias("Implementation") == "remote-coding"
        assert resolve_route_alias("unknown") == "default"


class TestBackwardCompatibility:
    """Test suite for backward compatibility."""

    def test_existing_profiles_work(self):
        """Test that existing profile names still work."""
        resolver = RouteAliasResolver()

        # These should resolve to themselves or appropriate defaults
        assert resolver.resolve_alias("default") == "default"

    def test_empty_and_none_handling(self):
        """Test handling of empty and None inputs."""
        resolver = RouteAliasResolver()

        assert resolver.resolve_alias("") == "default"
        assert resolver.resolve_alias("   ") == "default"

    def test_whitespace_handling(self):
        """Test handling of whitespace in aliases."""
        resolver = RouteAliasResolver()

        assert resolver.resolve_alias("  Explore  ") == "default"
        assert resolver.resolve_alias("\tImplementation\n") == "remote-coding"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
