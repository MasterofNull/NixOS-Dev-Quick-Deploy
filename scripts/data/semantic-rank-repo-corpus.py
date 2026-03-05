#!/usr/bin/env python3
"""
Semantic nearest-neighbor ranking over an existing repo corpus.

Input:
  data/github-keyword-repos-YYYY-MM-DD.json
Output:
  data/github-semantic-keyword-repos-YYYY-MM-DD.json
  data/github-semantic-keyword-repos-YYYY-MM-DD.md
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
import urllib.request
from pathlib import Path

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
TOP_K_PER_KEYWORD = 15
README_CHAR_LIMIT = 1800


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nixos-dev-quick-deploy-semantic-ranking"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fetch_readme(owner_repo: str) -> str:
    owner, repo = owner_repo.split("/", 1)
    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/readme.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/readme.md",
    ]
    for url in candidates:
        try:
            txt = _fetch_text(url)
            if txt.strip():
                return txt[:README_CHAR_LIMIT]
        except Exception:  # noqa: BLE001
            continue
    return ""


def _clean_text(text: str) -> str:
    t = re.sub(r"`[^`]+`", " ", text)
    t = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", t)
    t = re.sub(r"#+", " ", t)
    t = re.sub(r"[^A-Za-z0-9_./ -]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def main() -> int:
    date_str = dt.date.today().isoformat()
    in_path = Path(f"data/github-keyword-repos-{date_str}.json")
    out_json = Path(f"data/github-semantic-keyword-repos-{date_str}.json")
    out_md = Path(f"data/github-semantic-keyword-repos-{date_str}.md")
    if not in_path.exists():
        raise SystemExit(f"missing input corpus: {in_path}")

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    repos = payload["repos"]

    enriched = []
    for repo in repos:
        readme = _fetch_readme(repo["full_name"])
        time.sleep(0.2)
        text = _clean_text(
            " ".join(
                [
                    repo["full_name"],
                    " ".join(repo.get("matched_keywords", [])),
                    readme,
                ]
            )
        )
        enriched.append({**repo, "readme_excerpt": readme[:500], "semantic_text": text})

    docs = [r["semantic_text"] for r in enriched]
    vec = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
        sublinear_tf=True,
        stop_words="english",
    )
    x = vec.fit_transform(docs)
    n_components = max(2, min(180, x.shape[1] - 1, x.shape[0] - 1))
    if n_components >= 2:
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        emb = svd.fit_transform(x)
    else:
        svd = None
        emb = x.toarray()

    stars = [r.get("stargazers_count", 0) for r in enriched]
    max_log = math.log1p(max(stars) if stars else 1)

    per_keyword = {}
    union = {}
    for kw in KEYWORDS:
        q = vec.transform([kw])
        q_emb = svd.transform(q) if svd is not None else q.toarray()
        sims = cosine_similarity(emb, q_emb).reshape(-1)

        ranked = []
        for i, r in enumerate(enriched):
            sim = float(sims[i])
            s_norm = (math.log1p(r["stargazers_count"]) / max_log) if max_log > 0 else 0.0
            diversified = (0.78 * sim) + (0.22 * (1.0 - s_norm))
            ranked.append(
                {
                    "full_name": r["full_name"],
                    "html_url": r["html_url"],
                    "stargazers_count": r["stargazers_count"],
                    "matched_keywords": r.get("matched_keywords", []),
                    "semantic_score": round(sim, 6),
                    "diversified_score": round(diversified, 6),
                }
            )
        ranked.sort(key=lambda r: r["diversified_score"], reverse=True)
        top = ranked[:TOP_K_PER_KEYWORD]
        per_keyword[kw] = top
        for it in top:
            union[it["full_name"]] = it

    union_sorted = sorted(
        union.values(),
        key=lambda r: (r["diversified_score"], r["semantic_score"], r["stargazers_count"]),
        reverse=True,
    )

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": "semantic-nearest-neighbor-from-corpus",
        "embedding": "tfidf-bigram + truncated-svd (LSA)",
        "rerank": "cosine + star-diversity",
        "keywords": KEYWORDS,
        "top_k_per_keyword": TOP_K_PER_KEYWORD,
        "source_corpus_file": str(in_path),
        "source_unique_repos": len(repos),
        "per_keyword_top": per_keyword,
        "union_top": union_sorted,
    }
    out_json.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = []
    lines.append("# GitHub Semantic NN Discovery (From Local Corpus)")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now().isoformat()}")
    lines.append(f"Source corpus: `{in_path}`")
    lines.append("Method: TF-IDF + LSA semantic nearest-neighbor with size-diversity rerank")
    lines.append("")
    lines.append("## Top 15 Per Keyword")
    lines.append("")
    for kw in KEYWORDS:
        lines.append(f"### {kw}")
        lines.append("")
        lines.append("| Rank | Repo | Stars | Semantic | Diversified |")
        lines.append("|---|---|---:|---:|---:|")
        for i, r in enumerate(per_keyword[kw], start=1):
            lines.append(
                f"| {i} | [{r['full_name']}]({r['html_url']}) | {r['stargazers_count']} | "
                f"{r['semantic_score']:.4f} | {r['diversified_score']:.4f} |"
            )
        lines.append("")

    lines.append("## Union Top")
    lines.append("")
    lines.append("| Rank | Repo | Stars | Semantic | Diversified |")
    lines.append("|---|---|---:|---:|---:|")
    for i, r in enumerate(union_sorted[:80], start=1):
        lines.append(
            f"| {i} | [{r['full_name']}]({r['html_url']}) | {r['stargazers_count']} | "
            f"{r['semantic_score']:.4f} | {r['diversified_score']:.4f} |"
        )
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
