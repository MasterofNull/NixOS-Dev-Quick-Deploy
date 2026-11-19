# Harness-First Task Evidence

Date: 2026-11-18
Task ID: HF-20261118-video-ingest-slice1

## Objective
- Slice 1 of the video multimodal ingest design (rev 4): resilient acquisition and a timed transcript in `scripts/ai/aq-transcribe`. Root cause fixed: on 2026-11-18 a 429 caption failure (`|| true`) silently fell through to CPU Whisper, which ran 5 h at ~10 cores. Frames, OCR, descriptions and AIDB ingest are slices 2-3 and not built here.
- Rev-4 contract: one global flock for the whole run (second run exits 9, busy); exactly one `--dump-json` per URL run (id, availability and duration come from it; never cached); 429 terminal (exit 4) regardless of `--allow-whisper-on-error`; hard write limits (`ulimit -f` per process from the remaining cap, plus df before and du after each stage; exceeding the cache or bundle cap exits 7 and deletes that stage's outputs); no quarantine (a corrupt stage is deleted and redone); local inputs exempt from public-only; one media-relative timeline (VTT and Whisper times are already media-relative; frame times will be `pts_time - format.start_time`).
- Owner rule "no hardwired limits": every resource number comes from `resource_limits()` in `scripts/ai/lib/video_frames.py` as `{value, source}`: a host-derived default (CPU count, MemTotal, cache/out filesystem size and free space) with floors and ceilings, overridable by one `AQ_TRANSCRIBE_*` env var each. The chosen values and sources are written to `run.json` (`limits`). Caption/transcript sourcing: creator > auto > Whisper (last resort, lazy preflight, power gate exit 0 exactly else exit 5, nice/idle under a systemd-run quota, time budget).

## Workflow/Session IDs
- Workflow ID: none (delegated bounded slice)
- Session ID: Simurg@claude/sonnet under orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated implementer slice (Rule 17, model sonnet). Spec: `.agents/delegation/outputs/video-multimodal-ingest-DESIGN-rev3.md` (`video-multimodal-ingest-DESIGN-rev4.md` slice-1 sections; supersedes rev 3), limits audit `hardwired-limits-audit-20261118.md`. Independent review is the orchestrator's to route; not self-reviewed.

## Commands Executed
```bash
bash scripts/testing/test-aq-transcribe-acquisition.sh
python3 scripts/testing/test-ffmpeg-cve-mitigations.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Exit codes
| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | failure (including non-429 caption error without `--allow-whisper-on-error`) |
| 2 | policy reject: not public, cookies, URL credentials, over max media length, invalid limit env |
| 3 | missing tool |
| 4 | rate-limited (HTTP 429), terminal; never falls through to Whisper |
| 5 | power gate deferred, crashed or missing, or no systemd-run (fail closed) |
| 6 | Whisper exceeded its time budget (no transcript, no `.done`) |
| 7 | cache-full / bundle-full / write limit hit |
| 9 | busy: another run holds the global cache lock |

## Limits (host-derived defaults; each overridable; sources logged in run.json)
Sample derived values are from the dev host (1800 s media). Rows marked policy are policy defaults, not host facts.
| Limit | Derived default (floor / ceiling) | Env override |
|---|---|---|
| cpu_quota_pct | cores*100, cores = clamp(ncpu/4, 1, 16) (400) | AQ_TRANSCRIBE_CPU_QUOTA_PCT |
| memory_max_mb | 10% MemTotal, clamp 1-16 GiB, at most 50% MemTotal (2788) | AQ_TRANSCRIBE_MEMORY_MAX_MB |
| tasks_max | clamp(cores*16, floor, ceiling) (64) | AQ_TRANSCRIBE_TASKS_MAX |
| tasks_floor / tasks_ceiling (policy) | 32 / 4096 | AQ_TRANSCRIBE_TASKS_FLOOR / AQ_TRANSCRIBE_TASKS_CEILING |
| whisper_threads | cores (4) | AQ_TRANSCRIBE_WHISPER_THREADS |
| ffmpeg_threads | max(1, cores/2) (2) | AQ_TRANSCRIBE_FFMPEG_THREADS |
| whisper_factor | clamp(8/cores, 1, 8) (2.0) | AQ_TRANSCRIBE_WHISPER_FACTOR |
| whisper_budget_max_s (policy) | 14400 | AQ_TRANSCRIBE_WHISPER_BUDGET_MAX |
| whisper_budget_s | clamp(duration*factor, 300, budget_max); unknown duration -> budget_max (3600) | AQ_TRANSCRIBE_WHISPER_BUDGET |
| max_media_min | max(10, budget_max/factor/60) (120) | AQ_TRANSCRIBE_MAX_MIN |
| cache_max_bytes | min(10% cache fs, 50% free), floor 256 MiB, ceiling below (1.46 GB) | AQ_TRANSCRIBE_CACHE_MAX_GB |
| cache_ceiling_gb (policy) | 100 | AQ_TRANSCRIBE_CACHE_MAX_CEILING_GB |
| run_budget_mb | 15% of cache cap, clamp 16-1500 (209) | AQ_TRANSCRIBE_RUN_BUDGET_MB |
| ulimit_fraction (policy) | 0.25 of remaining cap per process (`ulimit -f`) | AQ_TRANSCRIBE_ULIMIT_FRACTION |
| bundle_max_mb | 2% of out-dir free space, clamp 50-2048 (263) | AQ_TRANSCRIBE_BUNDLE_MAX_MB |
| retries (policy) | 3 | AQ_TRANSCRIBE_RETRIES |
| backoff_base_s / backoff_mult (policy) | 30 / 3 -> 30 90 270 | AQ_TRANSCRIBE_BACKOFF_BASE_S / AQ_TRANSCRIBE_BACKOFF_MULT (or AQ_TRANSCRIBE_BACKOFF="s s s") |
| expiry_days (policy) | 7; expired entries are pruned first | AQ_TRANSCRIBE_EXPIRY_DAYS |
| max_height | 480 (<=2 CPUs or <6 GiB), 720 (<32 GiB), else 1080 (720) | AQ_TRANSCRIBE_MAX_HEIGHT |
Other existing overrides: AQ_TRANSCRIBE_CACHE, AQ_TRANSCRIBE_FFMPEG_TIMEOUT (600 s), AQ_TRANSCRIBE_POWER_GATE, AQ_TRANSCRIBE_DEFER_LOG, AQ_TRANSCRIBE_SLEEP.

## Validation Evidence
- `test-aq-transcribe-acquisition.sh`: 110 checks, 0 failed, on stubs with no network. Covers local VTT with no whisper/ffmpeg on PATH; caption-only URL without whisper; 429 terminal at meta/caps/media (3 backoffs 30/90/270, 4 attempts, Whisper never run, also with `--allow-whisper-on-error`); shared retry budget; non-429 caption error; Whisper under gate+quota with both backends normalising to identical segments; cache reuse; Whisper timeout exit 6; gate fail-closed exit 5; fingerprint misses; public-only; cache/bundle caps and exit 7; global lock exit 9; hard write limit; limits resolution, floors/ceilings, env overrides and run.json sources.
- Test isolation: every URL case uses a unique stub video id (captions are cached per id), so cases cannot interfere.
- `test-ffmpeg-cve-mitigations.py`: 6 tests OK (needs `flock` on PATH, from util-linux).
- Not covered: real yt-dlp/Whisper/systemd-run (stubs only); real-network 429; the real power gate. A URL rerun makes exactly one metadata call (never cached) but no caption or media call on a cache hit.
- Bug found and fixed in this pass: the Whisper path exited 1 (command not found, 127) because the per-process write limit was a bash function, and `systemd-run ... timeout ...` execs its command and cannot see shell functions. It is now an argv prefix (`bash -c 'ulimit -f ...; exec "$@"'`).

## Rollback Plan
- `git revert` the slice commit. Trigger: any regression in aq-transcribe callers. Cache lives under `${AQ_TRANSCRIBE_CACHE:-~/.cache/aq-transcribe}` and is disposable.

## Residual Risk
- `transcript.json` format changed from raw Whisper JSON to `aq-segments/1`; no in-repo consumer found besides the tests. Raw backend JSON is kept as `transcript.raw.<backend>.json` in the cache stage.
- Whisper needs systemd-run user scopes; hosts without them get exit 5 by design (fail closed).
- Quota/priority behavior on this APU is unmeasured.

## Hint Feedback
- None used (offline slice implementation).
