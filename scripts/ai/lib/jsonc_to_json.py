#!/usr/bin/env python3
"""
Convert JSONC (JSON with Comments) to valid JSON.

Strips // line comments and /* */ block comments outside JSON strings,
removes trailing commas before } or ], then validates and pretty-prints.

Usage:
    python3 jsonc_to_json.py <input_file> [output_file]

If output_file is omitted, writes to stdout.

Exit codes:
    0 = success
    1 = input file not found or read error
    2 = invalid JSON after normalization
"""

import json
import sys
from pathlib import Path


def jsonc_to_json(text: str) -> str:
    """
    Convert JSONC text to valid JSON.

    Args:
        text: JSONC string

    Returns:
        Valid JSON string

    Raises:
        json.JSONDecodeError: If the result is invalid JSON
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        # Handle escape sequences in strings
        if in_string and escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if in_string and char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue

        # Toggle string state
        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        # Skip comments only when outside strings
        if not in_string:
            # Handle line comments //
            if i + 1 < len(text) and char == '/' and text[i + 1] == '/':
                # Skip until end of line
                i += 2
                while i < len(text) and text[i] not in '\r\n':
                    i += 1
                # Include the newline in output if present
                if i < len(text) and text[i] in '\r\n':
                    result.append(text[i])
                    i += 1
                    if text[i - 1] == '\r' and i < len(text) and text[i] == '\n':
                        result.append('\n')
                        i += 1
                continue

            # Handle block comments /* */
            if i + 1 < len(text) and char == '/' and text[i + 1] == '*':
                i += 2
                while i + 1 < len(text):
                    if text[i] == '*' and text[i + 1] == '/':
                        i += 2
                        break
                    i += 1
                continue

        result.append(char)
        i += 1

    # Now remove trailing commas before } or ]
    text_normalized = ''.join(result)

    # Use a state machine to remove trailing commas outside strings
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text_normalized):
        char = text_normalized[i]

        # Handle escape sequences in strings
        if in_string and escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if in_string and char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue

        # Toggle string state
        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        # Remove trailing commas
        if not in_string and char == ',':
            # Look ahead, skipping whitespace
            j = i + 1
            while j < len(text_normalized) and text_normalized[j] in ' \t\n\r':
                j += 1

            # If we find } or ] after whitespace, skip the comma
            if j < len(text_normalized) and text_normalized[j] in '}]':
                i += 1
                continue

        result.append(char)
        i += 1

    normalized_json = ''.join(result)

    # Validate and pretty-print
    data = json.loads(normalized_json)
    return json.dumps(data, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 jsonc_to_json.py <input_file> [output_file]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    # Read input
    try:
        text = input_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert
    try:
        json_text = jsonc_to_json(text)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON after normalization: {e}", file=sys.stderr)
        sys.exit(2)

    # Write output
    try:
        if output_path:
            output_path.write_text(json_text, encoding='utf-8')
        else:
            print(json_text)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
