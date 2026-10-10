"""Deterministic static knowledge-graph builder (stdlib only, no LLM).

Emits the same schema as the upstream Understand-Anything graph
(`{metadata, nodes, edges}`) so scripts/ai/lib/understand_graph.py, aq-graph-query,
the MCP graph_query tool, aq-wiki and the dashboard keep working unchanged.

Sources (all from `git ls-files`): Python (ast), shell, Nix, Markdown, small
config files.  Same inputs always produce byte-identical output: `generated` is the
HEAD commit time (never wall clock), ids are stable, nodes/edges are sorted.

Edge confidence lives in `weight`: 1.0 resolved import, 0.8-0.9 resolved call or
reference, 0.5 name-only / unique-suffix guess.  Nothing here is "certain" beyond
what the weight says; consumers should treat sub-0.6 edges as hints.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

GENERATOR = "aq-graph-build"
SCHEMA_VERSION = "2.8.1"  # upstream graph format this output is compatible with
LLM_BACKUP_NAME = "knowledge-graph.llm-2026-07-01.json"
LLM_TAG = "summary:llm-2026-07"

EXCLUDE_PARTS = {"archive", "vendored", "vendor", "node_modules", "third_party", ".git"}
EXCLUDE_PREFIXES = (
    ".understand-anything/", ".agents/reports/", ".agent/collaboration/", ".agents/archive/",
    ".agent/skills/pptx/ooxml/schemas/",
)
SKIP_EXT = {
    "png", "jpg", "jpeg", "gif", "ico", "ttf", "otf", "woff", "woff2", "xsd", "pdf", "zip",
    "gz", "tar", "lock", "svg", "bin", "pyc", "so", "wasm", "gguf", "csv", "jsonl", "log",
    "txt", "html", "css", "js", "ts", "tsx", "rs", "toml_lock", "tmpl",
}
CONFIG_EXT = {"json", "yaml", "yml", "toml", "sql", "service", "timer", "conf", "ini", "cfg"}
CONFIG_MAX_BYTES = 200_000
MAX_FILE_BYTES = 1_500_000
EVIDENCE_PARTS = {"evidence", "outputs", "reports", "receipts", "snapshots"}

STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
COMMON_METHODS = {
    "get", "items", "keys", "values", "append", "extend", "update", "pop", "add", "join", "split",
    "strip", "read", "write", "close", "open", "format", "encode", "decode", "lower", "upper",
    "replace", "startswith", "endswith", "copy", "clear", "sort", "remove", "insert", "index",
    "count", "setdefault", "discard", "find", "rstrip", "lstrip", "readline", "readlines", "seek",
    "flush", "exists", "mkdir", "is_file", "is_dir", "resolve", "isoformat", "total_seconds",
    "strftime", "group", "match", "search", "sub", "findall", "dumps", "loads", "dump", "load",
    "run", "start", "stop", "send", "recv", "put", "wait", "result", "cancel", "done", "set",
    "info", "debug", "warning", "error", "exception", "log", "name", "__init__", "main",
}

_VAR_PREFIX = re.compile(r"^(?:\$\{[^}]*\}|\$\([^)]*\)|\$\w+|~)/?")
_PATH_TOK = re.compile(r"(?<![\w:/.])(?:[\w.${}\[\]%@~()-]*/)+[\w.@-]+")
_NAME_TOK = re.compile(r"(?<![\w/.])aq-[a-z0-9][a-z0-9_-]*")
_FILE_TOK = re.compile(r"(?<![\w/.-])[\w][\w.-]*\.(?:sh|py|nix)\b")
_SRC_LINE = re.compile(r"^\s*(?:source|\.)\s+[\"']?([^\s\"';&|]+)")


# ── git / filesystem ─────────────────────────────────────────────────────────

def _git(root: Path, *args: str) -> str:
    env = dict(os.environ)
    env["PATH"] = "/run/current-system/sw/bin:/run/wrappers/bin:" + env.get("PATH", "")
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       timeout=60, check=False, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def git_head(root: Path) -> Tuple[str, str]:
    """(sha, committer-date ISO-8601 UTC 'Z') of HEAD."""
    sha = _git(root, "rev-parse", "HEAD").strip()
    ts = _git(root, "show", "-s", "--format=%cI", "HEAD").strip()
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(ts).astimezone(timezone.utc)
    return sha, dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def tracked_files(root: Path) -> List[str]:
    out = _git(root, "ls-files", "-z")
    return sorted(p for p in out.split("\0") if p)


def _excluded(path: str) -> bool:
    if path.startswith(EXCLUDE_PREFIXES):
        return True
    parts = path.split("/")
    if any(p in EXCLUDE_PARTS for p in parts[:-1]):
        return True
    return False


def _read(root: Path, path: str) -> Optional[str]:
    try:
        p = root / path
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def classify(path: str, text_head: str) -> Optional[str]:
    """Return language label for in-scope files, else None."""
    name = path.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "py":
        return "python"
    if ext in ("sh", "bash"):
        return "shell"
    if ext == "nix":
        return "nix"
    if ext == "md":
        return "markdown"
    if ext in SKIP_EXT:
        return None
    if ext in CONFIG_EXT:
        parts = set(path.split("/")[:-1])
        if parts & EVIDENCE_PARTS:
            return None
        return "config:" + ext
    if not ext and path.startswith(("scripts/", ".githooks/")) and text_head.startswith("#!"):
        first = text_head.split("\n", 1)[0]
        if "python" in first:
            return "python"
        if re.search(r"\b(ba|z|da|k)?sh\b", first):
            return "shell"
    return None


def _clean(s: str, cap: int = 300) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= cap else s[: cap - 1].rstrip() + "…"


def _bucket(lines: int, lo: int, hi: int) -> str:
    return "simple" if lines < lo else ("moderate" if lines < hi else "complex")


# ── model ────────────────────────────────────────────────────────────────────

class Graph:
    def __init__(self) -> None:
        self.nodes: Dict[str, dict] = {}
        self.src: Dict[str, str] = {}  # id -> summary source (docstring|heading|comment|signature|none)
        self.edges: Dict[Tuple[str, str, str], float] = {}

    def node(self, nid: str, ntype: str, name: str, path: str, summary: str = "", src: str = "none",
             tags: Iterable[str] = (), complexity: str = "simple", start: Optional[int] = None,
             end: Optional[int] = None, language: Optional[str] = None) -> None:
        if nid in self.nodes:
            return
        n = {"id": nid, "type": ntype, "name": name, "filePath": path, "summary": _clean(summary),
             "tags": sorted(set(tags)), "complexity": complexity}
        if start is not None:
            n["startLine"] = start
            n["endLine"] = end if end is not None else start
        if language:
            n["language"] = language
        self.nodes[nid] = n
        self.src[nid] = src

    def edge(self, s: str, t: str, etype: str, weight: float = 1.0) -> None:
        if s == t or s not in self.nodes or t not in self.nodes:
            return
        k = (s, t, etype)
        if weight > self.edges.get(k, 0):
            self.edges[k] = round(weight, 2)


# ── reference resolution (paths in strings, shell, nix, docs) ───────────────

class Resolver:
    def __init__(self, files: Set[str]) -> None:
        self.files = files
        self.by_base: Dict[str, List[str]] = defaultdict(list)
        self.suffix: Dict[str, List[str]] = defaultdict(list)
        for f in sorted(files):
            parts = f.split("/")
            self.by_base[parts[-1]].append(f)
            for i in range(len(parts) - 1):
                self.suffix["/".join(parts[i:])].append(f)
        self.scripts: Dict[str, List[str]] = defaultdict(list)
        for f in sorted(files):
            if f.startswith("scripts/") and "." not in f.rsplit("/", 1)[-1]:
                self.scripts[f.rsplit("/", 1)[-1]].append(f)
        self._cache: Dict[Tuple[str, str], Optional[Tuple[str, float]]] = {}

    def norm(self, tok: str, from_dir: str) -> Optional[str]:
        base = from_dir
        while True:
            m = _VAR_PREFIX.match(tok)
            if not m:
                break
            tok = tok[m.end():]
            base = ""
        tok = tok.strip("\"'`()[]<>,;:")
        if not tok or "$" in tok or "*" in tok or "{" in tok or "%" in tok:
            return None
        parts = []
        for seg in (base + "/" + tok if base and not tok.startswith("/") else tok).split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if not parts:
                    return None
                parts.pop()
            else:
                parts.append(seg)
        return "/".join(parts)

    def resolve(self, tok: str, from_dir: str) -> Optional[Tuple[str, float]]:
        key = (tok, from_dir)
        if key in self._cache:
            return self._cache[key]
        res = self._resolve(tok, from_dir)
        self._cache[key] = res
        return res

    def _resolve(self, tok: str, from_dir: str) -> Optional[Tuple[str, float]]:
        tok = tok.strip().strip("\"'`")
        if tok.startswith("aq-") and "/" not in tok:
            c = self.scripts.get(tok, [])
            if not c:
                return None
            ai = [x for x in c if x.startswith("scripts/ai/")]
            pick = ai if ai else c
            return (pick[0], 0.8) if len(pick) == 1 else None
        for rel in (from_dir, ""):
            p = self.norm(tok, rel)
            if p and p in self.files:
                return p, 0.9
            if p and p + "/default.nix" in self.files:
                return p + "/default.nix", 0.9
        p = self.norm(tok, "")
        if not p:
            return None
        if "/" in p:
            parts = p.split("/")
            for k in range(min(len(parts) - 1, 4)):  # absolute deploy paths: /srv/repo/scripts/x -> scripts/x
                sub = "/".join(parts[k:])
                if sub in self.files:
                    return sub, 0.6
                c = self.suffix.get(sub, [])
                if len(c) == 1:
                    return c[0], 0.6
            return None
        if re.search(r"\.(sh|py|nix)$", p):
            c = self.by_base.get(p, [])
            if len(c) == 1:
                return c[0], 0.5
        return None


def extract_ref_tokens(text: str) -> List[str]:
    toks = [m.group(0) for m in _PATH_TOK.finditer(text)]
    toks += [m.group(0) for m in _NAME_TOK.finditer(text)]
    toks += [m.group(0) for m in _FILE_TOK.finditer(text)]
    return toks


# ── Python ───────────────────────────────────────────────────────────────────

def _comment_header(text: str) -> str:
    lines = []
    for ln in text.split("\n")[:40]:
        s = ln.strip()
        if s.startswith("#!") or re.match(r"#.*(coding[:=]|shellcheck|vim?:|-\*-)", s):
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            if body and not set(body) <= set("-=_*~#"):
                lines.append(body)
            elif lines:
                break
        elif not s:
            if lines:
                break
        else:
            break
    return " ".join(lines[:3])


def _first_line(doc: Optional[str]) -> str:
    if not doc:
        return ""
    for ln in doc.strip().split("\n"):
        if ln.strip():
            return ln.strip()
    return ""


def _signature(fn) -> str:
    try:
        args = ast.unparse(fn.args)
    except Exception:  # noqa: BLE001
        args = "..."
    ret = ""
    if getattr(fn, "returns", None) is not None:
        try:
            ret = " -> " + ast.unparse(fn.returns)
        except Exception:  # noqa: BLE001
            pass
    return f"{fn.name}({args}){ret}"


def _iter_defs(body):
    for st in body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield st
        elif isinstance(st, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            for attr in ("body", "orelse", "finalbody"):
                yield from _iter_defs(getattr(st, attr, []) or [])
            for h in getattr(st, "handlers", []) or []:
                yield from _iter_defs(h.body)


class PyInfo:
    def __init__(self, path: str) -> None:
        self.path = path
        self.funcs: Dict[str, str] = {}            # top-level name -> node id
        self.classes: Dict[str, str] = {}          # class name -> node id
        self.methods: Dict[Tuple[str, str], str] = {}
        self.bases: Dict[str, List[ast.expr]] = {}
        self.imports: List[Tuple[Optional[str], int, List[Tuple[str, Optional[str]]], int]] = []
        self.calls: List[Tuple[str, Optional[str], tuple]] = []  # (src id, enclosing class, descriptor)
        self.str_consts: List[str] = []
        self.parsed = False


class PyIndex:
    def __init__(self, py_files: List[str]) -> None:
        self.files = set(py_files)
        self.mod: Dict[str, List[str]] = defaultdict(list)
        for f in sorted(py_files):
            p = f[:-3] if f.endswith(".py") else f
            parts = p.split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts:
                continue
            # contiguous identifier-valid tail
            tail = []
            for seg in reversed(parts):
                if not seg.isidentifier():
                    break
                tail.append(seg)
            tail.reverse()
            for i in range(len(tail)):
                self.mod[".".join(tail[i:])].append(f)

    def lookup(self, dotted: str, importer: str) -> Tuple[List[str], float]:
        cands = self.mod.get(dotted, [])
        if not cands:
            return [], 0.0
        if len(cands) == 1:
            return cands, 1.0
        idir = importer.split("/")[:-1]

        def score(c: str) -> int:
            n = 0
            for a, b in zip(idir, c.split("/")[:-1]):
                if a != b:
                    break
                n += 1
            return n
        scored = sorted(((score(c), c) for c in cands), key=lambda x: (-x[0], x[1]))
        if scored[0][0] > scored[1][0]:
            return [scored[0][1]], 0.8
        top = [c for s, c in scored if s == scored[0][0]]
        return (top[:3], 0.5) if len(top) <= 3 else ([], 0.0)

    def relative(self, importer: str, level: int, module: Optional[str]) -> Optional[str]:
        d = importer.split("/")[:-1]
        if level - 1 > len(d):
            return None
        d = d[: len(d) - (level - 1)]
        base = "/".join(d + (module.split(".") if module else []))
        for cand in (base + ".py", base + "/__init__.py"):
            if cand in self.files:
                return cand
        return None


class Stats:
    def __init__(self) -> None:
        self.imp_total = 0
        self.imp_resolved = 0
        self.imp_ambiguous = 0
        self.imp_stdlib = 0
        self.imp_external = 0
        self.imp_unresolved_internal = 0
        self.parse_errors: List[str] = []
        self.files = 0

    def as_dict(self) -> dict:
        non_std = self.imp_total - self.imp_stdlib
        return {
            "python_import_statements_names": self.imp_total,
            "resolved_to_repo_files": self.imp_resolved,
            "of_which_ambiguous": self.imp_ambiguous,
            "stdlib": self.imp_stdlib,
            "external_or_unresolved": self.imp_external,
            "resolved_share_of_non_stdlib": round(self.imp_resolved / non_std, 4) if non_std else None,
            "resolved_share_of_all": round(self.imp_resolved / self.imp_total, 4) if self.imp_total else None,
            "parse_errors": len(self.parse_errors),
        }


def build_python(g: Graph, root: Path, texts: Dict[str, str], pyfiles: List[str], res: Resolver,
                 stats: Stats) -> Dict[str, PyInfo]:
    infos: Dict[str, PyInfo] = {}
    pidx = PyIndex(pyfiles)
    for path in pyfiles:
        text = texts[path]
        info = PyInfo(path)
        infos[path] = info
        nlines = text.count("\n") + 1
        lang_script = "." not in path.rsplit("/", 1)[-1]
        ntype = "script" if lang_script else "file"
        fid = f"file:{path}"
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            stats.parse_errors.append(path)
            g.node(fid, ntype, path.rsplit("/", 1)[-1], path, _comment_header(text), "comment",
                   ["python", "parse-error"], _bucket(nlines, 150, 600), language="python")
            continue
        info.parsed = True
        doc = _first_line(ast.get_docstring(tree))
        hdr = _comment_header(text) if not doc else ""
        tags = ["python"]
        if lang_script:
            tags.append("cli")
        g.node(fid, ntype, path.rsplit("/", 1)[-1], path, doc or hdr, "docstring" if doc else ("comment" if hdr else "none"),
               tags, _bucket(nlines, 150, 600), language="python")

        def add_func(fn, qual: str, cls: Optional[str]) -> str:
            nid = f"function:{path}:{qual}"
            ln = (fn.end_lineno or fn.lineno) - fn.lineno + 1
            d = _first_line(ast.get_docstring(fn))
            ftags = ["python"]
            if isinstance(fn, ast.AsyncFunctionDef):
                ftags.append("async")
            g.node(nid, "function", qual, path, d or _signature(fn), "docstring" if d else "signature",
                   ftags, _bucket(ln, 40, 120), fn.lineno, fn.end_lineno, "python")
            return nid

        for st in _iter_defs(tree.body):
            if isinstance(st, ast.ClassDef):
                cid = f"class:{path}:{st.name}"
                if cid in g.nodes:
                    continue
                ln = (st.end_lineno or st.lineno) - st.lineno + 1
                d = _first_line(ast.get_docstring(st))
                try:
                    bases = ", ".join(ast.unparse(b) for b in st.bases)
                except Exception:  # noqa: BLE001
                    bases = ""
                g.node(cid, "class", st.name, path, d or f"class {st.name}({bases})", "docstring" if d else "signature",
                       ["python"], _bucket(ln, 60, 250), st.lineno, st.end_lineno, "python")
                g.edge(fid, cid, "contains", 0.8)
                info.classes[st.name] = cid
                info.bases[st.name] = list(st.bases)
                for m in st.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        qual = f"{st.name}.{m.name}"
                        mid = add_func(m, qual, st.name)
                        g.edge(cid, mid, "contains", 0.8)
                        info.methods.setdefault((st.name, m.name), mid)
                        _collect_calls(m, mid, st.name, info)
            else:
                nid = f"function:{path}:{st.name}"
                if nid in g.nodes:
                    continue
                add_func(st, st.name, None)
                g.edge(fid, nid, "contains", 0.8)
                info.funcs.setdefault(st.name, nid)
                _collect_calls(st, nid, None, info)

        # module-level calls (e.g. `if __name__ == "__main__": main()`) and imports anywhere
        for st in tree.body:
            if not isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _collect_calls(st, fid, None, info, skip_defs=True)

        doc_nodes = {id(n.body[0].value) for n in ast.walk(tree)
                     if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and n.body and isinstance(n.body[0], ast.Expr)
                     and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                info.imports.append((None, 0, [(a.name, a.asname) for a in node.names], node.lineno))
            elif isinstance(node, ast.ImportFrom):
                info.imports.append((node.module, node.level, [(a.name, a.asname) for a in node.names], node.lineno))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_nodes:
                if 3 <= len(node.value) <= 400:
                    info.str_consts.append(node.value)

    # ── pass 2: imports -> edges + bindings ─────────────────────────────────
    binds: Dict[str, Dict[str, tuple]] = {}
    imported_files: Dict[str, Set[str]] = {}
    for path in pyfiles:
        info = infos[path]
        fid = f"file:{path}"
        bind: Dict[str, tuple] = {}
        imp_files: Set[str] = set()
        for module, level, names, _ln in info.imports:
            if module is None and level == 0:  # `import a.b.c [as x]`
                for name, asname in names:
                    stats.imp_total += 1
                    top = name.split(".")[0]
                    cands, w = pidx.lookup(name, path)
                    if not cands:
                        if top in STDLIB:
                            stats.imp_stdlib += 1
                        else:
                            stats.imp_external += 1
                        continue
                    stats.imp_resolved += 1
                    if w < 1.0:
                        stats.imp_ambiguous += 1
                    for c in cands:
                        g.edge(fid, f"file:{c}", "imports", w)
                        imp_files.add(c)
                    if asname:
                        bind[asname] = ("mod", cands[0])
                    elif len(cands) == 1 and "." not in name:
                        bind[name] = ("mod", cands[0])
                    else:
                        top_c, _ = pidx.lookup(top, path)
                        if top_c:
                            bind[top] = ("mod", top_c[0])
                continue
            # from X import a, b
            if level:
                target = pidx.relative(path, level, module)
                tcands, tw = ([target], 1.0) if target else ([], 0.0)
            else:
                tcands, tw = pidx.lookup(module or "", path)
                if not tcands and module and module.split(".")[0] in STDLIB:
                    stats.imp_stdlib += len(names)
                    stats.imp_total += len(names)
                    continue
            for name, asname in names:
                stats.imp_total += 1
                local = asname or name
                if name == "*":
                    if tcands:
                        stats.imp_resolved += 1
                        for c in tcands:
                            g.edge(fid, f"file:{c}", "imports", tw)
                            imp_files.add(c)
                    else:
                        stats.imp_external += 1
                    continue
                sub: Optional[str] = None
                if level:
                    base = "/".join(path.split("/")[: len(path.split("/")) - level] + (module.split(".") if module else []) + [name])
                    for cand in (base + ".py", base + "/__init__.py"):
                        if cand in pidx.files:
                            sub = cand
                            break
                else:
                    sc, _sw = pidx.lookup(f"{module}.{name}" if module else name, path)
                    if sc:
                        sub = sc[0]
                if tcands:
                    stats.imp_resolved += 1
                    if tw < 1.0:
                        stats.imp_ambiguous += 1
                    for c in tcands:
                        g.edge(fid, f"file:{c}", "imports", tw)
                        imp_files.add(c)
                    bind[local] = ("sym", tcands[0], name)
                    if sub:
                        g.edge(fid, f"file:{sub}", "imports", tw)
                        imp_files.add(sub)
                        if name not in infos.get(tcands[0], PyInfo("")).funcs and name not in infos.get(tcands[0], PyInfo("")).classes:
                            bind[local] = ("mod", sub)
                elif sub:
                    stats.imp_resolved += 1
                    g.edge(fid, f"file:{sub}", "imports", 1.0)
                    imp_files.add(sub)
                    bind[local] = ("mod", sub)
                elif (module or "").split(".")[0] in STDLIB:
                    stats.imp_stdlib += 1
                else:
                    stats.imp_external += 1
        binds[path] = bind
        imported_files[path] = imp_files

    # importlib / path-literal loaders: `spec_from_file_location("x", ... "lib" / "x.py")`
    for path in pyfiles:
        info = infos[path]
        fid = f"file:{path}"
        text = texts[path]
        loader = any(k in text for k in ("spec_from_file_location", "SourceFileLoader", "run_path", "load_source"))
        d = path.rsplit("/", 1)[0] if "/" in path else ""
        for s in info.str_consts:
            for tok in extract_ref_tokens(s):
                r = res.resolve(tok, d)
                if not r or r[0] == path:
                    continue
                target, w = r
                g.edge(fid, f"file:{target}", "imports" if (loader and target.endswith(".py")) else "calls",
                       min(w, 0.7))
                imported_files[path].add(target)

    # ── pass 3: calls / extends ──────────────────────────────────────────────
    def resolve_sym(fpath: str, name: str, depth: int = 0) -> Optional[Tuple[str, str]]:
        """(kind, node-id) for a top-level symbol of fpath, chasing one re-export hop."""
        inf = infos.get(fpath)
        if not inf:
            return None
        if name in inf.funcs:
            return "function", inf.funcs[name]
        if name in inf.classes:
            return "class", inf.classes[name]
        b = binds.get(fpath, {}).get(name)
        if b and b[0] == "sym" and depth < 3:
            return resolve_sym(b[1], b[2], depth + 1)
        return None

    for path in pyfiles:
        info = infos[path]
        if not info.parsed:
            continue
        bind = binds.get(path, {})
        fid = f"file:{path}"
        imported = sorted(imported_files.get(path, set()) | {path})
        # extends
        for cname, bases in info.bases.items():
            cid = info.classes[cname]
            for b in bases:
                tgt = None
                if isinstance(b, ast.Name):
                    if b.id in info.classes and b.id != cname:
                        tgt = info.classes[b.id]
                    elif b.id in bind and bind[b.id][0] == "sym":
                        r = resolve_sym(bind[b.id][1], bind[b.id][2])
                        if r and r[0] == "class":
                            tgt = r[1]
                elif isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name):
                    bb = bind.get(b.value.id)
                    if bb and bb[0] == "mod":
                        r = resolve_sym(bb[1], b.attr)
                        if r and r[0] == "class":
                            tgt = r[1]
                if tgt:
                    g.edge(cid, tgt, "extends", 0.9)
        # method lookup across class + repo bases (one level of local/imported inheritance)
        def find_method(cls: str, meth: str, fpath: str, seen=0) -> Optional[str]:
            inf = infos[fpath]
            if (cls, meth) in inf.methods:
                return inf.methods[(cls, meth)]
            if seen > 3:
                return None
            for b in inf.bases.get(cls, []):
                if isinstance(b, ast.Name):
                    if b.id in inf.classes:
                        r = find_method(b.id, meth, fpath, seen + 1)
                        if r:
                            return r
                    bb = binds.get(fpath, {}).get(b.id)
                    if bb and bb[0] == "sym":
                        sr = resolve_sym(bb[1], bb[2])
                        if sr and sr[0] == "class":
                            tp = sr[1].split(":", 2)[1]
                            r = find_method(sr[1].rsplit(":", 1)[1], meth, tp, seen + 1)
                            if r:
                                return r
            return None

        # name-only candidate index over imported modules' methods + funcs
        name_cands: Dict[str, Set[str]] = defaultdict(set)
        for f in imported:
            inf = infos.get(f)
            if not inf:
                continue
            for (c, m), mid in inf.methods.items():
                name_cands[m].add(mid)
            for n, nid in inf.funcs.items():
                name_cands[n].add(nid)

        for src, cls, desc in info.calls:
            kind = desc[0]
            tgt = None
            w = 0.9
            if kind == "name":
                n = desc[1]
                if n in info.funcs:
                    tgt = info.funcs[n]
                elif n in info.classes:
                    tgt = info.classes[n]
                elif n in bind and bind[n][0] == "sym":
                    r = resolve_sym(bind[n][1], bind[n][2])
                    tgt = r[1] if r else None
            else:
                base, attr, deep = desc[1], desc[2], desc[3]
                if base in ("self", "cls") and cls and not deep:
                    tgt = find_method(cls, attr, path)
                    w = 0.8
                elif base in bind and not deep:
                    b = bind[base]
                    if b[0] == "mod":
                        r = resolve_sym(b[1], attr)
                        tgt = r[1] if r else None
                    else:
                        r = resolve_sym(b[1], b[2])
                        if r and r[0] == "class":
                            cpath, cname = r[1].split(":", 2)[1], r[1].rsplit(":", 1)[1]
                            tgt = find_method(cname, attr, cpath)
                            w = 0.8
                elif base in info.classes and not deep:
                    tgt = find_method(base, attr, path)
                    w = 0.8
                if tgt is None and attr not in COMMON_METHODS and not attr.startswith("__"):
                    c = name_cands.get(attr, set())
                    if len(c) == 1:
                        tgt = next(iter(c))
                        w = 0.5
            if tgt:
                g.edge(src, tgt, "calls", w)
    return infos


def _collect_calls(root_node, src_id: str, cls: Optional[str], info: PyInfo, skip_defs: bool = False) -> None:
    stack = [root_node]
    while stack:
        node = stack.pop()
        if skip_defs and node is not root_node and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                info.calls.append((src_id, cls, ("name", f.id)))
            elif isinstance(f, ast.Attribute):
                v = f.value
                deep = False
                while isinstance(v, ast.Attribute):
                    v = v.value
                    deep = True
                if isinstance(v, ast.Name):
                    info.calls.append((src_id, cls, ("attr", v.id, f.attr, deep)))
                else:
                    info.calls.append((src_id, cls, ("attr", "", f.attr, True)))
        stack.extend(ast.iter_child_nodes(node))


# ── Shell ────────────────────────────────────────────────────────────────────

def build_shell(g: Graph, root: Path, texts: Dict[str, str], shfiles: List[str], res: Resolver) -> None:
    for path in shfiles:
        text = texts[path]
        nlines = text.count("\n") + 1
        fid = f"file:{path}"
        hdr = _comment_header(text)
        g.node(fid, "script", path.rsplit("/", 1)[-1], path, hdr, "comment" if hdr else "none",
               ["shell"], _bucket(nlines, 100, 400), language="shell")
        d = path.rsplit("/", 1)[0] if "/" in path else ""
        src_toks: Set[str] = set()
        for ln in text.split("\n"):
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            m = _SRC_LINE.match(ln)
            if m:
                tok = m.group(1)
                r = res.resolve(tok, d)
                if r and r[0] != path:
                    g.edge(fid, f"file:{r[0]}", "imports", 1.0 if r[1] >= 0.9 else r[1])
                    src_toks.add(tok)
                    continue
            for tok in extract_ref_tokens(ln):
                if tok in src_toks:
                    continue
                r = res.resolve(tok, d)
                if r and r[0] != path:
                    g.edge(fid, f"file:{r[0]}", "calls", min(r[1], 0.8))


# ── Nix ──────────────────────────────────────────────────────────────────────

def mask_nix(s: str) -> str:
    """Blank comments and string/interpolation contents (length- and newline-preserving)."""
    out = list(s)
    n = len(s)
    i = 0
    stack: List[str] = []
    depth: List[int] = []

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        mode = stack[-1] if stack else "code"
        c = s[i]
        if mode in ("code", "interp"):
            if c == "#" and (i == 0 or s[i - 1] not in "$"):
                j = s.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if s.startswith("/*", i):
                j = s.find("*/", i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if c == '"':
                stack.append("dq")
                i += 1
                continue
            if s.startswith("''", i):
                stack.append("ind")
                i += 2
                continue
            if mode == "interp":
                if c == "{":
                    depth[-1] += 1
                elif c == "}":
                    if depth[-1] == 0:
                        stack.pop()
                        depth.pop()
                        out[i] = " "
                        i += 1
                        continue
                    depth[-1] -= 1
                if out[i] != "\n":
                    out[i] = " "
            i += 1
        elif mode == "dq":
            if c == "\\":
                blank(i, i + 2)
                i += 2
            elif c == '"':
                stack.pop()
                i += 1
            elif s.startswith("${", i):
                stack.append("interp")
                depth.append(0)
                blank(i, i + 2)
                i += 2
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
        else:  # ind
            if s.startswith("'''", i) or s.startswith("''$", i) or s.startswith("''\\", i):
                blank(i, i + 3)
                i += 3
            elif s.startswith("''", i):
                stack.pop()
                i += 2
            elif s.startswith("${", i):
                stack.append("interp")
                depth.append(0)
                blank(i, i + 2)
                i += 2
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
    return "".join(out)


def _match_brace(masked: str, i: int) -> int:
    """Index of the '}' matching the '{' at masked[i] (or len-1)."""
    d = 0
    for k in range(i, len(masked)):
        c = masked[k]
        if c == "{":
            d += 1
        elif c == "}":
            d -= 1
            if d == 0:
                return k
    return len(masked) - 1


def _nix_string_at(orig: str, masked: str, i: int) -> str:
    """Decode the nix string literal whose opening quote starts at/after i."""
    m = re.compile(r"\s*(\"|'')").match(masked, i)
    if not m:
        return ""
    q = m.group(1)
    a = m.end()
    j = masked.find(q, a)
    if j < 0:
        return ""
    body = orig[a:j]
    if q == "''":
        lines = body.split("\n")
        ind = min((len(x) - len(x.lstrip()) for x in lines if x.strip()), default=0)
        body = "\n".join(x[ind:] for x in lines)
    return body


_KEY_RE = re.compile(r"\s*([A-Za-z_][\w'-]*|\"[^\"]*\")\s*=(?!=)")


def _top_keys(masked: str, orig: str, lbrace: int, rbrace: int) -> List[Tuple[str, int, int]]:
    out = []
    i = lbrace + 1
    d = 1
    expect = True
    while i < rbrace:
        c = masked[i]
        if d == 1 and expect:
            m = _KEY_RE.match(masked, i)
            if m:
                key = orig[m.start(1):m.end(1)].strip('"')
                out.append((key, m.start(1), m.end()))
                expect = False
                i = m.end()
                continue
            if not c.isspace():
                expect = False
        if c in "{[(":
            d += 1
        elif c in "}])":
            d -= 1
        elif c == ";" and d == 1:
            expect = True
        i += 1
    return out


_UNIT_DECL = re.compile(r"systemd\.(?:(user)\.)?(services|timers|sockets)\.(\"[^\"]*\"|[A-Za-z_][\w'-]*)((?:\.[\w'-]+)*)\s*=(?!=)")
_UNIT_SET = re.compile(r"systemd\.(?:(user)\.)?(services|timers|sockets)\s*=\s*\{")
_IMPORTS_BLOCK = re.compile(r"\bimports\s*=\s*(?:\[|lib\.[\w.]+\s*\[)")
_IMPORT_FN = re.compile(r"\bimport\s+(\.{1,2}/[\w./+-]+)")
_NIX_PATH = re.compile(r"(?<![\w$/.\"'])(\.{1,2}/[\w./+@-]+)")
_ALIAS = re.compile(r"\b(\w+)\s*=\s*config\.(mySystem(?:\.\w+)*)\s*;")
_MYSYS = re.compile(r"\bmySystem(?:\.[A-Za-z_][\w'-]*)+")


def parse_options(orig: str, masked: str, path: str) -> List[Tuple[str, str, int, int]]:
    """[(dotted-name, description, startLine, endLine)] for options declared under mySystem."""
    m = re.search(r"\boptions\.mySystem\s*=\s*\{", masked)
    if not m:
        return []
    lb = m.end() - 1
    out: List[Tuple[str, str, int, int]] = []

    def line_of(off: int) -> int:
        return orig.count("\n", 0, off) + 1

    def walk(lbrace: int, prefix: str) -> None:
        rb = _match_brace(masked, lbrace)
        for key, ks, vs in _top_keys(masked, orig, lbrace, rb):
            name = f"{prefix}.{key}" if prefix else key
            mm = re.compile(r"\s*(?:lib\.)?(mkOption|mkEnableOption|mkPackageOption)\b").match(masked, vs)
            if mm:
                kind = mm.group(1)
                if kind == "mkOption":
                    bi = masked.find("{", mm.end())
                    be = _match_brace(masked, bi)
                    dm = re.search(r"\bdescription\s*=", masked[bi:be])
                    desc = _nix_string_at(orig, masked, bi + dm.end()) if dm else ""
                    out.append((name, desc, line_of(ks), line_of(be)))
                elif kind == "mkEnableOption":
                    desc = _nix_string_at(orig, masked, mm.end())
                    out.append((name, "Enable " + desc if desc else "Enable option", line_of(ks), line_of(ks)))
                else:
                    out.append((name, "Package option", line_of(ks), line_of(ks)))
                continue
            sm = re.compile(r"\s*\{").match(masked, vs)
            if sm:
                walk(sm.end() - 1, name)

    walk(lb, "mySystem")
    return out


def build_nix(g: Graph, root: Path, texts: Dict[str, str], nixfiles: List[str], res: Resolver) -> Dict[str, List[dict]]:
    pending_units: Dict[str, List[dict]] = defaultdict(list)
    option_names: Dict[str, str] = {}
    nix_masked: Dict[str, str] = {}
    for path in nixfiles:
        text = texts[path]
        nlines = text.count("\n") + 1
        masked = mask_nix(text)
        nix_masked[path] = masked
        fid = f"file:{path}"
        hdr = _comment_header(text)
        src = "comment"
        if not hdr:
            dm = re.search(r"\bdescription\s*=", masked)
            hdr = _nix_string_at(text, masked, dm.end()).strip().split("\n")[0] if dm else ""
            src = "docstring" if hdr else "none"
        g.node(fid, "config", path.rsplit("/", 1)[-1], path, hdr, src, ["nix"], _bucket(nlines, 150, 500), language="nix")

    # options first so cross-references resolve
    opt_path = "nix/modules/core/options.nix"
    if opt_path in nix_masked:
        for name, desc, s, e in parse_options(texts[opt_path], nix_masked[opt_path], opt_path):
            oid = f"option:{name}"
            first = next((x.strip() for x in desc.split("\n") if x.strip()), "")
            g.node(oid, "config", name, opt_path, first or "mySystem option", "docstring" if first else "none",
                   ["nix", "option"], "simple", s, e, "nix")
            g.edge(f"file:{opt_path}", oid, "contains", 0.8)
            option_names[name] = oid

    unit_files: Dict[str, Set[str]] = defaultdict(set)
    for path in nixfiles:
        text = texts[path]
        masked = nix_masked[path]
        fid = f"file:{path}"
        d = path.rsplit("/", 1)[0]
        # imports
        for m in _IMPORTS_BLOCK.finditer(masked):
            lb = masked.index("[", m.start())
            depth = 0
            end = len(masked)
            for k in range(lb, len(masked)):
                if masked[k] == "[":
                    depth += 1
                elif masked[k] == "]":
                    depth -= 1
                    if depth == 0:
                        end = k
                        break
            for pm in _NIX_PATH.finditer(masked[lb:end]):
                r = res.resolve(pm.group(1), d)
                if r and r[0] != path:
                    g.edge(fid, f"file:{r[0]}", "imports", 1.0)
        for m in _IMPORT_FN.finditer(masked):
            r = res.resolve(m.group(1), d)
            if r and r[0] != path:
                g.edge(fid, f"file:{r[0]}", "imports", 1.0)
        # other relative path literals + repo script references
        for pm in _NIX_PATH.finditer(masked):
            r = res.resolve(pm.group(1), d)
            if not r or r[0] == path or (fid, f"file:{r[0]}", "imports") in g.edges:
                continue
            tgt = r[0]
            etype = "calls" if (tgt.startswith("scripts/") and not tgt.endswith(".nix")) else ("imports" if tgt.endswith(".nix") else "configures")
            g.edge(fid, f"file:{tgt}", etype, 0.6)
        for tok in extract_ref_tokens(_strip_nix_comments(text)):
            if tok.startswith(("./", "../")):
                continue
            r = res.resolve(tok, d)
            if r and r[0] != path and r[0].startswith(("scripts/", "config/")):
                g.edge(fid, f"file:{r[0]}", "calls" if r[0].startswith("scripts/") else "configures", min(r[1], 0.7))

        # units
        decls = []
        for m in _UNIT_DECL.finditer(masked):
            nm = text[m.start(3):m.end(3)].strip('"')
            if "${" in nm or not nm:
                continue
            decls.append((m.start(), m.group(1), m.group(2), nm))
        for sm in _UNIT_SET.finditer(masked):
            lb = sm.end() - 1
            rb = _match_brace(masked, lb)
            for key, ks, _vs in _top_keys(masked, text, lb, rb):
                if "${" in key or not key:
                    continue
                decls.append((ks, sm.group(1), sm.group(2), key))
        decls.sort()
        seen_here: Set[Tuple[str, str]] = set()
        for idx, (off, user, kind, nm) in enumerate(decls):
            end = decls[idx + 1][0] if idx + 1 < len(decls) else len(text)
            if (kind, nm) in seen_here:
                continue
            seen_here.add((kind, nm))
            span = text[off:end]
            dm = re.search(r"\bdescription\s*=\s*\"([^\"]*)\"", span[:4000])
            pending_units[nm + "|" + kind].append({
                "name": nm, "kind": kind, "user": bool(user), "path": path,
                "line": text.count("\n", 0, off) + 1, "endline": text.count("\n", 0, end) + 1,
                "desc": dm.group(1) if dm else "", "span": _strip_nix_comments(span),
            })
            unit_files[nm + "|" + kind].add(path)

        # mySystem.* references -> option nodes (configures)
        uncommented = _strip_nix_comments(text)  # keeps ${...} interpolations, unlike `masked`
        aliases = {}
        for am in _ALIAS.finditer(uncommented):
            aliases[am.group(1)] = am.group(2)
        refs: Set[str] = set()
        for m in _MYSYS.finditer(uncommented):
            refs.add(m.group(0))
        for alias, base in aliases.items():
            for m in re.finditer(r"\b" + re.escape(alias) + r"((?:\.[A-Za-z_][\w'-]*)+)", uncommented):
                refs.add(base + m.group(1))
        for r in refs:
            parts = r.split(".")
            while parts:
                nm = ".".join(parts)
                if nm in option_names:
                    if path != opt_path:
                        g.edge(fid, option_names[nm], "configures", 0.6)
                    break
                parts.pop()

    # materialise unit nodes (sorted for determinism)
    for key in sorted(pending_units):
        decls = pending_units[key]
        first = sorted(decls, key=lambda x: (x["path"], x["line"]))[0]
        nm, kind = first["name"], first["kind"]
        prefix = {"services": "service", "timers": "timer", "sockets": "socket"}[kind]
        uid = f"{prefix}:{nm}"
        desc = next((x["desc"] for x in sorted(decls, key=lambda x: (x["path"], x["line"])) if x["desc"]), "")
        tags = ["nix", "systemd", prefix] + (["user-unit"] if first["user"] else [])
        suffix = {"service": ".service", "timer": ".timer", "socket": ".socket"}[prefix]
        g.node(uid, "service", nm + (suffix if prefix != "service" else ""), first["path"],
               desc or f"systemd {prefix} {nm}", "docstring" if desc else "none", tags, "simple",
               first["line"], first["endline"], "nix")
        for dcl in decls:
            g.edge(f"file:{dcl['path']}", uid, "configures", 1.0)
            if "." not in dcl["path"].rsplit("/", 1)[-1]:
                continue
            for tok in extract_ref_tokens(dcl["span"]):
                r = res.resolve(tok, dcl["path"].rsplit("/", 1)[0])
                if r and r[0].startswith(("scripts/", "ai-stack/", "dashboard/", "tools/")) and not r[0].endswith(".nix"):
                    g.edge(uid, f"file:{r[0]}", "calls", min(r[1] + 0.0, 0.8))
    for key in sorted(pending_units):
        nm, kind = pending_units[key][0]["name"], pending_units[key][0]["kind"]
        if kind == "timers" and f"service:{nm}" in g.nodes:
            g.edge(f"timer:{nm}", f"service:{nm}", "calls", 0.9)
    return pending_units


def _strip_nix_comments(text: str) -> str:
    return "\n".join(re.sub(r"(^|\s)#.*$", "", ln) for ln in text.split("\n"))


# ── Markdown / config ────────────────────────────────────────────────────────

_MD_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
_MD_TICK = re.compile(r"`([^`\n]{2,200})`")


def md_summary(text: str) -> Tuple[str, str]:
    lines = text.split("\n")
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, min(len(lines), 60)):
            if lines[j].strip() == "---":
                fm = "\n".join(lines[1:j])
                dm = re.search(r"^description:\s*(.+)$", fm, re.M)
                i = j + 1
                if dm:
                    return dm.group(1).strip().strip("\"'"), "docstring"
                break
    heading = ""
    for k in range(i, min(len(lines), i + 80)):
        m = re.match(r"^#{1,3}\s+(.+?)\s*#*\s*$", lines[k])
        if m:
            heading = m.group(1)
            rest = lines[k + 1:k + 12]
            para = next((x.strip() for x in rest if x.strip() and not x.startswith(("#", "|", "```", "-", "*", ">", "<"))), "")
            return (f"{heading} - {para[:160]}" if para else heading), "heading"
    return "", "none"


def build_docs(g: Graph, root: Path, texts: Dict[str, str], mdfiles: List[str], res: Resolver) -> None:
    for path in mdfiles:
        text = texts[path]
        nlines = text.count("\n") + 1
        summ, src = md_summary(text)
        fid = f"file:{path}"
        tags = ["markdown"]
        if path.endswith("SKILL.md"):
            tags.append("skill")
        g.node(fid, "document", path.rsplit("/", 1)[-1], path, summ, src, tags,
               _bucket(nlines, 150, 500), language="markdown")
    for path in mdfiles:
        text = re.sub(r"```.*?```", lambda m: m.group(0), texts[path], flags=re.S)
        d = path.rsplit("/", 1)[0] if "/" in path else ""
        fid = f"file:{path}"
        cands: List[str] = []
        for m in _MD_LINK.finditer(text):
            u = m.group(1)
            if "://" not in u and not u.startswith("mailto:"):
                cands.append(u)
        for m in _MD_TICK.finditer(text):
            cands.extend(extract_ref_tokens(m.group(1)))
            first = m.group(1).split()[0] if m.group(1).split() else ""
            if "/" in first and "." in first.rsplit("/", 1)[-1]:
                cands.append(first)
        seen: Set[str] = set()
        for tok in cands:
            tok = re.sub(r":\d+(-\d+)?$", "", tok.strip().rstrip(".,;:)"))
            if tok in seen:
                continue
            seen.add(tok)
            r = res.resolve(tok, d)
            if r and r[0] != path:
                g.edge(fid, f"file:{r[0]}", "documents", min(r[1], 0.9))


def build_config_nodes(g: Graph, texts: Dict[str, str], cfgfiles: List[str]) -> None:
    for path in cfgfiles:
        text = texts[path]
        ext = path.rsplit(".", 1)[-1].lower()
        summ, src = "", "none"
        if ext == "json":
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    for k in ("description", "comment", "_comment", "title", "purpose"):
                        if isinstance(data.get(k), str) and data[k].strip():
                            summ, src = data[k], "docstring"
                            break
            except ValueError:
                pass
        else:
            h = _comment_header(text)
            if h:
                summ, src = h, "comment"
        g.node(f"file:{path}", "config", path.rsplit("/", 1)[-1], path, summ, src, [ext, "config"],
               _bucket(text.count("\n") + 1, 150, 600), language=ext)


# ── tests, capabilities ──────────────────────────────────────────────────────

def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (path.startswith(("scripts/testing/", "tests/")) or "/tests/" in path or "/test/" in path
            or name.startswith(("test_", "test-")) or name.endswith(("_test.py", "-test.sh", "_test.sh")))


def link_tests(g: Graph) -> None:
    tests = {n["id"] for n in g.nodes.values() if n["id"].startswith("file:") and is_test_path(n["filePath"])
             and n["type"] in ("file", "script")}
    add = []
    for (s, t, et), w in g.edges.items():
        if s in tests and t not in tests and et in ("imports", "calls") and t.startswith("file:") \
                and g.nodes[t]["type"] in ("file", "script", "config", "document"):
            add.append((s, t, max(w, 0.5)))
    for s, t, w in add:
        g.edge(s, t, "tests", w)
        g.edge(t, s, "tested_by", w)
    for tid in tests:
        n = g.nodes[tid]
        if "test" not in n["tags"]:
            n["tags"] = sorted(set(n["tags"]) | {"test"})


def apply_capabilities(g: Graph, root: Path) -> int:
    p = root / "config" / "capability-index.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    n = 0
    for e in data.get("entries", []):
        cls, kind, name, path = e.get("class"), e.get("kind"), e.get("name"), e.get("path")
        tags = {f"cap:{cls}", f"cap-kind:{kind}"}
        cat = re.sub(r"[^a-z0-9]+", "-", str(e.get("category", "")).lower()).strip("-")
        if cat:
            tags.add(f"cap-cat:{cat}")
        targets = []
        if kind in ("script", "skill", "mcp-tool"):
            targets.append(f"file:{path}")
            if kind == "mcp-tool":
                targets.append(f"function:{path}:{name}")
        elif kind == "unit":
            targets += [f"service:{name}", f"timer:{name}", f"file:{path}"]
        for t in targets:
            if t in g.nodes:
                g.nodes[t]["tags"] = sorted(set(g.nodes[t]["tags"]) | tags)
                n += 1
    return n


# ── LLM carry-forward ────────────────────────────────────────────────────────

def load_llm(root: Path, out_dir: Path) -> Optional[dict]:
    for cand in (out_dir / LLM_BACKUP_NAME, out_dir / "knowledge-graph.json"):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("metadata", {}).get("generator") != GENERATOR:
            return data
    return None


def carry_forward(g: Graph, old: dict) -> int:
    from_ids: Dict[str, dict] = {}
    by_key: Dict[Tuple[str, str, str], dict] = {}
    kind_of = {"function": "function", "function:": "function", "class": "class", "class:": "class"}
    for n in old.get("nodes", []):
        s = str(n.get("summary") or "").strip()
        if not s:
            continue
        fp, nm, ty = n.get("filePath") or "", n.get("name") or "", str(n.get("type"))
        if ty in kind_of:
            by_key.setdefault((kind_of[ty], fp, nm), n)
        if str(n.get("id", "")).startswith("file:") and str(n.get("id")) == f"file:{fp}":
            from_ids[n["id"]] = n
    carried = 0
    for nid, node in g.nodes.items():
        if g.src.get(nid) == "docstring":
            continue
        old_n = None
        if nid.startswith("file:"):
            old_n = from_ids.get(nid)
        elif nid.startswith(("function:", "class:")):
            kind = nid.split(":", 1)[0]
            qual = node["name"]
            old_n = by_key.get((kind, node["filePath"], qual)) or by_key.get((kind, node["filePath"], qual.rsplit(".", 1)[-1]))
        if not old_n:
            continue
        s = _clean(str(old_n["summary"]))
        if len(s) > len(node["summary"]):
            node["summary"] = s
            extra = [t for t in old_n.get("tags") or [] if isinstance(t, str)]
            node["tags"] = sorted(set(node["tags"]) | set(extra) | {LLM_TAG})
            carried += 1
    return carried


# ── top level ────────────────────────────────────────────────────────────────

def build(root: Path, old_graph: Optional[dict] = None) -> Tuple[dict, dict]:
    root = Path(root).resolve()
    sha, gen = git_head(root)
    files = [f for f in tracked_files(root) if not _excluded(f)]
    texts: Dict[str, str] = {}
    langs: Dict[str, str] = {}
    for f in files:
        ext = f.rsplit(".", 1)[-1] if "." in f.rsplit("/", 1)[-1] else ""
        if ext in SKIP_EXT:
            continue
        if ext in CONFIG_EXT:
            try:
                if (root / f).stat().st_size > CONFIG_MAX_BYTES:
                    continue
            except OSError:
                continue
        t = _read(root, f)
        if t is None:
            continue
        lang = classify(f, t[:200])
        if lang:
            langs[f] = lang
            texts[f] = t
    fileset = set(texts)
    res = Resolver(fileset)
    g = Graph()
    stats = Stats()
    py = sorted(f for f, l in langs.items() if l == "python")
    sh = sorted(f for f, l in langs.items() if l == "shell")
    nx = sorted(f for f, l in langs.items() if l == "nix")
    md = sorted(f for f, l in langs.items() if l == "markdown")
    cf = sorted(f for f, l in langs.items() if l.startswith("config:"))
    stats.files = len(texts)
    build_config_nodes(g, texts, cf)
    build_python(g, root, texts, py, res, stats)
    build_shell(g, root, texts, sh, res)
    build_nix(g, root, texts, nx, res)
    build_docs(g, root, texts, md, res)
    link_tests(g)
    caps = apply_capabilities(g, root)
    carried = carry_forward(g, old_graph) if old_graph else 0

    # directory containment is implied by filePath; add language-dir tag for search
    nodes = [g.nodes[k] for k in sorted(g.nodes)]
    edges = []
    for (s, t, et) in sorted(g.edges):
        edges.append({"source": s, "target": t, "type": et, "direction": "forward", "weight": g.edges[(s, t, et)]})
    project = ((old_graph or {}).get("metadata") or {}).get("project") or root.name
    graph = {
        "metadata": {
            "version": SCHEMA_VERSION, "generated": gen,
            "project": project,
            "generator": GENERATOR, "git_head": sha, "mode": "deterministic",
            "total_nodes": len(nodes), "total_edges": len(edges),
        },
        "nodes": nodes, "edges": edges,
    }
    info = {"python": stats.as_dict(), "capability_tags_applied": caps, "llm_summaries_carried": carried,
            "files_scanned": stats.files}
    return graph, info


def dumps(graph: dict) -> str:
    """One node / edge per line: valid JSON, stable, diff-friendly."""
    enc = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))  # noqa: E731
    parts = ['{"metadata":' + enc(graph["metadata"]), '"nodes":[\n' + ",\n".join(enc(n) for n in graph["nodes"]) + "\n]",
             '"edges":[\n' + ",\n".join(enc(e) for e in graph["edges"]) + "\n]}\n"]
    return ",\n".join(parts)


def write_atomic(path: Path, graph: dict, root: Path, backup: bool) -> Optional[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(dumps(graph), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))  # validate before swapping in
    moved = None
    if backup and path.exists():
        try:
            meta = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
        except (OSError, ValueError):
            meta = {}
        bk = path.parent / LLM_BACKUP_NAME
        if meta.get("generator") != GENERATOR and not bk.exists():
            os.replace(path, bk)
            moved = bk
    os.replace(tmp, path)
    return moved


def check_fresh(root: Path, graph_file: Path) -> Tuple[bool, str]:
    """Fresh = built by this generator and no in-scope tracked file changed since its git_head."""
    try:
        meta = json.loads(graph_file.read_text(encoding="utf-8")).get("metadata", {})
    except (OSError, ValueError):
        return False, "graph missing or unreadable"
    if meta.get("generator") != GENERATOR:
        return False, "graph not built by aq-graph-build"
    head = meta.get("git_head")
    try:
        cur = _git(root, "rev-parse", "HEAD").strip()
    except RuntimeError as exc:
        return False, str(exc)
    if head == cur:
        return True, f"git_head {cur[:10]} == HEAD"
    try:
        changed = _git(root, "diff", "--name-only", "-z", head, cur).split("\0")
    except RuntimeError:
        return False, f"git_head {str(head)[:10]} unknown to this repo"
    rel = [c for c in changed if c and not _excluded(c)]
    if rel:
        return False, f"{len(rel)} in-scope files changed since {str(head)[:10]} (e.g. {rel[0]})"
    return True, f"only excluded paths changed since {str(head)[:10]}"
