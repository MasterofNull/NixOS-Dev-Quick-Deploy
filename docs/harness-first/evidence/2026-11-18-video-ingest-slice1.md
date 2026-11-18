# Harness-First Task Evidence

Date: 2026-11-18
Task ID: HF-20261118-video-ingest-slice1

## Objective
- Slice 1 of the video multimodal ingest design (rev 3): resilient acquisition and a timed transcript in `scripts/ai/aq-transcribe`. Root cause fixed: on 2026-11-18 a 429 caption failure (`|| true`) silently fell through to CPU Whisper, which ran 5 h at ~10 cores. Frames, OCR, descriptions and AIDB ingest are slices 2-3 and not built here.
- Delivered: one yt-dlp wrapper (429 classifier, shared 3-retry budget, `--retries 0 --ignore-config --no-cookies`); 429 is terminal (exit 4) at id, metadata, caption and media steps; caption priority creator > auto > Whisper; lazy Whisper preflight; local `--subs`/adjacent VTT; public-only (exit 2); stage cache (.tmp, atomic rename, `.done` with fingerprint incl. subtitle sha256 and selection mode); `aq-segments/1` seconds schema with VTT/openai-whisper/whisper-cpp normalizers (`scripts/ai/lib/video_frames.py`); Whisper under the power gate (exit 0 exactly, fail closed exit 5) at nice/idle priority under a systemd-run quota with a time budget (timeout = exit 6, no transcript, no `.done`); cache cap at admission/write/end-of-run (exit 7); existing `-protocol_whitelist file,pipe` and ffmpeg timeout preserved.

## Workflow/Session IDs
- Workflow ID: none (delegated bounded slice)
- Session ID: Simurg@claude/sonnet under orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated implementer slice (Rule 17, model sonnet). Spec: `.agents/delegation/outputs/video-multimodal-ingest-DESIGN-rev3.md` (rev 3 slice-1 text, supersedes rev 2), Codex review `codex-20261118-124111-75wsj9.log`. Independent review is the orchestrator's to route; not self-reviewed.

## Commands Executed
```bash
bash scripts/testing/test-aq-transcribe-acquisition.sh
python3 scripts/testing/test-ffmpeg-cve-mitigations.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- `test-aq-transcribe-acquisition.sh`: 104 checks, 0 failed, on stubs with no network: local VTT with no whisper/ffmpeg on PATH; caption-only URL without whisper; 429 terminal at id/meta/caps/media (3 backoffs 30/90/270, 4 attempts, Whisper never run, also with `--allow-whisper-on-error`); shared retry budget across calls; non-429 caption error; Whisper under gate+quota; cache reuse with zero Whisper/media calls; both backends normalize to identical segments; Whisper timeout exit 6 on openai-whisper and whisper-cpp with no transcript/.done; gate deferral, crash, missing gate, missing systemd-run all exit 5; fingerprint miss on VTT-only edit, `--lang` change, truncated cache, stale .tmp; public-only (private/unlisted/needs_auth/missing, `--cookies*`, URL userinfo); cache cap (oldest-unprotected-first prune, live-lock protected blocks with exit 7 naming path and size, outright over-cap, bundles outside cache uncounted, end-of-run re-measure); nonzero source timestamps and rolling captions.
- `test-ffmpeg-cve-mitigations.py` updated for the gate/quota/JSON contract: 6 tests OK (protocol_whitelist and timeout preserved).
- Not covered: real yt-dlp/Whisper/systemd-run (stubs only); real-network 429 behavior; the real power gate was not invoked in tests. A URL rerun still makes the id, metadata and caption calls (needed to detect subtitle edits) but not the media download.

## Rollback Plan
- `git revert` the slice commit. Trigger: any regression in aq-transcribe callers. Cache lives under `${AQ_TRANSCRIBE_CACHE:-~/.cache/aq-transcribe}` and is disposable.

## Residual Risk
- `transcript.json` format changed from raw Whisper JSON to `aq-segments/1`; no in-repo consumer found besides the tests. Raw backend JSON is kept as `transcript.raw.<backend>.json` in the cache stage.
- Whisper needs systemd-run user scopes; hosts without them get exit 5 by design (fail closed).
- Quota/priority behavior on this APU is unmeasured.

## Hint Feedback
- None used (offline slice implementation).
