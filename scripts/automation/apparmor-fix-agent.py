#!/usr/bin/env python3
"""
apparmor-fix-agent.py — AppArmor denial scanner → rule generator → git commit.

Reads denial data from stdin (JSON) or scans journalctl directly.
Generates AppArmor rules, deduplicates against existing profile in
mcp-servers.nix, commits the fix, seeds RAG, and updates HANDOFF.md.

Exit codes:
  0 — rules committed
  1 — error
  2 — no new rules needed (all paths already covered)

Usage (from health spider):
  echo '{"profile":"command-center-dashboard-api","denials":[...]}' |
    apparmor-fix-agent.py --profile command-center-dashboard-api --input-json -

Usage (standalone):
  apparmor-fix-agent.py --profile command-center-dashboard-api --since 120
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
NIX_FILE    = REPO_ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"
HANDOFF_MD  = REPO_ROOT / ".agent" / "collaboration" / "HANDOFF.md"
EMBED_URL   = os.environ.get("LLAMA_EMBED_URL", "http://127.0.0.1:8081")
QDRANT_URL  = os.environ.get("QDRANT_URL",       "http://127.0.0.1:6333")

# Insertion anchor — rules added BEFORE the deny-home line in each profile block
DENY_HOME_PATTERN = re.compile(r"^\s+deny /home/\*\* wx,")

# ── Rule generation ────────────────────────────────────────────────────────────

def _op_to_perm(operation: str, mask: str) -> str:
    if "exec" in operation:
        return "ix"
    if operation == "file_lock":
        return "k"
    if any(c in mask for c in ("w", "c")):
        return "rw"
    return "r"


def _make_rule(operation: str, path: str, mask: str) -> Optional[Tuple[str, str]]:
    """
    Returns (rule_line, comment) or None if the path should be handled by a
    broader rule (e.g. /sys/devices/**).
    rule_line uses 12-space indent matching mcp-servers.nix style.
    """
    INDENT = "            "

    # Nix store — generalize hash-prefixed derivation name.
    # Path: /nix/store/<hash-name>/sub/path
    # parts: [nix, store, hash-name, sub, path, ...]
    # We want: /nix/store/**/sub/path  (skip parts[0..2])
    if path.startswith("/nix/store/"):
        parts = path.lstrip("/").split("/")
        rest = "/".join(parts[3:])   # skip nix, store, hash-name
        perm = "ix" if "exec" in operation else "r"
        return f"{INDENT}/nix/store/**/{rest} {perm},", f"nix store {operation}"

    # /proc/<pid>/... → @{pids} AppArmor variable
    m = re.match(r"^/proc/(\d+)/(.+)$", path)
    if m:
        rest = m.group(2)
        perm = _op_to_perm(operation, mask)
        return f"{INDENT}/proc/@{{pids}}/{rest} {perm},", f"/proc/<pid> → @{{pids}}"

    # /proc/ root directory listing
    if path == "/proc/":
        return f"{INDENT}/proc/ r,", "proc root listing"

    # /sys/devices/ subtree — emit a single broad rule below, not per-path
    if path.startswith("/sys/devices/"):
        return None  # Caller handles consolidation

    # Default: emit path verbatim + computed permission
    perm = _op_to_perm(operation, mask)
    trailing = " r," if path.endswith("/") else f" {perm},"
    return f"{INDENT}{path}{trailing}", operation


def _consolidate(denials: List[Dict[str, str]]) -> Tuple[List[Tuple[str, str]], bool]:
    """
    Returns (rules, needs_sys_devices_broad_rule).
    Consolidates /sys/devices/* variants into one broad rule.
    """
    rules: List[Tuple[str, str]] = []
    has_sys_devices = False
    for d in denials:
        result = _make_rule(d["operation"], d["path"], d["mask"])
        if result is None:
            has_sys_devices = True  # Handled by broad rule
        else:
            rules.append(result)
    if has_sys_devices:
        rules.append(("            /sys/devices/** r,", "/sys/devices subtree (hwmon/thermal/ACPI)"))
    return rules, has_sys_devices


# ── Profile block manipulation ─────────────────────────────────────────────────

def _find_profile_block(lines: List[str], profile: str) -> Tuple[int, int]:
    """
    Returns (deny_home_lineno, block_end_lineno) within lines list (0-indexed).
    deny_home_lineno: line to insert BEFORE.
    Returns (-1, -1) if profile block not found.
    """
    # Find the profile name in a comment or apparmor_parser invocation context.
    # The dashboard profile is generated with the profile name as the nix drv name.
    # Search for the deny /home/** wx, line nearest to a reference to the profile.
    # Strategy: find all deny /home/** wx, lines, pick the one inside the right block.
    # Profile name markers in the file: drv name = profile name.

    # Simpler: each profile block has exactly one `deny /home/** wx,`.
    # We identify which block a given line belongs to by its surrounding context.
    # For a single-profile search, we find all occurrences and pick the one
    # whose preceding 200 lines contain the profile name.

    deny_candidates: List[int] = []
    for i, line in enumerate(lines):
        if DENY_HOME_PATTERN.match(line):
            deny_candidates.append(i)

    for deny_idx in deny_candidates:
        # Look back up to 200 lines for the profile name
        window = "\n".join(lines[max(0, deny_idx - 200):deny_idx])
        if profile in window:
            return deny_idx, deny_idx  # block_end not needed; insert at deny_idx
    return -1, -1


def _path_already_covered(nix_text: str, profile: str, candidate_rule: str) -> bool:
    """
    Rough check: if the literal path from the rule already appears in the profile
    block text, skip it. Handles wildcards by extracting the path prefix.
    """
    # Extract the path portion from the rule
    m = re.search(r"(/[^\s]+)\s+[a-z,]+,$", candidate_rule.strip())
    if not m:
        return False
    path = m.group(1).rstrip("/")

    # Find the profile block: 200 lines around the deny /home/** line for this profile
    lines = nix_text.splitlines()
    deny_idx, _ = _find_profile_block(lines, profile)
    if deny_idx == -1:
        return False
    block = "\n".join(lines[max(0, deny_idx - 200):deny_idx + 1])

    # If path (with any trailing **) is already present, consider covered
    path_base = path.replace("/**", "").replace("/*", "")
    return path_base in block or path in block


# ── Git helpers ────────────────────────────────────────────────────────────────

def _git_commit(message: str) -> Optional[str]:
    """Stage mcp-servers.nix + HANDOFF.md and commit. Returns short hash or None."""
    try:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "add",
             str(NIX_FILE.relative_to(REPO_ROOT)),
             str(HANDOFF_MD.relative_to(REPO_ROOT))],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "commit", "-m", message],
            check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"git commit failed: {e.stderr.decode()[:200]}\n")
        return None


# ── RAG seeding ────────────────────────────────────────────────────────────────

def _seed_rag(profile: str, denials: List[Dict[str, str]], rules: List[str]) -> None:
    try:
        paths = [d["path"] for d in denials[:5]]
        text = (
            f"Error: AppArmor denial in profile {profile}. "
            f"Denied paths: {paths}. "
            f"Context: Service startup blocked by missing AppArmor rules. "
            f"Solution: Add rules to mcp-servers.nix profile block: {rules[:5]}. "
            f"After commit run: sudo nixos-rebuild switch --flake .#hyperd-ai-dev"
        )
        embed_req = urllib.request.Request(
            f"{EMBED_URL}/v1/embeddings",
            data=json.dumps({"input": text, "model": "bge-m3"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(embed_req, timeout=10) as r:
            vector = json.loads(r.read())["data"][0]["embedding"]

        import uuid
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"apparmor-fix:{profile}:{paths}"))
        upsert_req = urllib.request.Request(
            f"{QDRANT_URL}/collections/error-solutions/points",
            data=json.dumps({"points": [{
                "id": point_id,
                "vector": vector,
                "payload": {
                    "error_type": "apparmor_denial",
                    "error_message": f"AppArmor DENIED in profile {profile}: {paths}",
                    "context": f"Service using profile {profile} blocked on startup or runtime",
                    "solution": f"Add to mcp-servers.nix profile block: {rules}. Then nixos-rebuild switch.",
                    "tags": ["apparmor", profile, "health-spider", "auto-fix"],
                    "source": "apparmor-fix-agent",
                    "fixed_at": datetime.now(timezone.utc).isoformat(),
                },
            }]}).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(upsert_req, timeout=10) as r:
            r.read()
    except Exception as e:
        sys.stderr.write(f"RAG seed warning: {e}\n")


# ── HANDOFF update ─────────────────────────────────────────────────────────────

def _update_handoff(profile: str, rules: List[str], commit: str, denial_paths: List[str]) -> None:
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = (
            f"\n### [{ts}] apparmor-fix-agent\n"
            f"**Auto-committed AppArmor fix** `{commit}` — profile `{profile}`  \n"
            f"Rules added ({len(rules)}):\n"
            + "\n".join(f"  - `{r.strip()}`" for r in rules) + "\n"
            f"Denied paths that triggered: {denial_paths[:5]}  \n"
            f"⚠️  **Pending rebuild: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`**\n"
        )
        with open(HANDOFF_MD, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        sys.stderr.write(f"HANDOFF update warning: {e}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def _scan_journalctl(profile: str, since_seconds: int) -> List[Dict[str, str]]:
    # journalctl --since expects local time (not UTC)
    since = datetime.fromtimestamp(time.time() - since_seconds).strftime("%Y-%m-%d %H:%M:%S")
    try:
        r = subprocess.run(
            ["journalctl", "-k", f"--since={since}", "--no-pager", "-q"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        sys.exit(f"journalctl error: {e}")

    seen: set = set()
    denials = []
    for line in r.stdout.splitlines():
        if f'profile="{profile}"' not in line or 'apparmor="DENIED"' not in line:
            continue
        def _f(key):
            marker = f'{key}="'
            if marker not in line:
                return ""
            s = line.index(marker) + len(marker)
            return line[s:line.index('"', s)]
        op, path, mask = _f("operation"), _f("name"), _f("requested_mask")
        key = (op, path)
        if key not in seen and path:
            seen.add(key)
            denials.append({"operation": op, "path": path, "mask": mask})
    return denials


def main() -> int:
    parser = argparse.ArgumentParser(description="AppArmor fix agent")
    parser.add_argument("--profile", required=True, help="AppArmor profile name")
    parser.add_argument("--input-json", metavar="FILE",
                        help="Read denial JSON from file or '-' for stdin")
    parser.add_argument("--since", type=int, default=120,
                        help="Scan journalctl for denials in last N seconds (default: 120)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # --- Load denials ---
    if args.input_json:
        src = sys.stdin if args.input_json == "-" else open(args.input_json)
        data = json.load(src)
        denials = data.get("denials", [])
    else:
        denials = _scan_journalctl(args.profile, args.since)

    if not denials:
        json.dump({"rules_added": [], "commit_hash": None, "message": "no denials found"}, sys.stdout)
        return 2

    # --- Generate rules ---
    nix_text = NIX_FILE.read_text(encoding="utf-8")
    rules_raw, _ = _consolidate(denials)

    # Deduplicate against existing profile content
    new_rules: List[Tuple[str, str]] = []
    for rule_line, comment in rules_raw:
        if _path_already_covered(nix_text, args.profile, rule_line):
            continue
        new_rules.append((rule_line, comment))

    # Remove exact duplicates within new_rules
    seen_rules: set = set()
    deduped: List[Tuple[str, str]] = []
    for rule_line, comment in new_rules:
        key = rule_line.strip()
        if key not in seen_rules:
            seen_rules.add(key)
            deduped.append((rule_line, comment))

    if not deduped:
        json.dump({"rules_added": [], "commit_hash": None, "message": "all paths already covered"}, sys.stdout)
        return 2

    if args.dry_run:
        json.dump({"rules_added": [r for r, _ in deduped], "commit_hash": None, "message": "dry-run"}, sys.stdout)
        return 0

    # --- Insert rules into mcp-servers.nix ---
    lines = nix_text.splitlines(keepends=True)
    deny_idx, _ = _find_profile_block(lines, args.profile)
    if deny_idx == -1:
        sys.stderr.write(f"Could not find profile block for '{args.profile}' in {NIX_FILE}\n")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    insert_block = (
        f"            # auto-added by apparmor-fix-agent {ts}\n"
        + "\n".join(f"{rule}  # {cmt}" for rule, cmt in deduped)
        + "\n"
    )
    lines.insert(deny_idx, insert_block)
    NIX_FILE.write_text("".join(lines), encoding="utf-8")

    # --- Commit ---
    denial_paths = [d["path"] for d in denials]
    rule_lines = [r for r, _ in deduped]
    msg = (
        f"fix(apparmor): auto-add {len(deduped)} rule(s) to {args.profile} profile\n\n"
        f"AppArmor-fix-agent detected {len(denials)} denial(s) and generated rules.\n"
        f"Paths: {denial_paths[:5]}\n"
        f"Requires: sudo nixos-rebuild switch --flake .#hyperd-ai-dev\n\n"
        f"Co-Authored-By: health-spider <noreply@local>"
    )
    _update_handoff(args.profile, rule_lines, "pending-commit", denial_paths)
    commit_hash = _git_commit(msg)
    if not commit_hash:
        return 1

    # --- Knowledge injection ---
    _seed_rag(args.profile, denials, rule_lines)

    json.dump({
        "rules_added": rule_lines,
        "commit_hash": commit_hash,
        "profile": args.profile,
        "denial_count": len(denials),
    }, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
