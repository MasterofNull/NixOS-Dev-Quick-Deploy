#!/usr/bin/env python3
"""Enforce platform-owner approval when harness-first high-impact path policy changes in a PR."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TARGET_FILE = "config/harness-first-high-impact-paths.txt"
OWNERS_FILE = Path("config/harness-first-platform-owners.txt")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def info(msg: str) -> None:
    print(f"INFO: {msg}")


def gh_paginated(repo: str, endpoint: str, token: str) -> list[dict]:
    page = 1
    out: list[dict] = []
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = f"https://api.github.com/repos/{repo}/{endpoint}?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "harness-first-owner-approval-gate",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            fail(f"GitHub API error {exc.code} for {endpoint}: {body}")

        if not isinstance(payload, list):
            fail(f"unexpected API payload for {endpoint}: expected list")

        out.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return out


def load_owners(path: Path) -> list[str]:
    if not path.exists():
        fail(f"missing owners file: {path}")

    owners: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            line = line[1:]
        # Team approvals are not directly visible as team entities in the PR review API.
        if "/" in line:
            fail(
                "team entries are not supported in config/harness-first-platform-owners.txt; "
                "use individual GitHub handles"
            )
        owners.append(line.lower())

    if not owners:
        fail(f"no owners configured in {path}")
    return owners


def main() -> None:
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        info("non-PR event; skipping platform-owner approval gate")
        return

    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    if not event_path:
        fail("GITHUB_EVENT_PATH is required")

    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not repo:
        fail("GITHUB_REPOSITORY is required")

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        fail("GITHUB_TOKEN is required for PR approval gate")

    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        fail(f"unable to parse event payload: {exc}")

    pr_number = event.get("pull_request", {}).get("number")
    if not isinstance(pr_number, int):
        fail("pull_request.number missing from event payload")

    changed_files = gh_paginated(repo, f"pulls/{pr_number}/files", token)
    changed_paths = {item.get("filename") for item in changed_files if isinstance(item, dict)}

    if TARGET_FILE not in changed_paths:
        info(f"{TARGET_FILE} unchanged; skipping owner-approval requirement")
        return

    owners = load_owners(OWNERS_FILE)
    reviews = gh_paginated(repo, f"pulls/{pr_number}/reviews", token)

    latest_state_by_user: dict[str, str] = {}
    def sort_key(item: dict) -> tuple[str, int]:
        ts = str(item.get("submitted_at") or "")
        rid = int(item.get("id") or 0)
        return (ts, rid)

    for review in sorted((r for r in reviews if isinstance(r, dict)), key=sort_key):
        user = (review.get("user") or {}).get("login")
        state = review.get("state")
        if not user or not state:
            continue
        latest_state_by_user[str(user).lower()] = str(state).upper()

    approved_owners = [owner for owner in owners if latest_state_by_user.get(owner) == "APPROVED"]
    if not approved_owners:
        owner_states = ", ".join(
            f"{owner}:{latest_state_by_user.get(owner, 'NONE')}" for owner in owners
        )
        fail(
            f"{TARGET_FILE} changed but no platform-owner approval found; "
            f"required one of [{', '.join(owners)}], states [{owner_states}]"
        )

    info(
        f"platform-owner approval satisfied for {TARGET_FILE}; "
        f"approved by {', '.join(approved_owners)}"
    )


if __name__ == "__main__":
    main()
