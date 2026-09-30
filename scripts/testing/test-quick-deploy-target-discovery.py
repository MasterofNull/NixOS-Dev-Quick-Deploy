#!/usr/bin/env python3
"""Guard against reporting a discovered NixOS target as missing on timeout."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "nixos-quick-deploy.sh"


def main() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("assert_targets_exist() {")
    end = source.index("\n}\n", start) + 3
    function = source[start:end]

    discovery = 'available_nixos="$(list_configuration_names "nixosConfigurations" || true)"'
    membership = '[[ " ${available_nixos} " != *" ${nixos_target} "* ]]'
    evaluation = 'if ! nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\\"${nixos_target}\\".config.system.stateVersion"'

    assert discovery in function, "target names must be discovered before existence checks"
    assert membership in function, "existence must be checked against discovered names"
    assert evaluation in function, "configuration evaluation must remain a distinct failure"
    assert function.index(discovery) < function.index(membership) < function.index(evaluation)


if __name__ == "__main__":
    main()
