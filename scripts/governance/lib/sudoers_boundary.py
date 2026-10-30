#!/usr/bin/env python3
"""Allowlist check of the evaluated sudoers (owner boundary).

CLI:
  sudoers_boundary.py declared   evaluate the flake config and check it (exit 1 on violation or eval failure)
  sudoers_boundary.py passwordless <cmd...>   read `sudo -n -l` text on stdin; exit 0 if cmd runs without a password
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FLAKE_HOST = "hyperd-ai-dev"
PRINCIPAL = "hyperd"

STORE = r"/nix/store/[a-z0-9]{32}-"
# (package-name prefix, binary, exact argument string) for fixed-argument rules.
EXACT = [
    ("systemd-", "systemctl", a)
    for a in (
        "start crowdsec-firewall-bouncer",
        "stop crowdsec-firewall-bouncer",
        "restart crowdsec-firewall-bouncer",
        "is-active crowdsec-firewall-bouncer",
        "restart firewall",
        "is-active firewall",
        "is-active nftables",
        "restart llama-cpp",
        "is-active llama-cpp",
        "start ai-local-training-loop.service",
        "stop ai-local-training-loop.service",
        "restart ai-local-training-loop.service",
    )
] + [
    ("crowdsec-", "cscli", "decisions list -o json"),
    ("iptables-", "iptables", "-L -n -v"),
]
VERBS = ("start", "stop", "restart")
TIMESTAMP_RE = re.compile(r'(?<![\w])(!?)timestamp_timeout(?![\w])(?:\s*([+-]?=)\s*"?([^\s,"]*)"?)?')


def parse_nopasswd(sudoers: str) -> list[tuple[str, str]]:
    """(principal, command) for every NOPASSWD entry in every non-comment line."""
    entries = []
    for line in sudoers.splitlines():
        if line.lstrip().startswith("#") or "NOPASSWD" not in line:
            continue
        principal = line.split()[0]
        for part in re.split(r"NOPASSWD:\s*", line)[1:]:
            entries.append((principal, part.strip().rstrip(",").strip()))
    return entries


def timestamp_values(sudoers: str) -> list[str]:
    """Every timestamp_timeout setting on any Defaults line (any scope), as text.

    Plain `=` assignments yield the value; negation (`!`), `+=`/`-=` and a bare
    flag yield a marker string that is never "0".
    """
    values = []
    for line in sudoers.splitlines():
        if not line.lstrip().startswith("Defaults"):
            continue
        for neg, op, val in TIMESTAMP_RE.findall(line):
            if neg:
                values.append("!negated")
            elif op != "=":
                values.append(f"bare-or-{op or 'flag'}")
            else:
                values.append(val)
    return values


def check_sudoers(sudoers: str, units: list[str], wrappers: dict[str, str]) -> list[str]:
    """Return the list of violations (empty means the boundary holds)."""
    problems: list[str] = []
    values = timestamp_values(sudoers)
    if not values or any(v != "0" for v in values):
        problems.append(f"timestamp_timeout must be exactly 0 everywhere, got {values or 'unset'}")

    entries = parse_nopasswd(sudoers)
    if not entries:
        problems.append("no NOPASSWD entries found (evaluation looks wrong)")
    wrapper_paths = set(wrappers.values())
    unit_set = set(units)
    for principal, command in entries:
        if principal != PRINCIPAL:
            problems.append(f"NOPASSWD for principal {principal}: {command}")
            continue
        if command in wrapper_paths:
            continue
        m = re.fullmatch(STORE + r"([^/]+)/bin/(\S+) (.+)", command)
        if not m:
            problems.append(f"not an allowlisted store-path command: {command}")
            continue
        pkg, binary, args = m.groups()
        if any(pkg.startswith(p) and binary == b and args == a for p, b, a in EXACT):
            continue
        u = re.fullmatch(r"--no-block (start|stop|restart) (\S+)", args)
        if pkg.startswith("systemd-") and binary == "systemctl" and u and u.group(2) in unit_set:
            continue
        problems.append(f"NOPASSWD rule not on the allowlist: {command}")
    # every approved unit/verb must be present, so the check also notices lost rules
    present = {c for _, c in entries}
    for unit in units:
        for verb in VERBS:
            if not any(re.fullmatch(STORE + r"systemd-[^/]+/bin/systemctl --no-block " + verb + " " + re.escape(unit), c) for c in present):
                problems.append(f"missing dashboard rule: {verb} {unit}")
    missing = set(wrappers.values()) - present
    for path in sorted(missing):
        problems.append(f"missing wrapper rule: {path}")
    return problems


def nix_eval(attr: str, raw: bool) -> str:
    result = subprocess.run(
        ["nix", "eval", "--raw" if raw else "--json", f".#nixosConfigurations.{FLAKE_HOST}.config.{attr}"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"nix eval {attr} failed: {result.stderr.strip()[-300:]}")
    return result.stdout


def declared() -> int:
    try:
        sudoers = nix_eval("security.sudo.configFile", raw=True)
        boundary = json.loads(nix_eval("system.build.aqSudoBoundary", raw=False))
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[sudo-readiness] FAIL: cannot evaluate the declared sudoers: {exc}", file=sys.stderr)
        return 1
    problems = check_sudoers(sudoers, boundary["units"], boundary["wrappers"])
    if problems:
        for p in problems:
            print(f"[sudo-readiness] FAIL: declared: {p}", file=sys.stderr)
        return 1
    n = len(parse_nopasswd(sudoers))
    print(f"[sudo-readiness] PASS: declared sudoers: {n} NOPASSWD rules all on the allowlist (hyperd only); timestamp_timeout=0")
    return 0


def passwordless(command: list[str]) -> int:
    sys.path.insert(0, str(REPO_ROOT / "dashboard" / "backend"))
    from api.services.service_manager import listing_allows_nopasswd

    return 0 if listing_allows_nopasswd(sys.stdin.read(), command) else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "declared":
        sys.exit(declared())
    if len(sys.argv) >= 3 and sys.argv[1] == "passwordless":
        sys.exit(passwordless(sys.argv[2:]))
    print(__doc__, file=sys.stderr)
    sys.exit(2)
