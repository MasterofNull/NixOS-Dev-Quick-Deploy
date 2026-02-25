---
name: all-mcp-directory
description: Instructions and workflow for the all-mcp-directory skill.
---

#!/usr/bin/env python3
"""
# Skill: all-mcp-directory

Offline-friendly client for browsing the community MCP server directory.

Examples:

```bash
python .agent/skills/all-mcp-directory/SKILL.md --query nix --limit 5
python .agent/skills/all-mcp-directory/SKILL.md --refresh
```
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Iterable, List


FALLBACK_DATA = [
    {
        "name": "nixpkgs-mcp",
        "url": "https://github.com/nix-community/nixpkgs-mcp",
        "description": "Query nixpkgs and surface package metadata.",
        "tags": ["nix", "devtools"],
    },
    {
        "name": "open-webui-tools",
        "url": "https://github.com/open-webui/open-webui/tree/main/packages/mcp-server",
        "description": "Expose Open WebUI automation hooks to MCP clients.",
        "tags": ["ops", "ui"],
    },
    {
        "name": "stripe-mcp",
        "url": "https://github.com/stripe/mcp-server",
        "description": "Interact with Stripe test accounts directly from MCP agents.",
        "tags": ["finance", "api"],
    },
    {
        "name": "timescale-toolkit",
        "url": "https://github.com/timescale/toolkit-mcp",
        "description": "Introspect TimescaleDB hypertables and run diagnostics.",
        "tags": ["database", "monitoring"],
    },
]

REMOTE_ENDPOINTS = [
    "https://www.allmcpservers.com/api/servers.json",
    "https://www.allmcpservers.com/api/servers",
]


def fetch_remote_catalog() -> List[dict] | None:
    for url in REMOTE_ENDPOINTS:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310
                payload = response.read().decode()
        except (urllib.error.URLError, TimeoutError):
            continue

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict) and "servers" in data:
            return data["servers"]  # type: ignore[return-value]
        if isinstance(data, list):
            return data
    return None


def filter_catalog(catalog: Iterable[dict], query: str | None) -> list[dict]:
    if not query:
        return list(catalog)
    q = query.lower()
    results = []
    for entry in catalog:
        haystack = " ".join(
            [entry.get("name", ""), entry.get("description", ""), " ".join(entry.get("tags", []))]
        ).lower()
        if q in haystack:
            results.append(entry)
    return results


def print_entry(entry: dict) -> None:
    name = entry.get("name", "(unknown)")
    url = entry.get("url", "")
    description = entry.get("description", "")
    tags = ", ".join(entry.get("tags", []))
    print(f"• {name}")
    if description:
        print(f"  {description}")
    if tags:
        print(f"  Tags: {tags}")
    if url:
        print(f"  URL: {url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browse MCP directory entries")
    parser.add_argument("--query", help="Filter by keyword")
    parser.add_argument("--limit", type=int, default=10, help="Maximum entries to display")
    parser.add_argument("--refresh", action="store_true", help="Attempt to download the live directory")
    args = parser.parse_args(argv)

    catalog = None
    if args.refresh:
        catalog = fetch_remote_catalog()
        if catalog:
            print(f"Fetched {len(catalog)} entries from allmcpservers.com")
        else:
            print("⚠️  Unable to refresh directory; falling back to bundled snapshot.")

    if catalog is None:
        catalog = FALLBACK_DATA

    results = filter_catalog(catalog, args.query)
    if not results:
        print("No matching MCP servers found.")
        return 0

    for entry in results[: args.limit]:
        print_entry(entry)

    if len(results) > args.limit:
        print(f"… {len(results) - args.limit} more entries available. Increase --limit to view them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

## Maintenance
- Version: 1.0.0
- Keep this skill aligned with current repository workflows.
