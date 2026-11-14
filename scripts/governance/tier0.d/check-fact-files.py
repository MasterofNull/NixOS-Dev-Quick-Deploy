#!/usr/bin/env python3
"""Tier0 extension: Persona P3 fact files (.agent/memory/facts/<subject>.md).

Validates format and privacy, caps facts per commit, and enforces that another lane's claim is
never changed, deleted, renamed or split without an `owner_reply:` (git cannot see a clean
overwrite). Also prints the conflict-rate report: `check-fact-files.py --report`.

Checked set: staged changes (pre-commit) plus commits between merge-base(origin/main, HEAD) and HEAD
(branch diff). Baseline for the lane comparison is origin/main, fetched best-effort first so a stale
ref cannot mask a newly landed claim (FACT_CHECK_NO_FETCH=1 skips the fetch).
Design: .agents/plans/persona-p3-collapse-20261113/DESIGN.md
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

TAG = "[tier0.d/check-fact-files]"
FACTS_DIR = ".agent/memory/facts/"
SUBJECT_RE = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
MAX_PER_COMMIT = 10
PRIVATE_RE = re.compile(
    r"(/home/[A-Za-z0-9_.-]+|/run/secrets|deploy-options\.local\.nix"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY)"
)
LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9+_=-]{32,}")
HEX_RE = re.compile(r"^[0-9a-f]{7,64}$")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    out: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        out[k.strip()] = v.split(" #", 1)[0].strip().strip("'\"")
    return out


def lane_of(instance: str) -> str:
    """`Simurg@codex/gpt-6.1#ab12` and PERSONA=0 `codex/gpt-6.1` both give `codex`."""
    s = instance.strip()
    if s.startswith("Simurg@"):
        s = s[len("Simurg@"):]
    s = s.split("#", 1)[0]
    return s.split("/", 1)[0].strip().lower() if "/" in s else ""


def _git(repo: Path, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False, timeout=timeout)


def _show(repo: Path, spec: str) -> str | None:
    r = _git(repo, "show", spec)
    return r.stdout if r.returncode == 0 else None


def content_errors(rel: str, text: str) -> tuple[list[str], dict[str, str]]:
    fm = parse_frontmatter(text)
    if fm is None:
        return [f"{rel}: missing or malformed front-matter"], {}
    errs: list[str] = []
    stem = Path(rel).stem
    subject = fm.get("subject", "")
    if not SUBJECT_RE.match(subject):
        errs.append(f"{rel}: subject {subject!r} must match {SUBJECT_RE.pattern}")
    if subject != stem:
        errs.append(f"{rel}: subject {subject!r} must equal the filename stem {stem!r}")
    if not fm.get("claim"):
        errs.append(f"{rel}: missing 'claim'")
    ev = fm.get("evidence", "")
    if not 8 <= len(ev) <= 300:
        errs.append(f"{rel}: 'evidence' must be 8-300 chars (got {len(ev)})")
    if not lane_of(fm.get("instance", "")):
        errs.append(f"{rel}: 'instance' must be Simurg@<lane>/<model>#<session> or <lane>/<model>")
    if PRIVATE_RE.search(text):
        errs.append(f"{rel}: contains a private path, email, host-config reference or token pattern")
    for tok in LONG_TOKEN_RE.findall(text):
        if not HEX_RE.match(tok) and re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok):
            errs.append(f"{rel}: contains a high-entropy string ({tok[:8]}...)")
            break
    return errs, fm


def _facts(names: str) -> list[tuple[str, str]]:
    out = []
    for ln in names.splitlines():
        if "\t" in ln:
            st, p = ln.split("\t", 1)
            if p.startswith(FACTS_DIR) and p.endswith(".md"):
                out.append((st[0], p))
    return out


def _gitleaks(repo: Path, rel: str, text: str) -> list[str]:
    cfg = repo / ".gitleaks.toml"
    if not cfg.is_file() or subprocess.run(["sh", "-c", "command -v gitleaks"], capture_output=True).returncode:
        return []
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "f.md").write_text(text, encoding="utf-8")
        r = subprocess.run(["gitleaks", "dir", td, "--no-banner", "--config", str(cfg), "--exit-code", "1"],
                           capture_output=True, text=True, check=False)
    return [f"{rel}: gitleaks flagged a secret"] if r.returncode == 1 else []


# Co-Authored-By trailer substring -> lane; an unrecognized trailer falls through to unknown (fail closed).
TRAILER_LANES = (("claude", "claude"), ("codex", "codex"), ("openai", "codex"), ("gemini", "gemini"),
                 ("google", "gemini"), ("qwen", "local"), ("local", "local"))


def _actor_lane(msg: str, new_fms: dict[str, dict[str, str]]) -> str:
    """Lane doing a delete: new facts in the unit, `instance:` message line, Co-Authored-By trailer, then AQ_INSTANCE_LANE."""
    for fm in new_fms.values():
        if lane_of(fm.get("instance", "")):
            return lane_of(fm["instance"])
    m = re.search(r"^instance:\s*(\S+)", msg, re.M)
    if m:
        return lane_of(m.group(1))
    for t in re.findall(r"^Co-Authored-By:\s*(.+)$", msg, re.M | re.I):
        for key, lane in TRAILER_LANES:
            if key in t.lower():
                return lane
    return os.environ.get("AQ_INSTANCE_LANE", "").strip().lower()


def check_repo(repo: Path, base: str = "origin/main") -> list[str]:
    errs: list[str] = []
    have_base = _git(repo, "rev-parse", "--verify", "-q", base).returncode == 0
    base_ref = base if have_base else "HEAD"
    mb = _git(repo, "merge-base", base_ref, "HEAD").stdout.strip() if _git(repo, "rev-parse", "-q", "--verify", "HEAD").returncode == 0 else ""

    # (label, status+path list, reader of the NEW content, commit message text, predecessor ref prefix)
    units: list[tuple[str, list[tuple[str, str]], object, str, str]] = []
    staged = _facts(_git(repo, "diff", "--cached", "--name-status", "--no-renames", "--", FACTS_DIR).stdout)
    if staged:
        units.append(("staged", staged, lambda p: _show(repo, f":{p}"), "", "HEAD"))
    if mb:
        revs = _git(repo, "rev-list", "--reverse", f"{mb}..HEAD").stdout.split()
        for sha in revs:
            fl = _facts(_git(repo, "diff-tree", "-r", "--no-commit-id", "--name-status", "--no-renames", "-m", "--first-parent", sha).stdout)
            if fl:
                msg = _git(repo, "log", "-1", "--format=%B", sha).stdout
                units.append((sha[:9], fl, (lambda s: (lambda p: _show(repo, f"{s}:{p}")))(sha), msg, f"{sha}^"))

    for label, files, reader, msg, prev in units:
        if len(files) > MAX_PER_COMMIT:
            errs.append(f"{label}: {len(files)} fact files touched, cap is {MAX_PER_COMMIT} per commit")
        new_fms: dict[str, dict[str, str]] = {}
        deleted: list[str] = []
        for status, rel in files:
            if status == "D":
                deleted.append(rel)
                continue
            text = reader(rel)  # type: ignore[operator]
            if text is None:
                errs.append(f"{rel}: cannot read new content")
                continue
            e, fm = content_errors(rel, text)
            errs.extend(e)
            errs.extend(_gitleaks(repo, rel, text))
            if not fm:
                continue
            new_fms[rel] = fm
            # Baselines: the predecessor revision (per-commit transition) and current main.
            for ref in dict.fromkeys((prev, base_ref)):
                old = _show(repo, f"{ref}:{rel}")
                old_fm = parse_frontmatter(old) if old else None
                if not old_fm:
                    continue
                ol, nl = lane_of(old_fm.get("instance", "")), lane_of(fm.get("instance", ""))
                if old_fm.get("claim") != fm.get("claim") and ol != nl:
                    reply = fm.get("owner_reply", "").strip()
                    if not reply or reply == old_fm.get("owner_reply", "").strip():
                        msg_e = (
                            f"{rel}: claim changed across lanes ({ol} -> {nl}) without a fresh 'owner_reply'. "
                            f"Ask the owner (1 keep mine, 2 keep theirs, 3 keep both) and record the answer. "
                            f"theirs ({ol}): {old_fm.get('claim')!r} | mine ({nl}): {fm.get('claim')!r}"
                        )
                        if msg_e not in errs:
                            errs.append(msg_e)
        actor = _actor_lane(msg, new_fms)
        for rel in deleted:
            subj = Path(rel).stem
            splits = [f for p, f in new_fms.items()
                      if Path(p).stem.startswith(subj + ".") and f.get("owner_reply", "").strip()]
            has_reply = len(splits) >= 2 or "owner_reply:" in msg
            for ref in dict.fromkeys((prev, base_ref)):
                old = _show(repo, f"{ref}:{rel}")
                old_fm = parse_frontmatter(old) if old else None
                if not old_fm:
                    continue  # fact not on this baseline: nothing of another lane is lost there
                ol = lane_of(old_fm.get("instance", ""))
                # main baseline: any delete needs the reply; predecessor (branch-only): only a lane change does
                if has_reply or (ref != base_ref and ol == actor):
                    continue
                msg_e = (
                    f"{rel}: deletes or renames a fact on {ref} (lane {ol}, claim {old_fm.get('claim')!r}); "
                    f"needs 2 scoped split facts '{subj}.<scope>' carrying 'owner_reply'"
                    f"{'' if actor else ' (acting lane unknown: set AQ_INSTANCE_LANE or add an instance: line to the message)'}"
                )
                if msg_e not in errs:
                    errs.append(msg_e)
    return errs


def report(repo: Path) -> str:
    """Conflict-rate counters from git history of the facts dir (design section 4)."""
    log = _git(repo, "log", "--format=%H", "--", FACTS_DIR, timeout=60).stdout.split()
    subjects: dict[str, dict] = {}
    deletes = 0
    for sha in reversed(log):
        for st, p in _facts(_git(repo, "diff-tree", "-r", "--no-commit-id", "--name-status", "--no-renames", "-m", "--first-parent", "--root", sha).stdout):
            s = subjects.setdefault(Path(p).stem, {"lanes": set(), "claim": None, "reply": "", "changes": 0, "replies": 0})
            if st == "D":
                deletes += 1
                continue
            fm = parse_frontmatter(_show(repo, f"{sha}:{p}") or "") or {}
            claim, reply = fm.get("claim"), fm.get("owner_reply", "").strip()
            if claim and s["claim"] is not None and claim != s["claim"]:
                s["changes"] += 1
            if claim:
                s["claim"] = claim
            s["lanes"].add(lane_of(fm.get("instance", "")))
            if reply and reply != s["reply"]:
                s["replies"] += 1
            if reply:
                s["reply"] = reply
    live = sorted(p.stem for p in (repo / FACTS_DIR).glob("*.md")) if (repo / FACTS_DIR).is_dir() else []
    multi = sum(1 for s in subjects.values() if len(s["lanes"] - {""}) > 1)
    claim_changes = sum(s["changes"] for s in subjects.values())
    replies = sum(s["replies"] for s in subjects.values())
    return (f"facts_total={len(live)} subjects_seen={len(subjects)} multi_lane_subjects={multi} "
            f"claim_changes={claim_changes} owner_reply_entries={replies} deletes={deletes}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="--pre-commit")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--base", default="origin/main")
    a, _ = ap.parse_known_args(argv)
    top = a.repo or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False).stdout.strip() or "."
    repo = Path(top)
    if a.report:
        print(report(repo))
        return 0
    if os.environ.get("FACT_CHECK_NO_FETCH") != "1":
        try:
            _git(repo, "fetch", "-q", "origin", "main", timeout=8)
        except subprocess.TimeoutExpired:
            pass
    errs = check_repo(repo, a.base)
    for e in errs:
        print(f"{TAG} FAIL: {e}", file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
