#!/usr/bin/env python3
"""Tests for scripts/deploy/lean-ctx-set-shell-security.py."""
import importlib.util
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
    print("lean-ctx shell_security editor: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
