"""capability_index — deterministic agent-loaded index of existing capabilities.

Input : a capability-audit report (capability-audit/1 JSON).
Output: docs/agent-guides/CAPABILITY-INDEX.md (compact, grouped by category) and
        config/capability-index.json (machine form).
Every capability NOT classified DEAD-CANDIDATE is listed, except kinds that are
not invocable tools (artifact, catalog claims). Purposes are read STATICALLY
(module docstring / leading comment / SKILL.md description) — no script is run.
Pure function of (audit report, repo files): no timestamps, stable ordering.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = "capability-index/1"
EXCLUDE_CLASSES = {"DEAD-CANDIDATE"}
EXCLUDE_KINDS = {"artifact", "catalog"}
MAX_BYTES = 40_000
PURPOSE_MAX = {"script": 78, "skill": 70, "mcp-tool": 78}

# First matching category wins; order is the display order.
CATEGORIES: List[tuple] = [
    ("Capability, audit and reuse", ("capability", "audit", "inventory", "catalog")),
    ("Hints, context and memory", ("hint", "context", "memory", "recall", "handoff", "resume", "session", "compact", "prime")),
    ("Search, RAG and knowledge", ("rag", "search", "query", "embed", "knowledge", "wiki", "aidb", "qdrant", "retriev", "index")),
    ("QA, health and monitoring", ("qa", "health", "monitor", "check", "smoke", "status", "diagnos", "probe", "alert", "dashboard", "report", "metric")),
    ("Agents, delegation and loops", ("agent", "delegat", "loop", "orchestr", "dispatch", "swarm", "codex", "gemini", "antigravity", "local", "consensus", "review", "a2a")),
    ("Workflow, planning and PM", ("workflow", "plan", "prd", "slice", "tracker", "pm-", "sop", "lifecycle", "task")),
    ("Models and inference", ("model", "llama", "llm", "inference", "prompt", "train", "eval", "bench", "cascade", "qwen")),
    ("NixOS, deploy and system", ("nix", "deploy", "flake", "system", "service", "systemd", "boot", "rebuild", "update", "install", "unit")),
    ("Security, approval and governance", ("secur", "approv", "policy", "guard", "lease", "gate", "govern", "scan", "vuln", "secret", "sign", "audit-")),
    ("Git, commit and release", ("git", "commit", "branch", "pr-", "release", "merge", "worktree")),
    ("MCP tools", ("mcp",)),
]
DEFAULT_CATEGORY = "Other tools"
UNIT_CATEGORY = "Systemd units (services and timers)"


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except OSError:
        return ""


def _clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _strip_name_prefix(line: str, name: str) -> str:
    # "aq-foo - does X" / "aq-foo: does X" / "foo.py — does X" -> "does X"
    m = re.match(r"^[`\w./-]+\s*(?:--|[—–:-])\s+(.*)$", line)
    if m and (name in line.split()[0] or line.split()[0].lower().startswith(("aq", name.split(".")[0].lower()))):
        return m.group(1)
    return line


def _usable(text: str, name: str) -> bool:
    t = text.strip().strip("`")
    return len(t) >= 12 and t.lower() != name.lower() and not re.match(r"^phase [\d.]+\S*\.?$", t, re.I)


def purpose_from_script(path: Path, name: str) -> str:
    text = _read(path)
    if not text:
        return ""
    first = text.splitlines()[0] if text else ""
    if "python" in first:
        try:
            doc = ast.get_docstring(ast.parse(text)) or ""
        except (SyntaxError, ValueError):
            doc = ""
        for ln in doc.splitlines()[:6]:
            cand = _strip_name_prefix(ln.strip(), name)
            if _usable(cand, name):
                return cand
        return ""
    for ln in text.splitlines()[1:40]:
        s = ln.strip()
        if not s.startswith("#"):
            if s and not s.startswith(("set ", ".", "source ")):
                break
            continue
        body = s.lstrip("#").strip()
        if not body or re.match(r"^(shellcheck|aq-usage-hook|!|-\*-|=+$|-+$|─+)", body) or "aq-shim" in body:
            continue
        cand = _strip_name_prefix(body, name)
        if _usable(cand, name):
            return cand
    return ""


def purpose_from_skill(path: Path) -> str:
    text = _read(path)
    m = re.search(r"^description:\s*(.+)$", text, re.M)
    if m:
        return m.group(1).strip().strip("\"'")
    for ln in text.splitlines():
        s = ln.strip()
        if s and not s.startswith(("#", "---")):
            return s
    return ""


def mcp_descriptions(root: Path) -> Dict[str, str]:
    p = root / "scripts" / "ai" / "mcp-bridge-hybrid.py"
    out: Dict[str, str] = {}
    try:
        tree = ast.parse(_read(p))
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            kv = {k.value: v.value for k, v in zip(node.keys, node.values)
                  if isinstance(k, ast.Constant) and isinstance(v, ast.Constant) and isinstance(v.value, str)}
            if "name" in kv and "description" in kv:
                out.setdefault(kv["name"], kv["description"])
    return out


def categorize(name: str, purpose: str, kind: str) -> str:
    if kind == "mcp-tool":
        return "MCP tools"
    if kind == "unit":
        return UNIT_CATEGORY
    hay = (name + " " + purpose).lower()
    nm = name.lower()
    for cat, kws in CATEGORIES:
        if any(k in nm for k in kws):
            return cat
    for cat, kws in CATEGORIES:
        if any(k in hay for k in kws):
            return cat
    return DEFAULT_CATEGORY


def primary_kind(kinds: List[str]) -> str:
    for k in ("script", "skill", "mcp-tool", "unit"):
        if k in kinds:
            return k
    return kinds[0] if kinds else "other"


def build_index(audit: Dict[str, Any], root: Path, source: str = "") -> Dict[str, Any]:
    mcp_desc = mcp_descriptions(root)
    entries: List[Dict[str, Any]] = []
    for row in audit.get("capabilities", []):
        if row.get("class") in EXCLUDE_CLASSES:
            continue
        kinds = list(row.get("kinds", []))
        if not kinds or set(kinds) <= EXCLUDE_KINDS:
            continue
        kind = primary_kind(kinds)
        name = row["name"]
        paths = row.get("paths", [])
        purpose = ""
        if kind == "script" and paths:
            purpose = purpose_from_script(root / paths[0], name)
        elif kind == "skill" and paths:
            purpose = purpose_from_skill(root / paths[0])
        elif kind == "mcp-tool":
            purpose = mcp_desc.get(name, "")
        purpose = _clip(purpose, PURPOSE_MAX.get(kind, 78)) if kind != "unit" else ""
        entries.append({
            "name": name, "kind": kind, "purpose": purpose,
            "category": categorize(name, purpose, kind),
            "class": row.get("class", ""), "path": paths[0] if paths else "",
        })
    entries.sort(key=lambda e: (e["category"], e["kind"], e["name"]))
    return {
        "schema": SCHEMA,
        "source_audit": source,
        "audit_window_days": audit.get("window_days"),
        "excluded_classes": sorted(EXCLUDE_CLASSES),
        "count": len(entries),
        "entries": entries,
    }


def _cat_order(cats: List[str]) -> List[str]:
    order = [c for c, _ in CATEGORIES] + [DEFAULT_CATEGORY, UNIT_CATEGORY]
    return sorted(cats, key=lambda c: order.index(c) if c in order else len(order))


def render_markdown(idx: Dict[str, Any]) -> str:
    ents = idx["entries"]
    cats: Dict[str, List[Dict[str, Any]]] = {}
    for e in ents:
        cats.setdefault(e["category"], []).append(e)
    L = [
        "# Capability Index",
        "",
        "Check here for an EXISTING tool before writing new code. Grep for your keyword; read only the matching rows.",
        f"Generated by `scripts/ai/aq-capability-index` from the capability audit ({idx['source_audit'] or 'live run'}); "
        f"{idx['count']} entries, DEAD-CANDIDATE and non-invocable (artifact/catalog) capabilities excluded. "
        "Machine form: `config/capability-index.json`. Class: A=ACTIVE, U=UNUSED-AVAILABLE, "
        "X=UNDISCOVERABLE, S=STALE-CLAIM, K=ACKNOWLEDGED (kept claim, documented), D=KEEP-DECLARED (host/profile-specific or operator-run), B=BROKEN. Kind: sc=script (aq-* run via PATH), sk=skill, mcp=MCP tool.",
        "",
    ]
    abbr = {"ACTIVE": "A", "UNUSED-AVAILABLE": "U", "UNDISCOVERABLE": "X", "STALE-CLAIM": "S", "ACKNOWLEDGED": "K", "KEEP-DECLARED": "D", "BROKEN": "B"}
    kab = {"script": "sc", "skill": "sk", "mcp-tool": "mcp", "unit": "unit"}
    for cat in _cat_order(list(cats)):
        items = cats[cat]
        L.append(f"## {cat} ({len(items)})")
        if cat == UNIT_CATEGORY:
            L.append(", ".join(f"{e['name']}[{abbr.get(e['class'], '?')}]" for e in items))
        else:
            for e in items:
                p = f" — {e['purpose']}" if e["purpose"] else ""
                L.append(f"- `{e['name']}` {kab.get(e['kind'], e['kind'])}/{abbr.get(e['class'], '?')}{p}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def newest_audit(root: Path) -> Optional[Path]:
    reports = sorted((root / ".agents" / "reports").glob("capability-audit-*.json"))
    return reports[-1] if reports else None
