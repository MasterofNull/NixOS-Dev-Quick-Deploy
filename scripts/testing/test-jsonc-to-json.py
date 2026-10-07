#!/usr/bin/env python3
"""
Tests for jsonc_to_json converter.

Validates:
- Trailing commas in objects and arrays
- Line comments (//) and block comments (/* */)
- URLs and other strings with // or /* preserved
- Already-valid JSON passes through unchanged (semantically)
- Invalid input raises appropriate errors
"""

import json
import sys
import tempfile
from pathlib import Path

# Add the lib directory to path so we can import the helper
sys.path.insert(0, str(Path(__file__).parent.parent / 'ai' / 'lib'))

from jsonc_to_json import jsonc_to_json


def test_trailing_commas_object():
    """Test removal of trailing commas in objects."""
    jsonc = '{"key": "value",}'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"key": "value"}
    print("✓ Trailing commas in objects")


def test_trailing_commas_array():
    """Test removal of trailing commas in arrays."""
    jsonc = '["a", "b",]'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == ["a", "b"]
    print("✓ Trailing commas in arrays")


def test_trailing_commas_nested():
    """Test removal of trailing commas in nested structures."""
    jsonc = '''{
    "items": [
        "a",
        "b",
    ],
    "nested": {
        "key": "value",
    },
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"items": ["a", "b"], "nested": {"key": "value"}}
    print("✓ Trailing commas in nested structures")


def test_line_comments():
    """Test removal of line comments."""
    jsonc = '''{
    "key": "value"  // This is a comment
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"key": "value"}
    print("✓ Line comments (//) removed")


def test_block_comments():
    """Test removal of block comments."""
    jsonc = '''{
    /* This is a block comment */
    "key": "value"
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"key": "value"}
    print("✓ Block comments (/* */) removed")


def test_urls_preserved():
    """Test that URLs with // are preserved inside strings."""
    jsonc = '{"url": "https://example.com/path"}'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"url": "https://example.com/path"}
    print("✓ URLs with // preserved in strings")


def test_comment_like_strings_preserved():
    """Test that comment-like patterns inside strings are preserved."""
    jsonc = '{"comment": "/* not a comment */", "slash": "a // not a comment"}'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"comment": "/* not a comment */", "slash": "a // not a comment"}
    print("✓ Comment-like patterns in strings preserved")


def test_escaped_quotes_in_strings():
    """Test that escaped quotes are handled correctly."""
    jsonc = r'{"escaped": "value with \" quote"}'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"escaped": 'value with " quote'}
    print("✓ Escaped quotes in strings handled")


def test_mixed_comments_and_commas():
    """Test combination of comments and trailing commas."""
    jsonc = '''{
    "key1": "value1",  // comment
    "key2": "value2",  /* block */ /* another */
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"key1": "value1", "key2": "value2"}
    print("✓ Mixed comments and trailing commas")


def test_valid_json_unchanged():
    """Test that valid JSON stays valid."""
    valid_json = '{"key": "value", "array": [1, 2, 3]}'
    result_text = jsonc_to_json(valid_json)
    result = json.loads(result_text)
    expected = json.loads(valid_json)
    assert result == expected
    print("✓ Valid JSON passes through unchanged (semantically)")


def test_vsccodium_settings_example():
    """Test with realistic VSCodium settings structure."""
    jsonc = '''{
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
  },
  "workbench.colorTheme": "Activate SCARLET protocol (beta)",
  "explorer.autoReveal": false,  // Don't auto-reveal in explorer
  /* Settings for specific tools */
  "files.exclude": {
    "**/__pycache__": true,
  },
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result["workbench.colorTheme"] == "Activate SCARLET protocol (beta)"
    assert result["explorer.autoReveal"] is False
    assert result["files.exclude"]["**/__pycache__"] is True
    print("✓ VSCodium settings example with comments and commas")


def test_empty_structures():
    """Test empty objects and arrays."""
    jsonc = '{"empty_obj": {}, "empty_array": []}'
    result = json.loads(jsonc_to_json(jsonc))
    assert result == {"empty_obj": {}, "empty_array": []}
    print("✓ Empty objects and arrays")


def test_multiline_strings():
    """Test strings with newlines."""
    jsonc = r'{"multiline": "line1\nline2"}'
    result = json.loads(jsonc_to_json(jsonc))
    assert "multiline" in result
    print("✓ Multiline strings handled")


def test_invalid_json_raises_error():
    """Test that invalid JSON raises an error."""
    invalid_jsonc = '{"unclosed": "string'
    try:
        jsonc_to_json(invalid_jsonc)
        assert False, "Should have raised json.JSONDecodeError"
    except json.JSONDecodeError:
        print("✓ Invalid JSON raises json.JSONDecodeError")


def test_complex_vscodium_real_example():
    """Test with complex real VSCodium settings including extensions config."""
    jsonc = '''{
  "workbench.colorTheme": "Activate SCARLET protocol (beta)",
  "workbench.preferredDarkColorTheme": "Activate SCARLET protocol (beta)",
  "window.autoDetectColorScheme": false,
  "claude-code.environmentVariables": [
    {
      "name": "CLAUDE_API_KEY",
      "value": "sk-...",  // actual key redacted
    },
  ],
  "continue.enableTabAutocomplete": false,  /* turned off for APU */
  "git.autofetch": false,
  "extensions": {
    "recommendations": [
      "ms-python.python",  // Python support
      "rust-lang.rust-analyzer",  // Rust
    ],
  },
}'''
    result = json.loads(jsonc_to_json(jsonc))
    assert result["workbench.colorTheme"] == "Activate SCARLET protocol (beta)"
    assert result["continue.enableTabAutocomplete"] is False
    assert len(result["claude-code.environmentVariables"]) == 1
    assert "extensions" in result
    print("✓ Complex VSCodium real-world example")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_trailing_commas_object,
        test_trailing_commas_array,
        test_trailing_commas_nested,
        test_line_comments,
        test_block_comments,
        test_urls_preserved,
        test_comment_like_strings_preserved,
        test_escaped_quotes_in_strings,
        test_mixed_comments_and_commas,
        test_valid_json_unchanged,
        test_vsccodium_settings_example,
        test_empty_structures,
        test_multiline_strings,
        test_invalid_json_raises_error,
        test_complex_vscodium_real_example,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}", file=sys.stderr)
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
