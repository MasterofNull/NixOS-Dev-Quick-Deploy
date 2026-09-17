# Graft Parity Roundtable — Claude Analysis

Evidence-based review of 5 registered frontier-evidence candidates (trailhq/Graft) against
this repo's existing code-understanding stack: `.understand-anything/`, lean-ctx (MCP), and
`blast_radius_classifier.py`. All findings below come from reading the actual files and
live-testing the actual MCP tools in this session (not from documentation claims).

Repo read: `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy` (worktree `/tmp/graft-research`).

---

## fe-d191f4cdf93c — content-hash crux caching keyed by file body

**VERDICT: SUPPORT**

Evidence:
- `.understand-anything/ua-batch-processor.py` (534 lines) has **no content-hash caching at
  all** — no `hashlib` import, no `content_hash`/`sha256`/`md5` field anywhere in the file.
  Cache/staleness fields present are only `timestamp` (wall-clock strings via
  `time.strftime`), nothing keyed to file body content.
- `scripts/ai/aq-wiki`'s staleness detector, `_git_changed_paths_since(since_ts)`, diffs
  `git log` output against a stored timestamp — i.e. staleness is **git-commit/timestamp
  keyed**, not body-hash keyed. A file touched by an unrelated reformat/rebase, or a
  cherry-pick that changes line numbers without changing semantic content, will be flagged
  stale even though Graft's crux-hash approach would consider it unchanged.
- lean-ctx's own config (`~/.lean-ctx/config.toml`) has `content_defined_chunking = false`
  (off by default) — the capability name exists in the binary but is not the caching key we
  actually run on, and it isn't documented anywhere in `.agent/skills/lean-ctx/` or
  `.agents/plans/lean-ctx-workspace-identity/` as a body-hash-survives-line-shifts guarantee.

Conclusion: our cache invalidation is timestamp/git-diff-path based end to end, not
content-hash-of-body based. This is a real, narrow gap — not reinventing anything lean-ctx
already provides (its own chunking flag is off and undocumented for this purpose).

**Bounded slice** (`graft-parity-cache`): add a `body_sha256` field per extracted
symbol/crux excerpt in `ua-batch-processor.py`'s batch output (hash the extracted text
block, not the whole file), and gate `aq-wiki cmd_update`'s per-node regeneration on hash
mismatch instead of (or in addition to) `_git_changed_paths_since`. Pure stdlib
(`hashlib.sha256`), no LLM, no new dependency — respects minimal-code ladder.

---

## fe-313bd793165a — zero-cost per-query structural freshness (~3ms, no LLM)

**VERDICT: SUPPORT (sharpest gap found)**

Evidence (live-tested this session):
- `ctx_graph(action="status")` returned: `Last scan: 2026-06-10 23:24:52` — **the call-graph
  index lean-ctx uses for `ctx_callers`/`ctx_callees`/`ctx_graph impact` is ~3 months stale**
  (today is 2026-09-08). It is a one-time build (`ctx_graph action=build`), not refreshed
  automatically.
- Despite that staleness, `ctx_callers(symbol="classify")` returned a confident-looking
  answer ("No callers found for 'classify' (58999 edges in graph)") with **no staleness
  warning surfaced in the tool output**. An agent calling this tool has no signal that the
  answer may not reflect the last 3 months of commits or any uncommitted edits.
- `scripts/ai/aq-wiki --status` is a **manual** CLI freshness check (prints
  MISSING/STALE/OK per section) — it is not invoked automatically before a query, and
  nothing in `.claude/settings.json` (77 lines, no `hooks` key at all) wires a pre-query or
  per-prompt refresh.
- Graft's claimed behavior (re-parse only changed files with tree-sitter, ~3ms, before
  every query, no LLM) is a capability we do not have anywhere in this stack: not in
  understand-anything (LLM-heavy, batch, manual), not in lean-ctx (build-once, silent when
  stale).

This is the strongest real gap of the five: it's not "we lack the feature," it's "we have
the feature and it silently serves stale data with no signal to the caller."

**Bounded slice** (`graft-parity-freshness`): two parts, cheapest first —
1. *Cheap*: surface index age in `ctx_callers`/`ctx_callees`/`ctx_graph` output (one line:
   `index age: Nd — run ctx_graph build to refresh`). No code change to the graph engine,
   just don't hide the timestamp that `status` already computes.
2. *If (1) proves insufficient*: wire a cheap incremental refresh — `git diff --stat` since
   last graph build timestamp, tree-sitter re-parse only those files (lean-ctx already does
   tree-sitter AST parsing for `ctx_symbol`/`ctx_read`, so this is reusing an existing
   capability, not adding a parser) — triggered lazily on the next `ctx_graph`/`ctx_callers`
   call when age exceeds a small threshold (e.g. >1h), never per-keystroke.

---

## fe-d850a1dc53e5 — two-pass build: deterministic structural, then optional LLM deep

**VERDICT: CONCERNS (partial parity, split across two disconnected systems)**

Evidence:
- `ua-batch-processor.py` genuinely has a fast/LLM split: `is_fast_path()` (line 189) routes
  a batch to the deterministic `fast_graph()` (file-level nodes only, `simple_summary`/
  `file_tags`, no LLM) vs the LLM-backed `llm_graph()` (streams to Qwen3-35B). **But** the
  fast path only fires when `not (has_strict_code and has_real_imports)` — i.e. any
  Python/JS/TS file with real cross-file imports (the majority of code with actual wiring
  value) is forced onto the LLM path. Graft's Tier-1 is deterministic for **all** code
  (wiring graph + per-file cards come from tree-sitter with zero LLM calls); ours is
  deterministic only for docs/config/license/import-less files.
- Separately, lean-ctx's `ctx_graph` (58999 edges, 19105 symbols, 1656 files) **is** built by
  static/tree-sitter analysis with no LLM involved in that path — this is structurally
  closer to Graft's Tier-1. But it is a disconnected tool from understand-anything's
  knowledge-graph/wiki pipeline; nothing in `ua-batch-processor.py` or `aq-wiki` consumes
  `ctx_graph`'s edges. Two systems, two mechanisms, no shared foundation.

Conclusion: the deterministic-vs-LLM split Graft champions is real and valuable, and half of
it already exists in this repo (lean-ctx's tree-sitter graph) — the gap is that
understand-anything's LLM-heavy path doesn't build on top of it, so we pay LLM cost for
structural information (imports/wiring) that lean-ctx could already supply for free.

**Bounded slice** (`graft-parity-twopass`): extend `is_fast_path`/`fast_graph` in
`ua-batch-processor.py` so wiring/call edges for Python/JS/TS batches are sourced from
lean-ctx's already-built `ctx_graph`/`ctx_callers`/`ctx_callees` (deterministic, cached)
first; reserve the LLM call (`llm_graph`) strictly for narrative summaries/concept nodes
layered on top, mirroring Graft's tiering with tooling we already have installed. No new
parser, no new dependency — this is a wiring change, not a build.

---

## fe-2bcad93fae26 — per-symbol call-graph + trace-calls vs our file-level blast radius

**VERDICT: REJECT (equivalent already exists — under a different, unrelated file name)**

Evidence:
- Read both `blast_radius_classifier.py` files in full:
  `ai-stack/mcp-servers/hybrid-coordinator/blast_radius_classifier.py` (39 lines) and
  `ai-stack/mcp-servers/hybrid-coordinator/extensions/blast_radius_classifier.py` (159
  lines). **Neither is a code call-graph tool.** Both classify *shell/action strings* into
  risk tiers (critical/high/medium/low) via regex over patterns like `rm -rf`,
  `DROP TABLE`, `nixos-rebuild switch`, `git push --force` — this is the guarded-execution
  approval-gate classifier (Phase 28), unrelated to source-code blast radius entirely. The
  candidate's framing ("we have blast_radius_classifier.py — assess parity") rests on a
  false premise: that file was never meant to do what Graft's `graft_trace_calls` does.
- The actual equivalent lives in lean-ctx, and it works, live-tested this session:
  - `ctx_callers(symbol="classify")` → real per-symbol caller lookup over a 58999-edge graph.
  - `ctx_callees` → same, inverse direction.
  - `ctx_symbol(name, kind, file)` → isolated per-symbol code read (90-97% token reduction
    vs whole-file), directly comparable to Graft's per-symbol wiring cards.
  - `ctx_graph(action="impact", path=...)` → separate file-level blast-radius answer
    ("No files depend on blast_radius_classifier.py") — so we have **both** granularities
    Graft offers (per-symbol via ctx_callers/callees, file-level via ctx_graph impact),
    just split across two lean-ctx actions instead of one Graft command.

Conclusion: no real gap in capability. The only real issue is #2 above (the index backing
`ctx_callers` is 3 months stale) — that's a freshness problem, not a missing-feature problem,
and is already covered by the `graft-parity-freshness` slice.

**No new slice.** Recommend closing this candidate with a one-line doc note (not a build
task) pointing future agents at `ctx_callers`/`ctx_callees`/`ctx_symbol` as the call-graph
tool, so `blast_radius_classifier.py` stops being mistaken for one.

---

## fe-9cd0de9036c3 — deep agent integration: auto-sync hooks + per-prompt injection + statusline

**VERDICT: SUPPORT (accurately describes a real gap, scope it carefully)**

Evidence:
- `.claude/settings.json` (77 lines, read in full) has **no `hooks` key at all** — no
  SessionStart, UserPromptSubmit, PreToolUse, or PostToolUse hooks wired to any context
  refresh, and no `statusLine` entry either.
- `scripts/ai/aq-session-start` pulls AIDB bootstrap context + ranked hints from the hybrid
  coordinator (`${COORD_URL}/hints?...`) — this is explicitly a **once-per-session**
  hydration step ("mandatory context hydration"), not per-prompt.
- `scripts/ai/aq-wiki --status` is CLI-invoked manually; nothing calls it automatically on
  file change or before a prompt is answered.
- So today: context injection = session-start only. Graft's claimed per-prompt injection +
  auto-sync-on-file-change + live statusline genuinely does not exist here in any form.

Caveat: a literal per-prompt full context re-injection would work against this harness's own
rules — Rule 5 (compact aggressively, sub-agents get slice-relevant context only) and Rule 16
(any hook/behavioral change must land in CLAUDE.md + CODEX.md + LOCAL-AGENT.md + GEMINI.md +
WORKFLOW-CANON.md in the same cycle, since hooks are a canonical harness behavior change).
A heavy per-prompt injection modeled directly on Graft would be over-scope for a
local-first/APU-constrained harness that already leans on `aq-session-start` + `aq-hints` for
on-demand pull-based context.

**Bounded slice** (`graft-parity-integration`), cheapest first:
1. A `UserPromptSubmit` hook (declared in `.claude/settings.json`, committed — NixOS/agent
   parity rule applies) that emits **one line**: graph age + `git status --short` uncommitted
   file count (e.g. `graph: 3mo stale, 4 uncommitted files — ctx_graph build recommended`).
   No LLM, no large payload, directly closes the "sees uncommitted edits" and "auto-sync"
   halves of the claim without violating the compaction rules.
2. A `statusLine` command (separate, smaller slice) sourced from `ctx_graph status` +
   `git status --short`, gated behind Rule 16 agent-parity (must land in all agent files the
   same cycle since it's a canonical settings.json change) and Rule 22 minimal-code (reuse
   `ctx_graph status`'s existing output, no new telemetry pipeline).

---

## Summary Table

| Candidate | Verdict | Real gap? | Slice |
|---|---|---|---|
| fe-d191f4cdf93c — content-hash crux caching | **SUPPORT** | Yes — invalidation is git/timestamp-keyed, not body-hash | `graft-parity-cache`: add `body_sha256` per crux excerpt, gate regen on hash mismatch |
| fe-313bd793165a — zero-cost per-query freshness | **SUPPORT** | Yes — `ctx_graph` index is 3mo stale, no staleness signal surfaced | `graft-parity-freshness`: surface index age in tool output; lazy incremental tree-sitter refresh on threshold |
| fe-d850a1dc53e5 — two-pass build (structural→LLM) | **CONCERNS** | Half-exists, disconnected — lean-ctx's tree-sitter graph isn't consumed by understand-anything's LLM batch pipeline | `graft-parity-twopass`: route wiring/imports through `ctx_graph`/`ctx_callers` first, reserve LLM for narrative only |
| fe-2bcad93fae26 — per-symbol call-graph | **REJECT** | No — `ctx_callers`/`ctx_callees`/`ctx_symbol` already do this live (58999-edge graph); `blast_radius_classifier.py` is an unrelated action-risk classifier | None — doc pointer only |
| fe-9cd0de9036c3 — deep agent integration | **SUPPORT** | Yes — zero hooks/statusline in `.claude/settings.json`, injection is session-start-only | `graft-parity-integration`: one-line freshness hook (cheap) + statusline (Rule 16 gated) |
