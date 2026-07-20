# Antigravity routing — root cause + proper fix (no workarounds)

**Status:** finding + proposal, 2026-07-20, Fable 5 orchestrator. Awaiting owner scoping decision.
**Prompted by:** owner directive 2026-07-20 — "make sure our system is operating as intended... if
our routing is supposed to work, then that issue should be resolved. I don't want a system built upon
the foundations of workarounds and patches."

## What actually happens (verified in the code, not assumed)

There are two things named "Antigravity." Only one is the designed lane.

1. **The designed, working lane — file-drop inbox (`aq-collab-round`).** It drops a task file into
   `.agent/collaboration/antigravity-inbox/<name>.md`; the Antigravity IDE (its OWN Google OAuth,
   real Gemini) watches the dir and writes the response. **No API key, does not touch the
   switchboard.** The script's own docstring is explicit: *"We do NOT call a headless key-based lane
   (that would fall back to local Qwen)."* This is what produced the real reviews (C0.6, B3, VF-7,
   L2B-B).

2. **The mis-wired lane — `delegate-to-antigravity --loop` → `aq-antigravity-agent`.** This does the
   exact thing the design forbids: it routes through the switchboard `antigravity-collective` profile,
   which is `forceProvider: remote` → the keyed Gemini-direct endpoint. Under the no-key policy the
   wired secret is an OpenRouter key against a Gemini endpoint, so the call fails (502/503). Then
   `aq-antigravity-agent` runs with `enable_fallback=True, fallback_endpoint=COORDINATOR_URL`, so on
   failure it **silently falls back to the hybrid-coordinator's RAG search** and returns keyword hits
   (file names + scores) that look like output but are not a review. Two probes (fast + pro) both
   degraded this way.

**So the answer to "is the routing supposed to work?": no — the `--loop` path is not the sanctioned
Antigravity lane and cannot be under the no-key policy.** It contradicts the design and hides its own
failure. The inbox lane is the one that is supposed to work, and does.

## Two real defects (independent of each other)

- **D1 — silent degradation masks failure (faithful-reporting).** `aq-antigravity-agent`'s
  `enable_fallback=True` turns a failed remote review into a RAG search result with no signal to the
  caller that the review never happened. An agent could commit on the strength of junk. This is the
  more dangerous of the two and is worth fixing regardless of D2.
- **D2 — `delegate-to-antigravity --loop` advertises itself as an Antigravity agent lane but routes
  to the forbidden keyed path.** Same class as the already-logged
  `retired-gemini-dispatch-route-remains-executable` (a dead route left silently executable).

## Proper fix (not a patch) — proposed slice `antigravity-routing-consolidation`

1. **Make the inbox lane the single sanctioned Antigravity route in `delegate-to-antigravity` too.**
   Either (a) `delegate-to-antigravity` for Antigravity identity delegates via the inbox drop
   mechanism (reusing `aq-collab-round`'s `_drop_antigravity`), or (b) `--loop`/`aq-antigravity-agent`
   stops using the `antigravity-collective` keyed-remote profile for Antigravity work.
2. **Remove the silent RAG fallback for review/analysis tasks (D1).** On remote/route failure the
   lane must fail LOUDLY (return an explicit error), never a RAG result dressed as an answer. If a
   coordinator-RAG mode is ever wanted, it must be an explicit, separately-named mode, not a silent
   fallback under a "reviewer" request.
3. **Scrub the stale docstring** in `delegate-to-antigravity` (the "Google AI Studio key" guidance
   that invites a forbidden key swap), per the design's §3.3.
4. No API key added anywhere (the hard line).

- **Risk tier: MEDIUM** (touches a dispatch script's routing + a switchboard-adjacent fallback;
  shared surface, no live-data/migration). Right-sized gating: orchestrator design review + ONE
  independent acceptance. Implementer: cheap coder lane (Sonnet/local/Codex-on-return) — NOT
  Antigravity (it's a reviewer lane, and this is its own plumbing).
- **Relation to the claim-receipt slice:** complementary. Claim-receipt makes the *inbox* lane
  attributable; this consolidation makes the *dispatch wrappers* stop pointing at the broken keyed
  path and stop masking failures. Together they make "delegate a review to Antigravity" mean one
  honest thing.

## Interim (until the fix lands) — not a workaround, an explicit choice

Route Antigravity reviews through `aq-collab-round` (the real inbox lane), never
`delegate-to-antigravity --loop`. This is using the sanctioned mechanism, not patching the broken one.

`RECORD: finding + proposal only. No code/config/Nix/credential change made here. Awaiting owner
scoping of the antigravity-routing-consolidation slice.`
