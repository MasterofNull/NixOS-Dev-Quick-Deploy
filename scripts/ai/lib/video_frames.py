#!/usr/bin/env python3
"""Pure-Python helpers for scripts/ai/aq-transcribe (slice 1: acquisition + timed transcript).

Stdlib only. Subcommands keep the bash entry thin: segment normalizers (aq-segments/1),
stage `.done` records with fingerprints, and the cache-cap accounting (exit 7 = cache-full).
Transcript text is attacker-controllable data: it is parsed and stripped, never executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

SCHEMA = "aq-segments/1"
HELPER_SCHEMA = 1
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
TAG = re.compile(r"<[^>]*>")
CUE = re.compile(
    r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s+-->\s+(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)
EXPIRY_S = 7 * 86400


def clean(s: str) -> str:
    return " ".join(CTRL.sub("", s).split())


def _secs(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_vtt(text: str) -> list[dict]:
    """VTT cues -> segments. Rolling captions (a cue repeating the previous cue's lines) collapse."""
    segs: list[dict] = []
    prev_lines: list[str] = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = block.split("\n")
        cue_at = [i for i, ln in enumerate(lines) if CUE.match(ln)]
        if not cue_at:
            continue
        idx = cue_at[0]
        m = CUE.match(lines[idx])
        assert m is not None
        g = m.groups()
        start, end = _secs(*g[0:4]), _secs(*g[4:8])
        cur = [clean(TAG.sub("", ln)) for ln in lines[idx + 1 :]]
        cur = [ln for ln in cur if ln]
        new = [ln for ln in cur if ln not in prev_lines]
        prev_lines = cur or prev_lines
        if not new:
            if segs:
                segs[-1]["end_s"] = max(segs[-1]["end_s"], end)
            continue
        segs.append({"start_s": start, "end_s": max(start, end), "text": " ".join(new), "src": "vtt"})
    return segs


def parse_whisper_json(doc: dict) -> tuple[list[dict], str]:
    """openai-whisper (segments[].start/end seconds) or whisper-cpp (transcription[].offsets ms)."""
    segs: list[dict] = []
    if isinstance(doc.get("segments"), list):
        for s in doc["segments"]:
            a, b = float(s["start"]), float(s["end"])
            segs.append({"start_s": a, "end_s": max(a, b), "text": clean(str(s.get("text", ""))), "src": "whisper-openai"})
        return segs, "openai"
    if isinstance(doc.get("transcription"), list):
        for s in doc["transcription"]:
            off = s.get("offsets") or {}
            a, b = float(off["from"]) / 1000.0, float(off["to"]) / 1000.0
            segs.append({"start_s": a, "end_s": max(a, b), "text": clean(str(s.get("text", ""))), "src": "whisper-cpp"})
        return segs, "cpp"
    raise ValueError("unrecognized whisper json")


def finalize(segs: list[dict], source_kind: str, lang: str) -> dict:
    segs = sorted((s for s in segs if s["text"]), key=lambda s: (s["start_s"], s["end_s"]))
    for i, s in enumerate(segs, 1):
        s["id"] = f"s{i:05d}"
        s["start_s"] = round(s["start_s"], 3)
        s["end_s"] = round(s["end_s"], 3)
    return {"schema": SCHEMA, "source_kind": source_kind, "lang": lang, "segments": segs}


def write_transcript(doc: dict, outdir: Path) -> None:
    (outdir / "transcript.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    (outdir / "transcript.txt").write_text("\n".join(s["text"] for s in doc["segments"]) + "\n")


def valid_transcript(p: Path) -> bool:
    try:
        d = json.loads(p.read_text())
        return d.get("schema") == SCHEMA and isinstance(d.get("segments"), list) and all(
            s["start_s"] <= s["end_s"] for s in d["segments"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def fingerprint(args: list[str]) -> str:
    """args: key=value pairs; sha256 over sorted canonical JSON (subtitle sha + selection mode are keys)."""
    kv = dict(a.split("=", 1) for a in args)
    kv["helper_schema"] = str(HELPER_SCHEMA)
    return hashlib.sha256(json.dumps(kv, sort_keys=True).encode()).hexdigest()


def done_write(stage: str, stagedir: Path, donefile: Path, fp: str) -> None:
    outs = [
        {"path": str(f.relative_to(stagedir)), "size": f.stat().st_size, "sha256": sha256_file(f)}
        for f in sorted(stagedir.rglob("*"))
        if f.is_file()
    ]
    rec = {"stage": stage, "outputs": outs, "fingerprint": fp, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    donefile.parent.mkdir(parents=True, exist_ok=True)
    tmp = donefile.with_name(donefile.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, donefile)


def done_check(stagedir: Path, donefile: Path, fp: str) -> bool:
    try:
        rec = json.loads(donefile.read_text())
        if rec.get("fingerprint") != fp or not rec.get("outputs"):
            return False
        for o in rec["outputs"]:
            f = stagedir / o["path"]
            if not f.is_file() or f.stat().st_size != o["size"] or sha256_file(f) != o["sha256"]:
                return False
        return valid_transcript(stagedir / "transcript.json")
    except (OSError, ValueError, KeyError, TypeError):
        return False


def meta_check(p: Path) -> int:
    """Print the video id; exit 2 unless availability == 'public' exactly."""
    try:
        m = json.loads(p.read_text())
    except (OSError, ValueError):
        print("metadata unreadable: availability unknown", file=sys.stderr)
        return 2
    if m.get("availability") != "public":
        print(f"not public (availability={m.get('availability')!r}); public videos only", file=sys.stderr)
        return 2
    dur = m.get("duration")
    est = m.get("filesize_approx") or m.get("filesize") or 0
    print(json.dumps({"duration_s": dur if isinstance(dur, (int, float)) else -1, "est_bytes": int(est) if isinstance(est, (int, float)) else 0}))
    return 0


# ---- cache cap (exit 7 = cache-full) --------------------------------------------------------

def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def _locked(entry: Path) -> bool:
    lk = entry / ".lock"
    try:
        pid = int(lk.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def cache_usage(root: Path) -> int:
    return sum(_size(e) for e in root.iterdir()) if root.is_dir() else 0


def cache_admit(root: Path, current: str, need: int, max_bytes: int) -> int:
    root.mkdir(parents=True, exist_ok=True)
    if need > max_bytes:
        print(f"cache-full: need {need} B exceeds the cap {max_bytes} B outright", file=sys.stderr)
        return 7
    entries = sorted((e for e in root.iterdir()), key=lambda e: e.stat().st_mtime)
    prot = [e for e in entries if e.name == current or (e.is_dir() and _locked(e))]
    cand = [e for e in entries if e not in prot]
    usage = cache_usage(root)
    now = time.time()
    # 7-day-expired first, then LRU; both are oldest-first by mtime.
    cand.sort(key=lambda e: (now - e.stat().st_mtime <= EXPIRY_S, e.stat().st_mtime))
    while usage + need > max_bytes and cand:
        e = cand.pop(0)
        sz = _size(e)
        shutil.rmtree(e, ignore_errors=True) if e.is_dir() else e.unlink(missing_ok=True)
        usage -= sz
        print(f"cache-prune: {e} ({sz} B)", file=sys.stderr)
    if usage + need > max_bytes:
        print(f"cache-full: {usage}+{need} B exceeds cap {max_bytes} B; protected entries block reclamation:", file=sys.stderr)
        for e in prot:
            print(f"  {e} {_size(e)} B", file=sys.stderr)
        return 7
    return 0


def cache_check_write(root: Path, need: int, max_bytes: int) -> int:
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    if free < need * 2:
        print(f"cache-full: free space {free} B < 2x write need {need} B", file=sys.stderr)
        return 7
    if cache_usage(root) + need > max_bytes:
        print(f"cache-full: write of {need} B would exceed cap {max_bytes} B", file=sys.stderr)
        return 7
    return 0


def cache_measure(root: Path, max_bytes: int) -> int:
    u = cache_usage(root)
    if u > max_bytes:
        print(f"cache-full: end-of-run usage {u} B exceeds cap {max_bytes} B; entries:", file=sys.stderr)
        for e in sorted(root.iterdir()):
            print(f"  {e} {_size(e)} B", file=sys.stderr)
        return 7
    return 0


def main(argv: list[str]) -> int:
    c, a = argv[1], argv[2:]
    if c == "vtt2seg":  # <vtt> <out_dir> <source_kind> <lang>
        write_transcript(finalize(parse_vtt(Path(a[0]).read_text(errors="replace")), a[2], a[3]), Path(a[1]))
    elif c == "whisper2seg":  # <whisper.json> <out_dir> <source_kind> <lang> -> prints backend
        segs, be = parse_whisper_json(json.loads(Path(a[0]).read_text()))
        write_transcript(finalize(segs, a[2], a[3]), Path(a[1]))
        print(be)
    elif c == "fingerprint":
        print(fingerprint(a))
    elif c == "done-write":  # <stage> <stagedir> <donefile> <fp>
        done_write(a[0], Path(a[1]), Path(a[2]), a[3])
    elif c == "done-check":  # <stagedir> <donefile> <fp>
        return 0 if done_check(Path(a[0]), Path(a[1]), a[2]) else 1
    elif c == "meta-check":
        return meta_check(Path(a[0]))
    elif c == "sha256":
        print(sha256_file(Path(a[0])))
    elif c == "cache-admit":  # <root> <current> <need> <max>
        return cache_admit(Path(a[0]), a[1], int(a[2]), int(float(a[3])))
    elif c == "cache-check-write":  # <root> <need> <max>
        return cache_check_write(Path(a[0]), int(a[1]), int(float(a[2])))
    elif c == "cache-measure":  # <root> <max>
        return cache_measure(Path(a[0]), int(float(a[1])))
    else:
        print(f"unknown subcommand {c}", file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
