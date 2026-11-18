#!/usr/bin/env python3
"""Idempotently set the top-level `shell_security` key in a lean-ctx config.toml.

Used by the leanCtxShellSecurity activation script (Rule 13). Every other line
is preserved byte-for-byte; a missing file is created 0600.
"""
import os
import re
import sys
from pathlib import Path

VALID = ("enforce", "warn", "off")
_KEY = re.compile(rb"^\s*shell_security\s*=")
_TABLE = re.compile(rb"^\s*\[")


def set_shell_security(path: Path, value: str) -> bool:
    """Return True when the file was changed."""
    if value not in VALID:
        raise ValueError(f"invalid shell_security {value!r}")
    new = f'shell_security = "{value}"'.encode()
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(new + b"\n")
        return True
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    eol = b"\r\n" if lines and lines[0].endswith(b"\r\n") else b"\n"
    first_table = next(
        (i for i, ln in enumerate(lines) if _TABLE.match(ln)), len(lines)
    )
    # Only top-level lines (before the first table) count; a same-named key
    # inside a [table] is a different key.
    for i in range(first_table):
        if _KEY.match(lines[i]):
            ending = lines[i][len(lines[i].rstrip(b"\r\n")):]
            if lines[i] == new + ending:
                return False
            lines[i] = new + ending
            break
    else:
        if first_table > 0 and not lines[first_table - 1].endswith(b"\n"):
            lines[first_table - 1] += eol
        insert = [new + eol]
        if first_table < len(lines):
            insert.append(eol)
        lines[first_table:first_table] = insert
    path.write_bytes(b"".join(lines))
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: lean-ctx-set-shell-security.py <config.toml> <enforce|warn|off>",
              file=sys.stderr)
        return 2
    changed = set_shell_security(Path(argv[1]), argv[2])
    print(f"lean-ctx shell_security={argv[2]}: {'updated' if changed else 'unchanged'} {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
