#!/usr/bin/env python3
"""Regression-check declared ownership for hybrid working-memory state."""

import json
import shlex
import subprocess


def nix_eval(attribute: str, *, raw: bool = False) -> str:
    command = ["nix", "eval", f".#nixosConfigurations.hyperd-ai-dev.config.{attribute}"]
    if raw:
        command.append("--raw")
    else:
        command.append("--json")
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    return result.stdout


def main() -> None:
    data_dir = nix_eval("mySystem.deployment.mutableSpaces.aiStackStateDir", raw=True)
    state_dir = f"{data_dir}/agent"
    bootstrap = nix_eval("systemd.services.ai-mutable-path-bootstrap.script", raw=True)
    parent_created = []
    for line in bootstrap.splitlines():
        try:
            args = shlex.split(line)
        except ValueError:
            continue
        if len(args) == 3 and args[0] == "create_path" and args[2] == data_dir:
            parent_created.append(args)
    assert not parent_created, f"bootstrap must preserve shared state parent; found {parent_created!r}"

    rules = json.loads(nix_eval("systemd.tmpfiles.rules"))
    matching = [rule.split() for rule in rules if len(rule.split()) >= 2 and rule.split()[1] == state_dir]
    assert len(matching) == 1, f"expected one working-memory state rule; got {matching!r}"
    fields = matching[0]
    assert fields[:5] == ["d", state_dir, "0750", "ai-hybrid", "ai-stack"], (
        f"expected ai-hybrid-owned working-memory child directory; got {fields!r}"
    )


if __name__ == "__main__":
    main()
    print("PASS: shared state parent is excluded and working-memory child is declared")
