#!/usr/bin/env python3
"""sweep-dashboard: trace every dashboard card to its fetch, route and producer, and flag the lies on the way.

Recovery sweep P2.4 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Static by default: reads
the dashboard HTML, assets/dashboard.js (plus inline scripts) and dashboard/backend/api/{main.py,routes,services}.
Writes nothing except the optional --report/--trace files. A fact that cannot be determined is "unknown" and is
never counted as a pass.

Trace per card: card (DOM id + label) -> fetch (JS function + endpoint) -> route (handler or NO_ROUTE) ->
producer (file, URL/env, command, DB/client or computed).

Finding classes:
  NO_FETCH         card has a placeholder and no JS ever references its id (nothing updates it)
  NO_ROUTE         a fetch targets a route the backend does not serve (or serves under another method)
  NO_PRODUCER      a route reads a file path that nothing in the repo writes
  HARDCODED        literal number/status/model shown as if measured: HTML literal never replaced, JS
                   `?? 94` / catch-branch literal, or a route returning a constant
  SILENT_DEFAULT   route turns a failure/missing data into 0 / ok / healthy instead of unknown
  FAKE_FALLBACK    mock/sample/fixture/random data reachable from a production path
  RETIRED_REF      Antigravity (retired IDE lane) shown as live

Every finding carries a confidence (high/medium/low) and the limit of the heuristic that produced it. All
heuristics are lexical or AST-level over source text; none executes the dashboard. See LIMITS below.

--live: read-only GET against the running dashboard. Safe-GET rule (applied before any request): the route must
be declared GET, the JS call site must not pass a non-GET method, the path must have no parameters, no verb
segment (fire/execute/restart/...), and the handler plus the helpers it calls (2 hops) must contain no
side-effect marker (subprocess, file writes, outbound POST/PUT/DELETE, os.remove...). Anything else is skipped
and reported as unknown. Residual effect of a GET: the middleware appends one operator-audit line and counts
one rate-limit token per request. Base URL: --base-url, else $DASHBOARD_API_URL, else DASHBOARD_API_URL from
config/service-endpoints.sh (sourced in a subshell). Never POST.

Usage: sweep-dashboard.py [--json] [--report PATH] [--trace PATH] [--fail-on CLASS,...] [--repo DIR]
                          [--live] [--base-url URL] [--fresh-s N] [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[2]
CLASSES = ("NO_FETCH", "NO_ROUTE", "NO_PRODUCER", "HARDCODED", "SILENT_DEFAULT", "FAKE_FALLBACK", "RETIRED_REF")
LIMITS = {
    "html": "ids are matched lexically; a label is the nearest preceding text chunk and can belong to a neighbour",
    "js_span": "functions are split on column-0 declarations; indented/minified code collapses to one span, "
               "so a card and an endpoint in the same span are linked without proof of data flow",
    "js_ref": "an id counts as referenced if it appears as a quoted string, `#id`, or under a dynamic-id prefix; "
              "ids built by concatenation from runtime data are invisible",
    "chain": "a render function with no fetch is linked to the endpoints of its callers (2 hops); data passed "
             "through globals, events or WebSocket frames is not followed and the card is reported UNTRACED",
    "route": "routes come from decorators plus include_router prefixes in main.py; routes added by loops, "
             "mounts or plugins are invisible, so NO_ROUTE can be a false positive for those",
    "producer": "producers are string constants, env defaults and calls found by AST within 2 hops; paths built "
                "at runtime are not seen, so NO_PRODUCER is limited to literal/default paths",
    "writer": "'something writes it' means another repo file mentions the path/basename on a write-like line; "
              "a mention is not proof the writer runs or is enabled",
    "silent": "SILENT_DEFAULT is an AST pattern (except/missing-data branch returning 0/ok/healthy); a legitimate "
              "zero is indistinguishable from a masked failure without runtime evidence",
    "hardcoded_route": "a route is 'constant' only if its body has no call and no non-constant name; "
                       "constants loaded from config files are not constant",
    "live": "freshness comes from timestamp-looking keys in the JSON; no timestamp means unknown freshness",
}
STATUS_LIT = re.compile(r"^\W*(ok|healthy|online|nominal|active|pass(ed|ing)?|up|running|ready|connected|"
                        r"enabled|good|green|stable|synchronized|operational)\W*$", re.I)
METRIC_LIT = re.compile(r"^\W*[-+]?\d[\d.,]*\s*(%|ms|s|m|h|hrs?|gb|mb|kb|tb|°c|c|x|ops|/s|tok/s|layers|cores|"
                        r"connections|gates|\s*/\s*\d+.*)?\W*$", re.I)
PLACEHOLDER = re.compile(r"^\W*(--+|—|–|-|\.\.\.|…|n/?a|loading.*|\?|unknown|\s*)\W*$", re.I)
HONEST_LIT = re.compile(r"^\W*(--+|—|–|-|…|\.\.\.|n/?a|unknown|loading.*|error|unavailable|no data|\?)?\W*$", re.I)
VERB_SEG = re.compile(r"(^|/)(fire|execute|restart|start|stop|run|trigger|reset|clear|delete|apply|revoke|sync|"
                      r"refresh|reload|control|guidance|action|actions|kill|deploy|rollback|approve|reject|"
                      r"cancel|install|remove|enable|disable|update|set|create|launch|rebuild)(/|$|-)", re.I)
SIDE_EFFECT_ATTRS = {"system", "popen", "remove", "unlink", "rmdir", "rename", "replace", "makedirs", "mkdir",
                     "rmtree", "move", "copy", "copy2", "copyfile", "write", "write_text", "write_bytes",
                     "touch", "post", "put", "delete", "patch", "kill", "terminate", "send_signal", "restart",
                     "execute", "executemany", "commit", "setex", "set", "publish", "lpush", "rpush", "hset",
                     "sadd", "xadd", "create_subprocess_exec", "create_subprocess_shell", "run", "check_call",
                     "check_output", "Popen", "call"}
SIDE_EFFECT_NAMES = {"subprocess", "system", "Popen", "create_subprocess_exec", "create_subprocess_shell"}
FILE_PATH_RE = re.compile(r"^/(var|run|etc|tmp|home|proc|sys|opt|srv|nix/var)/[\w./@%-]*$")
FAKE_NAME_RE = re.compile(r"(?:^|_)(mock|fake|dummy|demo|fixture|stub|synthetic)(?:s)?(?:_|$)|sample_?data|"
                          r"^(Mock|Fake|Dummy|Demo|Fixture|Stub)")
OPT_IN_RE = re.compile(r"(TEST|MOCK|DEMO|FIXTURE|DEBUG|DEV_MODE|SIMULAT|DRY_RUN)", re.I)
RETIRED_WORDS = re.compile(r"(retired|deprecated|legacy|archived|former|sunset|removed|no longer)", re.I)
OK_WORDS = {"ok", "healthy", "up", "online", "running", "pass", "passing", "passed", "good", "active", "success",
            "available", "ready", "green", "nominal", "connected"}
STATUS_KEYS = {"status", "health", "state", "ok", "healthy", "overall", "result", "available", "ready"}
ERR_KEYS = {"error", "detail", "message", "reason", "unknown", "err", "warning", "errors"}
TS_KEYS = re.compile(r"(timestamp|updated_at|generated_at|last_[a-z_]*(at|run|update|seen|ts|time)|^ts$|^time$|"
                     r"created_at|checked_at|collected_at|as_of|mtime)", re.I)


# ───────────────────────────── helpers ─────────────────────────────
def rel(p, repo):
    try:
        return os.path.relpath(p, repo)
    except ValueError:
        return str(p)


def read(p):
    try:
        return Path(p).read_text(errors="replace")
    except OSError:
        return ""


def strip_js_comments(src: str) -> str:
    """Blank out // and /* */ comments, keeping length and newlines so line numbers stay valid."""
    out, i, n, q = [], 0, len(src), None
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == q or (c == "\n" and q != "`"):
                q = None
            i += 1
            continue
        if c in "'\"`":
            q = c
            out.append(c)
        elif c == "/" and nxt == "/" and (i == 0 or src[i - 1] != ":"):
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        elif c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


# ───────────────────────────── HTML ─────────────────────────────
class PageParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.elems, self.scripts = [], {}, []
        self._script = None
        self.last_label = ""
        self.texts = []  # (line, text) of every non-empty chunk, for retired-ref scanning

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if tag in ("script", "style"):
            self._script = {"tag": tag, "src": a.get("src"), "line": line, "text": []}
            return
        for e in self.stack:
            e["desc"] += 1
        el = {"tag": tag, "id": a.get("id"), "line": line, "text": "", "desc": 0, "cls": a.get("class", ""),
              "label": a.get("aria-label") or a.get("title") or self.last_label}
        for k, v in attrs:
            if k.startswith("on") and v:
                el.setdefault("handlers", []).append(v)
        if a.get("id"):
            self.elems.setdefault(a["id"], el)
        if tag not in self.VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]["tag"] == tag and tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._script:
            s, self._script = self._script, None
            if s["tag"] == "script":
                self.scripts.append({"src": s["src"], "line": s["line"], "text": "".join(s["text"])})
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self._script is not None:
            self._script["text"].append(data)
            return
        t = " ".join(data.split())
        if not t:
            return
        self.texts.append((self.getpos()[0], t))
        for e in self.stack:
            if len(e["text"]) < 240:
                e["text"] = (e["text"] + " " + t).strip()
        if re.search(r"[A-Za-z]{3}", t) and 3 <= len(t) <= 60 and not METRIC_LIT.match(t):
            self.last_label = t


def parse_page(path):
    p = PageParser()
    p.feed(read(path))
    return p


# ───────────────────────────── JS ─────────────────────────────
DECL_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(|"
    r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)")
STR_RE = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`", re.S)
WRITE_TOK = re.compile(r"\bsetText\(|\bsetHtml\(|\.textContent\s*=|\.innerHTML\s*=|\.innerText\s*=|\.value\s*=|"
                       r"\.insertAdjacentHTML\(|\.append\(|\.appendChild\(|\.style\.width\s*=|\.setAttribute\(")
LAYOUT_KEY = re.compile(r"(client|offset|inner|scroll)(Width|Height)|\.(val|length|size|width|height)$")
DEFAULT_RE = re.compile(r"([A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*)+)\s*(\?\?|\|\|)\s*(\d+(?:\.\d+)?)\b(?!\s*[*/%+\-]|\w)")
TERN_RE = re.compile(r"([A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*)+)\s*!=\s*null\s*\?[^:;\n]+:\s*(\d+(?:\.\d+)?)\s*[;,)]")
SETTEXT_LIT_RE = re.compile(r"\bsetText\(\s*[\"']([\w-]+)[\"']\s*,\s*[\"'`]?([^\"'`\n)]*)[\"'`]?\s*\)")
FAKE_JS_RE = re.compile(r"\b([Mm]ock\w*|[Ff]ake\w*|[Dd]ummy\w*|sampleData\w*|demoData\w*|MOCK_\w+|SAMPLE_DATA\w*|generateDemo\w*|"
                        r"simulate[A-Z]\w*)\b|Math\.random\(\)(?!\s*\.toString)")


def balanced(text, start):
    """Index just past the ')' matching the '(' at text[start]; strings are skipped."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            m = STR_RE.match(text, i)
            i = m.end() if m else i + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def norm_endpoint(raw):
    p = raw.replace("${BASE}", "")
    p = re.sub(r"\$\{[^}]*\}", "{}", p)
    p = p.split("?")[0].split("#")[0]
    if len(p) > 1:
        p = p.rstrip("/")
    return p


class Span:
    def __init__(self, name, start, end, text, src):
        self.name, self.start, self.end, self.text, self.src = name, start, end, text, src
        self.endpoints = []  # {path, method, line, via}
        self.unresolved = 0
        self.refs = set()
        self.calls = set()
        self.has_write = bool(WRITE_TOK.search(text))

    @property
    def key(self):
        return f"{self.src.label}:{self.name}"


class JsSource:
    def __init__(self, label, text, base_line=1):
        self.label = label
        self.base_line = base_line
        self.raw = text
        self.text = strip_js_comments(text)
        self.spans = self._split()

    def _split(self):
        lines = self.text.split("\n")
        decls = []
        for i, ln in enumerate(lines):
            m = DECL_RE.match(ln)
            if m:
                decls.append((i, m.group(1) or m.group(2)))
        if not decls:
            return [Span("<script>", 0, len(lines) - 1, self.text, self)]
        spans, covered = [], [False] * len(lines)
        for k, (i, name) in enumerate(decls):
            limit = decls[k + 1][0] - 1 if k + 1 < len(decls) else len(lines) - 1
            end = limit
            for j in range(i + 1, limit + 1):
                if lines[j].startswith("}") or lines[j].startswith(")"):
                    end = j
                    break
            spans.append(Span(name, i, end, "\n".join(lines[i:end + 1]), self))
            for j in range(i, end + 1):
                covered[j] = True
        top, cur = [], []
        for i, ln in enumerate(lines):
            if not covered[i]:
                cur.append(i)
            elif cur:
                top.append(cur)
                cur = []
        if cur:
            top.append(cur)
        for chunk in top:
            t = "\n".join(lines[i] for i in chunk)
            if t.strip():
                spans.append(Span("<top-level>", chunk[0], chunk[-1], t, self))
        return spans

    def line_of(self, span, offset):
        return self.base_line + span.start + span.text.count("\n", 0, offset)


def extract_endpoints(span):
    text = span.text
    # variable-held literal paths in this span, for apiFetch(url)
    assigned = {}
    for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;\n]+)", text):
        lits = [s for s in (g for t in STR_RE.findall(m.group(2)) for g in t) if s.startswith("/")]
        if lits:
            assigned[m.group(1)] = lits
    for m in re.finditer(r"\b(apiFetch|fetch)\s*\(", text):
        if m.start() > 0 and text[m.start() - 1] in "._$" or text[max(0, m.start() - 9):m.start()].endswith("function "):
            continue
        end = balanced(text, m.end() - 1)
        args = text[m.end():end - 1]
        line = span.src.line_of(span, m.start())
        method = "GET"
        mm = re.search(r"method\s*:\s*[\"'`](\w+)", args)
        if mm:
            method = mm.group(1).upper()
        elif re.search(r"\bopts\b|\boptions\b|\.\.\.", args.split(",", 1)[1] if "," in args else ""):
            method = "GET?"  # options object passed by variable: method unknown, assumed GET
        lits = [s for t in STR_RE.findall(args) for s in t if s]
        # only the first argument's literals count as paths
        first = args
        depth = 0
        for i, c in enumerate(args):
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "," and depth == 0:
                first = args[:i]
                break
        paths = [s for t in STR_RE.findall(first) for s in t if s and ("/" in s)]
        paths = [s for s in paths if s.startswith("/") or s.startswith("${BASE}/") or "/api/" in s]
        head = first.lstrip()
        if paths and head and head[0] not in "'\"`" and "?" not in first:
            paths = []  # `IDENT + "/x"`: the base is a runtime value, the literal is only a suffix
        paths = [s for s in paths if s != "/"]
        if not paths:
            ident = re.match(r"\s*([A-Za-z_$][\w$]*)\s*$", first)
            if ident and ident.group(1) in assigned:
                paths, via = assigned[ident.group(1)], "variable"
            else:
                span.unresolved += 1
                continue
        else:
            via = "literal"
        for raw in paths:
            p = norm_endpoint(raw)
            if m.group(1) == "apiFetch":
                p = "/api" + p
            elif p.startswith("{}"):
                p = p[2:]
            span.endpoints.append({"path": p, "method": method, "line": line, "via": via})
    for m in re.finditer(r"new\s+(WebSocket|EventSource)\s*\(", text):
        end = balanced(text, m.end() - 1)
        lits = [s for t in STR_RE.findall(text[m.end():end - 1]) for s in t if "/" in s]
        for raw in lits:
            raw = re.sub(r"^.*location\.host\}", "", raw)
            if not raw.startswith("/"):
                continue
            span.endpoints.append({"path": norm_endpoint(raw), "method": m.group(1).upper(),
                                   "line": span.src.line_of(span, m.start()), "via": "literal"})


def build_js(sources):
    spans, by_name = [], {}
    for s in sources:
        for sp in s.spans:
            extract_endpoints(sp)
            spans.append(sp)
            if sp.name not in ("<script>", "<top-level>"):
                by_name.setdefault(sp.name, []).append(sp)
    names = set(by_name)
    for sp in spans:
        for w in set(re.findall(r"[A-Za-z_$][\w$]*", sp.text)):
            if w in names and w != sp.name:
                sp.calls.add(w)
    callers = {}
    for sp in spans:
        for c in sp.calls:
            callers.setdefault(c, []).append(sp)
    return spans, by_name, callers


def nearest_eps(span, line):
    """Endpoint of the closest apiFetch/fetch at or above `line` in the span: the `.then(cb)` that owns it."""
    prev = [e for e in span.endpoints if e["line"] <= line]
    if not prev:
        return []
    top = max(e["line"] for e in prev)
    return sorted({e["path"] for e in prev if e["line"] == top})


def chain_endpoints(span, callers, depth=2, seen=None):
    """Endpoints that feed this span: its own, else those of its callers (breadth-first, depth hops)."""
    seen = seen or set()
    if span.endpoints:
        return [(e, span.name, 0) for e in span.endpoints], 0
    out, level = [], [span]
    for hop in range(1, depth + 1):
        nxt = []
        for s in level:
            for c in callers.get(s.name, []):
                if c.key in seen:
                    continue
                seen.add(c.key)
                if c.endpoints:
                    out += [(e, c.name, hop) for e in c.endpoints]
                else:
                    nxt.append(c)
        if out:
            return out, hop
        level = nxt
    return [], None


# ───────────────────────────── backend routes ─────────────────────────────
class PyModule:
    def __init__(self, path, repo):
        self.path, self.repo = Path(path), repo
        self.src = read(path)
        try:
            self.tree = ast.parse(self.src)
        except SyntaxError:
            self.tree = ast.parse("")
        self.funcs, self.methods, self.consts, self.imports = {}, {}, {}, {}
        for n in self.tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[n.name] = n
            elif isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.methods.setdefault(m.name, []).append(m)
            elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                tgt = n.targets[0] if isinstance(n, ast.Assign) else n.target
                if isinstance(tgt, ast.Name) and n.value is not None:
                    self.consts[tgt.id] = n.value
        self.docstrings = set()
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
                b = n.body[0]
                if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                    self.docstrings.add(id(b.value))
        for n in ast.walk(self.tree):
            if isinstance(n, ast.ImportFrom):
                target = self.resolve(n)
                for a in n.names:
                    sub = self.resolve(n, a.name)
                    if sub:
                        self.imports[a.asname or a.name] = sub
                    elif target:
                        self.imports[a.asname or a.name] = target

    def resolve(self, node, sub=None):
        mod = node.module or ""
        if sub:
            mod = (mod + "." + sub) if mod else sub
        backend = self.repo / "dashboard/backend"
        if node.level:
            base = self.path.parent
            for _ in range(node.level - 1):
                base = base.parent
            cand = base.joinpath(*mod.split(".")) if mod else base
        else:
            cand = backend.joinpath(*mod.split("."))
        for c in (cand.with_suffix(".py"), cand / "__init__.py"):
            if c.is_file() and not (sub is None and c.name == "__init__.py" and False):
                return c
        return None


class Backend:
    def __init__(self, repo):
        self.repo = Path(repo)
        self.api = self.repo / "dashboard/backend/api"
        self.modules = {}
        self.routes = []   # dicts: method, path, segs, handler, module, line, file
        self.ws_paths = []
        self.unmounted = []
        main = self.api / "main.py"
        if main.is_file():
            self._build(main)

    def mod(self, path):
        path = Path(path)
        if path not in self.modules:
            self.modules[path] = PyModule(path, self.repo)
        return self.modules[path]

    @staticmethod
    def _const_str(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    def _router_prefix(self, m):
        pref = {}
        for name, v in m.consts.items():
            if isinstance(v, ast.Call) and getattr(v.func, "id", getattr(v.func, "attr", "")) == "APIRouter":
                p = ""
                for kw in v.keywords:
                    if kw.arg == "prefix":
                        p = self._const_str(kw.value) or ""
                pref[name] = p
        return pref

    def _build(self, main):
        mm = self.mod(main)
        mounted = set()
        for n in ast.walk(mm.tree):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "include_router" and n.args:
                a = n.args[0]
                if not (isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)):
                    continue
                alias, rname = a.value.id, a.attr
                target = mm.imports.get(alias)
                if target is None:
                    continue
                inc = ""
                for kw in n.keywords:
                    if kw.arg == "prefix":
                        inc = self._const_str(kw.value) or ""
                rm = self.mod(target)
                rpref = self._router_prefix(rm).get(rname, "")
                mounted.add(Path(target))
                self._collect(rm, rname, inc + rpref)
        for p in sorted((self.api / "routes").glob("*.py")):
            if p not in mounted and p.name != "__init__.py" and re.search(r"@\w+\.(get|post)\(", read(p)):
                self.unmounted.append(rel(p, self.repo))
        # direct @app.* routes in main.py
        self._collect(mm, "app", "")

    def _collect(self, m, rname, prefix):
        for fn in list(m.funcs.values()):
            for d in fn.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and
                        isinstance(d.func.value, ast.Name) and d.func.value.id == rname):
                    continue
                meth = d.func.attr.lower()
                path = self._const_str(d.args[0]) if d.args else None
                if path is None:
                    for kw in d.keywords:
                        if kw.arg == "path":
                            path = self._const_str(kw.value)
                if path is None:
                    continue
                full = (prefix + path) or "/"
                if meth == "websocket":
                    self.ws_paths.append(full)
                if meth in ("get", "post", "put", "delete", "patch", "websocket", "head"):
                    self.routes.append({"method": meth.upper(), "path": full, "segs": segs(full), "handler": fn.name,
                                        "module": m, "line": fn.lineno, "file": rel(m.path, self.repo), "fn": fn})

    def match(self, path, method="GET"):
        """Return (route, status) where status is ok | method-mismatch | none."""
        es = segs(path)
        hit_other = None
        for r in self.routes:
            if seg_match(es, r["segs"]):
                if r["method"] == method or (method in ("GET?", "WEBSOCKET", "EVENTSOURCE") and r["method"] in ("GET", "WEBSOCKET")):
                    return r, "ok"
                hit_other = hit_other or r
        return (hit_other, "method-mismatch") if hit_other else (None, "none")


def segs(p):
    return [s for s in p.strip("/").split("/") if s != ""] or [""]


def seg_match(ep, rt):
    i = 0
    for k, r in enumerate(rt):
        if r.startswith("{") and r.endswith("}") and ":path" in r:
            return len(ep) > k
        if i >= len(ep):
            return False
        e = ep[i]
        if r.startswith("{") or e == "{}" or "{}" in e:
            i += 1
            continue
        if e != r:
            return False
        i += 1
    return i == len(ep)


# ───────────────────────── route analysis (AST) ─────────────────────────
def static_strings(node, mod, env_out=None, _depth=0):
    """String values a node can take statically: constants, module consts, env defaults, Path joins."""
    if _depth > 6 or node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        v = mod.consts.get(node.id)
        return static_strings(v, mod, env_out, _depth + 1) if v is not None else []
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            parts.append(v.value if isinstance(v, ast.Constant) else "{}")
        return ["".join(parts)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
        left = static_strings(node.left, mod, env_out, _depth + 1)
        right = static_strings(node.right, mod, env_out, _depth + 1)
        return [l.rstrip("/") + "/" + r.lstrip("/") if isinstance(node.op, ast.Div) else l + r
                for l in left for r in right] or left
    if isinstance(node, ast.Call):
        fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if fname in ("get", "getenv") and node.args:
            envn = static_strings(node.args[0], mod, None, _depth + 1)
            if envn and env_out is not None and re.match(r"^[A-Z][A-Z0-9_]+$", envn[0]):
                env_out.add(envn[0])
            if len(node.args) > 1:
                return static_strings(node.args[1], mod, env_out, _depth + 1)
            return []
        if fname in ("Path", "join", "expanduser", "resolve", "str") and node.args:
            out = []
            for a in node.args:
                out = [o + "/" + s if o else s for o in (out or [""]) for s in static_strings(a, mod, env_out, _depth + 1)] \
                    if fname == "join" else static_strings(a, mod, env_out, _depth + 1)
            return out
    return []


class Producer:
    def __init__(self):
        self.files, self.urls, self.envs, self.commands, self.clients = {}, set(), set(), set(), set()
        self.followed = []

    def summary(self):
        parts = [f"file {p}" for p in sorted(self.files)]
        parts += [f"url {u}" for u in sorted(self.urls)]
        parts += [f"env {e}" for e in sorted(self.envs) if e.endswith(("_URL", "_ENDPOINT", "_HOST", "_PORT"))]
        parts += [f"cmd {c}" for c in sorted(self.commands)]
        parts += [f"client {c}" for c in sorted(self.clients)]
        return "; ".join(parts[:8]) + (f" (+{len(parts) - 8} more)" if len(parts) > 8 else "") if parts else "computed (no file, URL, command or client found)"


CLIENT_NAMES = {"psycopg": "postgres", "psycopg2": "postgres", "asyncpg": "postgres", "sqlite3": "sqlite",
                "redis": "redis", "aioredis": "redis", "qdrant_client": "qdrant", "aiohttp": "http-service",
                "httpx": "http-service", "requests": "http-service", "psutil": "host (psutil, live)",
                "docker": "docker"}


def follow_targets(fn, mod, backend):
    """Functions called from fn that we can resolve: same-module helpers, imported service functions/methods."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name):
            if n.func.id in mod.funcs and mod.funcs[n.func.id] is not fn:
                out.append((mod.funcs[n.func.id], mod))
            elif n.func.id in mod.imports:
                tm = backend.mod(mod.imports[n.func.id])
                if n.func.id in tm.funcs:
                    out.append((tm.funcs[n.func.id], tm))
        elif isinstance(n.func, ast.Attribute):
            name = n.func.attr
            if name in mod.funcs and isinstance(n.func.value, ast.Name) and n.func.value.id in ("self",):
                out.append((mod.funcs[name], mod))
            for imp in {p for p in mod.imports.values() if "services" in str(p)}:
                tm = backend.mod(imp)
                cands = tm.methods.get(name, [])
                if len(cands) == 1:
                    out.append((cands[0], tm))
                elif name in tm.funcs:
                    out.append((tm.funcs[name], tm))
    return out


def walk_reach(fn, mod, backend, depth=2):
    """[(function, module, hop)] for fn and everything it resolvably calls within depth hops."""
    seen, out, level = {id(fn)}, [(fn, mod, 0)], [(fn, mod)]
    for hop in range(1, depth + 1):
        nxt = []
        for f, m in level:
            for tf, tm in follow_targets(f, m, backend):
                if id(tf) not in seen:
                    seen.add(id(tf))
                    out.append((tf, tm, hop))
                    nxt.append((tf, tm))
        level = nxt
    return out


def analyse_producer(reach, repo):
    prod = Producer()
    for fn, mod, hop in reach:
        if hop:
            prod.followed.append(f"{rel(mod.path, repo)}:{fn.name}")
        for n in ast.walk(fn):
            vals, env = [], set()
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                vals = [n.value]
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in mod.consts:
                vals = static_strings(n, mod, env)
            elif isinstance(n, ast.Call):
                vals = static_strings(n, mod, env)
                fname = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if fname in ("run", "check_output", "check_call", "Popen", "create_subprocess_exec", "create_subprocess_shell") and n.args:
                    a = n.args[0]
                    lits = [x for x in (static_strings(e, mod) for e in (a.elts if isinstance(a, (ast.List, ast.Tuple)) else [a])) for x in x]
                    if lits:
                        prod.commands.add(" ".join(lits[:3])[:80])
            for v in vals:
                if FILE_PATH_RE.match(v) and "{}" not in v:
                    prod.files[v] = rel(mod.path, repo)
                elif re.match(r"^https?://", v):
                    prod.urls.add(re.sub(r"\{\}.*", "{}", v)[:80])
            prod.envs |= env
            if isinstance(n, ast.Name) and n.id in CLIENT_NAMES:
                prod.clients.add(CLIENT_NAMES[n.id])
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in CLIENT_NAMES:
                prod.clients.add(CLIENT_NAMES[n.value.id])
    return prod


def has_side_effect(reach):
    for fn, mod, _ in reach:
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr in SIDE_EFFECT_ATTRS:
                    if f.attr in ("get", "set") or (f.attr == "run" and not (isinstance(f.value, ast.Name) and f.value.id == "subprocess")):
                        continue
                    if f.attr == "call" and not (isinstance(f.value, ast.Name) and f.value.id == "subprocess"):
                        continue
                    return f"{f.attr}() in {fn.name}"
                if isinstance(f, ast.Name) and f.id in SIDE_EFFECT_NAMES:
                    return f"{f.id}() in {fn.name}"
                if isinstance(f, ast.Name) and f.id == "open":
                    mode = ""
                    if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                        mode = str(n.args[1].value)
                    for kw in n.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = str(kw.value.value)
                    if any(c in mode for c in "wax+"):
                        return f"open(mode={mode!r}) in {fn.name}"
    return None


def ok_value(v):
    if isinstance(v, ast.Constant):
        if v.value is True:
            return True
        if isinstance(v.value, str) and v.value.strip().lower() in OK_WORDS:
            return True
        if isinstance(v.value, (int, float)) and not isinstance(v.value, bool) and v.value == 0:
            return True
    return False


def silent_return(ret):
    """True if a Return value presents success/zero with no error marker."""
    v = ret.value
    if v is None:
        return False
    if isinstance(v, ast.Constant):
        return ok_value(v)
    if isinstance(v, ast.Dict):
        keys = {k.value for k in v.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if keys & ERR_KEYS or any(k.lower().startswith(("err", "unknown")) for k in keys):
            return False
        for k, val in zip(v.keys, v.values):
            kn = k.value if isinstance(k, ast.Constant) else ""
            if kn in STATUS_KEYS and ok_value(val):
                return True
            if kn in {"score", "count", "total", "healthy", "pct", "percent", "rate", "value"} and isinstance(val, ast.Constant) \
                    and isinstance(val.value, (int, float)) and not isinstance(val.value, bool) and val.value in (0, 100):
                return True
    return False


def missing_guard(test):
    t = ast.unparse(test)
    return bool(re.search(r"\.exists\(\)|os\.path\.(exists|isfile|isdir)|\bnot\s+\w+(\.\w+)*\s*$|is None|== None|len\(.*\)\s*==\s*0", t)) \
        and bool(re.match(r"^(not\s|.*(is None|== None|== 0))", t) or "not " in t)


def scan_silent(fn, mod):
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.ExceptHandler):
            if any(isinstance(x, ast.Raise) for x in ast.walk(n)):
                continue
            for r in [x for x in ast.walk(n) if isinstance(x, ast.Return)]:
                if silent_return(r):
                    out.append((r.lineno, "except branch returns ok/zero instead of unknown: " + ast.unparse(r)[:90], "high"))
        elif isinstance(n, ast.If) and missing_guard(n.test):
            for r in [x for x in n.body if isinstance(x, ast.Return)]:
                if silent_return(r):
                    out.append((r.lineno, f"missing-data branch `if {ast.unparse(n.test)[:50]}` returns ok/zero: " + ast.unparse(r)[:70], "medium"))
    return out


def lit_only(node, mod, depth=0):
    """True if the expression is built only from literals (following module-level literal constants)."""
    if depth > 4:
        return False
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(lit_only(e, mod, depth + 1) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is None or lit_only(k, mod, depth + 1) for k in node.keys) and all(lit_only(v, mod, depth + 1) for v in node.values)
    if isinstance(node, ast.Name) and node.id in mod.consts:
        return lit_only(mod.consts[node.id], mod, depth + 1)
    if isinstance(node, ast.Call):
        f = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if f in ("now", "utcnow", "isoformat", "time", "strftime", "timestamp", "dict"):
            return all(lit_only(a, mod, depth + 1) for a in node.args) if f == "dict" else True
        return False
    if isinstance(node, ast.UnaryOp):
        return lit_only(node.operand, mod, depth + 1)
    return False


def literal_payload(node, mod, depth=0):
    """Does the literal contain a number or status word that would read as a measurement?"""
    if isinstance(node, ast.Name) and node.id in mod.consts and depth < 4:
        return literal_payload(mod.consts[node.id], mod, depth + 1)
    for n in ast.walk(node):
        if isinstance(n, ast.Constant):
            if isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
                return True
            if isinstance(n.value, str) and (n.value.strip().lower() in OK_WORDS or STATUS_LIT.match(n.value)):
                return True
    return False


def body_nodes(fn):
    """Nodes inside the function body only; decorators (`@router.get(...)`) are calls and names but not logic."""
    for st in fn.body:
        yield from ast.walk(st)


def scan_hardcoded_route(fn, mod):
    if any(isinstance(n, (ast.Await, ast.Call)) and not (isinstance(n, ast.Call) and lit_only(n, mod)) for n in body_nodes(fn)):
        return None
    params = {a.arg for a in fn.args.args}
    for n in body_nodes(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in params and n.id not in mod.consts \
                and n.id not in ("True", "False", "None", "dict", "list"):
            return None
    rets = [n for n in body_nodes(fn) if isinstance(n, ast.Return) and n.value is not None]
    if not rets:
        return None
    for r in rets:
        if lit_only(r.value, mod) and literal_payload(r.value, mod):
            return (r.lineno, "route returns a constant with numbers/status words and reads nothing: " + ast.unparse(r)[:90])
    return None


def scan_fake(fn, mod):
    out = []
    gated_lines = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and OPT_IN_RE.search(ast.unparse(n.test)):
            for x in ast.walk(n):
                if hasattr(x, "lineno"):
                    gated_lines.add(x.lineno)
    dict_keys = {id(k) for d in ast.walk(fn) if isinstance(d, ast.Dict) for k in d.keys if k is not None}
    for n in ast.walk(fn):
        ln = getattr(n, "lineno", 0)
        if ln in gated_lines:
            continue
        name = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else \
            n.name if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn else None
        if name and FAKE_NAME_RE.search(name) and not name.startswith("__"):
            out.append((ln, f"identifier `{name}` on a production path", "medium"))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                and n.func.value.id == "random" and n.func.attr in ("random", "randint", "uniform", "choice", "gauss"):
            out.append((ln, f"random.{n.func.attr}() feeding a response", "high"))
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"(mock|sample|fake|demo|simulated|placeholder)( data)?", n.value.strip(), re.I) \
                and id(n) not in mod.docstrings and id(n) not in dict_keys:
            out.append((ln, f"response/branch literal {n.value!r}", "medium"))
    return out


def scan_retired_py(fn, mod):
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and "antigravity" in n.value.lower() \
                and id(n) not in mod.docstrings and not RETIRED_WORDS.search(n.value):
            out.append((getattr(n, "lineno", 0), f"string {n.value[:60]!r} names the retired Antigravity lane", "medium"))
    return out


# ───────────────────────── writer search (NO_PRODUCER) ─────────────────────────
WRITE_LINE = re.compile(r"(>>?\s*[\"']?\$?\{?[\w/.-]*|\btee\b|write|dump|open\([^)]*[\"'][wax]|mkdir|touch|StateDirectory|"
                        r"LogsDirectory|tmpfiles|ReadWritePaths|os\.replace|rename|\bmv\b|\bcp\b|append|FileHandler|"
                        r"\bsave|\bpersist|\bemit|\blog_to|json\.dump)", re.I)
WRITER_DIRS = ("scripts", "ai-stack", "nix", "systemd", "lib", "config", "dashboard", "deploy", "phases", "templates", "tools")
_writer_cache = {}


def writer_corpus(repo):
    key = str(repo)
    if key in _writer_cache:
        return _writer_cache[key]
    corpus = []
    for d in WRITER_DIRS:
        root = Path(repo) / d
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix not in (".py", ".sh", ".nix", ".service", ".timer", ".json", ".yaml", ".yml", "") \
                    or "/tests/" in str(p) or p.name.startswith("test-") or "node_modules" in p.parts:
                continue
            try:
                if p.stat().st_size > 800_000:
                    continue
            except OSError:
                continue
            corpus.append((rel(p, repo), read(p)))
    _writer_cache[key] = corpus
    return corpus


def find_writer(path, reader_file, repo):
    """(evidence, strength) where evidence names a file:line that writes `path`, or None."""
    base = os.path.basename(path.rstrip("/"))
    needles = [path]
    if len(base) >= 6:
        needles.append(base)
    for f, text in writer_corpus(repo):
        if f == reader_file or f.startswith("dashboard/backend/api/routes/"):
            continue
        for nd in needles:
            if nd not in text:
                continue
            for i, ln in enumerate(text.split("\n"), 1):
                if nd in ln and WRITE_LINE.search(ln):
                    return f"{f}:{i}", ("exact path" if nd == path else "basename")
            # path declared as a service state/log dir by a parent directory
    parent = os.path.dirname(path.rstrip("/"))
    for f, text in writer_corpus(repo):
        if f.startswith("nix/") and parent and parent in text and re.search(r"StateDirectory|tmpfiles|LogsDirectory|ReadWritePaths", text):
            return f, "parent dir declared by nix"
    return None


# ───────────────────────────── analysis ─────────────────────────────
def page_scripts(page_path, page, repo):
    srcs, repo = [], Path(repo)
    label = rel(page_path, repo)
    for i, sc in enumerate(page.scripts):
        if sc["src"]:
            sp = sc["src"].split("?")[0]
            if sp.startswith("http") or "/vendor/" in sp:
                continue
            cand = repo / sp.lstrip("/")
            if cand.is_file():
                srcs.append(("file", str(cand), JsSource(rel(cand, repo), read(cand))))
        elif sc["text"].strip():
            srcs.append(("inline", label, JsSource(f"{label}#inline{i}", sc["text"], sc["line"])))
    return srcs


def default_pages(repo):
    repo = Path(repo)
    pages = []
    if (repo / "dashboard.html").is_file():
        pages.append(repo / "dashboard.html")
    for pat in ("assets/*.html", "assets/modules/*.html", "assets/cockpit/*.html", "dashboard/backend/static/*.html"):
        pages += sorted(repo.glob(pat))
    return pages


def card_candidate(el, referenced_ids, ids_written):
    txt = el["text"]
    leafish = el["desc"] <= 3
    placeholder = bool(PLACEHOLDER.match(txt)) and leafish
    literal = leafish and txt and (bool(METRIC_LIT.match(txt)) or bool(STATUS_LIT.match(txt)))
    return placeholder, literal


def analyse(repo, pages=None):
    repo = Path(repo)
    backend = Backend(repo)
    pages = [Path(p) for p in (pages or default_pages(repo))]
    findings, cards, endpoints = [], [], {}
    js_seen = {}
    page_data = []
    all_js_text = ""
    for pp in pages:
        pg = parse_page(pp)
        srcs = page_scripts(pp, pg, repo)
        page_data.append((pp, pg, srcs))
        for kind, key, js in srcs:
            if key not in js_seen:
                js_seen[key] = js
    sources = list(js_seen.values()) + [s for _, _, ss in page_data for k, _, s in ss if k == "inline"]
    spans, by_name, callers = build_js(sources)
    all_js_text = "\n".join(s.text for s in sources)
    quoted = set()
    for t in STR_RE.findall(all_js_text):
        quoted.update(x for x in t if x)
    hash_refs = set(re.findall(r"#([A-Za-z][\w-]*)", all_js_text))
    dyn_prefixes = set()
    for m in re.finditer(r"(?:getElementById|setText|setHtml|\$)\(\s*`([^`$]*)\$\{", all_js_text):
        if m.group(1):
            dyn_prefixes.add(m.group(1))
    for m in re.finditer(r"""(?:getElementById|setText|setHtml)\(\s*["']([\w-]+)["']\s*\+""", all_js_text):
        dyn_prefixes.add(m.group(1))
    handler_text = ""

    # id -> spans referencing it
    span_refs = {}
    id_re = re.compile(r"""["'`#]([A-Za-z][\w-]*)["'`]?""")
    for sp in spans:
        ids = set(id_re.findall(sp.text))
        sp.refs = ids
        for i in ids:
            span_refs.setdefault(i, []).append(sp)

    route_cache, prod_cache = {}, {}

    def route_info(ep):
        k = (ep["path"], ep["method"])
        if k not in route_cache:
            r, st = backend.match(ep["path"], ep["method"])
            info = {"route": r, "status": st}
            if r:
                reach = walk_reach(r["fn"], r["module"], backend)
                prod = analyse_producer(reach, repo)
                info.update(reach=reach, prod=prod)
            route_cache[k] = info
        return route_cache[k]

    seen_find = {}

    def add(cls, subject, evidence, conf, where, cards_=None, limit="", **kw):
        k = (cls, subject, evidence[:60])
        if k in seen_find:
            f = seen_find[k]
            for c in cards_ or []:
                if c not in f["cards"]:
                    f["cards"].append(c)
            return
        f = {"class": cls, "subject": subject, "evidence": evidence, "confidence": conf, "where": where,
             "cards": list(cards_ or []), "limit": limit or LIMITS.get(kw.get("lim", ""), "")}
        f.update({k2: v for k2, v in kw.items() if k2 != "lim"})
        seen_find[k] = f
        findings.append(f)

    # ---- cards ----
    card_rows = []
    used_endpoints = {}
    for pp, pg, srcs in page_data:
        plabel = rel(pp, repo)
        for cid, el in pg.elems.items():
            placeholder, literal = card_candidate(el, quoted, None)
            ref_spans = span_refs.get(cid, [])
            writers = [s for s in ref_spans if s.has_write]
            referenced = bool(ref_spans) or cid in hash_refs or any(cid.startswith(p) for p in dyn_prefixes)
            dyn_only = not ref_spans and cid not in hash_refs and any(cid.startswith(p) for p in dyn_prefixes)
            if not (placeholder or literal or writers):
                continue
            row = {"id": cid, "page": plabel, "line": el["line"], "label": el["label"] or cid, "initial": el["text"][:40],
                   "writers": [], "fetch": [], "route": None, "producer": None, "status": None}
            cards.append(row)
            if not referenced and not el.get("handlers"):
                row["status"] = "NO_FETCH"
                if literal and not placeholder:
                    add("HARDCODED", cid, f"HTML shows literal {el['text'][:30]!r} and no script ever references #{cid}: it is never replaced",
                        "high", f"{plabel}:{el['line']}", [cid], lim="html", label=row["label"])
                else:
                    add("NO_FETCH", cid, f"placeholder {el['text'][:30]!r} and no script references #{cid}", "high",
                        f"{plabel}:{el['line']}", [cid], lim="js_ref", label=row["label"])
                continue
            if dyn_only:
                row["status"] = "UNTRACED"
                row["note"] = "id only matches a dynamic-id prefix"
                continue
            if not writers:
                row["status"] = "UNTRACED"
                row["note"] = "referenced but never written (show/hide, attribute or listener only)"
                continue
            eps_all = []
            for sp in writers:
                row["writers"].append(sp.name)
                eps, hop = chain_endpoints(sp, callers)
                for e, via, h in eps:
                    eps_all.append((e, sp, via, h))
            if not eps_all:
                row["status"] = "UNTRACED"
                row["note"] = "written by JS but no fetch reachable in 2 caller hops (WebSocket/timer/DOM-derived or unresolved fetch)"
                if literal:
                    add("HARDCODED", cid, f"HTML shows literal {el['text'][:30]!r}; JS writes it from no traced fetch ({', '.join(row['writers'][:2])})",
                        "low", f"{plabel}:{el['line']}", [cid], lim="chain", label=row["label"])
                continue
            direct = all(h == 0 for _, _, _, h in eps_all)
            multi = len({e["path"] for e, _, _, _ in eps_all}) > 1
            row["fetch"] = sorted({f"{via}() -> {e['method']} {e['path']}" for e, _, via, _ in eps_all})[:6]
            row["confidence"] = "high" if direct and not multi else "medium" if direct or not multi else "low"
            routes_found = []
            for e, sp, via, h in eps_all:
                used_endpoints.setdefault((e["path"], e["method"]), []).append((cid, via, e["line"], sp.src.label))
                info = route_info(e)
                if info["route"] is not None and info["status"] == "ok":
                    routes_found.append((e, info))
                else:
                    detail = "no route serves this path" if info["status"] == "none" else \
                        f"path exists only as {info['route']['method']} ({info['route']['file']}:{info['route']['line']}) but the page calls {e['method'].rstrip('?')}"
                    add("NO_ROUTE", e["path"], f"{via}() at {e['line']} fetches {e['method'].rstrip('?')} {e['path']}: {detail}",
                        "high" if direct else "medium", f"{sp.src.label}:{e['line']}", [cid], lim="route", label=row["label"])
            if routes_found:
                e, info = routes_found[0]
                r = info["route"]
                row["route"] = f"{r['file']}:{r['line']} {r['handler']}"
                row["producer"] = info["prod"].summary()
                row["status"] = "TRACED"
            else:
                row["status"] = "NO_ROUTE"

            # JS fallback literals in writer spans
            for sp in writers:
                for m in DEFAULT_RE.finditer(sp.text):
                    expr, op, num = m.groups()
                    if float(num) in (0, 1) or LAYOUT_KEY.search(expr):
                        continue
                    line = sp.src.line_of(sp, m.start())
                    add("HARDCODED", f"{sp.name}:{expr}", f"`{expr} {op} {num}` shows {num} as if measured when the response lacks the field",
                        "medium", f"{sp.src.label}:{line}", [cid], lim="js_span", js_key=expr.split(".")[-1], js_default=num, span=sp.name, eps=nearest_eps(sp, line))
                for m in TERN_RE.finditer(sp.text):
                    expr, num = m.groups()
                    line = sp.src.line_of(sp, m.start())
                    add("HARDCODED", f"{sp.name}:{expr}", f"`{expr} != null ? ... : {num}` shows {num} as if measured when the field is missing",
                        "medium", f"{sp.src.label}:{line}", [cid], lim="js_span", js_key=expr.split(".")[-1], js_default=num, span=sp.name, eps=nearest_eps(sp, line))
            # per-card JS literal write
        # setText literal writes (per page sources)
    for sp in spans:
        for m in SETTEXT_LIT_RE.finditer(sp.text):
            cid, val = m.group(1), m.group(2).strip()
            if cid in {c["id"] for c in cards} and not HONEST_LIT.match(val) and (METRIC_LIT.match(val) or STATUS_LIT.match(val)) and "${" not in val:
                ctx = sp.text[max(0, m.start() - 200):m.start()]
                in_fail = bool(re.search(r"catch|else\s*\{|\.catch\(|if\s*\(\s*!", ctx))
                add("HARDCODED", cid, f"setText({cid!r}, {val!r}) writes a literal as if measured" + (" (failure/else branch: shown when the fetch fails)" if in_fail else ""),
                    "high" if in_fail else "medium", f"{sp.src.label}:{sp.src.line_of(sp, m.start())}", [cid], lim="js_span")

    # JS fake data / retired refs in spans that write cards
    card_ids = {c["id"] for c in cards}
    for sp in spans:
        if not sp.has_write:
            continue
        wrote = [c for c in sp.refs if c in card_ids][:6]
        code_only = STR_RE.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], sp.text)
        for m in FAKE_JS_RE.finditer(code_only):
            line = sp.src.line_of(sp, m.start())
            add("FAKE_FALLBACK", f"{sp.name}", f"`{m.group(0)}` in a function that writes cards", "medium",
                f"{sp.src.label}:{line}", wrote, lim="js_span")
            break
    # RETIRED_REF in HTML/JS text
    for pp, pg, srcs in page_data:
        plabel = rel(pp, repo)
        for ln, t in pg.texts:
            if "antigravity" in t.lower() and not RETIRED_WORDS.search(t):
                near = [(i, e) for i, e in pg.elems.items() if abs(e["line"] - ln) <= 1]
                owner = min(near, key=lambda ie: abs(ie[1]["line"] - ln), default=None)
                add("RETIRED_REF", f"{plabel}:{ln}", f"text {t[:70]!r} presents the retired Antigravity lane", "high" if owner else "medium",
                    f"{plabel}:{ln}", [owner[0]] if owner else [], limit="text scan only; context (retired/legacy wording elsewhere on the page) is not read")
    for sp in spans:
        for m in re.finditer(r"antigravity", sp.text, re.I):
            ln = sp.text.split("\n")[sp.text.count("\n", 0, m.start())]
            if not RETIRED_WORDS.search(ln):
                add("RETIRED_REF", sp.name, f"JS references Antigravity: {ln.strip()[:80]!r}", "medium",
                    f"{sp.src.label}:{sp.src.line_of(sp, m.start())}", [], limit="text scan only")

    # ---- route-level findings for every route a card (or any traced fetch) uses ----
    route_cards = {}
    for (path, method), uses in used_endpoints.items():
        info = route_info({"path": path, "method": method})
        if info["route"] is None or info["status"] != "ok":
            continue
        r = info["route"]
        cids = sorted({u[0] for u in uses})
        route_cards.setdefault((r["file"], r["handler"]), {"route": r, "paths": set(), "cards": set(), "info": info})
        route_cards[(r["file"], r["handler"])]["paths"].add(f"{method.rstrip('?')} {path}")
        route_cards[(r["file"], r["handler"])]["cards"].update(cids)
    for (f, h), rc in sorted(route_cards.items()):
        r, info = rc["route"], rc["info"]
        subj = f"{r['file']}:{h}"
        where_base = r["file"]
        cl = sorted(rc["cards"])
        hc = scan_hardcoded_route(r["fn"], r["module"])
        if hc:
            add("HARDCODED", subj, hc[1], "high", f"{where_base}:{hc[0]}", cl, lim="hardcoded_route", paths=sorted(rc["paths"]))
        for fn, mod, hop in info["reach"]:
            fl = rel(mod.path, repo)
            for ln, ev, conf in scan_silent(fn, mod):
                add("SILENT_DEFAULT", subj, ev + (f" [via {fl}:{fn.name}]" if hop else ""), conf if hop == 0 else ("medium" if conf == "high" else "low"),
                    f"{fl}:{ln}", cl, lim="silent", paths=sorted(rc["paths"]))
            for ln, ev, conf in scan_fake(fn, mod):
                add("FAKE_FALLBACK", subj, ev + (f" [via {fl}:{fn.name}]" if hop else ""), conf, f"{fl}:{ln}", cl, limit=LIMITS["silent"].split(";")[0] + "; helper reach is 2 hops",
                    paths=sorted(rc["paths"]))
            for ln, ev, conf in scan_retired_py(fn, mod):
                add("RETIRED_REF", subj, ev, conf, f"{fl}:{ln}", cl, limit="string scan; route output not executed", paths=sorted(rc["paths"]))
        prod = info["prod"]
        for p, readf in sorted(prod.files.items()):
            if "*" in p or p.endswith("/"):
                continue
            w = find_writer(p, readf, repo)
            if w is None:
                add("NO_PRODUCER", f"{subj} <- {p}", f"route reads {p} ({readf}); no repo file writes that path or its basename", "medium",
                    f"{readf}", cl, lim="writer", paths=sorted(rc["paths"]))
    # cards written from routes with unresolved fetch: note only (in stats)
    stats = {
        "pages": len(pages), "js_sources": len(sources), "js_spans": len(spans),
        "html_ids": sum(len(pg.elems) for _, pg, _ in page_data),
        "routes": len(backend.routes), "unmounted_route_modules": backend.unmounted,
        "cards": len(cards), "endpoints_used": len(used_endpoints),
        "unresolved_fetches": sum(s.unresolved for s in spans),
        "status": {},
    }
    for c in cards:
        stats["status"][c["status"]] = stats["status"].get(c["status"], 0) + 1
    counts = {c: 0 for c in CLASSES}
    card_counts = {c: set() for c in CLASSES}
    for f in findings:
        counts[f["class"]] += 1
        card_counts[f["class"]].update(f["cards"])
    order = {"high": 0, "medium": 1, "low": 2}
    cls_rank = {c: i for i, c in enumerate(CLASSES)}
    findings.sort(key=lambda f: (cls_rank[f["class"]], order[f["confidence"]], -len(f["cards"]), f["subject"]))
    return {"stats": stats, "counts": counts, "cards_by_class": {k: len(v) for k, v in card_counts.items()},
            "findings": findings, "cards": cards, "endpoints": {f"{m} {p}": [u[0] for u in v] for (p, m), v in used_endpoints.items()},
            "_used": used_endpoints, "_backend": backend, "_route_cards": route_cards}


# ───────────────────────────── live mode ─────────────────────────────
def resolve_base_url(repo, override=None):
    if override:
        return override.rstrip("/"), "--base-url"
    env = os.environ.get("DASHBOARD_API_URL")
    if env:
        return env.rstrip("/"), "$DASHBOARD_API_URL"
    sh = Path(repo) / "config/service-endpoints.sh"
    if sh.is_file():
        try:
            r = subprocess.run(["bash", "-c", '. "$1" >/dev/null 2>&1; printf %s "${DASHBOARD_API_URL:-}"', "x", str(sh)],
                               capture_output=True, text=True, timeout=10)
            if r.stdout.strip():
                return r.stdout.strip().rstrip("/"), "config/service-endpoints.sh"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None, "unresolved"


def walk_blank(v, path="", out=None, keys=None):
    out = [] if out is None else out
    keys = set() if keys is None else keys
    if isinstance(v, dict):
        for k, x in v.items():
            keys.add(k)
            walk_blank(x, f"{path}.{k}" if path else k, out, keys)
    elif isinstance(v, list):
        if not v and path:
            out.append(path)
        for x in v[:3]:
            walk_blank(x, path + "[]", out, keys)
    elif v is None or (isinstance(v, str) and v.strip().lower() in ("", "--", "unknown", "n/a", "null", "none")):
        out.append(path or "<root>")
    return out, keys


def find_ts(v, depth=0):
    """Newest timestamp-looking value (epoch seconds) in a JSON document, or None."""
    best = None
    if isinstance(v, dict):
        for k, x in v.items():
            if TS_KEYS.search(str(k)) and isinstance(x, (str, int, float)) and not isinstance(x, bool):
                t = to_epoch(x)
                if t and (best is None or t > best):
                    best = t
            elif depth < 3 and isinstance(x, (dict, list)):
                t = find_ts(x, depth + 1)
                if t and (best is None or t > best):
                    best = t
    elif isinstance(v, list) and depth < 3:
        for x in v[:5]:
            t = find_ts(x, depth + 1)
            if t and (best is None or t > best):
                best = t
    return best


def to_epoch(x):
    try:
        if isinstance(x, (int, float)):
            n = float(x)
            if n > 1e12:
                n /= 1000
            return n if 1e9 < n < 4e9 else None
        s = str(x).strip()
        if re.fullmatch(r"\d{9,13}(\.\d+)?", s):
            return to_epoch(float(s))
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if re.match(r"\d{4}-\d\d-\d\d", s) else None
    except (ValueError, OverflowError):
        return None


def live_probe(res, repo, base, fresh_s, timeout=8.0, delay=0.15):
    backend = res["_backend"]
    out = {"base_url": base, "method": "GET only", "probes": [], "skipped": []}
    for (path, method), uses in sorted(res["_used"].items()):
        why = None
        if method not in ("GET", "GET?"):
            why = f"call site method is {method}"
        elif "{}" in path or "{" in path:
            why = "path has a parameter; no safe value to substitute"
        elif VERB_SEG.search(path):
            why = "verb-like path segment"
        r, st = backend.match(path, "GET")
        if not why and st != "ok":
            why = "no GET route (NO_ROUTE); not requested"
        if not why:
            reach = walk_reach(r["fn"], r["module"], backend)
            se = has_side_effect(reach)
            if se:
                why = f"side-effect marker in handler chain: {se}"
        if why:
            out["skipped"].append({"endpoint": path, "reason": why})
            continue
        url = base + path
        t0 = time.time()
        rec = {"endpoint": path, "cards": sorted({u[0] for u in uses})[:8], "n_cards": len({u[0] for u in uses}), "http": None,
               "ms": None, "ctype": None, "bytes": None, "blank": [], "keys": 0, "fresh": "unknown", "age_s": None, "error": None}
        try:
            req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json", "User-Agent": "sweep-dashboard/1 (read-only)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(2_000_000)
                rec.update(http=resp.status, ctype=resp.headers.get("content-type", ""), bytes=len(body))
        except urllib.error.HTTPError as e:
            rec.update(http=e.code, error=f"HTTP {e.code}")
            body = b""
        except Exception as e:  # noqa: BLE001 - any transport failure is "unknown", recorded verbatim
            rec["error"] = f"{type(e).__name__}: {e}"[:120]
            body = b""
        rec["ms"] = int((time.time() - t0) * 1000)
        if body and "json" in (rec["ctype"] or ""):
            try:
                doc = json.loads(body)
                blank, keys = walk_blank(doc)
                rec["blank"], rec["keys"] = blank[:12], len(keys)
                rec["_keys"] = keys
                ts = find_ts(doc)
                if ts:
                    rec["age_s"] = int(time.time() - ts)
                    rec["fresh"] = "fresh" if rec["age_s"] <= fresh_s else "stale"
                if isinstance(doc, (dict, list)) and not doc:
                    rec["blank"] = ["<root empty>"]
            except ValueError:
                rec["error"] = "body is not valid JSON"
        elif body:
            rec["error"] = f"non-JSON content-type {rec['ctype']!r} (dashboard JS ignores it)"
        out["probes"].append(rec)
        time.sleep(delay)
    # confirm JS literal defaults against the live responses of the endpoints fetched in the same span
    for f in res["findings"]:
        if f["class"] == "HARDCODED" and f.get("js_key") and f.get("eps"):
            got = [p for p in out["probes"] if p["endpoint"] in f["eps"] and "_keys" in p]
            if not got:
                continue
            where = ", ".join(p["endpoint"] for p in got)
            if any(f["js_key"] in p["_keys"] for p in got):
                f["live"] = f"key `{f['js_key']}` present in live response of {where}; the literal is a fallback only"
            else:
                f["live"] = f"key `{f['js_key']}` absent from live response of {where}: the page shows the literal {f['js_default']}"
                f["confidence"] = "high"
    for p in out["probes"]:
        p.pop("_keys", None)
    out["producer_files"] = []
    for f in res["findings"]:
        if f["class"] == "NO_PRODUCER":
            fp = f["subject"].split(" <- ")[-1]
            try:
                st = os.stat(fp)
                out["producer_files"].append({"path": fp, "exists": True, "age_s": int(time.time() - st.st_mtime)})
            except OSError as e:
                out["producer_files"].append({"path": fp, "exists": False, "error": type(e).__name__})
    return out


# ───────────────────────────── report ─────────────────────────────
def render_report(res, live, day, argv):
    s, L = res["stats"], []
    L += [f"# Dashboard provenance sweep, {day}", "",
          "## Objective",
          "Recovery sweep P2.4 (`.agents/plans/system-integrity-recovery/tracker.json`): trace every dashboard card to its fetch, backend route and producer, and flag cards that show literals, defaults or retired lanes as if measured. Report only: no finding is fixed here.", "",
          "## Workflow/Session IDs",
          f"Branch feat/sweep-dashboard, worktree `.agents/delegation/worktrees/p24-dashboard-sweep`. Date {day}. Command: `scripts/governance/sweep-dashboard.py {' '.join(argv)}`.", "",
          "## Delegation Decision",
          "Orchestrator: caller session. Implementer: Claude Sonnet 5.5 (Rule 17, balanced tier). One new script, one test, a CI manifest entry and this report; no dashboard code changed.", "",
          "## Validation Evidence", "",
          f"Scope: {s['pages']} HTML pages, {s['js_sources']} JS sources ({s['js_spans']} function spans), {s['html_ids']} HTML ids, {s['routes']} mounted backend routes.",
          f"Cards traced: {s['cards']} (an id with a placeholder/literal, or one a script writes). Distinct endpoints the cards use: {s['endpoints_used']}. Fetch calls whose URL could not be resolved statically: {s['unresolved_fetches']}.", "",
          "Card status: " + ", ".join(f"{k} {v}" for k, v in sorted(s["status"].items())) +
          ". TRACED = fetch and route both found. UNTRACED = no fetch found for a JS-written card (unknown, not a pass).", ""]
    L += ["### Counts per class", "", "| Class | Findings | Cards affected |", "|---|---:|---:|"]
    for c in CLASSES:
        L.append(f"| {c} | {res['counts'][c]} | {res['cards_by_class'][c]} |")
    L += [f"| **Total** | **{sum(res['counts'].values())}** | |", ""]
    if s["unmounted_route_modules"]:
        L += ["Route modules defining routes but never included in `main.py` (their routes are not served): " +
              ", ".join(f"`{m}`" for m in s["unmounted_route_modules"]) + ".", ""]
    L += ["### Findings", "", "| # | Class | Conf | Subject | Evidence | Where | Cards |", "|---:|---|---|---|---|---|---|"]
    for i, f in enumerate(res["findings"], 1):
        cards_ = ", ".join(f"`{c}`" for c in f["cards"][:4]) + (f" +{len(f['cards']) - 4}" if len(f["cards"]) > 4 else "")
        ev = f["evidence"].replace("|", "\\|")
        if f.get("live"):
            ev += " LIVE: " + f["live"].replace("|", "\\|")
        L.append(f"| {i} | {f['class']} | {f['confidence']} | `{f['subject'][:70].replace('|', '/')}` | {ev[:260]} | `{f['where']}` | {cards_} |")
    L.append("")
    if live is not None:
        L += ["### Live probe", ""]
        if live.get("skipped_all"):
            L += [live["skipped_all"], ""]
        else:
            L += [f"Base URL: `{live['base_url']}` ({live['source']}). Method: GET only. Probed {len(live['probes'])}; skipped {len(live['skipped'])} (unknown, not counted as pass).",
                  "Safe-GET determination: route declared GET in the AST, call site has no non-GET method, no path parameter, no verb-like segment, and no side-effect marker (subprocess, file write, outbound POST/PUT/DELETE, remove/rename) in the handler or helpers within 2 hops. The only server-side effect of a request is the operator-audit line and one rate-limit token counted by the middleware.", "",
                  "| Endpoint | HTTP | ms | Bytes | Blank fields | Freshness | Cards |", "|---|---:|---:|---:|---|---|---:|"]
            for p in live["probes"]:
                bl = ", ".join(p["blank"][:5]) + (f" +{len(p['blank']) - 5}" if len(p["blank"]) > 5 else "") if p["blank"] else ("none" if p["http"] == 200 and not p["error"] else (p["error"] or "unknown"))
                fr = p["fresh"] if p["age_s"] is None else f"{p['fresh']} (age {p['age_s']}s)"
                L.append(f"| `{p['endpoint']}` | {p['http'] or '-'} | {p['ms']} | {p['bytes'] or '-'} | {bl.replace('|', '/')[:120]} | {fr} | {p['n_cards']} |")
            if live.get("producer_files"):
                L += ["", "Files read by NO_PRODUCER routes (os.stat on this host, read-only):", ""]
                for pf in live["producer_files"]:
                    L.append(f"- `{pf['path']}`: " + (f"exists, modified {pf['age_s']}s ago" if pf["exists"] else f"missing ({pf['error']})"))
            L += ["", "Skipped:", ""]
            for k in live["skipped"]:
                L.append(f"- `{k['endpoint']}`: {k['reason']}")
            L.append("")
    L += ["## Residual Risk", "", "What this heuristic cannot see (each finding row also carries its own limit in the JSON output):", ""]
    for k, v in LIMITS.items():
        L.append(f"- {k}: {v}.")
    L += ["", "## Rollback Plan", "", "Delete the script, test, CI manifest entry and this report. Nothing else is touched.", "",
          "## Hint Feedback", "", "No hints were consulted; the P2.3 sweep script supplied the layout and flag conventions."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--report", help="write the dated markdown report to this path")
    ap.add_argument("--trace", help="write the full card trace (every card, fetch, route, producer) as JSON")
    ap.add_argument("--fail-on", default="", help="comma list of classes that make the exit status non-zero (default: report only)")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--live", action="store_true", help="read-only GET probe of the running dashboard (never in CI)")
    ap.add_argument("--base-url", help="dashboard base URL for --live (default: $DASHBOARD_API_URL or config/service-endpoints.sh)")
    ap.add_argument("--fresh-s", type=int, default=900, help="age in seconds under which a response timestamp counts as fresh")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args(argv)
    fail = [c for c in a.fail_on.split(",") if c]
    bad = [c for c in fail if c not in CLASSES]
    if bad:
        ap.error(f"unknown class {bad}; choose from {CLASSES}")
    res = analyse(a.repo)
    live = None
    if a.live:
        base, src = resolve_base_url(a.repo, a.base_url)
        if not base:
            live = {"skipped_all": "Live probe skipped: no dashboard URL (set --base-url or DASHBOARD_API_URL). All live facts are unknown."}
        else:
            live = live_probe(res, a.repo, base, a.fresh_s)
            live["source"] = src
    argv_s = sys.argv[1:] if argv is None else argv
    if a.report:
        Path(a.report).write_text(render_report(res, live, a.date, argv_s))
    if a.trace:
        Path(a.trace).write_text(json.dumps({"date": a.date, "stats": res["stats"], "cards": res["cards"],
                                             "endpoints": res["endpoints"]}, indent=1, default=str) + "\n")
    public = {k: v for k, v in res.items() if not k.startswith("_")}
    if a.json:
        print(json.dumps({**public, "live": live}, indent=1, default=str))
    else:
        s = res["stats"]
        print(f"sweep-dashboard: {s['cards']} cards, {s['endpoints_used']} endpoints, {s['routes']} routes; "
              f"status {dict(sorted(s['status'].items()))}")
        for k, v in res["counts"].items():
            print(f"  {k:15} {v:4}  ({res['cards_by_class'][k]} cards)")
        if live and live.get("probes") is not None:
            print(f"  live: probed {len(live['probes'])}, skipped {len(live['skipped'])}")
    return 1 if any(res["counts"][c] for c in fail) else 0


if __name__ == "__main__":
    sys.exit(main())
