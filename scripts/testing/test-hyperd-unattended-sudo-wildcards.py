#!/usr/bin/env python3
"""Owner-boundary regression checks for hyperd's sudo configuration.

Static: the host class declares no NOPASSWD rule.
Evaluated (needs `nix`; skipped with a message when unavailable, set
REQUIRE_NIX_EVAL=1 to make that a failure): the generated sudoers has
timestamp_timeout=0, no wildcard/unbounded NOPASSWD rule outside an explicit
allowlist, the exact dashboard per-unit set, and the privileged wrappers reject
hostile arguments.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS_PATH = REPO_ROOT / "nix/modules/host-classes/p14s-amd-ai-workstation.nix"
FLAKE_HOST = "hyperd-ai-dev"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance" / "lib"))
from sudoers_boundary import check_sudoers, parse_nopasswd  # noqa: E402

EXPECTED_DASHBOARD_UNITS = {
    "ai-aidb", "ai-hybrid-coordinator", "ai-ralph-wiggum", "ai-auth-selftest",
    "ai-otel-collector", "llama-cpp", "llama-cpp-embed", "qdrant", "postgresql",
    "redis-mcp", "ai-aider-wrapper", "ai-drop-daemon", "ai-health-spider",
    "ai-nixos-docs", "ai-switchboard", "ai-throttler",
    "command-center-dashboard-api",
}

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
    boundary = json.loads(
        nix("eval", "--json", f".#nixosConfigurations.{FLAKE_HOST}.config.system.build.aqSudoBoundary").stdout
    )
    problems = check_sudoers(sudoers, boundary["units"], boundary["wrappers"])
    assert_true(not problems, f"evaluated sudoers violates the allowlist: {problems}")
    units = {u.removesuffix(".service") for u in boundary["units"]}
    assert_true(
        units == EXPECTED_DASHBOARD_UNITS,
        f"dashboard unit set drifted: +{units - EXPECTED_DASHBOARD_UNITS} -{EXPECTED_DASHBOARD_UNITS - units}",
    )
    print(f"PASS: {len(entries)} NOPASSWD rules all on the allowlist; {len(units)} dashboard units x3 verbs")

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


def check_allowlist_logic() -> None:
    """Fixture sudoers lines: the allowlist accepts the approved set and rejects drift."""
    h = "0" * 32
    sd = f"/nix/store/{h}-systemd-260.5/bin/systemctl"
    w = {"aq-nft-dashboard": f"/nix/store/{h}-aq-nft-dashboard/bin/aq-nft-dashboard"}
    units = ["ai-aidb.service"]
    good_rules = [w["aq-nft-dashboard"], f"{sd} restart llama-cpp"] + [
        f"{sd} --no-block {v} ai-aidb.service" for v in ("start", "stop", "restart")
    ]
    base = "Defaults timestamp_timeout=0\n"

    def line(*cmds: str, who: str = "hyperd") -> str:
        return f"{who}     ALL=(ALL:ALL)    " + ", ".join(f"NOPASSWD: {c}" for c in cmds) + "\n"

    assert_true(
        parse_nopasswd(line(*good_rules)) == [("hyperd", c) for c in good_rules],
        "parse_nopasswd must split NOPASSWD entries",
    )
    assert_true(parse_nopasswd("# NOPASSWD: x\nroot ALL=(ALL) ALL\n") == [], "comments/non-NOPASSWD ignored")
    assert_true(not check_sudoers(base + line(*good_rules), units, w), "good fixture must pass")
    bad_cases = {
        "store bash": line(*good_rules, f"/nix/store/{h}-bash-5/bin/bash"),
        "bare nft": line(*good_rules, f"/nix/store/{h}-nftables-1/bin/nft"),
        "other unit": line(*good_rules, f"{sd} --no-block start evil.service"),
        "unlisted systemctl": line(*good_rules, f"{sd} start evil.service"),
        "wildcard": line(*good_rules, f"{sd} *"),
        "other principal": line(*good_rules) + line(f"{sd} restart llama-cpp", who="%wheel"),
    }
    for name, text in bad_cases.items():
        assert_true(check_sudoers(base + text, units, w), f"{name} must be rejected")
    assert_true(check_sudoers(line(*good_rules), units, w), "missing timestamp_timeout must be rejected")
    assert_true(
        check_sudoers(base + "Defaults:hyperd timestamp_timeout=5\n" + line(*good_rules), units, w),
        "a later timestamp_timeout override must be rejected",
    )
    assert_true(check_sudoers(base + line(*good_rules[:-1]), units, w), "lost dashboard rule must be reported")
    ts_bad = [
        "Defaults:hyperd timestamp_timeout = 5",
        "Defaults timestamp_timeout =5",
        "Defaults@host timestamp_timeout=5",
        "Defaults>root timestamp_timeout = 5",
        "Defaults!/bin/ls timestamp_timeout=5",
        "Defaults env_reset, timestamp_timeout = 5",
        "Defaults timestamp_timeout=-1",
        "Defaults timestamp_timeout=0.5",
        "Defaults !timestamp_timeout",
        "Defaults timestamp_timeout",
        'Defaults timestamp_timeout="5"',
    ]
    for override in ts_bad:
        assert_true(
            check_sudoers(base + override + "\n" + line(*good_rules), units, w),
            f"override must be rejected: {override}",
        )
    assert_true(
        not check_sudoers("Defaults env_reset, timestamp_timeout = 0\n" + line(*good_rules), units, w),
        "spaced `= 0` is still zero",
    )
    print("PASS: allowlist logic accepts the approved set and rejects drift (fixtures)")


def main() -> None:
    check_allowlist_logic()
    check_host_class()
    check_evaluated()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
