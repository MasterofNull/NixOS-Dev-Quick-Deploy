#!/usr/bin/env python3
"""Resolve a mid-merge whose only conflicts are additive manifest files, from the git index stages.

JSON manifests: three-way merge by structure. Lists of identified objects (feature/id/name/script/path) merge by
identity; other lists take theirs' order then ours' new items, minus anything either side removed from base. Scalars
take whichever side changed; both changed differently is a true conflict. Workflow file: `git merge-file --union`
(both sides' added lines). Any other conflicted path, a modify/delete conflict, or a result that does not validate
raises ManifestConflict; nothing is written or staged in that case.

  merge_manifests.py <worktree>      exit 0 resolved+staged, exit 1 stop (reason on stderr)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

JSON_MANIFESTS = ("config/ci-checks.json", "config/activation-manifest.json")
WORKFLOW = ".github/workflows/test.yml"
RESOLVABLE = frozenset(JSON_MANIFESTS) | {WORKFLOW}
ID_KEYS = ("feature", "id", "name", "script", "path")


class ManifestConflict(Exception):
    pass


def _git(w, *a):
    return subprocess.run(["git", "-C", w, *a], capture_output=True, text=True)


def _stage(w, n, p):
    r = _git(w, "show", f":{n}:{p}")
    return r.stdout if r.returncode == 0 else None


def _key(x):
    return json.dumps(x, sort_keys=True)


def _ident(x):
    if isinstance(x, dict):
        for k in ID_KEYS:
            if isinstance(x.get(k), str):
                return f"{k}={x[k]}"
    return None


def merge(b, o, t, path="$"):
    """Three-way merge of base b, ours o, theirs t."""
    if o == t:
        return o
    if b == o:
        return t
    if b == t:
        return o
    if isinstance(o, dict) and isinstance(t, dict):
        b = b if isinstance(b, dict) else {}
        res = {}
        for k in list(t) + [k for k in o if k not in t]:
            if k in o and k in t:
                res[k] = merge(b.get(k), o[k], t[k], f"{path}.{k}")
            elif k in t:
                if k in b and b[k] != t[k]:
                    raise ManifestConflict(f"{path}.{k}: deleted here, changed there")
                if k not in b:
                    res[k] = t[k]
            else:
                if k in b and b[k] != o[k]:
                    raise ManifestConflict(f"{path}.{k}: deleted there, changed here")
                if k not in b:
                    res[k] = o[k]
        return res
    if isinstance(o, list) and isinstance(t, list):
        b = b if isinstance(b, list) else []
        ids = lambda L: {_ident(x): x for x in L if _ident(x)}
        if ids(o) or ids(t):
            bi, oi, ti = ids(b), ids(o), ids(t)
            res = []
            for x in t:
                i = _ident(x)
                if i and i in oi and i in bi:
                    res.append(merge(bi[i], oi[i], x, f"{path}[{i}]"))
                elif i and i in oi:
                    res.append(merge(None, oi[i], x, f"{path}[{i}]"))
                elif i and i in bi and bi[i] != x:
                    raise ManifestConflict(f"{path}[{i}]: deleted here, changed there")
                elif i and i in bi:
                    pass
                else:
                    res.append(x)
            have = {_ident(x) for x in res}
            bk = {_key(x) for x in b}
            for x in o:
                i = _ident(x)
                if i:
                    if i not in have and i not in bi:
                        res.append(x)
                    elif i in bi and i not in ti and bi[i] != x:
                        raise ManifestConflict(f"{path}[{i}]: deleted there, changed here")
                elif _key(x) not in bk and _key(x) not in {_key(y) for y in res}:
                    res.append(x)
            return res
        bk = {_key(x) for x in b}
        res = [x for x in t if not (_key(x) in bk and _key(x) not in {_key(y) for y in o})]
        seen = {_key(x) for x in res}
        res += [x for x in o if _key(x) not in seen and _key(x) not in bk]
        return res
    raise ManifestConflict(f"{path}: both sides changed: {o!r:.60} vs {t!r:.60}")


def _dupes(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            _dupes(v, f"{path}.{k}")
    elif isinstance(node, list):
        seen = set()
        for x in node:
            i = _ident(x)
            if i:
                if i in seen:
                    raise ManifestConflict(f"merged result invalid: duplicate {i} in {path}")
                seen.add(i)
            _dupes(x, path)


def _render_json(b, o, t):
    merged = merge(json.loads(b) if b else None, json.loads(o), json.loads(t))
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    _dupes(json.loads(text))
    return text


def _render_workflow(b, o, t):
    with tempfile.TemporaryDirectory() as d:
        for n, s in (("o", o), ("b", b or ""), ("t", t)):
            with open(os.path.join(d, n), "w") as fh:
                fh.write(s)
        subprocess.run(["git", "merge-file", "--union", "o", "b", "t"], cwd=d, capture_output=True)
        text = open(os.path.join(d, "o")).read()
    if any(line.startswith(("<<<<<<<", ">>>>>>>")) for line in text.splitlines()):
        raise ManifestConflict("merged workflow still has conflict markers")
    try:
        import yaml
    except ImportError:
        return text
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestConflict(f"merged workflow is not valid YAML: {str(e).splitlines()[0][:100]}")
    return text


def resolve(w):
    """Resolve and stage every conflicted path in worktree w, or raise ManifestConflict with nothing changed."""
    paths = [p for p in _git(w, "diff", "--name-only", "--diff-filter=U").stdout.split("\n") if p]
    if not paths:
        raise ManifestConflict("no conflicted paths")
    bad = [p for p in paths if p not in RESOLVABLE]
    if bad:
        raise ManifestConflict("conflict outside the additive manifests: " + " ".join(bad))
    out = {}
    for p in paths:
        b, o, t = _stage(w, 1, p), _stage(w, 2, p), _stage(w, 3, p)
        if o is None or t is None:
            raise ManifestConflict(f"{p}: deleted on one side")
        try:
            out[p] = _render_json(b, o, t) if p.endswith(".json") else _render_workflow(b, o, t)
        except ValueError as e:
            raise ManifestConflict(f"{p}: not valid JSON on a side or in the result: {str(e)[:100]}")
    for p, s in out.items():
        with open(os.path.join(w, p), "w") as fh:
            fh.write(s)
        if _git(w, "add", p).returncode != 0:
            raise ManifestConflict(f"git add {p} failed")
    return paths


if __name__ == "__main__":
    try:
        print("resolved " + " ".join(resolve(sys.argv[1])))
    except ManifestConflict as e:
        print(f"STOP: {e}", file=sys.stderr)
        sys.exit(1)
