#!/usr/bin/env python3
"""aq-context-packet — Zero-token deterministic Surgical Context Packet compiler (Slice F1).

Builds a <=2,500-token surgical context slice for Tier-1 (Local System 1) and Tier-2
(Pooled Subscription) implementer dispatches in <200ms on laptop CPU using:
  1. Python AST symbol extraction (exact target function/class bodies or signature fallback)
  2. .understand-anything/knowledge-graph.json caller/callee blast-radius edges
  3. Compiler-verified 1-shot trajectory exemplar injection (<=400 tokens, for local System 1)

Zero LLM tokens. Stdlib-only execution.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

def _find_repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    for parent in (cur, *cur.parents):
        if (parent / "flake.nix").is_file() or (parent / ".git").exists():
            return parent
    return Path.cwd()


REPO = _find_repo_root()
GRAPH_PATH = REPO / ".understand-anything" / "knowledge-graph.json"
TRAJECTORIES_PATH = Path("/var/lib/ai-stack/hybrid/distillation/trajectories.jsonl")
CHARS_PER_TOKEN = 4  # conservative deterministic estimate


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _extract_python_symbols(path: Path, wanted_symbols: list[str], signatures_only: bool = False) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"# ERROR reading {path}: {exc}\n"

    lines = src.splitlines()
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        snippet = "\n".join(lines[:60])
        return f"# {path.relative_to(REPO)} (raw head, non-Python or syntax error)\n{snippet}\n"

    blocks: list[str] = []
    wanted_set = set(wanted_symbols)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if wanted_set and node.name not in wanted_set:
                continue
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            if signatures_only:
                sig_line = lines[start - 1] if 1 <= start <= len(lines) else node.name
                doc = ast.get_docstring(node)
                doc_summary = f'  """{doc.splitlines()[0]}"""' if doc else ""
                blocks.append(f"L{start}-L{end}: {sig_line}\n{doc_summary}".rstrip())
            else:
                body = "\n".join(lines[start - 1 : end])
                blocks.append(f"# L{start}-L{end}\n{body}")
    if not blocks and not signatures_only:
        return _extract_python_symbols(path, [], signatures_only=True)
    return "\n\n".join(blocks)


def _graph_neighbors(rel_path: str) -> list[str]:
    if not GRAPH_PATH.is_file():
        return []
    try:
        data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    edges = data.get("edges", []) if isinstance(data, dict) else []
    neighbors: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("source", ""))
        tgt = str(edge.get("target", ""))
        rel = str(edge.get("relation", edge.get("type", "calls")))
        if rel_path in src and tgt:
            neighbors.append(f"out ({rel}) -> {tgt}")
        elif rel_path in tgt and src:
            neighbors.append(f"in  ({rel}) <- {src}")
        if len(neighbors) >= 8:
            break
    return neighbors


def _best_verified_exemplar(task: str, max_tokens: int = 400) -> str:
    if not TRAJECTORIES_PATH.is_file():
        return ""
    task_words = {w.lower() for w in task.split() if len(w) > 3}
    best_score = -1
    best_rec: dict[str, Any] | None = None
    try:
        lines = TRAJECTORIES_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except OSError:
        return ""
    for raw in lines:
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if not isinstance(rec, dict) or rec.get("review_disposition") not in ("PASS", "PASS_WITH_FOLLOWUPS"):
            continue
        hay = f"{rec.get('task', '')} {' '.join(rec.get('paths', []))}".lower()
        score = sum(1 for w in task_words if w in hay)
        if score > best_score:
            best_score = score
            best_rec = rec
    if not best_rec:
        return ""
    diff_preview = str(best_rec.get("verified_diff", ""))[: max_tokens * CHARS_PER_TOKEN]
    return (
        f"## Verified 1-Shot Exemplar ({best_rec.get('id', 'verified')})\n"
        f"- Task: {best_rec.get('task', '')}\n"
        f"```diff\n{diff_preview}\n```\n"
    )


def build_packet(
    task: str,
    specs: list[str],
    *,
    max_tokens: int = 2500,
    include_exemplar: bool = False,
) -> dict[str, Any]:
    exemplar_budget = 400 if include_exemplar else 0
    code_budget = max(100, max_tokens - exemplar_budget - 100)

    sections: list[str] = [f"# Surgical Context Packet\n- **Task**: {task}\n"]
    neighbor_lines: list[str] = []
    file_entries: list[tuple[Path, str, list[str]]] = []

    for spec in specs:
        parts = spec.split(":")
        rel = parts[0]
        syms = [s for s in parts[1:] if s]
        p = (REPO / rel).resolve()
        file_entries.append((p, rel, syms))
        neighbor_lines.extend(_graph_neighbors(rel))

    if neighbor_lines:
        sections.append("## Call-Graph Blast Radius\n" + "\n".join(f"- `{n}`" for n in neighbor_lines[:8]) + "\n")

    # Pass 1: full symbol bodies
    code_chunks: list[str] = []
    for p, rel, syms in file_entries:
        if p.suffix == ".py" and p.is_file():
            chunk = _extract_python_symbols(p, syms, signatures_only=False)
        elif p.is_file():
            raw_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:80]
            chunk = "\n".join(raw_lines)
        else:
            chunk = "# (file does not exist yet)"
        code_chunks.append(f"## `{rel}`\n```python\n{chunk}\n```\n")

    joined_code = "\n".join(code_chunks)
    degraded_to_signatures = False
    if _estimate_tokens(joined_code) > code_budget:
        # Automatic AST signature fallback to stay strictly within budget
        degraded_to_signatures = True
        sig_chunks: list[str] = []
        for p, rel, syms in file_entries:
            if p.suffix == ".py" and p.is_file():
                chunk = _extract_python_symbols(p, syms, signatures_only=True)
            elif p.is_file():
                chunk = "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[:30])
            else:
                chunk = "# (new file)"
            sig_chunks.append(f"## `{rel}` (AST signatures — budget fallback)\n```python\n{chunk}\n```\n")
        joined_code = "\n".join(sig_chunks)
        if _estimate_tokens(joined_code) > code_budget:
            joined_code = joined_code[: code_budget * CHARS_PER_TOKEN]

    sections.append(joined_code)

    if include_exemplar:
        ex = _best_verified_exemplar(task, max_tokens=exemplar_budget)
        if ex:
            sections.append(ex)

    markdown = "\n".join(sections)
    tokens = _estimate_tokens(markdown)
    return {
        "task": task,
        "paths": specs,
        "max_tokens": max_tokens,
        "estimated_tokens": tokens,
        "degraded_to_signatures": degraded_to_signatures,
        "markdown": markdown,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="Bounded slice task description")
    ap.add_argument("--paths", nargs="+", required=True, help="rel/path.py[:symbol1[:symbol2]]")
    ap.add_argument("--max-tokens", type=int, default=2500, help="Token ceiling (default 2500)")
    ap.add_argument("--system1-exemplar", action="store_true", help="Reserve <=400t for 1-shot verified exemplar")
    ap.add_argument("--json", action="store_true", help="Emit JSON metadata + markdown")
    args = ap.parse_args(argv)

    pkt = build_packet(
        args.task,
        args.paths,
        max_tokens=args.max_tokens,
        include_exemplar=args.system1_exemplar,
    )
    if args.json:
        print(json.dumps(pkt, indent=2))
    else:
        sys.stdout.write(pkt["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
