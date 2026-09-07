#!/usr/bin/env python3
"""Static contract tests for the AQ-OS Workstation golden profile (p1-golden-profile).

Fast, hermetic checks (no Nix build) that protect the slice's invariants:
- the profile is registered (enum + flake import),
- the base is professional dev + gaming,
- local AI is OPTIONAL and OFF by default, and
- EVERY AI dependency lives inside the `aiOn` (cfg.roles.aiStack.enable) guard, so
  the AI-off golden path pulls in no AI stack.

The authoritative functional check is a Nix eval of the profile with AI off vs on
(run during development and by the operator's rebuild); this suite guards the
source shape so a regression that leaks an AI dep onto the AI-off path fails a
commit cheaply.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE = REPO / "nix" / "modules" / "profiles" / "aqos-workstation.nix"
OPTIONS = REPO / "nix" / "modules" / "core" / "options.nix"
FLAKE = REPO / "flake.nix"
PKGS = REPO / "nix" / "data" / "profile-system-packages.nix"

# mySystem options that introduce local-AI dependencies. None of these may be set
# on the always-applied base — they belong only inside the aiOn guard.
AI_OPTION_TOKENS = (
    "mySystem.mcpServers.enable",
    "mySystem.aiStack.switchboard.enable",
    "mySystem.monitoring.commandCenter.enable",
    "mySystem.aiStack.identityKernel.enable",
    "mySystem.aiStack.agentMesh.enable",
    "mySystem.aiStack.affectiveEngine.enable",
    "mySystem.aiStack.worldModel.enable",
    "mySystem.aiStack.executionCellRunner",
    "mySystem.aiStack.leaseSigningAuthority",
)


def test_registered() -> None:
    opts = OPTIONS.read_text()
    m = re.search(r'profile = lib\.mkOption \{\s*type = lib\.types\.enum \[([^\]]*)\]', opts)
    assert m, "could not find the mySystem.profile enum"
    assert '"aqos-workstation"' in m.group(1), "aqos-workstation missing from the profile enum"
    assert "./nix/modules/profiles/aqos-workstation.nix" in FLAKE.read_text(), \
        "flake.nix does not import the golden profile module"


def test_base_is_dev_plus_gaming() -> None:
    src = PROFILE.read_text()
    assert 'cfg.profile == "aqos-workstation"' in src
    for role in ("desktop", "gaming", "cppDev", "virtualization"):
        assert re.search(rf"mySystem\.roles\.{role}\.enable = lib\.mkDefault true", src), role
    # gaming stack signal
    assert "programs.gamemode.enable" in src


def test_local_ai_optional_and_off_by_default() -> None:
    src = PROFILE.read_text()
    assert re.search(r"mySystem\.roles\.aiStack\.enable = lib\.mkDefault false", src), \
        "aiStack must default to false (AI is optional)"
    assert "aiOn = cfg.roles.aiStack.enable" in src, "expected an aiOn binding on the aiStack flag"


def _base_vs_guarded(src: str) -> tuple[str, str]:
    """Split the profile config into the base block and the `lib.mkIf aiOn` block."""
    idx = src.index("lib.mkIf aiOn")
    return src[:idx], src[idx:]


def test_every_ai_dep_is_behind_the_aiOn_guard() -> None:
    src = PROFILE.read_text()
    base, guarded = _base_vs_guarded(src)
    for tok in AI_OPTION_TOKENS:
        # Any AI option that appears at all must appear ONLY in the guarded block.
        assert tok not in base, f"AI dependency leaked onto the AI-off base path: {tok}"
    # And the guard must actually enable the core AI surface when opted in.
    assert "mySystem.mcpServers.enable = lib.mkDefault true" in guarded
    assert "mySystem.aiStack.switchboard.enable = lib.mkDefault true" in guarded


def test_package_list_has_no_ai_service_tooling() -> None:
    src = PKGS.read_text()
    assert re.search(r"aqos-workstation = \[", src), "aqos-workstation package list missing"
    m = re.search(r"aqos-workstation = \[(.*?)\];", src, re.S)
    body = m.group(1)
    # Transcription/research tools present; heavy AI-data tooling absent.
    for want in ('"yt-dlp"', '"ffmpeg"', '"openai-whisper"'):
        assert want in body, want
    for forbid in ('"dvc"',):
        assert forbid not in body, f"AI-data tool {forbid} should not be on the golden list"


def main() -> int:
    test_registered()
    test_base_is_dev_plus_gaming()
    test_local_ai_optional_and_off_by_default()
    test_every_ai_dep_is_behind_the_aiOn_guard()
    test_package_list_has_no_ai_service_tooling()
    print("test-aqos-golden-profile: ok 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
