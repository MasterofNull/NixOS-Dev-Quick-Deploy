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
EXPIRY_S = 7 * 86400  # policy default; resource_limits() "expiry_days" (AQ_TRANSCRIBE_EXPIRY_DAYS) overrides


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
    vid = m.get("id")
    if not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", vid):
        print("metadata has no usable id", file=sys.stderr)
        return 2
    dur = m.get("duration")
    est = m.get("filesize_approx") or m.get("filesize") or 0
    print(json.dumps({"id": vid, "duration_s": dur if isinstance(dur, (int, float)) else -1, "est_bytes": int(est) if isinstance(est, (int, float)) else 0}))
    return 0


# ---- cache cap (exit 7 = cache-full) --------------------------------------------------------

def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def cache_usage(root: Path) -> int:
    return sum(_size(e) for e in root.iterdir()) if root.is_dir() else 0


def _rm(e: Path) -> None:
    shutil.rmtree(e, ignore_errors=True) if e.is_dir() else e.unlink(missing_ok=True)


def sweep_orphans(root: Path) -> None:
    """Under the global lock no other run is live: tmp dirs, work dirs and .part files are orphans."""
    for e in root.iterdir():
        if e.is_dir():
            for sub in e.iterdir():
                if sub.name == "work" or sub.name.endswith((".tmp", ".part")):
                    _rm(sub)


def cache_admit(root: Path, run_budget: int, max_bytes: int, expiry_s: float = EXPIRY_S) -> int:
    """Called while holding the global flock. Prune expired, then oldest-first, until
    usage <= cap - run_budget. Everything under the cache is prunable (no live entries exist)."""
    root.mkdir(parents=True, exist_ok=True)
    if run_budget > max_bytes:
        print(f"cache-full: run budget {run_budget} B exceeds the cap {max_bytes} B", file=sys.stderr)
        return 7
    sweep_orphans(root)
    entries = sorted((e for e in root.iterdir() if e.name != ".lock"), key=lambda e: e.stat().st_mtime)
    now = time.time()
    entries.sort(key=lambda e: (now - e.stat().st_mtime <= expiry_s, e.stat().st_mtime))
    usage = cache_usage(root)
    while usage > max_bytes - run_budget and entries:
        e = entries.pop(0)
        sz = _size(e)
        _rm(e)
        usage -= sz
        print(f"cache-prune: {e} ({sz} B)", file=sys.stderr)
    if usage > max_bytes - run_budget:
        print(f"cache-full: usage {usage} B leaves less than the run budget {run_budget} B under cap {max_bytes} B", file=sys.stderr)
        return 7
    return 0


def remaining(root: Path, max_bytes: int, fraction: float) -> tuple[int, int]:
    """(remaining bytes under the cap, per-process `ulimit -f` in KiB blocks)."""
    rem = max(0, max_bytes - cache_usage(root))
    return rem, max(1, int(rem * fraction) // 1024)


def cache_check_write(root: Path, need: int) -> int:
    """df before a stage: the filesystem must have room for the largest single write."""
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    if free < need:
        print(f"cache-full: free space {free} B < per-process write limit {need} B", file=sys.stderr)
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


# ---- host-derived, overridable resource limits ------------------------------------------------
# One place for every resource knob. Each limit has a host-derived default and one
# AQ_TRANSCRIBE_* env var that overrides it; floors/ceilings keep tiny and huge hosts sane.
# `source` is recorded per limit (env|derived) in run.json so behaviour is observable on any host.
MB = 1 << 20
GB = 1 << 30


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def read_host(cache_root: str = ".", out_dir: str = ".") -> dict:
    """Live host readings: CPU count, MemTotal, cache-fs size/free, out-fs free."""

    def anc(p: str) -> str:
        q = Path(p).resolve()
        while not q.exists() and q != q.parent:
            q = q.parent
        return str(q)

    try:
        ncpu = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        ncpu = os.cpu_count() or 1
    mem = 0
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            if ln.startswith("MemTotal:"):
                mem = int(ln.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    cu = shutil.disk_usage(anc(cache_root))
    ou = shutil.disk_usage(anc(out_dir))
    return {"ncpu": ncpu, "mem_total": mem, "cache_total": cu.total, "cache_free": cu.free, "out_free": ou.free}


def resource_limits(env: dict, host: dict, duration_s: float = -1.0) -> dict:
    """name -> {"value": v, "source": "env"|"derived"}. Env overrides win; invalid env raises ValueError."""
    out: dict = {}

    def pick(name: str, var: str, derived, cast=float):
        raw = env.get(var)
        if raw not in (None, ""):
            try:
                out[name] = {"value": cast(raw), "source": f"env:{var}"}
            except ValueError as e:
                raise ValueError(f"{var}={raw!r} is not a valid number") from e
        else:
            out[name] = {"value": derived() if callable(derived) else derived, "source": "derived"}
        return out[name]["value"]

    ncpu = max(1, int(host["ncpu"]))
    mem = int(host["mem_total"]) or 4 * GB  # unreadable /proc: assume a small host
    cores = int(_clamp(ncpu // 4, 1, 16))
    pick("cpu_quota_pct", "AQ_TRANSCRIBE_CPU_QUOTA_PCT", cores * 100, int)
    mem_mb = pick("memory_max_mb", "AQ_TRANSCRIBE_MEMORY_MAX_MB",
                  lambda: int(min(_clamp(mem * 0.10, 1 * GB, 16 * GB), mem * 0.5) // MB), int)
    out["memory_max_bytes"] = {"value": int(mem_mb) * MB, "source": out["memory_max_mb"]["source"]}
    # Policy defaults (not host facts): TasksMax floor/ceiling around cores*16.
    t_lo = pick("tasks_floor", "AQ_TRANSCRIBE_TASKS_FLOOR", 32, int)
    t_hi = pick("tasks_ceiling", "AQ_TRANSCRIBE_TASKS_CEILING", 4096, int)
    pick("tasks_max", "AQ_TRANSCRIBE_TASKS_MAX", int(_clamp(cores * 16, t_lo, t_hi)), int)
    pick("whisper_threads", "AQ_TRANSCRIBE_WHISPER_THREADS", cores, int)
    pick("ffmpeg_threads", "AQ_TRANSCRIBE_FFMPEG_THREADS", max(1, cores // 2), int)

    # Whisper time budget scales with media duration; fewer cores -> larger factor.
    factor = pick("whisper_factor", "AQ_TRANSCRIBE_WHISPER_FACTOR", round(_clamp(8.0 / cores, 1.0, 8.0), 3))
    bmax = pick("whisper_budget_max_s", "AQ_TRANSCRIBE_WHISPER_BUDGET_MAX", 4 * 3600, int)
    if duration_s and duration_s > 0:
        derived_budget = int(_clamp(duration_s * factor, 300, bmax))
    else:
        derived_budget = int(bmax)  # unknown duration: the ceiling, never unbounded
    pick("whisper_budget_s", "AQ_TRANSCRIBE_WHISPER_BUDGET", derived_budget, int)
    pick("max_media_min", "AQ_TRANSCRIBE_MAX_MIN", int(max(10, bmax / factor / 60)), int)

    # Cache cap: fraction of the cache fs (size and free), with floor and an overridable ceiling.
    ceil_gb = pick("cache_ceiling_gb", "AQ_TRANSCRIBE_CACHE_MAX_CEILING_GB", 100.0)
    cap_bytes = int(_clamp(min(host["cache_total"] * 0.10, host["cache_free"] * 0.50), 256 * MB, ceil_gb * GB))
    raw = env.get("AQ_TRANSCRIBE_CACHE_MAX_GB")
    if raw not in (None, ""):
        try:
            out["cache_max_bytes"] = {"value": int(float(raw) * GB), "source": "env:AQ_TRANSCRIBE_CACHE_MAX_GB"}
        except ValueError as e:
            raise ValueError(f"AQ_TRANSCRIBE_CACHE_MAX_GB={raw!r} is not a valid number") from e
    else:
        out["cache_max_bytes"] = {"value": cap_bytes, "source": "derived"}
    cap = out["cache_max_bytes"]["value"]
    pick("run_budget_mb", "AQ_TRANSCRIBE_RUN_BUDGET_MB", int(_clamp(cap * 0.15 / MB, 16, 1500)), int)
    pick("ulimit_fraction", "AQ_TRANSCRIBE_ULIMIT_FRACTION", 0.25)
    pick("bundle_max_mb", "AQ_TRANSCRIBE_BUNDLE_MAX_MB", int(_clamp(host["out_free"] * 0.02 / MB, 50, 2048)), int)

    # Acquisition retry policy.
    # Policy defaults: 429 retry count, backoff growth multiplier, cache entry expiry.
    pick("retries", "AQ_TRANSCRIBE_RETRIES", 3, int)
    mult = pick("backoff_mult", "AQ_TRANSCRIBE_BACKOFF_MULT", 3, int)
    pick("expiry_days", "AQ_TRANSCRIBE_EXPIRY_DAYS", 7, float)
    base = pick("backoff_base_s", "AQ_TRANSCRIBE_BACKOFF_BASE_S", 30, int)
    sched = env.get("AQ_TRANSCRIBE_BACKOFF")
    if sched:
        try:
            lst = [int(x) for x in sched.split()]
        except ValueError as e:
            raise ValueError(f"AQ_TRANSCRIBE_BACKOFF={sched!r} must be space-separated seconds") from e
        out["backoff_schedule_s"] = {"value": lst, "source": "env:AQ_TRANSCRIBE_BACKOFF"}
        out["retries"] = {"value": len(lst), "source": "env:AQ_TRANSCRIBE_BACKOFF"}
    else:
        n = int(out["retries"]["value"])
        out["backoff_schedule_s"] = {"value": [int(base * mult**i) for i in range(n)], "source": out["retries"]["source"] if out["retries"]["source"] != "derived" else out["backoff_base_s"]["source"]}
    # Download max resolution (consumed by the frame stage; audio-only slice 1 only reports it).
    pick("max_height", "AQ_TRANSCRIBE_MAX_HEIGHT",
         480 if (ncpu <= 2 or mem < 6 * GB) else (720 if mem < 32 * GB else 1080), int)
    return out


def limits_cli(cache_root: str, out_dir: str, duration_s: float, kv: bool) -> int:
    try:
        lim = resource_limits(dict(os.environ), read_host(cache_root, out_dir), duration_s)
    except ValueError as e:
        print(f"limits: {e}", file=sys.stderr)
        return 2
    if kv:
        for k, v in lim.items():
            val = " ".join(str(x) for x in v["value"]) if isinstance(v["value"], list) else v["value"]
            print(f"{k}={val}")
    else:
        print(json.dumps(lim, indent=1))
    return 0


def media_relative(pts: float, start_time: float) -> float:
    """One timeline = media-relative seconds (frame ts = pts_time - format.start_time).
    VTT cues and Whisper segments are already media-relative and must not be shifted."""
    return round(pts - start_time, 3)


def dir_size(p: Path) -> int:
    return _size(p) if p.exists() else 0


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
    elif c == "limits":  # <cache_root> <out_dir> <duration_s>
        return limits_cli(a[0], a[1], float(a[2]), False)
    elif c == "limits-kv":
        return limits_cli(a[0], a[1], float(a[2]), True)
    elif c == "bundle-check":  # <out_dir> <stage_dir> <max_mb>: size after the last write
        sz = dir_size(Path(a[0])) + dir_size(Path(a[1]))
        if sz > int(float(a[2])) * MB:
            print(f"bundle-full: {a[0]} would be {sz} B, over the {a[2]} MB bundle cap", file=sys.stderr)
            return 7
    elif c == "sha256":
        print(sha256_file(Path(a[0])))
    elif c == "cache-admit":  # <root> <run_budget_bytes> <max> [expiry_days]
        return cache_admit(Path(a[0]), int(float(a[1])), int(float(a[2])),
                           float(a[3]) * 86400 if len(a) > 3 else EXPIRY_S)
    elif c == "remaining":  # <root> <max> <fraction> -> "<bytes> <ulimit_kib>"
        r, k = remaining(Path(a[0]), int(float(a[1])), float(a[2]))
        print(r, k)
    elif c == "cache-check-write":  # <root> <need_bytes>
        return cache_check_write(Path(a[0]), int(float(a[1])))
    elif c == "media-relative":  # <pts> <format.start_time>
        print(media_relative(float(a[0]), float(a[1])))
    elif c == "cache-measure":  # <root> <max>
        return cache_measure(Path(a[0]), int(float(a[1])))
    else:
        print(f"unknown subcommand {c}", file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
