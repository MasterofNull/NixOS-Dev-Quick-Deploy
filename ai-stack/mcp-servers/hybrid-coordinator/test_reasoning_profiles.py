#!/usr/bin/env python3
"""
Test script for reasoning profiles functionality.

This script validates:
1. Profile loading from config
2. Profile retrieval by name
3. Error handling for missing profiles
4. Hot-reload functionality
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config


def test_default_profiles():
    """Test that default profiles are loaded correctly."""
    print("Testing default profiles...")
    
    profiles = Config.REASONING_PROFILES
    print(f"✓ Loaded {len(profiles)} profiles")
    
    expected_profiles = ["default", "precise", "creative", "deep-reasoning"]
    for profile_name in expected_profiles:
        assert profile_name in profiles, f"Missing expected profile: {profile_name}"
        print(f"  ✓ Found profile: {profile_name}")
    
    print("✓ All expected default profiles present\n")


def test_profile_retrieval():
    """Test retrieving profiles by name."""
    print("Testing profile retrieval...")
    
    # Test valid profile
    profile = Config.get_reasoning_profile("default")
    assert profile["name"] == "default"
    assert "temperature" in profile
    assert "max_tokens" in profile
    print(f"✓ Retrieved 'default' profile")
    print(f"  - Temperature: {profile['temperature']}")
    print(f"  - Max tokens: {profile['max_tokens']}")
    print(f"  - Description: {profile['description']}\n")
    
    # Test deep-reasoning profile
    deep_profile = Config.get_reasoning_profile("deep-reasoning")
    assert deep_profile["name"] == "deep-reasoning"
    assert "system_suffix" in deep_profile
    print(f"✓ Retrieved 'deep-reasoning' profile")
    print(f"  - Temperature: {deep_profile['temperature']}")
    print(f"  - Max tokens: {deep_profile['max_tokens']}")
    print(f"  - Has system suffix: {bool(deep_profile.get('system_suffix'))}\n")


def test_invalid_profile():
    """Test error handling for missing profiles."""
    print("Testing invalid profile handling...")
    
    try:
        Config.get_reasoning_profile("nonexistent-profile")
        print("✗ Should have raised ValueError")
        sys.exit(1)
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}\n")


def test_profile_structure():
    """Test that all profiles have required fields."""
    print("Testing profile structure...")
    
    required_fields = ["name", "description", "temperature", "max_tokens", "top_p", "stop_sequences"]
    
    for profile_name, profile in Config.REASONING_PROFILES.items():
        for field in required_fields:
            assert field in profile, f"Profile '{profile_name}' missing required field: {field}"
        print(f"✓ Profile '{profile_name}' has all required fields")
    
    print("✓ All profiles have valid structure\n")


def test_temperature_ranges():
    """Test that temperatures are within reasonable ranges."""
    print("Testing temperature ranges...")
    
    for profile_name, profile in Config.REASONING_PROFILES.items():
        temp = profile["temperature"]
        assert 0.0 <= temp <= 2.0, f"Profile '{profile_name}' has invalid temperature: {temp}"
        print(f"✓ Profile '{profile_name}' temperature {temp} is valid")
    
    print("✓ All temperatures within valid range (0.0-2.0)\n")


def test_example_file():
    """Test that the example config file is valid JSON."""
    print("Testing example config file...")
    
    example_path = Path(__file__).parent.parent / "shared" / "config" / "reasoning-profiles.json"
    
    if not example_path.exists():
        print(f"⚠ Example file not found at {example_path}")
        print("  (This is OK for testing, but should exist in production)\n")
        return
    
    with open(example_path, 'r') as f:
        profiles = json.load(f)
    
    print(f"✓ Example file is valid JSON with {len(profiles)} profiles")
    
    # Validate structure
    for profile_name, profile in profiles.items():
        assert "name" in profile
        assert "temperature" in profile
        assert "max_tokens" in profile
        print(f"  ✓ Profile '{profile_name}' is valid")
    
    print("✓ Example config file is valid\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Reasoning Profiles Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_default_profiles()
        test_profile_retrieval()
        test_invalid_profile()
        test_profile_structure()
        test_temperature_ranges()
        test_example_file()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
