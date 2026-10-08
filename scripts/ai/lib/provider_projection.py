#!/usr/bin/env python3
"""Canonical provider projection compiler -- ECC parity P0-B (preview + drift check only).

One typed contract (roles/tools/hooks/capabilities + canon regions) is built from
existing sources and projected per provider (codex, claude, gemini, local). There
is deliberately NO write path: `project`/`check` never modify a provider file.
canon-compile.py stays the only writer of canon regions.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "aqos-provider-projection/v1"
# provider -> instruction files it owns. "shared" is a non-provider group.
PROVIDER_FILES: dict[str, tuple[str, ...]] = {
    "codex": ("AGENTS.md", ".agent/CODEX.md"),
    "claude": ("CLAUDE.md",),
    "gemini": (".agent/GEMINI.md",),
    "local": (".agent/LOCAL-AGENT.md",),
    "shared": (".agent/WORKFLOW-CANON.md",),
}
_MANIFEST_KEYS = {"blocks", "agent_files"}
_BLOCK_KEYS = {"source", "summary", "targets"}
_TARGET_KEYS = {"path", "mode"}
_MODES = {"full", "summary"}

BEGIN = "<!-- canon:begin {name} -->"
END = "<!-- canon:end {name} -->"

# Explicit vendor-shaped patterns only; no generic secret-scan facility is
# source-verified in this repo (P0B-SOURCE-PREFLIGHT.md).
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_=-]{24,}"),
)


class ProjectionError(ValueError):
    """Fail-closed error with a stable reason code."""

    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason


def _resolver():
    path = Path(__file__).with_name("aqos_install_resolver.py")
    spec = importlib.util.spec_from_file_location("aqos_install_resolver", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def output_hash(value: Any) -> str:
    """sha256 over RFC 8785 canonical JSON (reuses the install resolver helpers)."""
    r = _resolver()
    return r.sha256_bytes(r.jcs_bytes(value))


def _sha(text: str) -> str:
    return _resolver().sha256_bytes(text.encode("utf-8"))


def find_secret(text: str) -> str | None:
    """Pattern id of the first secret-shaped match; never returns the value."""
    for i, pat in enumerate(_SECRET_PATTERNS):
        if pat.search(text):
            return f"pattern-{i}"
    return None


def _scan(label: str, text: str) -> None:
    hit = find_secret(text)
    if hit:
        raise ProjectionError("secret_shaped_value", f"{label} contains a secret-shaped value ({hit})")


def _load_manifest(repo: Path) -> dict:
    path = repo / "canon" / "canon.yaml"
    if not path.is_file():
        raise ProjectionError("manifest_missing", "canon/canon.yaml not found")
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ProjectionError("manifest_invalid", "canon.yaml is not a mapping")
    unknown = set(manifest) - _MANIFEST_KEYS
    if unknown:
        raise ProjectionError("unknown_field", f"manifest keys: {sorted(unknown)}")
    return manifest


def _provider_of(path: str) -> str:
    owners = [p for p, files in PROVIDER_FILES.items() if path in files]
    if len(owners) != 1:
        raise ProjectionError("unknown_target" if not owners else "colliding_field",
                              f"target {path} maps to providers {owners}")
    return owners[0]


def _roles(repo: Path) -> list[str]:
    path = repo / "docs" / "architecture" / "role-matrix.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## Role Definitions\n(.*?)^## ", text, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    return sorted(set(re.findall(r"^### ([a-z][a-z0-9_-]*)\s*$", m.group(1), re.MULTILINE)))


def _capabilities(repo: Path) -> tuple[list[str], list[str]]:
    path = repo / "config" / "agent-capability-contract.json"
    if not path.is_file():
        return [], []
    data = json.loads(path.read_text(encoding="utf-8"))
    caps = sorted(k for k, v in (data.get("required_behaviors") or {}).items() if v is True)
    tools = sorted((data.get("required_services") or {}).keys())
    return caps, tools


def _hooks(repo: Path) -> list[str]:
    path = repo / ".claude" / "settings.json"
    if not path.is_file():
        return []
    return sorted((json.loads(path.read_text(encoding="utf-8")).get("hooks") or {}).keys())


def build_contract(repo: Path) -> dict:
    """Typed contract from canon.yaml + role-matrix + capability contract + claude hooks."""
    repo = Path(repo)
    manifest = _load_manifest(repo)
    blocks: dict[str, dict] = {}
    seen: set[tuple[str, str]] = set()
    for name, spec in (manifest.get("blocks") or {}).items():
        if not isinstance(spec, dict):
            raise ProjectionError("manifest_invalid", f"block {name} is not a mapping")
        if set(spec) - _BLOCK_KEYS:
            raise ProjectionError("unknown_field", f"block {name} keys: {sorted(set(spec) - _BLOCK_KEYS)}")
        targets = []
        for t in spec.get("targets") or []:
            if isinstance(t, dict) and set(t) - _TARGET_KEYS:
                raise ProjectionError("unknown_field", f"block {name} target keys: {sorted(set(t) - _TARGET_KEYS)}")
            path, mode = (t, "full") if isinstance(t, str) else (t.get("path"), t.get("mode", "full"))
            if mode not in _MODES:
                raise ProjectionError("unknown_field", f"block {name} mode {mode!r}")
            if (name, path) in seen:
                raise ProjectionError("colliding_field", f"block {name} targets {path} twice")
            seen.add((name, path))
            if mode == "summary" and "summary" not in spec:
                raise ProjectionError("manifest_invalid", f"block {name} summary mode without summary source")
            targets.append({"path": path, "mode": mode, "provider": _provider_of(path)})
        full = (repo / "canon" / spec["source"]).read_text(encoding="utf-8")
        summary = (repo / "canon" / spec["summary"]).read_text(encoding="utf-8") if "summary" in spec else None
        blocks[name] = {"targets": targets, "full": full, "summary": summary}
    caps, tools = _capabilities(repo)
    return {"blocks": blocks, "roles": _roles(repo), "tools": tools,
            "hooks": {"claude": _hooks(repo)}, "capabilities": caps}


def _rendered(name: str, body: str) -> str:
    return f"{BEGIN.format(name=name)}\n{body.rstrip()}\n{END.format(name=name)}"


def project(repo: Path) -> dict:
    """Deterministic projection (hashes and sizes only, no content) plus its output hash."""
    contract = build_contract(repo)
    for name, blk in contract["blocks"].items():
        _scan(f"canon block {name}", blk["full"] + (blk["summary"] or ""))
    _scan("contract metadata", json.dumps({k: contract[k] for k in ("roles", "tools", "hooks", "capabilities")}))
    providers: dict[str, dict] = {
        p: {"files": {f: {"regions": {}} for f in files}} for p, files in PROVIDER_FILES.items()}
    for name, blk in contract["blocks"].items():
        for t in blk["targets"]:
            body = blk["summary"] if t["mode"] == "summary" else blk["full"]
            text = _rendered(name, body)
            providers[t["provider"]]["files"][t["path"]]["regions"][name] = {
                "mode": t["mode"], "sha256": _sha(text), "bytes": len(text.encode("utf-8"))}
    for p, pdata in providers.items():
        pdata["roles"] = contract["roles"]
        pdata["tools"] = contract["tools"]
        pdata["capabilities"] = contract["capabilities"]
        pdata["hooks"] = contract["hooks"].get(p, [])
    return {"schema": SCHEMA_VERSION, "providers": providers,
            "output_sha256": output_hash({"schema": SCHEMA_VERSION, "providers": providers})}


def _region_re(name: str) -> re.Pattern:
    return re.compile(re.escape(BEGIN.format(name=name)) + r"\n.*?" + re.escape(END.format(name=name)), re.DOTALL)


def check(repo: Path) -> dict:
    """Read-only comparison of projection vs current files. Content outside owned
    canon regions is reported as preserved (not owned), never as drift."""
    repo = Path(repo)
    proj = project(repo)
    findings: list[dict] = []
    preserved: dict[str, dict] = {}
    for p, pdata in proj["providers"].items():
        for f, fdata in pdata["files"].items():
            if not fdata["regions"]:
                continue
            path = repo / f
            if not path.is_file():
                findings.append({"provider": p, "file": f, "status": "file_missing"})
                continue
            text = path.read_text(encoding="utf-8")
            owned = 0
            for name, region in fdata["regions"].items():
                m = _region_re(name).search(text)
                if m is None:
                    findings.append({"provider": p, "file": f, "block": name, "status": "region_missing"})
                    continue
                owned += len(m.group(0).encode("utf-8"))
                if _sha(m.group(0)) != region["sha256"]:
                    findings.append({"provider": p, "file": f, "block": name, "status": "drift"})
            preserved[f"{p}:{f}"] = {"not_owned_bytes": max(len(text.encode("utf-8")) - owned, 0),
                                     "status": "preserved"}
    findings.sort(key=lambda d: (d["provider"], d["file"], d.get("block", ""), d["status"]))
    return {"schema": SCHEMA_VERSION, "output_sha256": proj["output_sha256"],
            "drift": findings, "preserved": dict(sorted(preserved.items())),
            "status": "drift" if findings else "clean"}
