"""Deterministic capability-integration audit (no LLM, read-only).

Inventories every capability the harness ships (catalog entries, scripts/ai
executables, skills, MCP tools, systemd units, generated artifacts), gathers
boolean evidence per capability (discoverable / used / wired / tested / stale /
dead), classifies it and attaches an advisory next_action.  Nothing here
deletes, moves or edits anything (Rule 12); `archive-candidate` is advice only.
"""

from __future__ import annotations

import ast
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

CLASSES = ("ACTIVE", "UNUSED-AVAILABLE", "UNDISCOVERABLE", "STALE-CLAIM", "ACKNOWLEDGED", "STALE-ARTIFACT",
           "DEAD-CANDIDATE", "KEEP-DECLARED", "BROKEN")
AUDIT_VERSION = 3  # bump when classification rules change; the RSI adapter skips cross-version comparison
NEXT_ACTION = {
    "ACTIVE": "none",
    "UNUSED-AVAILABLE": "integrate-into-repertoire",
    "UNDISCOVERABLE": "add-discovery",
    "STALE-CLAIM": "refresh",
    "ACKNOWLEDGED": "none",
    "STALE-ARTIFACT": "regenerate",
    "DEAD-CANDIDATE": "archive-candidate",
    "KEEP-DECLARED": "none",
    "BROKEN": "fix",
}
LIVE_CLAIM_STATES = {"enabled", "active", "on"}
# Only these maturities assert "integrated and in use". available-unused / partial / enabled-unmeasured /
# scope-gated / quarantined are honest non-claims and can never be a STALE-CLAIM.
LIVE_CLAIM_MATURITY = {"integrated", "production", "official"}
GRAPH_ARTIFACT = ".understand-anything/knowledge-graph.json"
_GRAPH_MAX_AGE_FALLBACK = 14  # used only when config/understand-anything.json is unreadable


def artifact_refresh_days(repo_root: Path) -> Dict[str, float]:
    """Artifact path (relative to live root) -> max age in days before it is stale.

    The graph limit lives in config/understand-anything.json (staleness.max_age_days)
    so aq-graph-query staleness, phase-0 0.10.59 and this audit share one number.
    """
    days: float = _GRAPH_MAX_AGE_FALLBACK
    try:
        raw = json.loads((Path(repo_root) / "config" / "understand-anything.json").read_text(encoding="utf-8"))
        value = raw["staleness"]["max_age_days"]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            days = value
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {GRAPH_ARTIFACT: days}

CODE_EXT = {".py", ".sh", ".nix", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".html", ".bash", ".rs"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "archive", ".venv", "target"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-/]*")
EXT_STRIP = (".py", ".sh", ".nix", ".json", ".js", ".ts", ".md", ".yaml", ".yml", ".bash")
MAX_FILE = 1_500_000


def load_triage(root: Path) -> Dict[str, str]:
    """config/capability-triage.json -> {normalized key: reason} for deliberately-kept
    capabilities the usage/wiring heuristics cannot see (other hosts/profiles, hooks
    outside the scanned trees, operator-run tools).  Missing/invalid file -> {}."""
    try:
        data = json.loads((root / "config" / "capability-triage.json").read_text())
        return {norm(e["name"]): str(e.get("reason", "")) for e in data.get("keep", []) if e.get("name")}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def norm(name: str) -> str:
    n = str(name).strip().lower().replace("_", "-")
    for ext in EXT_STRIP:
        if n.endswith(ext):
            n = n[: -len(ext)]
            break
    return n


def _strip_aq(k: str) -> str:
    return k[3:] if k.startswith("aq-") else k


def aliases(key: str) -> Set[str]:
    s = _strip_aq(key)
    out = {key, s, "get-" + s}
    if s.startswith("get-"):
        out.add(s[4:])
    return out


def distinctive(key: str) -> bool:
    """Free-text matching only for names unlikely to be plain English words."""
    return "-" in key or key.startswith("aq")


def tokens_of(text: str) -> Set[str]:
    out: Set[str] = set()
    for t in TOKEN_RE.findall(text.lower()):
        t = t.rstrip(".-/")
        if len(t) < 3:
            continue
        out.add(norm(t))
        if "/" in t:
            out.add(norm(t.rsplit("/", 1)[1]))
    return out


def _read(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_FILE:
            return ""
        return p.read_text(errors="ignore")
    except OSError:
        return ""


def _walk(root: Path, exts: Optional[Set[str]] = None) -> Iterable[Path]:
    if not root.exists():
        return
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = Path(dp) / f
            if exts is None or p.suffix in exts or not p.suffix:
                yield p


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    base = parts[-1]
    return (
        "tests" in parts or "test" in parts or "testing" in parts
        or base.startswith(("test_", "test-")) or base.endswith(("_test.py", "-test.sh", "_test.sh"))
    )


class TokenIndex:
    def __init__(self) -> None:
        self.map: Dict[str, Set[str]] = defaultdict(set)

    def add(self, rel: str, text: str) -> None:
        for t in tokens_of(text):
            self.map[t].add(rel)

    def files(self, key: str, exclude: Set[str]) -> Set[str]:
        hits = self.map.get(key, set())
        return {h for h in hits if h not in exclude and norm(Path(h).name) != key}


def build_indexes(root: Path):
    wired, tested = TokenIndex(), TokenIndex()
    for top in ("scripts", "ai-stack", "nix", "dashboard"):
        for p in _walk(root / top, CODE_EXT):
            rel = str(p.relative_to(root))
            txt = _read(p)
            if not txt:
                continue
            (tested if _is_test(rel) else wired).add(rel, txt)
    return wired, tested


def build_discovery_index(root: Path) -> TokenIndex:
    idx = TokenIndex()
    ag = root / ".agent"
    skip_name = re.compile(r"PRD|PLAN|phase\d|COMPLETE|SUMMARY|RESEARCH|ANALYSIS|ACTIVATION-AUDIT|HANDOFF|REVIEW", re.I)
    files: List[Path] = [root / "CLAUDE.md", root / "AGENTS.md", ag / "SKILL_INDEX.md"]
    if ag.exists():
        files += [p for p in ag.glob("*.md") if not skip_name.search(p.name)]
        files += list((ag / "lanes").glob("*.md"))
    files += list((root / "docs" / "agent-guides").glob("*.md"))
    files += list((root / "canon").rglob("*.md")) if (root / "canon").exists() else []
    files += list((ag / "skills").glob("*/SKILL.md")) if ag.exists() else []
    files += [root / "config" / "progressive-disclosure-domains.json", root / "config" / "workflow-blueprints.json",
              root / "config" / "capability-index.json"]
    hc = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
    files += [hc / "knowledge" / "tooling_manifest.py", hc / "tooling_manifest.py"]
    files += list(hc.rglob("static_rules.py")) + list(hc.rglob("hints_engine*.py"))
    for p in files:
        if p.is_file():
            idx.add(str(p.relative_to(root)), _read(p))
    return idx


# ---------------------------------------------------------------- inventory

def inv_scripts(root: Path) -> List[Dict[str, Any]]:
    out = []
    d = root / "scripts" / "ai"
    if not d.exists():
        return out
    for p in sorted(d.iterdir()):
        if p.is_dir() or p.name.startswith(".") or p.suffix in (".md", ".json", ".txt", ".pyc"):
            continue
        out.append({"name": p.name, "kind": "script", "path": str(p.relative_to(root))})
    return out


def inv_skills(root: Path) -> List[Dict[str, Any]]:
    d = root / ".agent" / "skills"
    return [
        {"name": p.parent.name, "kind": "skill", "path": str(p.relative_to(root))}
        for p in sorted(d.glob("*/SKILL.md"))
    ] if d.exists() else []


def inv_mcp(root: Path) -> List[Dict[str, Any]]:
    p = root / "scripts" / "ai" / "mcp-bridge-hybrid.py"
    if not p.exists():
        return []
    try:
        tree = ast.parse(_read(p))
    except SyntaxError:
        return []
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOOLS" for t in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Dict):
                    for k, v in zip(sub.keys, sub.values):
                        if isinstance(k, ast.Constant) and k.value == "name" and isinstance(v, ast.Constant) \
                                and isinstance(v.value, str):
                            names.append(v.value)
    return [{"name": n, "kind": "mcp-tool", "path": str(p.relative_to(root))} for n in dict.fromkeys(names)]


UNIT_RE = re.compile(r'systemd\.(services|timers)\.(?:"([^"$@]+)"|([A-Za-z0-9_][A-Za-z0-9_-]*))')


def inv_units(root: Path) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for p in _walk(root / "nix" / "modules", {".nix"}):
        for m in UNIT_RE.finditer(_read(p)):
            suffix = "service" if m.group(1) == "services" else "timer"
            name = (m.group(2) or m.group(3))
            seen.setdefault(f"{name}.{suffix}", {"name": name, "kind": "unit", "unit": f"{name}.{suffix}",
                                                   "path": str(p.relative_to(root))})
    return [seen[k] for k in sorted(seen)]


def inv_catalog(root: Path) -> List[Dict[str, Any]]:
    p = root / "config" / "system-capability-catalog.json"
    if not p.exists():
        return []
    try:
        data = json.loads(_read(p))
    except ValueError:
        return []
    return data.get("entries", [])


# ----------------------------------------------------------------- runtime

def _parse_ts(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str) or not v:
        return None
    try:
        s = v.replace("Z", "+00:00")
        s = re.sub(r"\+00:00\+00:00$", "+00:00", s)
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.timestamp()
    except ValueError:
        return None


class Usage:
    """name -> (count, last_seen) from exact-name sources; text tokens separately."""

    def __init__(self) -> None:
        self.exact: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0])   # norm name -> [count,last]
        self.text: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0])
        self.sources: Dict[str, Any] = {}

    def hit(self, name: str, ts: float, exact: bool = True, n: int = 1) -> None:
        d = (self.exact if exact else self.text)[norm(name)]
        d[0] += n
        d[1] = max(d[1], ts)


_TOOL_RE = re.compile(r'"tool_name"\s*:\s*"([^"]+)"')
_TS_RE = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')


def scan_tool_audit(path: Path, cutoff: float, u: Usage) -> None:
    n = 0
    if not path.exists():
        u.sources["tool_audit"] = "missing"
        return
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                m = _TS_RE.search(line)
                if not m:
                    continue
                ts = _parse_ts(m.group(1))
                if ts is None or ts < cutoff:
                    continue
                t = _TOOL_RE.search(line)
                if t:
                    u.hit(t.group(1), ts)
                    n += 1
    except PermissionError:
        u.sources["tool_audit"] = "permission-denied"
        return
    u.sources["tool_audit"] = n


def scan_jsonl_names(path: Path, cutoff: float, u: Usage, keys: Iterable[str], tag: str) -> None:
    """Event-name style jsonl: counts the value of the first present key."""
    if not path.exists():
        u.sources[tag] = "missing"
        return
    n = 0
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                ts = _parse_ts(d.get("timestamp") or d.get("ts"))
                if ts is None or ts < cutoff:
                    continue
                for k in keys:
                    if d.get(k):
                        u.hit(str(d[k]), ts)
                        n += 1
                        break
    except PermissionError:
        u.sources[tag] = "permission-denied"
        return
    u.sources[tag] = n


AQ_USAGE_PREFER_MIN_TOOLS = 10


def aq_usage_distinct_tools(*paths: Path, cutoff: float) -> int:
    """Distinct tools in the window across aq-usage ledgers (0 if missing/empty)."""
    seen = set()
    for path in paths:
        try:
            with open(path, "r", errors="ignore") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    ts = _parse_ts(d.get("ts"))
                    name = d.get("script") or d.get("command")
                    if name and ts is not None and ts >= cutoff:
                        seen.add(str(name))
        except OSError:
            continue
    return len(seen)


def scan_text_tree(root: Path, cutoff: float, u: Usage, tag: str, max_bytes: int = 400_000) -> None:
    """Free-text evidence: distinctive name tokens in recently modified files."""
    n = 0
    if not root.exists():
        u.sources[tag] = "missing"
        return
    for p in _walk(root):
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime < cutoff or st.st_size > 20_000_000:
            continue
        try:
            with open(p, "r", errors="ignore") as f:
                txt = f.read(max_bytes)
        except OSError:
            continue
        for t in tokens_of(txt):
            if distinctive(t):
                u.hit(t, st.st_mtime, exact=False)
        n += 1
    u.sources[tag] = n


def scan_registry(path: Path, cutoff: float, u: Usage) -> None:
    if not path.exists():
        u.sources["delegation_registry"] = "missing"
        return
    n = 0
    try:
        f = open(path, "r", errors="ignore")
    except PermissionError:  # root-owned 0600 on the live host
        u.sources["delegation_registry"] = "permission-denied"
        return
    with f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = _parse_ts(d.get("created"))
            if ts is None or ts < cutoff:
                continue
            n += 1
            for t in tokens_of(str(d.get("description", ""))):
                if distinctive(t):
                    u.hit(t, ts, exact=False)
    u.sources["delegation_registry"] = n


def systemd_state(units: List[str], timeout: int = 20) -> Dict[str, Dict[str, str]]:
    if not units:
        return {}
    props = "Id,LoadState,ActiveState,Result,ExecMainStartTimestamp,LastTriggerUSec"
    try:
        r = subprocess.run(["systemctl", "show", "--timestamp=unix", f"--property={props}", *units],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for block in r.stdout.strip().split("\n\n"):
        d = dict(l.split("=", 1) for l in block.splitlines() if "=" in l)
        if "Id" in d:
            out[d["Id"]] = d
    return out


def journal_seen(unit: str, days: int) -> bool:
    try:
        r = subprocess.run(["journalctl", "-u", unit, "--since", f"-{days}d", "-n", "1", "-q", "--no-pager"],
                           capture_output=True, text=True, timeout=6)
        return bool(r.stdout.strip()) and "No entries" not in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def _unix(v: str) -> float:
    v = (v or "").lstrip("@")
    try:
        return float(v) if v else 0.0
    except ValueError:
        return 0.0


def check_script_health(root: Path, items: List[Dict[str, Any]]) -> Dict[str, str]:
    """Cheap breakage detection: python syntax errors and `bash -n` failures."""
    bad: Dict[str, str] = {}

    def one(it: Dict[str, Any]):
        p = root / it["path"]
        txt = _read(p)
        head = txt[:120]
        try:
            if p.suffix == ".py" or "python" in head.split("\n", 1)[0]:
                ast.parse(txt)
            elif p.suffix in (".sh", ".bash") or re.match(r"#!.*\b(ba)?sh\b", head):
                r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return it["path"], "bash -n: " + r.stderr.strip().splitlines()[0][:120] if r.stderr else "bash -n failed"
        except SyntaxError as e:
            return it["path"], f"syntax error line {e.lineno}"
        except (OSError, subprocess.TimeoutExpired):
            return None
        return None

    with cf.ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, items):
            if res:
                bad[res[0]] = res[1]
    return bad


# ------------------------------------------------------------------- audit

def run_audit(
    repo_root: Path,
    live_root: Optional[Path] = None,
    days: int = 30,
    now: Optional[float] = None,
    tool_audit: Optional[Path] = Path("/var/log/ai-audit-sidecar/tool-audit.jsonl"),
    telemetry_dir: Optional[Path] = Path("/var/lib/ai-stack/hybrid/telemetry"),
    delegation_dir: Optional[Path] = None,
    use_systemd: bool = True,
    use_journal: bool = True,
    unit_states: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    repo_root = Path(repo_root)
    live_root = Path(live_root) if live_root else repo_root
    delegation_dir = Path(delegation_dir) if delegation_dir else live_root / ".agents" / "delegation"
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    cutoff = now - days * 86400

    # --- inventory (dedup by normalized key) -------------------------------
    caps: Dict[str, Dict[str, Any]] = {}

    def add(item: Dict[str, Any]) -> Dict[str, Any]:
        k = norm(item["name"])
        c = caps.get(k)
        if c is None:
            c = {"key": k, "name": item["name"], "kinds": [], "paths": [], "unit": None, "catalog": []}
            caps[k] = c
        if item["kind"] not in c["kinds"]:
            c["kinds"].append(item["kind"])
        if item.get("path") and item["path"] not in c["paths"]:
            c["paths"].append(item["path"])
        if item.get("unit"):
            c["unit"] = item["unit"]
        return c

    scripts = inv_scripts(repo_root)
    for it in scripts + inv_skills(repo_root) + inv_mcp(repo_root) + inv_units(repo_root):
        add(it)

    catalog = inv_catalog(repo_root)
    for e in catalog:
        refs = [r for r in e.get("primary_refs", []) if isinstance(r, str)]
        linked = []
        for r in refs:
            k = norm(Path(r).name)
            if r.startswith("scripts/ai/") and k in caps:
                linked.append(k)
        own = norm(e["id"])
        if own in caps:
            linked.append(own)
        if not linked:
            c = add({"name": e["id"], "kind": "catalog", "path": "config/system-capability-catalog.json"})
            linked = [c["key"]]
        for k in dict.fromkeys(linked):
            caps[k]["catalog"].append({"id": e["id"], "state": e.get("state"), "maturity": e.get("maturity"), "usage_evidence": e.get("usage_evidence"),
                                       "refs": [norm(Path(r).name) for r in e.get("primary_refs", [])]})

    artifact_days = artifact_refresh_days(repo_root)
    for rel, days_max in artifact_days.items():
        add({"name": Path(rel).name + "@" + rel, "kind": "artifact", "path": rel})

    # --- usage evidence ----------------------------------------------------
    u = Usage()
    prefer_ledger = False
    if tool_audit:
        scan_tool_audit(tool_audit, cutoff, u)
    if telemetry_dir:
        scan_jsonl_names(telemetry_dir / "hybrid-events.jsonl", cutoff, u, ("event_type", "event"), "hybrid_events")
        scan_jsonl_names(telemetry_dir / "aq-usage.jsonl", cutoff, u, ("script", "command"), "aq_usage")
        # Exact ledger is authoritative for aq-* scripts once it looks representative
        # (several distinct tools, not just one self-invoking timer); text-token
        # evidence is then ignored for them. See lib/aq-shim.sh.
        # The producer writes <repo>/.agents/telemetry/aq-usage.jsonl (gitignored);
        # the system telemetry dir held a stale Jul-11 copy. Read both.
        local_ledger = live_root / ".agents" / "telemetry" / "aq-usage.jsonl"
        if local_ledger.exists() and local_ledger.resolve() != (telemetry_dir / "aq-usage.jsonl").resolve():
            scan_jsonl_names(local_ledger, cutoff, u, ("script", "command"), "aq_usage_local")
        n_tools = aq_usage_distinct_tools(telemetry_dir / "aq-usage.jsonl", local_ledger, cutoff=cutoff)
        u.sources["aq_usage_distinct_tools"] = n_tools
        prefer_ledger = n_tools >= AQ_USAGE_PREFER_MIN_TOOLS
        u.sources["aq_usage_preferred"] = prefer_ledger
        scan_jsonl_names(telemetry_dir / "agent-run-events.jsonl", cutoff, u, ("tool", "tool_name", "event_type"),
                         "agent_run_events")
    scan_registry(delegation_dir / "registry.jsonl", cutoff, u)
    scan_text_tree(delegation_dir / "outputs", cutoff, u, "delegation_outputs")
    scan_text_tree(delegation_dir / "streams", cutoff, u, "delegation_streams")

    # units
    states: Dict[str, Dict[str, str]] = dict(unit_states or {})
    unit_names = [c["unit"] for c in caps.values() if c["unit"]]
    # timer and service of same name: query both
    for c in list(caps.values()):
        if c["unit"]:
            for suf in ("service", "timer"):
                n = f"{c['name']}.{suf}"
                if n not in unit_names:
                    unit_names.append(n)
    if use_systemd and unit_states is None:
        states = systemd_state(sorted(set(unit_names)))
    u.sources["systemd_units_queried"] = len(states)

    # --- code indexes ------------------------------------------------------
    wired_idx, tested_idx = build_indexes(repo_root)
    disc_idx = build_discovery_index(repo_root)
    health = check_script_health(repo_root, scripts)

    journal_cache: Dict[str, bool] = {}
    if use_journal and use_systemd:
        need = []
        for c in caps.values():
            if not c["unit"]:
                continue
            for suf in ("service", "timer"):
                s = states.get(f"{c['name']}.{suf}")
                if s and s.get("LoadState") == "loaded" and not _recent_unit(s, cutoff):
                    need.append(f"{c['name']}.{suf}")
        with cf.ThreadPoolExecutor(8) as ex:
            for n, ok in zip(need, ex.map(lambda x: journal_seen(x, days), need)):
                journal_cache[n] = ok

    # --- per-capability evidence ------------------------------------------
    triage = load_triage(repo_root)
    rows: List[Dict[str, Any]] = []
    for k, c in caps.items():
        defining = set(c["paths"])
        al = aliases(k)

        # used
        used_n, last = 0, 0.0
        where: List[str] = []
        for a in al:
            if a in u.exact:
                used_n += int(u.exact[a][0]); last = max(last, u.exact[a][1]); where.append("exact-log")
        if distinctive(k) and not (prefer_ledger and k.startswith("aq-") and "script" in c["kinds"]):
            for a in al:
                if a in u.text and distinctive(a):
                    used_n += int(u.text[a][0]); last = max(last, u.text[a][1]); where.append("delegation-text")
        unit_info = None
        if c["unit"]:
            unit_info = {}
            for suf in ("service", "timer"):
                un = f"{c['name']}.{suf}"
                s = states.get(un)
                if not s:
                    continue
                unit_info[un] = {"load": s.get("LoadState"), "active": s.get("ActiveState"),
                                 "result": s.get("Result")}
                if s.get("LoadState") != "loaded":
                    continue
                ts = max(_unix(s.get("ExecMainStartTimestamp", "")), _unix(s.get("LastTriggerUSec", "")))
                if s.get("ActiveState") == "active" or ts >= cutoff or journal_cache.get(un):
                    used_n += 1; last = max(last, ts); where.append("systemd")
        used = used_n > 0

        # wired / tested / discoverable
        wired_by = set()
        tested_by = set()
        disc_by = set()
        for a in {k, *(a for a in al if distinctive(a))}:
            wired_by |= wired_idx.files(a, defining)
            tested_by |= tested_idx.files(a, defining)
            disc_by |= disc_idx.files(a, defining)
        if "mcp-tool" in c["kinds"]:
            disc_by.add("mcp-tool-registry")
        wired = bool(wired_by)
        tested = bool(tested_by)
        discoverable = bool(disc_by)
        loaded_unit = bool(unit_info) and any(v["load"] == "loaded" for v in unit_info.values())

        # catalog claim / staleness
        claims = [x for x in c["catalog"]
                  if x["state"] in LIVE_CLAIM_STATES and x["maturity"] in LIVE_CLAIM_MATURITY]
        claim_stale = False
        claim_acked = False
        if claims:
            # entry-level usage: any linked capability or the entry id itself used
            ent_used = used
            for x in claims:
                for r in x["refs"] + [norm(x["id"])]:
                    for a in aliases(r):
                        if a in u.exact or (distinctive(a) and a in u.text):
                            ent_used = True
            claim_stale = not ent_used
            # A stale claim whose catalog entry documents why it is kept is acknowledged, not false.
            claim_acked = claim_stale and all(str(x.get("usage_evidence") or "").strip() for x in claims)
        artifact_stale = False
        age_days = None
        if "artifact" in c["kinds"]:
            rel = c["paths"][0]
            p = live_root / rel
            if p.exists():
                age_days = round((now - p.stat().st_mtime) / 86400, 1)
                artifact_stale = age_days > artifact_days[rel]
            else:
                artifact_stale = True
            used = not artifact_stale
        stale = claim_stale or artifact_stale

        broken = None
        for pth in c["paths"]:
            if pth in health:
                broken = health[pth]
        if unit_info:
            for un, v in unit_info.items():
                if v["active"] == "failed" or v["result"] not in (None, "", "success"):
                    broken = f"{un}: active={v['active']} result={v['result']}"

        dead = not (wired or used or discoverable or loaded_unit)

        if broken:
            cls = "BROKEN"
        elif "artifact" in c["kinds"]:
            cls = "STALE-ARTIFACT" if artifact_stale else "ACTIVE"
        elif used and (discoverable or wired) and not claim_stale:
            cls = "ACTIVE"
        elif claim_stale:
            cls = "ACKNOWLEDGED" if claim_acked else "STALE-CLAIM"
        elif k in triage and not (used or wired):
            cls = "KEEP-DECLARED"
        elif not discoverable and (wired or used or loaded_unit):
            cls = "UNDISCOVERABLE"
        elif discoverable and not used:
            cls = "UNUSED-AVAILABLE"
        elif dead:
            cls = "DEAD-CANDIDATE"
        else:
            cls = "ACTIVE" if used else "UNUSED-AVAILABLE"

        rows.append({
            "key": k, "name": c["name"], "kinds": c["kinds"], "paths": c["paths"],
            "class": cls, "next_action": NEXT_ACTION[cls],
            "evidence": {
                "discoverable": discoverable, "discovered_in": sorted(disc_by)[:5], "discovered_in_count": len(disc_by),
                "used": used, "use_count": used_n, "last_seen": _iso(last) if last else None, "use_sources": sorted(set(where)),
                "wired": wired, "wired_by_count": len(wired_by), "wired_by": sorted(wired_by)[:3],
                "tested": tested, "tested_by_count": len(tested_by),
                "stale": stale, "dead": dead,
                **({"unit": unit_info} if unit_info is not None else {}),
                **({"catalog_claims": c["catalog"]} if c["catalog"] else {}),
                **({"artifact_age_days": age_days} if age_days is not None else {}),
                **({"broken": broken} if broken else {}),
                **({"keep_reason": triage[k]} if k in triage else {}),
            },
        })

    rows.sort(key=lambda r: (r["class"], r["key"]))
    counts = Counter(r["class"] for r in rows)
    return {
        "schema": "capability-audit/1",
        "audit_version": AUDIT_VERSION,
        "generated_at": _iso(now),
        "window_days": days,
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "totals": {"capabilities": len(rows), "by_class": {c: counts.get(c, 0) for c in CLASSES},
                   "by_kind": dict(Counter(k for r in rows for k in r["kinds"]))},
        "usage_sources": u.sources,
        "capabilities": rows,
    }


def _recent_unit(s: Dict[str, str], cutoff: float) -> bool:
    return s.get("ActiveState") == "active" or max(
        _unix(s.get("ExecMainStartTimestamp", "")), _unix(s.get("LastTriggerUSec", ""))) >= cutoff


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_human(report: Dict[str, Any], top: int = 10) -> str:
    t = report["totals"]
    lines = [f"capability audit  window={report['window_days']}d  total={t['capabilities']}"]
    lines.append("  " + "  ".join(f"{c}={t['by_class'][c]}" for c in CLASSES))
    lines.append("  kinds: " + ", ".join(f"{k}={v}" for k, v in sorted(t["by_kind"].items())))
    lines.append("  usage sources: " + ", ".join(f"{k}={v}" for k, v in report["usage_sources"].items()))
    for cls in ("BROKEN", "STALE-CLAIM", "STALE-ARTIFACT", "UNDISCOVERABLE", "DEAD-CANDIDATE", "KEEP-DECLARED", "UNUSED-AVAILABLE"):
        rs = [r for r in report["capabilities"] if r["class"] == cls]
        if not rs:
            continue
        lines.append(f"\n{cls} ({len(rs)}) -> {NEXT_ACTION[cls]}")
        for r in rs[:top]:
            e = r["evidence"]
            lines.append(f"  {r['name']:<42} {'/'.join(r['kinds']):<10} disc={e['discovered_in_count']} "
                         f"used={e['use_count']} wired={e['wired_by_count']} tested={e['tested_by_count']}")
        if len(rs) > top:
            lines.append(f"  ... {len(rs) - top} more (use --json)")
    return "\n".join(lines)
