# antigravity-routing-consolidation — implementation spec

**Status:** PREPARED — proceed under owner standing authorization + orchestrator design (this doc).
**Risk tier:** MEDIUM (dispatch-wrapper routing + a switchboard-adjacent fallback; shared surface, no
live-data/migration/credentials). Right-sized gating: orchestrator design review (this) + ONE
independent acceptance after implementation. Implementer: cheap coder lane (Sonnet) — NOT Antigravity.
**Basis:** `ROUTING-FIX-PROPOSAL.md` (root cause). Decided scope below (the proposal's open options are
resolved here so the implementer makes no design calls).

## Decided scope — make the lane honest, do not fake a keyed path

The `delegate-to-antigravity --loop` route is NOT supposed to work for Antigravity under the no-key
policy; the sanctioned lane is the `aq-collab-round` inbox drop. This slice does not try to make the
keyed path function — it makes the wrappers fail honestly and point at the real lane, and removes the
silent degradation that returns RAG junk dressed as a review.

## File ceiling (exactly 3)

1. **`scripts/ai/aq-antigravity-agent`** — set the agent-loop `enable_fallback=False` (currently
   `True` with `fallback_endpoint=COORDINATOR_URL` around lines 96-98). On a remote/route failure the
   agent must return an explicit failure (non-zero status + the real error text), NEVER a
   hybrid-coordinator RAG result. If there is any code path that formats coordinator/RAG hits as the
   task "result", gate it so it cannot be reached for a `reviewer`/analysis task. The goal: a failed
   Antigravity call is visibly `failed`, not a list of file+score keyword hits.

2. **`scripts/ai/delegate-to-antigravity`** — (a) scrub the module docstring (lines ~1-16): remove
   the "secret must hold a Google AI Studio API key" guidance and any language presenting the
   switchboard/`remote-free` path as the working primary Antigravity route; state plainly that the
   keyed switchboard path is non-functional for Antigravity identity by policy and that the sanctioned
   lane is `aq-collab-round` (inbox drop, IDE OAuth, no keys). (b) When an Antigravity dispatch fails
   on the keyed route, the failure message must name `aq-collab-round` as the correct lane — no silent
   success, no RAG fallback surfaced as output.

3. **New `scripts/testing/test-antigravity-routing-honesty.py`** (or extend an existing antigravity
   test) — hermetic, offline: simulate a remote-route failure and assert the agent/wrapper returns an
   explicit failure, NOT RAG/keyword output; assert the `delegate-to-antigravity` docstring no longer
   advises a Google/Studio key and does name `aq-collab-round`. No real network/switchboard/binary.

No other file. **No API key, SOPS secret, or credential added anywhere** (verify with a diff grep at
acceptance).

## Explicitly OUT of scope (optional follow-up, do NOT do here)

Rerouting `delegate-to-antigravity` to actually perform an async inbox drop (turning it into a working
Antigravity delegate instead of a fail-honest pointer) is a separate enhancement. This slice only
stops the lying and documents the real lane; `aq-collab-round` remains the way to actually get an
Antigravity review.

## Validation

`bash -n`/`py_compile` as applicable on changed files; the new test passes offline; `git diff --check`
clean; `rg -n 'key|secret|token|credential'` over the diff shows no credential added. Then STAGE only
the 3 ceiling files; do NOT commit/Tier-0/self-accept — one independent acceptance follows.

`RECORD: orchestrator-designed, MEDIUM-tier. Implement under owner standing authorization; independent
acceptance before commit.`
