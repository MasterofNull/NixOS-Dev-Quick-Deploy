#!/usr/bin/env python3
"""
Lightweight discovery crawler: fetches a curated source list and produces
an evidence report with titles and links. Intended for human review only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = REPO_ROOT / "config" / "improvement-sources.txt"
SOURCES_JSON = REPO_ROOT / "config" / "improvement-sources.json"
OUT_DIR = REPO_ROOT / "docs" / "development"
USER_AGENT = "NixOS-Dev-Quick-Deploy-Discovery/1.0"
MIN_CANDIDATE_SCORE = 20.0
STATE_FILE = REPO_ROOT / "data" / "improvement-crawler-state.json"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


def fetch_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=8) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_json(url: str) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def parse_github_repo(url: str) -> tuple[str, str] | None:
    match = re.match(r"https?://github.com/([^/]+)/([^/]+)", url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    repo = repo.replace(".git", "")
    return owner, repo


def github_release_summary(data: dict | None, error: str | None) -> list[str]:
    if error:
        return [f"- **Error:** {error}"]
    if not data:
        return ["- **Latest release:** N/A"]
    lines = [
        f"- **Latest release:** {data.get('name') or data.get('tag_name', 'N/A')}",
        f"- **Tag:** {data.get('tag_name', 'N/A')}",
        f"- **Release URL:** {data.get('html_url', 'N/A')}",
        f"- **Published:** {data.get('published_at', 'N/A')}",
    ]
    return lines


def score_github_repo(repo_data: dict, release_data: dict | None, weight: float) -> float:
    stars = repo_data.get("stargazers_count", 0) or 0
    updated = repo_data.get("updated_at", "")
    stars_score = min(40.0, (max(stars, 1) ** 0.25) * 5.0)
    activity_score = 0.0
    if updated:
        updated_dt = dt.datetime.fromisoformat(updated.replace("Z", "+00:00"))
        delta_days = (dt.datetime.now(dt.timezone.utc) - updated_dt).days
        if delta_days <= 90:
            activity_score = 20.0
        elif delta_days <= 180:
            activity_score = 10.0
    release_score = 0.0
    if release_data and release_data.get("published_at"):
        published_dt = dt.datetime.fromisoformat(release_data["published_at"].replace("Z", "+00:00"))
        delta_days = (dt.datetime.now(dt.timezone.utc) - published_dt).days
        if delta_days <= 90:
            release_score = 20.0
        elif delta_days <= 180:
            release_score = 10.0
    raw_score = stars_score + activity_score + release_score
    return round(raw_score * weight, 2)


def normalize_link(base: str, link: str) -> str:
    if link.startswith("#"):
        return ""
    return urljoin(base, link)


def filter_links(base: str, links: List[str]) -> List[str]:
    seen = set()
    filtered: List[str] = []
    base_host = urlparse(base).netloc
    for link in links:
        normalized = normalize_link(base, link)
        if not normalized:
            continue
        if urlparse(normalized).netloc and urlparse(normalized).netloc != base_host:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(normalized)
    return filtered[:10]


def load_sources() -> List[dict]:
    if SOURCES_JSON.is_file():
        sources = json.loads(SOURCES_JSON.read_text())
        if not isinstance(sources, list):
            raise ValueError("improvement-sources.json must contain a list of sources")
        return sources
    if not SOURCES_FILE.is_file():
        raise FileNotFoundError(f"Sources file not found: {SOURCES_FILE}")
    sources: List[dict] = []
    for line in SOURCES_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sources.append({"url": line, "type": "unknown", "weight": 0.3})
    return sources


def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            data = json.loads(STATE_FILE.read_text())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def is_due(source: dict, state: dict, now: dt.datetime) -> bool:
    cadence_hours = source.get("cadence_hours")
    if not cadence_hours:
        return True
    url = source.get("url", "")
    if not url:
        return False
    last_checked = state.get(url)
    if not last_checked:
        return True
    try:
        last_dt = dt.datetime.fromisoformat(last_checked)
    except ValueError:
        return True
    delta = now - last_dt
    return delta.total_seconds() >= float(cadence_hours) * 3600


def get_github_repo_data(
    owner: str,
    repo: str,
    cache: dict[str, dict],
    errors: dict[str, str],
) -> dict | None:
    key = f"{owner}/{repo}"
    if key in cache:
        return cache[key]
    try:
        data = fetch_json(f"https://api.github.com/repos/{owner}/{repo}")
        cache[key] = data
        return data
    except Exception as exc:  # noqa: BLE001
        errors[key] = str(exc)
        return None


def get_github_release_data(
    owner: str,
    repo: str,
    cache: dict[str, dict],
    errors: dict[str, str],
) -> dict | None:
    key = f"{owner}/{repo}"
    if key in cache:
        return cache[key]
    try:
        data = fetch_json(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
        cache[key] = data
        return data
    except Exception as exc:  # noqa: BLE001
        errors[key] = str(exc)
        return None


def main() -> int:
    sources = load_sources()
    state = load_state()
    now = dt.datetime.now(dt.timezone.utc)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"IMPROVEMENT-DISCOVERY-REPORT-{timestamp}.md"

    out_lines = [
        "# Improvement Discovery Report",
        f"**Date:** {timestamp}",
        "",
        "## Candidate Summary (Scored)",
        "",
    ]

    candidates: List[tuple[float, List[str]]] = []
    signals: List[str] = []
    skipped: List[str] = []
    skipped_urls: List[str] = []

    repo_cache: dict[str, dict] = {}
    release_cache: dict[str, dict] = {}
    repo_errors: dict[str, str] = {}
    release_errors: dict[str, str] = {}

    for source in sources:
        url = source.get("url", "")
        source_type = source.get("type", "unknown")
        weight = float(source.get("weight", 0.3))
        if not url:
            continue
        if not is_due(source, state, now):
            skipped.append(f"- {url} (not due)")
            skipped_urls.append(url)
            continue
        if source_type == "github_release":
            try:
                repo_tuple = parse_github_repo(url)
                if not repo_tuple:
                    continue
                owner, repo = repo_tuple
                repo_data = get_github_repo_data(owner, repo, repo_cache, repo_errors)
                release_data = get_github_release_data(owner, repo, release_cache, release_errors)
                if not repo_data:
                    raise ValueError(repo_errors.get(f"{owner}/{repo}", "Missing repo data"))
                score = score_github_repo(repo_data, release_data, weight)
                lines = [
                    f"- **Repo:** {owner}/{repo}",
                    f"- **Score:** {score}",
                    f"- **Latest release:** {release_data.get('name') or release_data.get('tag_name', 'N/A')}",
                    f"- **Release URL:** {release_data.get('html_url', 'N/A')}",
                    f"- **Stars:** {repo_data.get('stargazers_count', 'N/A')}",
                ]
                if score >= MIN_CANDIDATE_SCORE:
                    candidates.append((score, [url, *lines]))
            except Exception as exc:  # noqa: BLE001
                signals.append(f"- {url} (error: {exc})")
        elif source_type == "social":
            signals.append(f"- {url} (social signal; requires corroboration)")
        else:
            signals.append(f"- {url} (review manually)")

    rate_limit_hit = any(
        "rate limit exceeded" in err.lower()
        for err in list(repo_errors.values()) + list(release_errors.values())
    )
    if rate_limit_hit:
        out_lines.insert(2, "**Note:** GitHub rate limit exceeded; set `GITHUB_TOKEN` or `GH_TOKEN` and rerun.")
        out_lines.insert(3, "")

    if candidates:
        for score, lines in sorted(candidates, key=lambda x: x[0], reverse=True):
            out_lines.append(f"### {lines[0]}")
            out_lines.extend(lines[1:])
            out_lines.append("")
    else:
        out_lines.append("- No candidates met the score threshold.")
        out_lines.append("")

    out_lines.extend([
        "## Signals (Low-Trust)",
        "",
    ])
    out_lines.extend(signals or ["- None"])
    out_lines.append("")
    out_lines.append("## Skipped (Not Due)")
    out_lines.append("")
    out_lines.extend(skipped or ["- None"])
    out_lines.append("")

    out_lines.append("## Sources Reviewed")
    out_lines.append("")

    for source in sources:
        url = source.get("url", "")
        source_type = source.get("type", "unknown")
        weight = source.get("weight", 0.3)
        out_lines.append(f"### {url}")
        try:
            github_repo = parse_github_repo(url)
            if github_repo:
                owner, repo = github_repo
                cache_key = f"{owner}/{repo}"
                repo_error = repo_errors.get(cache_key)
                release_error = release_errors.get(cache_key)
                out_lines.append(f"- **Type:** {source_type}")
                out_lines.append(f"- **Weight:** {weight}")
                out_lines.extend(github_release_summary(release_cache.get(cache_key), release_error))
                if repo_error:
                    out_lines.append(f"- **Repo Error:** {repo_error}")
                elif cache_key in repo_cache:
                    out_lines.append(f"- **Stars:** {repo_cache[cache_key].get('stargazers_count', 'N/A')}")
            else:
                out_lines.append(f"- **Type:** {source_type}")
                out_lines.append(f"- **Weight:** {weight}")
                if source_type in {"social", "research", "discussion", "forum"}:
                    out_lines.append("- **Note:** Low-trust source; full crawl skipped")
                else:
                    html = fetch_url(url)
                    parser = LinkParser()
                    parser.feed(html)
                    title = parser.title.strip() or "Untitled"
                    out_lines.append(f"- **Title:** {title}")
                    filtered = filter_links(url, parser.links)
                    if filtered:
                        out_lines.append("- **Top Links:**")
                        for link in filtered:
                            out_lines.append(f"  - {link}")
                    else:
                        out_lines.append("- **Top Links:** None detected")
        except Exception as exc:  # noqa: BLE001
            out_lines.append(f"- **Error:** {exc}")
        out_lines.append("")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines))
    for source in sources:
        url = source.get("url", "")
        if url and url not in skipped_urls:
            state[url] = now.isoformat()
    save_state(state)
    print(f"Wrote discovery report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
