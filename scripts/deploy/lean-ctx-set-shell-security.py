#!/usr/bin/env python3
"""Idempotently set the top-level `shell_security` key in a lean-ctx config.toml.

Used by the leanCtxShellSecurity activation script (Rule 13). Every other line
is preserved byte-for-byte; a missing file is created 0600.
"""
import os
import re
import stat
import sys
from pathlib import Path

VALID = ("enforce", "warn", "off")
_KEY = re.compile(rb"^\s*shell_security\s*=")
_TABLE = re.compile(rb"^\s*\[")


def _check_owner(st: os.stat_result, uid: int, what: str) -> None:
    if st.st_uid != uid:
        raise PermissionError(f"{what} is owned by uid {st.st_uid}, expected {uid}")


def set_shell_security(path: Path, value: str, uid: int | None = None) -> bool:
    """Return True when the file was changed.

    Refuses symlinked or foreign-owned parent/target (`uid` defaults to the
    effective uid; injectable for tests) and replaces atomically via a temp
    file in the same directory.
    """
    if value not in VALID:
        raise ValueError(f"invalid shell_security {value!r}")
    uid = os.geteuid() if uid is None else uid
    name = path.name
    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _check_owner(os.fstat(dfd), uid, f"directory {path.parent}")
        data = None
        mode = 0o600
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        except FileNotFoundError:
            pass
        else:
            with os.fdopen(fd, "rb") as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode):
                    raise PermissionError(f"{path} is not a regular file")
                _check_owner(st, uid, str(path))
                mode = stat.S_IMODE(st.st_mode)
                data = f.read()
        out = _render(data, value)
        if out == data:
            return False
        tmp = f".{name}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=dfd)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(out)
                f.flush()
                os.fchmod(f.fileno(), mode)
                os.fsync(f.fileno())
            os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except OSError:
                pass
            raise
        return True
    finally:
        os.close(dfd)


def _render(data: bytes | None, value: str) -> bytes:
    new = f'shell_security = "{value}"'.encode()
    if data is None:
        return new + b"\n"
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
            lines[i] = new + ending
            break
    else:
        if first_table > 0 and not lines[first_table - 1].endswith(b"\n"):
            lines[first_table - 1] += eol
        insert = [new + eol]
        if first_table < len(lines):
            insert.append(eol)
        lines[first_table:first_table] = insert
    return b"".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: lean-ctx-set-shell-security.py <config.toml> <enforce|warn|off>",
              file=sys.stderr)
        return 2
    try:
        changed = set_shell_security(Path(argv[1]), argv[2])
    except (OSError, ValueError) as e:
        print(f"lean-ctx shell_security: refused {argv[1]}: {e}", file=sys.stderr)
        return 1
    print(f"lean-ctx shell_security={argv[2]}: {'updated' if changed else 'unchanged'} {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
