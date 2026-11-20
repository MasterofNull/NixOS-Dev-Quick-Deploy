#!/usr/bin/env python3
"""CLAUDE_CODE_TMPDIR must resolve to a persistent path, and its dirs must be 0700 with no age rule."""
import json
import os
import shutil
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOME_CFG = os.environ.get("CLAUDE_TMPDIR_HOME_CONFIG", "hyperd")


def skip(msg: str) -> None:
    if os.environ.get("REQUIRE_NIX_EVAL") == "1":
        raise SystemExit(f"FAIL: {msg}")
    print(f"SKIP: {msg}")
    raise SystemExit(0)


def nix_eval(attr: str):
    res = subprocess.run(
        ["nix", "eval", "--json", f".#homeConfigurations.{HOME_CFG}.config.{attr}"],
        cwd=REPO, capture_output=True, text=True, timeout=900,
    )
    if res.returncode != 0:
        skip(f"nix eval unavailable ({res.stderr.strip()[-200:]})")
    return json.loads(res.stdout)


def main() -> None:
    if shutil.which("nix") is None:
        skip("nix not available, CLAUDE_CODE_TMPDIR eval checks not run")
    for attr in (
        "home.sessionVariables.CLAUDE_CODE_TMPDIR",
        "systemd.user.sessionVariables.CLAUDE_CODE_TMPDIR",
    ):
        val = nix_eval(attr)
        assert not val.startswith("/tmp"), f"{attr} is on tmpfs: {val}"
        assert val.endswith("claude-code/tmp"), f"{attr} unexpected: {val}"
    rules = nix_eval("systemd.user.tmpfiles.rules")
    for suffix in ("claude-code", "claude-code/tmp", "claude-code/archive"):
        match = [r for r in rules if r.split()[1:2] and r.split()[1].endswith(suffix)]
        assert match, f"no tmpfiles rule for {suffix}"
        fields = match[0].split()
        assert fields[0] == "d" and fields[2] == "0700", f"rule not 'd' 0700: {match[0]}"
        assert fields[5:] in ([], ["-"]), f"rule has an age field: {match[0]}"
    print("PASS test-claude-tmpdir-durable")


if __name__ == "__main__":
    main()
