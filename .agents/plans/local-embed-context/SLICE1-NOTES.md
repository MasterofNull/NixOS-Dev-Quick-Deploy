# Slice 1 — aq-local-review — build notes

Implements Slice 1 of `DESIGN.md`: a standalone chunked map-reduce reviewer so
local (Qwen3-35B, ~12000-char/~3000-token context budget, full re-prefill every
call — no KV reuse) can produce a real, coverage-complete verdict on an artifact
too large to fit in one call, instead of abstaining once positional pruning
evicts the content under review.

## What shipped
- `scripts/ai/aq-local-review` (python3, executable) — CLI:
  `--target FILE --question TEXT [--out FILE] [--chunk-chars 5500]
  [--timeout 300] [--dry-run] [--json]`.
  - `chunk_text(text, cap)` — line-aware split: accumulates whole lines until
    the next line would exceed `cap`; never splits mid-line; a single line
    longer than `cap` becomes its own over-cap chunk rather than being cut.
  - MAP — one `delegate-to-local --mode direct --wait` call per chunk (prompt
    written to a `tempfile`, never interpolated into a shell arg). Output text
    is read back by parsing the task id out of delegate-to-local's stdout
    (`Delegating task: <id>`) and reading
    `.agents/delegation/outputs/<id>.log` directly — more robust than scraping
    the mixed `info()`/`cat` stdout stream.
  - CACHE — an ephemeral Qdrant collection `local-review-<uuid4>` is created;
    each non-trivial per-chunk finding (i.e. not exactly `NO FINDINGS`) is
    embedded (`bge-m3` via `:8081`) and upserted with
    `{chunk_index, finding}` payload. **Fully fail-open**: any embed/Qdrant
    error at create, upsert, or search time silently drops back to holding all
    findings in a plain Python list — the review always completes.
  - REDUCE — if the cache came up, embeds `--question` and retrieves the
    top-`K` (`K = min(chunk_count, 12)`) most relevant findings from Qdrant;
    otherwise passes every finding. One final local call synthesizes a single
    verdict, written to `--out` or stdout (or as JSON with `--json`,
    including `cache_used: bool`).
  - Cleanup: the ephemeral collection is deleted after REDUCE, fail-open
    (best-effort, never raises).
  - All subprocess calls are argv-list (`subprocess.run([...])`), never
    `shell=True`.

## How `--dry-run` works
Reads and chunks the target, builds the exact MAP prompt for every chunk via
`build_chunk_plan()`, and prints it (or emits JSON with `--json`) — the
function returns before any local/embed/Qdrant call is made, so `--dry-run`
is provably zero-network, zero-subprocess (verified in
`scripts/testing/test-aq-local-review.py` by monkeypatching `subprocess.run`
and `requests.post/put/delete` to raise if invoked).

## How to run a real review
```bash
scripts/ai/aq-local-review \
  --target path/to/large-artifact.md \
  --question "does this design respect the KV-cache constraint?" \
  --chunk-chars 5500 --timeout 300
```
Requires `delegate-to-local` (llama.cpp `:8080`) reachable for MAP/REDUCE.
The embed cache is optional — if `:8081`/Qdrant (`:6333`) are down, the review
still runs, just without top-K retrieval (all findings go to REDUCE).

## Known v1 limits (per DESIGN.md, deferred to later slices)
- Chunking is token/line-boundary, not semantic-boundary (Slice 4).
- No contextual/late-chunking summary prepended to embedded findings
  (Slice 4).
- Not yet wired as the local path for large `--target` in `aq-collab-round`
  (DESIGN.md Slice 1 bullet 5) — this build is the standalone helper only;
  the aq-collab-round wiring is a separate follow-up slice.
- Embed-cache correctness (retrieval relevance/hit-rate) is unmeasured here —
  Slice 1 acceptance is "coverage-complete verdict, fail-open when `:8081`
  down", not retrieval quality; that's Slices 2–4's measured territory.

---
## Follow-up fixes (2026-07-23, from real self-tests on the constrained APU)
1. **Bounded generation actually enforced.** `delegate-to-local --mode direct`
   reads `DIRECT_MAX_TOKENS` (default 4096), NOT `LLAMA_MAX_TOKENS`. The first fix
   set only the latter, so generation stayed unbounded and every chunk ran to
   ~4096 tokens and timed out. run_local now sets `DIRECT_MAX_TOKENS`
   (+ LLAMA_MAX_TOKENS as fallback) → map calls are genuinely capped (600 tok) and
   finite.
2. **Default per-call timeout raised to 600s** for constrained/slow hardware.
3. **Single-slot contention (known limitation, issues-backlog):** the APU has ONE
   serialized local inference slot. Running aq-local-review concurrently with other
   local-model users (e.g. tier0 phase0 QA) gets rejected ("banded slot"). Run it
   SERIALIZED via `aq-loop-queue --no-fanout` (overnight/idle), never concurrently.
   It is an overnight/queue tool, not interactive-concurrent. The per-chunk
   fail-open handles contention gracefully (honest "no verdict" rather than crash),
   but a real verdict needs an idle local slot.

The per-chunk fail-open + all-fail honest-report behavior is validated by both real
runs (it continued past every failure and reported truthfully).
