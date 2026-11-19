#!/usr/bin/env python3
"""Tests for scripts/deploy/lean-ctx-set-shell-security.py."""
import importlib.util
import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "setter", ROOT / "scripts/deploy/lean-ctx-set-shell-security.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
setter = mod.set_shell_security

TABLED = b'# my config\ntheme = "x"\n\n[memory]\nshell_security = "enforce"\nlimit = 3\n'


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.toml"
        # absent -> created 0600
        assert setter(p, "warn") is True
        assert p.read_bytes() == b'shell_security = "warn"\n'
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        # insert before first table, rest byte-identical
        p.write_bytes(TABLED)
        assert setter(p, "warn") is True
        out = p.read_bytes()
        assert out == (b'# my config\ntheme = "x"\n\nshell_security = "warn"\n\n[memory]\n'
                       b'shell_security = "enforce"\nlimit = 3\n'), out
        # idempotent
        assert setter(p, "warn") is False and p.read_bytes() == out
        # replace existing top-level value, other lines untouched
        assert setter(p, "off") is True
        assert p.read_bytes() == out.replace(b'= "warn"', b'= "off"', 1)
        # no tables: append; no trailing newline handled
        p.write_bytes(b'a = 1')
        assert setter(p, "warn") is True
        assert p.read_bytes() == b'a = 1\nshell_security = "warn"\n'
        # empty file
        p.write_bytes(b"")
        assert setter(p, "warn") is True and p.read_bytes() == b'shell_security = "warn"\n'
        # mode preserved on edit
        p.chmod(0o600)
        setter(p, "off")
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        # invalid value rejected
        try:
            setter(p, "bogus")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid value accepted")
    with tempfile.TemporaryDirectory() as d:
        dd = Path(d)
        victim = dd / "victim"
        victim.write_bytes(b"root secret\n")
        # symlinked target refused, victim untouched
        sub = dd / "h"
        sub.mkdir()
        (sub / "config.toml").symlink_to(victim)
        try:
            setter(sub / "config.toml", "warn")
        except OSError:
            pass
        else:
            raise AssertionError("symlinked target accepted")
        assert victim.read_bytes() == b"root secret\n"
        # symlinked parent dir refused
        (dd / "link").symlink_to(sub, target_is_directory=True)
        try:
            setter(dd / "link" / "x.toml", "warn")
        except OSError:
            pass
        else:
            raise AssertionError("symlinked parent accepted")
        # foreign-owned target / directory refused (injected uid)
        f = sub / "own.toml"
        f.write_bytes(b"a = 1\n")
        for bad in (os.geteuid() + 1,):
            try:
                setter(f, "warn", uid=bad)
            except PermissionError:
                pass
            else:
                raise AssertionError("foreign uid accepted")
        assert f.read_bytes() == b"a = 1\n"
        # atomic replace: new inode, 0600 preserved, no temp left
        f.chmod(0o600)
        ino = f.stat().st_ino
        assert setter(f, "warn") is True
        assert f.stat().st_ino != ino and stat.S_IMODE(f.stat().st_mode) == 0o600
        assert sorted(x.name for x in sub.iterdir()) == ["config.toml", "own.toml"]
    print("lean-ctx shell_security editor: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
