"""Append-only per-landing outcome receipts (raw facts, no derived metrics).

One JSON line per landed PR in <delegation dir>/outcome-receipts.jsonl (0600). A line that trips redaction
or the fail-closed scan goes (redacted) to outcome-receipts.quarantine.jsonl and never to the main log.
Token counts come from the delegation registry rows of the review runs; unknown stays null.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOG = "outcome-receipts.jsonl"
QUARANTINE = "outcome-receipts.quarantine.jsonl"
_PRIVACY = Path(__file__).resolve().parents[3] / "ai-stack/mcp-servers/shared"
_HITS = [
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S{4,}"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"/home/[^\s\"']+|/run/secrets[^\s\"']*"),
]
_BLOB = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_HEX = re.compile(r"[0-9a-f]{32,}")
_PURE_HEX = re.compile(r"[0-9a-f]{6,}")
_HEX_DELIM_RUN = re.compile(r"[0-9a-f]+(?:[\-_][0-9a-f]+)*")
_WORD_NUM = re.compile(r"[a-z]{2,}[0-9]{1,8}[a-z]?|[A-Z]{2,}[0-9]{1,8}[A-Z]?")
_B64_SLASH = re.compile(r"[A-Za-z0-9/]{32,}")


def _entropy(s: str) -> float:
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def _counter_entropy(counts: Counter[str], total: int) -> float:
    return -sum(c / total * math.log2(c / total) for c in counts.values() if c)


def _iter_hyphen_hex(s: str) -> list[str]:
    """Linear-time extraction of hyphen/underscore-delimited hex runs (no backtracking on plain hex)."""
    return [tok for m in _HEX_DELIM_RUN.finditer(s) if "-" in (tok := m.group(0)) or "_" in tok]


def _has_high_entropy_window(s: str) -> bool:
    """True iff `s` (>= 32 chars, non-hex) or any 32/36-char non-hex window inside `s` exceeds 4.0 bits."""
    n = len(s)
    if n < 32 or _HEX.fullmatch(s):
        return False
    if _entropy(s) > 4.0:
        return True
    for w in (32, 36):
        if n <= w:
            continue
        counts = Counter(s[:w])
        for i in range(n - w + 1):
            if i > 0:
                old_ch = s[i - 1]
                counts[old_ch] -= 1
                if counts[old_ch] == 0:
                    del counts[old_ch]
                counts[s[i + w - 1]] += 1
            if _counter_entropy(counts, w) > 4.0 and not _HEX.fullmatch(s[i : i + w]):
                return True
    return False


def _has_bad_b64_slash(b: str) -> bool:
    for bm in _B64_SLASH.finditer(b):
        sub = bm.group(0).strip("/")
        if len(sub) >= 32 and not _HEX.fullmatch(sub):
            non_hex = [s for s in sub.split("/") if s and not _HEX.fullmatch(s)]
            joined = "/".join(non_hex)
            if len(joined) >= 32 and _entropy(joined) > 4.35:
                return True
    return False


def _bad_alnum_span(run: list[str], *, require_entropy_gt4: bool = False) -> bool:
    """Linear-time two-pointer scan over minimal >=32-char sub-spans of an alphanumeric slash run."""
    n = len(run)
    if n == 0:
        return False
    full = "/".join(run)
    if len(full) < 32:
        return False
    if not _HEX.fullmatch(full):
        full_ent = _entropy(full)
        if (not require_entropy_gt4 or full_ent > 4.0) and (
            full != full.lower()
            or n < 3
            or full_ent > 4.2
            or sum(any(c.isdigit() for c in s) for s in run) > 1
        ):
            return True
    seg_upper = [s != s.lower() for s in run]
    seg_digit = [any(c.isdigit() for c in s) for s in run]
    counts: Counter[str] = Counter()
    span_len = 0
    upper_n = 0
    digit_n = 0
    j = 0
    for i in range(n):
        while j < n and span_len < 32:
            if j > i:
                counts["/"] += 1
                span_len += 1
            s = run[j]
            counts.update(s)
            span_len += len(s)
            upper_n += int(seg_upper[j])
            digit_n += int(seg_digit[j])
            j += 1
        if span_len < 32:
            break
        nseg = j - i
        is_single_hex = nseg == 1 and bool(_HEX.fullmatch(run[i]))
        if not is_single_hex:
            ent = _counter_entropy(counts, span_len)
            if (not require_entropy_gt4 or ent > 4.0) and (
                upper_n > 0 or nseg < 3 or ent > 4.2 or digit_n > 1
            ):
                return True
        if j < n:
            ext_counts = counts.copy()
            ext_counts["/"] += 1
            ext_counts.update(run[j])
            ext_len = span_len + 1 + len(run[j])
            ext_ent = _counter_entropy(ext_counts, ext_len)
            if (not require_entropy_gt4 or ext_ent > 4.0) and (
                (upper_n + int(seg_upper[j])) > 0
                or (nseg + 1) < 3
                or ext_ent > 4.2
                or (digit_n + int(seg_digit[j])) > 1
            ):
                return True
        s0 = run[i]
        counts.subtract(s0)
        for ch in set(s0):
            if counts[ch] <= 0:
                del counts[ch]
        span_len -= len(s0)
        upper_n -= int(seg_upper[i])
        digit_n -= int(seg_digit[i])
        if j > i + 1:
            counts["/"] -= 1
            if counts["/"] <= 0:
                del counts["/"]
            span_len -= 1
    return False


def _path_like(b: str) -> bool:
    """True iff a single `_BLOB` match `b` is a slash-separated repo path without secret-like runs or parts.

    Guards `_entropy_text` with whole-match and cross-segment checks so slash-less `_BLOB` matches
    (such as hyphenated tokens after `.`) and slash-containing credentials (`+`/`=`, `_B64_SLASH`
    runs of length `>= 32` whose non-`_HEX` segments have entropy `> 4.35`, contiguous alphanumeric
    slash runs of length `>= 32` without `>= 3` all-lowercase segments / `<= 1` digit-bearing
    segment / entropy `<= 4.2`, case changes within a segment or `>= 2` uppercase segments mixed
    with lowercase segments, `>= 32`-char runs from `_iter_hyphen_hex` inside a segment, non-hex/non-word+num
    mixed alphanumeric tokens of length `>= 8` or global `>= 2` chunks of length `>= 4` across
    segments, or `>= 12`-char high-entropy (`> 3.55`) non-hex parts) stay intact and subject to
    `_BLOB` entropy checks even in verified `files[*]` paths.
    """
    if "/" not in b or "+" in b or "=" in b:
        return False
    segs = b.split("/")
    if _has_bad_b64_slash(b):
        return False
    alnum_run: list[str] = []
    for seg in [*segs, ""]:
        if seg and seg.isalnum() and not _HEX.fullmatch(seg):
            alnum_run.append(seg)
        else:
            if alnum_run and _bad_alnum_span(alnum_run):
                return False
            alnum_run = []
    mixed_alnum_4 = 0
    upper_segs = 0
    for seg in segs:
        if not (seg == seg.lower() or seg == seg.upper()):
            return False
        if any(c.isupper() for c in seg):
            upper_segs += 1
        if any(len(tok) >= 32 for tok in _iter_hyphen_hex(seg.lower())):
            return False
        for part in (p for p in re.split(r"[\-_]", seg) if p):
            has_a = any(c.isalpha() for c in part)
            has_d = any(c.isdigit() for c in part)
            if has_a and has_d and not _PURE_HEX.fullmatch(part) and not _WORD_NUM.fullmatch(part):
                if len(part) >= 8:
                    return False
                if len(part) >= 4:
                    mixed_alnum_4 += 1
            if len(part) >= 12 and not _PURE_HEX.fullmatch(part) and _entropy(part) > 3.55:
                return False
    if mixed_alnum_4 >= 2:
        return False
    if upper_segs >= 2 and any(any(c.islower() for c in s) for s in segs):
        return False
    return True


def _no_dup_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate JSON key: {k!r}")
        out[k] = v
    return out


def _entropy_text(text: str, allowed_paths: set[str] | frozenset[str]) -> str:
    """Return `text` with verified `_path_like` `_BLOB` matches in `files[*].path`/`renamed_from` split on `/`, `-`, and `_`.

    Operates per `_BLOB` match on the JSON-escaped representation of verified `files[*].path` and
    `files[*].renamed_from` values (`val in allowed_paths`) so Unicode JSON escapes (e.g.
    `caf\\u00e9/docs/...`) and plain paths are handled uniformly while slash-less `_BLOB` matches
    (such as high-entropy hyphenated tokens after `.`) stay untouched. Replacing `/`, `-`, and `_`
    with spaces only inside `_path_like` `_BLOB` matches prevents benign path delimiters from
    joining normal segments into a 32+ char `_BLOB` match, while leaving `+`/`=`, high-entropy
    `_B64_SLASH` runs (`> 4.35`), opaque contiguous alphanumeric slash runs (requiring `>= 3`
    all-lowercase segments, `<= 1` digit-bearing segment, and entropy `<= 4.2`), case changes or
    multiple uppercase segments mixed with lowercase segments, `>= 32`-char runs from `_iter_hyphen_hex`
    inside a segment, non-hex/non-word+num mixed alphanumeric tokens (`>= 8` or global `>= 2`
    chunks of length `>= 4` across segments), and `>= 12`-char high-entropy (`> 3.55`) non-hex
    parts intact and subject to the entropy check.
    """
    if not allowed_paths:
        return text
    try:
        obj = json.loads(text, object_pairs_hook=_no_dup_pairs)
    except ValueError:
        return text
    if not isinstance(obj, dict) or not isinstance(obj.get("files"), list):
        return text
    masked_files = []
    changed = False
    for entry in obj["files"]:
        if isinstance(entry, dict):
            copy = dict(entry)
            for key in ("path", "renamed_from"):
                val = copy.get(key)
                if isinstance(val, str) and val in allowed_paths:
                    escaped = json.dumps(val, ensure_ascii=True)[1:-1]
                    masked = _BLOB.sub(
                        lambda m: re.sub(r"[/\-_]", " ", m.group(0)) if _path_like(m.group(0)) else m.group(0),
                        escaped,
                    )
                    if masked != escaped:
                        copy[key] = json.loads(f'"{masked}"')
                        changed = True
            masked_files.append(copy)
        else:
            masked_files.append(entry)
    if not changed:
        return text
    return json.dumps(dict(obj, files=masked_files), sort_keys=True)


def _high_entropy_blob(b: str) -> bool:
    """True iff `_BLOB` match `b` or a credential-like component inside `b` exceeds the entropy gate.

    Scores recognized components independently (32/36-char windows, `_iter_hyphen_hex`, `_B64_SLASH`,
    contiguous non-benign or alphanumeric slash sub-spans, and `[-_]` parts) so a long
    low-entropy parent directory or prefix cannot dilute a credential below 4.0 bits.
    """
    if _HEX.fullmatch(b):
        return False
    if _entropy(b) > 4.0:
        return True
    if "/" not in b:
        return any(_has_high_entropy_window(tok) for tok in _iter_hyphen_hex(b.lower()))
    if _has_bad_b64_slash(b):
        return True
    segs = b.split("/")
    nb_run: list[str] = []
    for seg in [*segs, ""]:
        if seg and ("+" in seg or "=" in seg or not (seg == seg.lower() or seg == seg.upper())):
            nb_run.append(seg)
        else:
            if nb_run:
                sub = "/".join(nb_run)
                if len(sub) >= 32 and not _HEX.fullmatch(sub) and _entropy(sub) > 4.0:
                    return True
                nb_run = []
    alnum_run: list[str] = []
    for seg in [*segs, ""]:
        if seg and seg.isalnum() and not _HEX.fullmatch(seg):
            alnum_run.append(seg)
        else:
            if alnum_run and _bad_alnum_span(alnum_run, require_entropy_gt4=True):
                return True
            alnum_run = []
    for seg in segs:
        if _has_high_entropy_window(seg):
            return True
        if any(_has_high_entropy_window(tok) for tok in _iter_hyphen_hex(seg.lower())):
            return True
        for part in (p for p in re.split(r"[\-_]", seg) if p):
            if (len(part) >= 12 and not _PURE_HEX.fullmatch(part) and _entropy(part) > 3.55) or _has_high_entropy_window(part):
                return True
    return False


def scan(text: str, *, allowed_paths: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Names of fail-closed findings in already-redacted text; empty means clean.

    `allowed_paths` splits verified `_path_like` `_BLOB` matches inside `files[*].path` and
    `files[*].renamed_from` on `/`, `-`, and `_` before the generic entropy heuristic so benign
    path delimiters do not join short segments into a 32+ char token. Remaining `_BLOB` matches
    are scored via `_high_entropy_blob` (independent component and 32/36-char window scoring)
    so long low-entropy parent directories or prefixes cannot dilute a credential below 4.0 bits.
    Slash-less `_BLOB` matches, non-path-like or secret-like components, tokens in any other field,
    pattern checks (`_HITS`), and `_redact` remain checked.
    """
    hits = [f"pattern{i}" for i, p in enumerate(_HITS) if p.search(text)]
    target = _entropy_text(text, allowed_paths)
    if any(_high_entropy_blob(b) for b in _BLOB.findall(target)):
        hits.append("entropy")
    return hits


def is_eligible(rec: dict) -> bool:
    """Independently reviewed (PASS, author not a reviewer) and CI-passing: eligible as a verified trajectory."""
    return ("PASS" in (rec.get("review_verdicts") or []) and rec.get("ci") == "pass"
            and rec.get("author_lane") not in (rec.get("reviewer_lanes") or []))


def _redact(text: str) -> tuple[str, list[str]]:
    sys.path.insert(0, str(_PRIVACY))
    try:
        from telemetry_privacy import redact_secrets
    except ImportError:
        return text, ["redactor_unavailable"]
    finally:
        sys.path.remove(str(_PRIVACY))
    return redact_secrets(text)


def _append(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def _registry_row(delegation_dir: Path, run_id: str) -> dict:
    row: dict = {}
    try:
        for ln in (delegation_dir / "registry.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") == run_id:
                row = r  # last row wins
    except OSError:
        pass
    return row


_USED = re.compile(r"^tokens used\s*\n\s*([\d,]+)\s*$", re.M)


def _logged_total(delegation_dir: Path, row: dict) -> int | None:
    """Codex logs end with 'tokens used' and a total (no in/out split); the registry row never carries it."""
    name = Path(str(row.get("output_file") or "")).name
    if not name:
        return None
    try:
        hits = _USED.findall((delegation_dir / "outputs" / name).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return int(hits[-1].replace(",", "")) if hits else None


def record_landing(delegation_dir: Path, *, pr: int, head: str, author_lane: str, reviews: list[dict],
                   request_changes_rounds: int = 0, tier0: str | None = None, ci: str | None = None,
                   tier0_failures: int = 0, ci_failures: int = 0, now: str | None = None) -> str:
    """Append one receipt. reviews: [{lane, run_id, verdict}]. Returns 'written', 'quarantined' or 'duplicate'."""
    d = Path(delegation_dir)
    d.mkdir(parents=True, exist_ok=True)
    tokens: dict = {}
    for rv in reviews:
        row = _registry_row(d, rv.get("run_id", ""))
        tin, tout = row.get("tokens_in"), row.get("tokens_out")
        tokens[rv["lane"]] = {"in": tin if isinstance(tin, int) else None, "out": tout if isinstance(tout, int) else None}
        total = _logged_total(d, row) if tokens[rv["lane"]] == {"in": None, "out": None} else None
        if total is not None:
            tokens[rv["lane"]]["total"] = total
    rec = {
        "schema": 1, "pr": pr, "head_sha": head, "author_lane": author_lane,
        "reviewer_lanes": sorted({r["lane"] for r in reviews}),
        "review_verdicts": [r.get("verdict") for r in reviews],
        "request_changes_rounds": request_changes_rounds,
        "tier0": tier0, "ci": ci, "tier0_failures": tier0_failures, "ci_failures": ci_failures,
        "tokens": tokens,  # {lane: {in, out}}; the author lane is absent: no per-PR author count is recorded anywhere
        "recorded_at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    main = d / LOG
    try:
        if any(json.loads(ln).get("pr") == pr for ln in main.read_text(encoding="utf-8").splitlines() if ln.strip()):
            return "duplicate"
    except (OSError, ValueError):
        pass
    redacted, found = _redact(json.dumps(rec, sort_keys=True))
    found = found + scan(redacted)
    if found:
        _append(d / QUARANTINE, json.dumps({"pr": pr, "recorded_at": rec["recorded_at"], "reasons": sorted(set(found)),
                                            "redacted": redacted}))
        print(f"WARN: outcome receipt for PR #{pr} quarantined ({','.join(sorted(set(found)))})", file=sys.stderr)
        return "quarantined"
    _append(main, redacted)
    return "written"
