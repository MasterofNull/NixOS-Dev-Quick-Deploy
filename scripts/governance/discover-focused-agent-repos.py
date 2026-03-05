#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SEEDS = [
    "cloudshipai/station",
    "CodebuffAI/codebuff",
    "badlogic/pi-mono",
]

QUERIES = [
    "coding agent cli mcp runtime in:name,description,readme archived:false is:public stars:40..30000 pushed:>=2025-06-01",
    "ai agent runtime self-hosted mcp in:name,description,readme archived:false is:public stars:40..30000 pushed:>=2025-06-01",
    "agent harness code execution in:name,description,readme archived:false is:public stars:20..20000 pushed:>=2025-06-01",
    "software engineering agent cli in:name,description,readme archived:false is:public stars:20..20000 pushed:>=2025-06-01",
    "open-source coding assistant terminal in:name,description,readme archived:false is:public stars:20..30000 pushed:>=2025-06-01",
]

EXCLUDED_OWNERS = {
    "openai",
    "anthropics",
    "microsoft",
    "google",
    "facebook",
    "meta",
    "aws",
    "github",
}

NOISE_PATTERNS = [
    "awesome",
    "curated list",
    "list of",
    "roadmap",
    "poc",
    "papers",
    "survey",
    "marketing",
    "make money",
]


def http_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nixos-dev-quick-deploy-focused-discovery",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def repo_text(r: dict) -> str:
    topics = " ".join(r.get("topics") or [])
    return " ".join(
        [
            r.get("full_name", ""),
            r.get("description") or "",
            topics,
            r.get("language") or "",
        ]
    ).strip()


def passes_intent_filter(r: dict) -> bool:
    text = repo_text(r).lower()
    if "agent" not in text:
        return False
    if not any(k in text for k in ["coding", "code", "runtime", "cli", "harness", "mcp", "toolkit"]):
        return False
    return True


def looks_noisy(r: dict) -> bool:
    name = r.get("full_name", "").lower()
    desc = (r.get("description") or "").lower()
    blob = f"{name} {desc}"
    return any(p in blob for p in NOISE_PATTERNS)


def main() -> int:
    today = dt.date.today().isoformat()
    out_json = f"data/github-focused-agent-repos-{today}.json"
    out_md = f"data/github-focused-agent-repos-{today}.md"

    # Seed metadata
    seed_repos = []
    for s in SEEDS:
        data = http_json(f"https://api.github.com/repos/{s}")
        seed_repos.append(
            {
                "full_name": data["full_name"],
                "html_url": data["html_url"],
                "description": data.get("description"),
                "language": data.get("language"),
                "topics": data.get("topics") or [],
                "stargazers_count": data.get("stargazers_count", 0),
                "updated_at": data.get("updated_at"),
            }
        )
        time.sleep(0.5)

    candidates = {}
    query_rows = []
    for q in QUERIES:
        enc = urllib.parse.quote(q)
        url = f"https://api.github.com/search/repositories?q={enc}&sort=stars&order=desc&per_page=50"
        payload = http_json(url)
        items = payload.get("items", [])
        query_rows.append({"query": q, "count": len(items)})
        for it in items:
            owner = it["full_name"].split("/")[0].lower()
            if owner in EXCLUDED_OWNERS:
                continue
            if it["full_name"] in SEEDS:
                continue
            repo = {
                "full_name": it["full_name"],
                "html_url": it.get("html_url"),
                "description": it.get("description"),
                "language": it.get("language"),
                "topics": it.get("topics") or [],
                "stargazers_count": it.get("stargazers_count", 0),
                "updated_at": it.get("updated_at"),
                "matched_queries": [],
            }
            if looks_noisy(repo):
                continue
            if not passes_intent_filter(repo):
                continue
            prev = candidates.get(repo["full_name"])
            if prev is None:
                candidates[repo["full_name"]] = repo
                prev = repo
            prev["stargazers_count"] = max(prev["stargazers_count"], repo["stargazers_count"])
            prev["matched_queries"].append(q)
        time.sleep(1.0)

    cand_list = list(candidates.values())
    docs = [repo_text(r) for r in cand_list]
    seed_docs = [repo_text(r) for r in seed_repos]

    vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1, max_df=0.9, stop_words="english")
    x_all = vec.fit_transform(docs + seed_docs)
    x_repos = x_all[: len(docs)]
    x_seeds = x_all[len(docs) :]
    sims = cosine_similarity(x_repos, x_seeds)

    ranked = []
    for i, r in enumerate(cand_list):
        sim_max = float(sims[i].max())
        sim_avg = float(sims[i].mean())
        # Balanced score: prioritize semantic similarity while keeping active/popular projects visible.
        stars = r["stargazers_count"]
        star_component = min(1.0, (stars / 10000.0))
        score = (0.72 * sim_max) + (0.20 * sim_avg) + (0.08 * star_component)
        ranked.append(
            {
                **r,
                "semantic_seed_max": round(sim_max, 6),
                "semantic_seed_avg": round(sim_avg, 6),
                "focused_score": round(score, 6),
                "matched_queries": sorted(set(r["matched_queries"])),
            }
        )

    ranked.sort(key=lambda r: r["focused_score"], reverse=True)
    top = ranked[:45]

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "seeds": seed_repos,
        "queries": query_rows,
        "candidate_count": len(cand_list),
        "top": top,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    lines = []
    lines.append("# Focused Agent Repo Discovery (Seed-Similarity)")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now().isoformat()}")
    lines.append("")
    lines.append("Seeds:")
    for s in seed_repos:
        lines.append(f"- `{s['full_name']}` ({s['stargazers_count']} stars)")
    lines.append("")
    lines.append("| Rank | Repo | Stars | Updated | Focused score | Seed sim max |")
    lines.append("|---|---|---:|---|---:|---:|")
    for idx, r in enumerate(top, start=1):
        upd = (r.get("updated_at") or "")[:10]
        lines.append(
            f"| {idx} | [{r['full_name']}]({r['html_url']}) | {r['stargazers_count']} | "
            f"{upd} | {r['focused_score']:.4f} | {r['semantic_seed_max']:.4f} |"
        )
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
