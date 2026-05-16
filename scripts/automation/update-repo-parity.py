#!/usr/bin/env python3
"""
scripts/automation/update-repo-parity.py

Purpose: Automated, staggered parity check between local state and upstream repositories.
Updates metadata for ~10-25% of the library per run to maintain a 3-4 day cycle.
"""

import sys
import json
import re
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
REPO_LIBRARY = ROOT / "docs/roadmap/REPO-LIBRARY.md"
PARITY_DB = ROOT / "data/parity/repo-parity-db.json"
FLAKE_LOCK = ROOT / "flake.lock"

# Configuration
STAGGER_INTERVAL_DAYS = 3
UPDATE_LIMIT_PER_RUN = 8  # Balanced limit for regular staggered updates
FETCH_TIMEOUT_SECONDS = 20
FETCH_ATTEMPTS = 2
CORE_SECTION = "Core Dependencies (Flake Inputs)"

def load_db():
    if not PARITY_DB.exists():
        return {}
    try:
        with open(PARITY_DB, 'r') as f:
            content = f.read()
            return json.loads(content) if content else {}
    except Exception:
        return {}

def save_db(db):
    with open(PARITY_DB, 'w') as f:
        json.dump(db, f, indent=2)

def get_library_repos():
    """Return repo metadata keyed by GitHub shorthand."""
    if not REPO_LIBRARY.exists():
        return {}

    repos = {}
    current_section = None
    with REPO_LIBRARY.open("r") as f:
        for line in f:
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                current_section = heading.group(1)
                continue

            if current_section is None:
                continue

            matches = re.findall(
                r"\[(github:[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)\]",
                line,
            )
            for repo in matches:
                repos[repo] = {
                    "section": current_section,
                    "tracking_kind": (
                        "core_flake_input"
                        if current_section == CORE_SECTION
                        else "reference_only"
                    ),
                }

    return repos

def get_flake_locked_rev(repo_url):
    """Try to find the locked revision in flake.lock."""
    if not FLAKE_LOCK.exists():
        return None
    
    with open(FLAKE_LOCK, 'r') as f:
        lock = json.load(f)
    
    parts = repo_url.split(':')
    if len(parts) < 2: return None
    path_parts = parts[1].split('/')
    if len(path_parts) < 2: return None
    
    owner, repo = path_parts[0], path_parts[1]
    
    for node in lock.get('nodes', {}).values():
        locked = node.get('locked', {})
        if locked.get('type') == 'github' and \
           locked.get('owner') == owner and \
           locked.get('repo') == repo:
            return locked.get('rev')
    return None

def fetch_upstream_metadata(repo_url):
    """Fetch latest commit from GitHub without needing a full git clone."""
    # Use 'git ls-remote' for a lightweight check
    parts = repo_url.split(':')
    if len(parts) < 2: return None
    
    https_url = f"https://github.com/{parts[1]}.git"
    last_error = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                ["git", "ls-remote", https_url, "HEAD"],
                capture_output=True,
                text=True,
                timeout=FETCH_TIMEOUT_SECONDS,
            )
            if result.returncode == 0 and result.stdout:
                rev = result.stdout.split()[0]
                return {
                    "rev": rev,
                    "timestamp": datetime.now().isoformat(),
                    "attempts": attempt,
                }

            stderr = (result.stderr or "").strip()
            last_error = {
                "kind": "git_ls_remote_failed",
                "detail": stderr or f"exit_code={result.returncode}",
                "attempts": attempt,
            }
        except subprocess.TimeoutExpired:
            last_error = {
                "kind": "timeout",
                "detail": f"git ls-remote exceeded {FETCH_TIMEOUT_SECONDS}s",
                "attempts": attempt,
            }
        except Exception as exc:
            last_error = {
                "kind": "exception",
                "detail": str(exc),
                "attempts": attempt,
            }

        if attempt < FETCH_ATTEMPTS:
            time.sleep(1)

    return {"error": last_error or {"kind": "unknown", "detail": "unknown fetch failure"}}


def classify_error_status(error_kind, error_detail):
    """Map low-level fetch failures to operator-facing status values."""
    detail = (error_detail or "").lower()
    if "repository not found" in detail:
        return "invalid_remote"
    if error_kind == "timeout" or "could not resolve host" in detail:
        return "transient_error"
    return "error"

def main():
    parser = argparse.ArgumentParser(description="Refresh staggered repo parity metadata")
    parser.add_argument(
        "--retry-problematic",
        action="store_true",
        help="refresh rows currently marked error, transient_error, or invalid_remote",
    )
    args = parser.parse_args()

    print(f"--- Starting Staggered Repo Parity Update ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
    db = load_db()
    lib_repos = get_library_repos()
    now = datetime.now()

    # Normalize existing records immediately so old "unknown" entries from prior
    # runs do not remain misleading until the next staggered refresh window.
    for repo, metadata in lib_repos.items():
        if repo not in db:
            continue
        db[repo]["section"] = metadata["section"]
        db[repo]["tracking_kind"] = metadata["tracking_kind"]
        if (
            metadata["tracking_kind"] == "reference_only"
            and db[repo].get("status") == "unknown"
            and db[repo].get("local_rev") is None
        ):
            db[repo]["status"] = "reference_only"
        if db[repo].get("status") == "error" and "error_kind" not in db[repo]:
            db[repo]["error_kind"] = "legacy_error"
            db[repo]["error_detail"] = (
                "Recorded by an older parity run before detailed fetch errors were stored"
            )
        if db[repo].get("status") == "error" and db[repo].get("error_kind"):
            db[repo]["status"] = classify_error_status(
                db[repo].get("error_kind"),
                db[repo].get("error_detail"),
            )

    # Preserve historical rows, but keep them out of active parity health once the
    # library stops referencing them (for example, after an upstream repo rename).
    for repo, entry in db.items():
        if repo not in lib_repos:
            entry["status"] = "retired_reference"
            entry["tracking_kind"] = "retired_reference"
            entry["retired_at"] = now.isoformat()
    
    to_update = []
    
    for repo in sorted(lib_repos):
        entry = db.get(repo, {})
        last_checked_str = entry.get('last_checked')
        current_local_rev = (
            get_flake_locked_rev(repo)
            if lib_repos[repo]["tracking_kind"] == "core_flake_input"
            else None
        )
        
        should_update = False
        if args.retry_problematic and entry.get("status") in {
            "error",
            "transient_error",
            "invalid_remote",
        }:
            should_update = True
        elif (
            lib_repos[repo]["tracking_kind"] == "core_flake_input"
            and current_local_rev != entry.get("local_rev")
        ):
            should_update = True
        elif not last_checked_str:
            should_update = True
        else:
            last_checked = datetime.fromisoformat(last_checked_str)
            if now - last_checked > timedelta(days=STAGGER_INTERVAL_DAYS):
                should_update = True
        
        if should_update:
            to_update.append(repo)

    print(f"Found {len(lib_repos)} repos in library. {len(to_update)} are due for update.")
    
    updated_count = 0
    for repo in to_update:
        if updated_count >= UPDATE_LIMIT_PER_RUN:
            print(f"Reached limit of {UPDATE_LIMIT_PER_RUN} updates per run. Staggering remaining.")
            break
            
        print(f"Updating {repo}...")
        upstream = fetch_upstream_metadata(repo)
        metadata = lib_repos[repo]
        if "rev" in upstream:
            local_rev = get_flake_locked_rev(repo)

            if metadata["tracking_kind"] == "reference_only":
                status = "reference_only"
            elif local_rev:
                status = "parity" if local_rev == upstream["rev"] else "outdated"
            else:
                status = "missing_local_rev"
            
            db[repo] = {
                "last_checked": now.isoformat(),
                "upstream_rev": upstream["rev"],
                "local_rev": local_rev,
                "status": status,
                "url": f"https://github.com/{repo.split(':')[1]}",
                "section": metadata["section"],
                "tracking_kind": metadata["tracking_kind"],
                "fetch_attempts": upstream["attempts"],
            }
            print(
                f"  Result: {status} "
                f"(Local: {local_rev[:7] if local_rev else 'N/A'}, "
                f"Upstream: {upstream['rev'][:7]})"
            )
        else:
            error = upstream.get("error", {})
            status = classify_error_status(
                error.get("kind", "unknown"),
                error.get("detail", "unknown fetch failure"),
            )
            db[repo] = {
                **db.get(repo, {}),
                "last_checked": now.isoformat(),
                "status": status,
                "url": f"https://github.com/{repo.split(':')[1]}",
                "section": metadata["section"],
                "tracking_kind": metadata["tracking_kind"],
                "error_kind": error.get("kind", "unknown"),
                "error_detail": error.get("detail", "unknown fetch failure"),
                "fetch_attempts": error.get("attempts", FETCH_ATTEMPTS),
            }
            print(
                f"  [{status.upper()}] {repo}: {db[repo]['error_kind']} "
                f"({db[repo]['error_detail']})"
            )
        updated_count += 1
    
    save_db(db)
    print(f"Parity database updated. {updated_count} repos refreshed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
