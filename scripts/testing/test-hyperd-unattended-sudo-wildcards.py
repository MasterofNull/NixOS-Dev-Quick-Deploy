#!/usr/bin/env python3
"""Owner-boundary regression checks for hyperd's sudo configuration.

Static: the host class declares no NOPASSWD rule.
Evaluated (needs `nix`; skipped with a message when unavailable, set
REQUIRE_NIX_EVAL=1 to make that a failure): the generated sudoers has
timestamp_timeout=0, no wildcard/unbounded NOPASSWD rule outside an explicit
allowlist, the exact dashboard per-unit set, and the privileged wrappers reject
hostile arguments.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS_PATH = REPO_ROOT / "nix/modules/host-classes/p14s-amd-ai-workstation.nix"
FLAKE_HOST = "hyperd-ai-dev"

# Wrappers take arguments but validate them; sudoers lists only their path.
VALIDATING_WRAPPERS = {
    "aq-nft-dashboard",
    "aq-llama-set-active-model",
    "aq-crowdsec-decision-delete",
}

# Every other NOPASSWD rule must be an exact command (binary + fixed args).
EXACT_ALLOWLIST = {
    "systemctl start crowdsec-firewall-bouncer",
    "systemctl stop crowdsec-firewall-bouncer",
    "systemctl restart crowdsec-firewall-bouncer",
    "systemctl is-active crowdsec-firewall-bouncer",
    "systemctl restart firewall",
    "systemctl is-active firewall",
    "systemctl is-active nftables",
    "cscli decisions list -o json",
    "iptables -L -n -v",
    "systemctl restart llama-cpp",
    "systemctl is-active llama-cpp",
    "systemctl start ai-local-training-loop.service",
    "systemctl stop ai-local-training-loop.service",
    "systemctl restart ai-local-training-loop.service",
}

EXPECTED_DASHBOARD_UNITS = {
    "ai-aidb", "ai-hybrid-coordinator", "ai-ralph-wiggum", "ai-auth-selftest",
    "ai-otel-collector", "llama-cpp", "llama-cpp-embed", "qdrant", "postgresql",
    "redis-mcp", "ai-aider-wrapper", "ai-drop-daemon", "ai-health-spider",
    "ai-nixos-docs", "ai-switchboard", "ai-throttler",
    "command-center-dashboard-api",
}

STORE_RE = re.compile(r"^/nix/store/[a-z0-9]{32}-([^/]+)/bin/(\S+)(?: (.*))?$")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_host_class() -> None:
    text = HOST_CLASS_PATH.read_text(encoding="utf-8")
    forbidden_commands = [
        '/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh *',
        '/run/current-system/sw/bin/nixos-rebuild *',
        '/run/current-system/sw/bin/systemctl *',
        '/run/current-system/sw/bin/journalctl *',
        '/run/current-system/sw/bin/flatpak *',
        'scripts/ai/aq-model-switch *',
    ]
    for command in forbidden_commands:
        assert_true(
            command not in text,
            f"root-equivalent command must not have a NOPASSWD rule: {command}",
        )
    assert_true(
        "NOPASSWD" not in text.replace("No NOPASSWD", ""),
        "host class must not declare any NOPASSWD sudo rule",
    )
    print("PASS: hyperd host class declares no NOPASSWD sudo rules")


def nix(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["nix", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def parse_nopasswd(sudoers: str) -> list[tuple[str, str]]:
    """Return (principal, command) for every NOPASSWD entry of every user/group."""
    entries = []
    for line in sudoers.splitlines():
        if line.lstrip().startswith("#") or "NOPASSWD" not in line:
            continue
        principal = line.split()[0]
        for part in re.split(r"NOPASSWD:\s*", line)[1:]:
            entries.append((principal, part.strip().rstrip(",").strip()))
    return entries


def build_wrapper(name: str) -> str:
    expr = (
        "let f = builtins.getFlake (toString ./.); in builtins.head "
        f'(builtins.filter (p: (p.name or "") == "{name}") '
        f"f.nixosConfigurations.{FLAKE_HOST}.config.environment.systemPackages)"
    )
    result = nix("build", "--no-link", "--print-out-paths", "--impure", "--expr", expr)
    assert_true(result.returncode == 0, f"cannot build {name}: {result.stderr[-400:]}")
    return f"{result.stdout.strip().splitlines()[-1]}/bin/{name}"


def run_rejected(binary: str, *args: str) -> None:
    result = subprocess.run([binary, *args], capture_output=True, text=True, check=False)
    assert_true(
        result.returncode == 2,
        f"{Path(binary).name} {list(args)} must be rejected with exit 2, "
        f"got {result.returncode}: {result.stderr.strip()[:200]}",
    )


def check_evaluated() -> None:
    if shutil.which("nix") is None:
        message = "SKIP: nix not available, evaluated-sudoers checks not run"
        if os.environ.get("REQUIRE_NIX_EVAL") == "1":
            raise AssertionError(message)
        print(message)
        return
    result = nix(
        "eval", "--raw", f".#nixosConfigurations.{FLAKE_HOST}.config.security.sudo.configFile"
    )
    if result.returncode != 0:
        message = f"SKIP: nix eval unavailable ({result.stderr.strip()[-200:]})"
        if os.environ.get("REQUIRE_NIX_EVAL") == "1":
            raise AssertionError(message)
        print(message)
        return
    sudoers = result.stdout

    assert_true(
        re.search(r"^Defaults\s+timestamp_timeout=0\s*$", sudoers, re.M) is not None,
        "effective sudoers must set `Defaults timestamp_timeout=0`",
    )
    assert_true(
        re.search(r"^Defaults\s+timestamp_timeout=(?!0\b)", sudoers, re.M) is None,
        "no other timestamp_timeout may be set",
    )
    print("PASS: effective sudoers has timestamp_timeout=0")

    entries = parse_nopasswd(sudoers)
    assert_true(entries, "expected the dashboard NOPASSWD rules in the sudoers")
    principals = {principal for principal, _ in entries}
    assert_true(
        principals == {"hyperd"}, f"NOPASSWD only expected for hyperd, got {principals}"
    )

    units: set[str] = set()
    unit_rules = 0
    wrappers_seen: dict[str, str] = {}
    for _, command in entries:
        assert_true("*" not in command, f"wildcard in NOPASSWD rule: {command}")
        match = STORE_RE.match(command)
        assert_true(match is not None, f"NOPASSWD rule not an exact store path: {command}")
        pkg, binary, args = match.group(1), match.group(2), match.group(3)
        if args is None:
            assert_true(
                binary in VALIDATING_WRAPPERS,
                f"bare binary with unbounded args is not an allowed wrapper: {command}",
            )
            wrappers_seen[binary] = command
            continue
        unit = re.fullmatch(r"--no-block (start|stop|restart) (\S+)\.service", args)
        if binary == "systemctl" and unit:
            units.add(unit.group(2))
            unit_rules += 1
            continue
        assert_true(
            f"{binary} {args}" in EXACT_ALLOWLIST,
            f"NOPASSWD rule outside the explicit allowlist: {binary} {args}",
        )
    assert_true(
        units == EXPECTED_DASHBOARD_UNITS,
        f"dashboard unit set drifted: +{units - EXPECTED_DASHBOARD_UNITS} "
        f"-{EXPECTED_DASHBOARD_UNITS - units}",
    )
    assert_true(unit_rules == 3 * len(units), "each dashboard unit needs exactly 3 verbs")
    assert_true(
        set(wrappers_seen) == VALIDATING_WRAPPERS,
        f"wrapper set mismatch: {set(wrappers_seen)}",
    )
    print(
        f"PASS: {len(entries)} NOPASSWD rules, all exact or validating wrappers; "
        f"{len(units)} dashboard units x3 verbs"
    )

    llama = build_wrapper("aq-llama-set-active-model")
    for bad in (["../x"], ["-t", "/etc"], ["a/b.gguf"], ["active.gguf"], ["x.gguf", "y.gguf"], []):
        run_rejected(llama, *bad)
    crowdsec = build_wrapper("aq-crowdsec-decision-delete")
    for bad in (["1;rm"], ["--id"], ["--id", "1"], ["1", "2"], ["-1"], [""], []):
        run_rejected(crowdsec, *bad)
    nft = build_wrapper("aq-nft-dashboard")
    bad_nft = [
        ["-f", "/etc/x"],
        ["-i", "x"],
        ["list", "ruleset", "-f", "x"],
        ["flush", "ruleset"],
        ["list", "chain", "../x", "filter", "input"],
        ["delete", "rule", "inet", "filter", "input", "handle", "1x"],
        ["-a", "delete", "rule", "inet", "filter", "input", "handle", "1"],
        ["add", "rule", "inet", "filter", "input", "tcp", "dport", "80", "accept"],
        ["add", "rule", "inet", "filter", "input", "tcp", "dport", "80", "drop", "comment", "x"],
        ["add", "rule", "inet", "filter", "input", "-f", "x", "accept", "comment", "x"],
        ["add", "rule", "inet", "filter", "input", "tcp;flush", "accept", "comment", "x"],
        ["add", "rule", "inet", "filter", "input", "tcp", "accept", "comment", "x;y"],
    ]
    for bad in bad_nft:
        run_rejected(nft, *bad)
    print("PASS: wrappers reject hostile arguments (llama, crowdsec, nft)")


def main() -> None:
    check_host_class()
    check_evaluated()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
