#!/usr/bin/env python3
"""
Reference curated RAG patterns/checklists.
"""

from __future__ import annotations

import argparse


TECHNIQUES = {
    "chunking": {
        "title": "Chunking & Metadata",
        "steps": [
            "Keep markdown chunks <= 512 tokens; include headings in chunk metadata.",
            "Store original relative paths so responses can cite exact files.",
            "Record git commit hash in metadata to detect stale embeddings.",
        ],
    },
    "routing": {
        "title": "Retriever Routing",
        "steps": [
            "Use keyword retrieval for config files, vector retrieval for prose-heavy docs.",
            "Fall back to ripgrep when embeddings return low scores (<0.3 cosine).",
            "Emit retrieval statistics (latency, hit rate) to monitoring dashboards.",
        ],
    },
    "hygiene": {
        "title": "Prompt Hygiene",
        "steps": [
            "Restate the user objective + retrieved facts in the system prompt.",
            "Ask the model to cite file paths when recommending code changes.",
            "Set explicit refusal policies so hallucinations get caught quickly.",
        ],
    },
    "evaluation": {
        "title": "RAG Evaluation",
        "steps": [
            "Log retrieved chunk IDs + scores for every completion.",
            "Use synthetic Q&A pairs derived from docs/ to measure precision & recall.",
            "Alert when hit rate drops below 80% or latency exceeds 500 ms.",
        ],
    },
}


def list_topics() -> None:
    print("Available RAG playbooks:")
    for key, spec in TECHNIQUES.items():
        print(f"- {key}: {spec['title']}")


def show_topic(key: str) -> int:
    topic = TECHNIQUES.get(key)
    if not topic:
        print(f"Unknown topic '{key}'. Run with --list to view options.")
        return 1
    print(topic["title"])
    for idx, step in enumerate(topic["steps"], 1):
        print(f"  {idx}. {step}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RAG reference helper")
    parser.add_argument("--list", action="store_true", help="List available topics")
    parser.add_argument("--show", choices=sorted(TECHNIQUES.keys()), help="Display a topic")
    args = parser.parse_args(argv)

    if args.list:
        list_topics()
        return 0

    if args.show:
        return show_topic(args.show)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
