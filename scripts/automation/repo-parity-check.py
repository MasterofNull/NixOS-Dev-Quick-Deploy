#!/usr/bin/env python3
"""
scripts/automation/repo-parity-check.py

Purpose: Verify parity between declared flake inputs and the Repo Library.
Only repositories listed under "Core Dependencies (Flake Inputs)" are treated as
required flake inputs; all other library sections are reference material.
"""

import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
REPO_LIBRARY = ROOT / "docs/roadmap/REPO-LIBRARY.md"
FLAKE_NIX = ROOT / "flake.nix"

CORE_SECTION = "Core Dependencies (Flake Inputs)"


def get_library_repos():
    """Extract GitHub repos grouped by the section that declares them."""
    if not REPO_LIBRARY.exists():
        return {}

    sections = {}
    current_section = None
    with REPO_LIBRARY.open("r") as f:
        for line in f:
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                current_section = heading.group(1)
                sections.setdefault(current_section, set())
                continue

            if current_section is None:
                continue

            matches = re.findall(
                r"\[(github:[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)\]",
                line,
            )
            sections[current_section].update(matches)

    return sections

def get_flake_inputs():
    """Extract github: URLs from flake.nix."""
    inputs = []
    if not FLAKE_NIX.exists():
        return inputs
    
    with open(FLAKE_NIX, 'r') as f:
        content = f.read()
    
    # Find patterns like github:owner/repo
    matches = re.findall(r'"(github:[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._-]+)?)"', content)
    return set(matches)

def main():
    print("--- Repo Library Parity Check ---")
    repos_by_section = get_library_repos()
    core_repos = repos_by_section.get(CORE_SECTION, set())
    reference_repos = set().union(
        *(repos for section, repos in repos_by_section.items() if section != CORE_SECTION)
    )
    flake_inputs = get_flake_inputs()

    if not repos_by_section:
        print("[ERROR] No repositories found in docs/REPO-LIBRARY.md")
        return 1

    print(f"Found {sum(len(repos) for repos in repos_by_section.values())} repository references in library.")
    print(f"Found {len(core_repos)} core flake-input repositories.")
    print(f"Found {len(reference_repos)} non-core reference repositories.")
    print(f"Found {len(flake_inputs)} github inputs in flake.nix.")

    missing = []
    for repo in core_repos:
        # Check if the repo (or a versioned variant) is in flake inputs
        # e.g. github:NixOS/nixpkgs matches github:NixOS/nixpkgs/nixos-25.11
        found = False
        for f_input in flake_inputs:
            if f_input.startswith(repo):
                found = True
                break
        
        if not found:
            missing.append(repo)

    if missing:
        print("\n[GAP] The following core repositories are in the library but NOT in flake.nix:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("\n[PASS] All core library repositories are accounted for in flake.nix.")

    if reference_repos:
        print(
            f"\n[INFO] {len(reference_repos)} non-core repositories are tracked as references "
            "and are intentionally excluded from flake-input parity."
        )

    return 0

if __name__ == "__main__":
    sys.exit(main())
