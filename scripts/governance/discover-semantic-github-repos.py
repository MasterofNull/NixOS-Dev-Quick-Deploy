#!/usr/bin/env python3
"""
Discover GitHub repositories for coding-agent keywords, then rank results using
semantic nearest-neighbor scoring with LSA embeddings + cosine similarity.

Outputs:
  - data/github-semantic-keyword-repos-YYYY-MM-DD.json
  - data/github-semantic-keyword-repos-YYYY-MM-DD.md
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import sys
import urllib.parse
import urllib.request
import time

from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


KEYWORDS = [
    "ai harness",
    "coding agent",
    "coding harness",
    "ai coding assistant",
    "autonomous coding agent",
    "llm coding agent",
    "agentic coding",
    "software engineering agent",
]

CANDIDATES_PER_KEYWORD = 60
TOP_K_PER_KEYWORD = 12
PAGES_PER_KEYWORD = 6


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "nixos-dev-quick-deploy-semantic-discovery",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _strip_tags(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _parse_repositories(page_html: str) -> list[dict]:
    # Parse one search result block at a time.
    blocks = re.findall(
        r'(<div class="Box-sc-62in7e-0 fXzjPH">.*?</ul></div>)',
        page_html,
        flags=re.DOTALL,
    )
    out: list[dict] = []
    for block in blocks:
        m_name = re.search(r'href="/([^"/]+/[^"/]+)"', block)
        m_star = re.search(r'aria-label="([0-9,]+) stars"', block)
        m_desc = re.search(
            r'<span class="Text__StyledText[^"]*search-match[^"]*">(.*?)</span>',
            block,
            flags=re.DOTALL,
        )
        m_lang = re.search(r'aria-label="([^"]+) language"', block)
        if not (m_name and m_star):
            continue
        full_name = m_name.group(1)
        stars = int(m_star.group(1).replace(",", ""))
        desc = _strip_tags(m_desc.group(1)) if m_desc else ""
        lang = m_lang.group(1) if m_lang else ""
        out.append(
            {
                "full_name": full_name,
                "html_url": f"https://github.com/{full_name}",
                "description": desc,
                "language": lang,
                "stargazers_count": stars,
                "updated_at": None,
                "topics": [],
            }
        )
    return out


def _search_keyword(keyword: str) -> list[dict]:
    enc = urllib.parse.quote_plus(keyword)
    collected: list[dict] = []
    for p in range(1, PAGES_PER_KEYWORD + 1):
        url = (
            "https://github.com/search"
            f"?o=desc&q={enc}&s=stars&type=repositories&p={p}"
        )
        page = _http_get_text(url)
        parsed = _parse_repositories(page)
        if not parsed:
            break
        collected.extend(parsed)
        if len(collected) >= CANDIDATES_PER_KEYWORD:
            break
        time.sleep(1.5)
    return collected[:CANDIDATES_PER_KEYWORD]


def _repo_text(item: dict) -> str:
    full_name = item.get("full_name", "")
    desc = item.get("description") or ""
    topics = " ".join(item.get("topics") or [])
    language = item.get("language") or ""
    return f"{full_name} {desc} {topics} {language}".strip()


def main() -> int:
    date_str = dt.date.today().isoformat()
    out_json = f"data/github-semantic-keyword-repos-{date_str}.json"
    out_md = f"data/github-semantic-keyword-repos-{date_str}.md"

    raw_by_keyword: dict[str, list[dict]] = {}
    merged: dict[str, dict] = {}

    for kw in KEYWORDS:
        try:
            items = _search_keyword(kw)
        except Exception as exc:  # noqa: BLE001
            print(f"error fetching '{kw}': {exc}", file=sys.stderr)
            return 2
        raw_by_keyword[kw] = items
        for it in items:
            full_name = it["full_name"]
            if full_name not in merged:
                merged[full_name] = {
                    "full_name": full_name,
                    "html_url": it.get("html_url"),
                    "description": it.get("description"),
                    "language": it.get("language"),
                    "stargazers_count": it.get("stargazers_count", 0),
                    "updated_at": it.get("updated_at"),
                    "topics": it.get("topics") or [],
                    "matched_keywords": set(),
                }
            merged[full_name]["matched_keywords"].add(kw)
            merged[full_name]["stargazers_count"] = max(
                merged[full_name]["stargazers_count"], it.get("stargazers_count", 0)
            )
        time.sleep(2.0)

    all_repos = list(merged.values())
    docs = [_repo_text(r) for r in all_repos]

    vec = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
        sublinear_tf=True,
    )
    x = vec.fit_transform(docs)
    n_components = max(2, min(200, x.shape[1] - 1, x.shape[0] - 1))
    if n_components >= 2:
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        emb = svd.fit_transform(x)
    else:
        emb = x.toarray()

    # Prepare global star normalization for diversity re-rank.
    star_vals = [r["stargazers_count"] for r in all_repos]
    max_log_star = math.log1p(max(star_vals) if star_vals else 1)

    per_keyword_top: dict[str, list[dict]] = {}
    top_union = {}
    for kw in KEYWORDS:
        qv = vec.transform([kw])
        if n_components >= 2:
            q_emb = svd.transform(qv)
        else:
            q_emb = qv.toarray()
        sims = cosine_similarity(emb, q_emb).reshape(-1)

        scored = []
        for i, repo in enumerate(all_repos):
            sim = float(sims[i])
            stars = repo["stargazers_count"]
            star_norm = (math.log1p(stars) / max_log_star) if max_log_star > 0 else 0.0
            # Blend relevance with anti-size bias so smaller high-relevance repos survive.
            rerank = (0.80 * sim) + (0.20 * (1.0 - star_norm))
            scored.append(
                {
                    **repo,
                    "matched_keywords": sorted(repo["matched_keywords"]),
                    "semantic_score": round(sim, 6),
                    "diversified_score": round(rerank, 6),
                }
            )
        scored.sort(key=lambda r: r["diversified_score"], reverse=True)
        top = scored[:TOP_K_PER_KEYWORD]
        per_keyword_top[kw] = top
        for r in top:
            top_union[r["full_name"]] = r

    union_sorted = sorted(
        top_union.values(),
        key=lambda r: (r["diversified_score"], r["semantic_score"], r["stargazers_count"]),
        reverse=True,
    )

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": "semantic-nearest-neighbor",
        "embedding": "tfidf-bigram + truncated-svd (LSA)",
        "ranking": "cosine similarity + star-diversity rerank",
        "keywords": KEYWORDS,
        "candidates_per_keyword": CANDIDATES_PER_KEYWORD,
        "pages_per_keyword": PAGES_PER_KEYWORD,
        "top_k_per_keyword": TOP_K_PER_KEYWORD,
        "unique_candidates": len(all_repos),
        "per_keyword_top": per_keyword_top,
        "union_top": union_sorted,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=True)

    lines = []
    lines.append("# GitHub Semantic NN Discovery (Keyword-Based)")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now().isoformat()}")
    lines.append(
        "Method: semantic nearest-neighbor (TF-IDF + LSA) with diversity re-rank to avoid star-only bias"
    )
    lines.append("")
    lines.append("## Union Top Repos")
    lines.append("")
    lines.append("| Rank | Repo | Stars | Semantic | Diversified | Matched keywords |")
    lines.append("|---|---|---:|---:|---:|---|")
    for idx, r in enumerate(union_sorted[:80], start=1):
        kws = ", ".join(r["matched_keywords"])
        lines.append(
            f"| {idx} | [{r['full_name']}]({r['html_url']}) | {r['stargazers_count']} | "
            f"{r['semantic_score']:.4f} | {r['diversified_score']:.4f} | {kws} |"
        )
    lines.append("")
    lines.append("## Top 12 Per Keyword")
    lines.append("")
    for kw in KEYWORDS:
        lines.append(f"### {kw}")
        lines.append("")
        lines.append("| Rank | Repo | Stars | Semantic | Diversified |")
        lines.append("|---|---|---:|---:|---:|")
        for idx, r in enumerate(per_keyword_top[kw], start=1):
            lines.append(
                f"| {idx} | [{r['full_name']}]({r['html_url']}) | {r['stargazers_count']} | "
                f"{r['semantic_score']:.4f} | {r['diversified_score']:.4f} |"
            )
        lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
