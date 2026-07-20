# DESIGN — Antigravity/Gemini Key-Free Reviewer Lane Restoration

Status: **PREPARED_ONLY / design — awaiting orchestrator + independent flagship review before any implementation**
Author: `claude-subagent-antigravity-lane-design` (bounded architect role — investigation + design only, no product-code/config/Nix edits)
Date: 2026-07-20
Grounding: owner directive `.agent/collaboration/PULSE.log` 2026-07-20T08:14:39-0700
`[owner] [acceptance-lane-directive]` — "build a slice to restore the no-key Antigravity/Gemini
OAuth lane ... so antigravity becomes a usable autonomous reviewer going forward ... do NOT add API
keys." Backlog anchor: `.agent/memory/issues-backlog.md`
`antigravity-cli-wake-has-no-attributable-claim-receipt` (line 23-26).

Hard constraint (non-negotiable, honored throughout this design): **no API key is added anywhere.**
Remote/IDE agents use their own OAuth/IDE session only. This document proposes zero credential,
zero SOPS-secret, and zero switchboard-key changes.

---

## 1. Existing work survey — what is already covered, what is not

Read before drafting: `.agents/plans/agent-connection-reliability/PROGRAM-PLAN.md`, its parent PRD
`.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`, `C0.6-CODEX-DESIGN-REVIEW.md`,
`.agent/collaboration/antigravity-inbox/agent-connection-reliability-c06-design-review.md`,
`antigravity-c0.5a-acceptance.md`, `C0.5-DESIGN-PACKET.md`, and the full antigravity-tagged
issues-backlog history.

**Finding: the durable-dispatch-fabric program does plan an Antigravity adapter, but it is not
this gap and it is not reachable soon.**

- The `agent-connection-reliability` program's target architecture (PRD §2) is a socket-activated
  `aq-dispatchd` broker over `AF_UNIX`, with an "Antigravity inbox/collector adapter" explicitly
  named as one of several provider adapters — but that adapter is scoped to **C3.3**, which sits
  behind **C1** (the broker itself, unimplemented) and **C2** (Claude canary, unimplemented). The
  program's current state (PROGRAM-PLAN.md, C0.6-CODEX-DESIGN-REVIEW.md dated 2026-07-17) is still
  at **C0.5/C0.6 — design-only, no live route authority, C1 not yet authorized.** Waiting for that
  chain to reach C3.3 to fix a currently-open reliability gap is disproportionate and not what the
  owner asked for on 2026-07-20.
- C0.5 ("Review Receipts and Recursive Feedback") is adjacent but answers a **different** question:
  it defines receipt/quorum/verdict contracts for **collaboration-round review findings**
  (`C0.5-DESIGN-PACKET.md` §"Review receipt contract" / §"Learning candidate contract"), not
  wake/claim/completion provenance for the **inbox transport mechanism** itself. Its schemas are not
  directly reusable here beyond general shape conventions (typed reasons, hash-bound subjects).
- **Conclusion: no existing design in this repo already specifies the wake→claim→output→completion
  receipt chain the owner asked for.** The issues-backlog action line (23-26) *names* that chain as
  the eventual fix but frames it as living inside "the planned broker-owned Antigravity adapter" —
  i.e., it assumes C1-C5 lands first. This design deliberately breaks that assumption: it specifies
  the same receipt chain as a **thin, additive extension of the mechanism that exists today**
  (`aq-collab-round` file-drop + `aq-antigravity-inbox` operator CLI), forward-compatible with the
  eventual C3.3 broker adapter but not dependent on it.

This document does not duplicate or re-litigate C0-C0.6; it is a **sibling, independently-scoped
slice** that closes the specific `antigravity-cli-wake-has-no-attributable-claim-receipt` gap now.

---

## 2. Current mechanism — read-only map

Two structurally separate lanes exist under the "Antigravity" name. Confusing them is itself a
source of past incidents (issues-backlog `antigravity-oauth-lane-vs-switchboard-keyed-remote-confusion`).

### 2a. The broken HTTP/key lane — `delegate-to-antigravity` → switchboard

`scripts/ai/delegate-to-antigravity` (`_run_switchboard`, lines ~296-407) POSTs to the local
switchboard (`:8085`) with profile `remote-free` (default) or `antigravity-collective`, which force
`provider=remote`. Switchboard resolves `REMOTE_LLM_URL` = Google Gemini direct
(`generativelanguage.googleapis.com/v1beta/openai`), but the wired secret
`/run/secrets/remote_llm_api_key` is an OpenRouter-style key (`sk-or-...`).
`ai-stack/switchboard/switchboard.py:3075-3086` detects this exact mismatch and **deliberately
refuses silent OpenRouter reroute**, returning HTTP 503:

```
"type": "remote_key_endpoint_mismatch",
"action": "use the no-key Antigravity IDE/OAuth lane for Gemini collaboration ...
           do not add API keys for Antigravity fan-out"
```

**This guard is correct and must not be "fixed" by adding a key.** I traced whether the wrapper
masks this failure as a silent local fallback (which would be worse — a caller believing it got a
real Antigravity/Gemini opinion when it got local Qwen instead). It does not: `_run_switchboard`'s
exception handling only treats HTTP `429/402` as retryable and `429/402/400/401/403` as
fallback-eligible (lines 356-378); `503` matches neither branch and falls through to the
unconditional `return "failed", 0, 0` (line 381) with the raw error body logged. So the route fails
**loudly and closed**, not silently. The remaining problem is purely labeling: the script's own
docstring (lines 1-16) still describes this as the primary, working Antigravity delegation path and
tells operators the secret "must hold a Google AI Studio API key" — which contradicts the no-key
policy and invites exactly the wrong fix (swap in a key). Backlog entry line 1449 already flags this
as SUPERSEDED guidance that was never fully scrubbed from the script header.

### 2b. The sanctioned no-key lane — file-drop inbox, IDE OAuth

Two scripts implement this, and neither performs an active "wake" today:

- **`scripts/ai/aq-collab-round`** (`_drop_antigravity`, lines 243-257): writes a task file to
  `.agent/collaboration/antigravity-inbox/<round>.md` and nothing else. It is a **passive drop** —
  the docstring literally says "the IDE agent (configured to poll)... polls this dir and responds."
  No subprocess is spawned to nudge the IDE.
  `_antigravity_inbox_live()` (lines 291-330) infers liveness from two weak proxies: `pgrep -fa
  antigravity` (process presence, not watch-configuration) and whether the **previously** dropped
  file was deleted within a 900s window, recorded in `.lane-state.json` (`{"last_drop": {"name",
  "ts"}}` — confirmed current content: `c05-tiered-policy-architecture.md`, one field, no claimant,
  no output binding).
- **`scripts/ai/aq-antigravity-inbox`** (130 lines, operator-side helper): `status` / `next` /
  `complete` only. `cmd_complete` (lines 87-100) `shutil.move()`s the file straight to an
  archive dir — no claim step precedes it, no receipt is written, no identity is captured for who or
  what invoked `complete`. The embedded `consume_contract` string ("IDE reads next, writes requested
  output, then archives... with `aq-antigravity-inbox complete`") is an **unenforced convention**,
  not a mechanism — nothing in the code distinguishes "the IDE did this autonomously" from "the
  owner did this manually" from "some unrelated process moved the file."

**The "CLI wake attempts" referenced in the issues-backlog incident
(`antigravity chat --reuse-window --mode agent`) do not exist in any tracked script** — repo-wide
grep for `reuse-window` matches only the backlog prose itself. The wake that produced the
unattributable incident was an ad hoc, un-codified invocation (by an agent or the owner, in a live
session), not a bug in an existing wake feature. This matters for scoping the fix: **there is no
wake mechanism to repair — one has to be built from nothing**, deliberately, as a thin logged
wrapper around exactly that kind of nudge, so it stops being ad hoc.

`.agent/ACTIVATION-AUDIT.md` line 52 already carries an open row: "Antigravity IDE inbox watcher |
inbox lane built | ⚠️ OPERATOR TODO | IDE must be configured to watch the inbox dir" — i.e. even the
passive-drop half of this lane has never been attested as actually working end-to-end; that
operator-side prerequisite is unchanged by this design (see §5).

### Exact break point (synthesis)

Wake → pickup → output → completion is one causal chain in intent, but today it is **four unlinked
events** with no shared identifier and no attributable actor:

1. A wake nudge may or may not happen, is never logged if it does.
2. "Pickup" is inferred after the fact from file deletion — indistinguishable from manual archiving.
3. Output (`.agents/plans/<round>/antigravity.md`) is never hashed or tied back to the inbox drop
   that supposedly produced it.
4. `complete` archives the file with no receipt of who called it or why.

This is exactly why the logged incident was unattributable: two wake attempts and one manual owner
prompt all preceded completion, and nothing in the system recorded which action — if any — was
causal.

---

## 3. Restoration design (key-free, additive, non-broker-dependent)

### 3.1 Principle

Add a small, file-based **claim-receipt ledger** as a thin layer bolted onto the transport that
already exists (§2b), not a rebuild. Every unit of work gets one `task_id` (reuse the round/drop
name — it is already unique per `aq-collab-round` invocation) and accumulates typed, appended
records in a per-task receipt file under
`.agent/collaboration/antigravity-inbox/receipts/<task_id>.json`. No network calls, no daemon, no
credentials — pure local JSON + `os.rename` CAS on the existing filesystem.

### 3.2 Four record types (wake → claim → output hash → completion)

1. **`wake_attempt`** — written by whichever actor attempts to nudge the IDE. Fields: `task_id`,
   `ts`, `actor` (`owner-manual` | `script:<name>`), `method` (`cli-nudge` | `passive-drop-only`),
   the exact argv actually run (for the CLI-nudge case, e.g. the existing but never-codified
   `antigravity chat --reuse-window --mode agent` invocation) and its exit code. A wake attempt is
   **never treated as proof of processing** — only as a logged, attributable input to the timeline.
   Codify this as a new `aq-antigravity-inbox wake <name>` subcommand: checks `pgrep antigravity`
   first, then runs a bounded, argv-fixed subprocess (no task content interpolated into the command
   line — avoids Rule 7 shell-injection surface), captures exit code, appends the record. This
   replaces the previously ad hoc, unlogged nudge with a logged one; it does not make the nudge
   mandatory — the passive poll remains sufficient and primary when the IDE is correctly configured.

2. **`claim`** — the pickup step becomes atomic and attributable instead of inferred from deletion.
   Extend `aq-antigravity-inbox` with a `claim <name> --actor <ide-watch|owner-manual>` subcommand
   that does an atomic `os.rename()` of the inbox `.md` file to a `.claimed-<task_id>` marker in the
   same directory (same-filesystem rename is a real CAS primitive: it can only succeed once, so two
   racing claimants cannot both win). Records `task_id`, `ts`, `actor`, and the SHA-256 of the
   pre-claim content. This is the single most important addition: it turns "file disappeared" from
   an inference into an atomic, exclusive, attributed event.

3. **`output_hash`** — when the expected output artifact appears (e.g.
   `.agents/plans/<round>/antigravity.md`, the path the drop itself already names — see
   `_drop_antigravity`'s "Respond by writing..." line), the completion step computes its SHA-256 and
   binds it into the same receipt record. This closes the "was this really the output of this
   task" gap.

4. **`completion`** — `aq-antigravity-inbox complete` is extended to **require a matching `claim`
   record for that `task_id` first**; if none exists it still archives (never block the operator —
   Rule 5/automation-first) but the receipt is explicitly flagged
   `completed_without_claim: true`, making an unattributed completion **visible** instead of
   indistinguishable from a clean one. On the normal path it writes `task_id`, `claim_actor`,
   `output_path`, `output_hash`, `ts`, then archives as today.

Net effect: the exact incident that opened the backlog item — two wake attempts plus one manual
owner prompt, no way to tell which caused completion — becomes reconstructable after the fact from
one JSON file per task: which wake attempts were logged, whether a `claim` preceded completion, who
claimed it, and whether the output hash matches what's on disk.

### 3.3 Disposition of the HTTP/key lane

**Recommendation: leave it disabled exactly as it is (the 503 guard is correct); this design changes
documentation only, not code.** Concretely (for a future, separately-authorized documentation-only
edit — out of scope for implementation today, but the correct next step to record):

- Update `delegate-to-antigravity`'s module docstring (lines 1-16) to state plainly that the
  switchboard/`remote-free` HTTP path is **structurally non-functional for Antigravity identity by
  design** (OpenRouter key vs. Gemini-direct endpoint, refused on purpose) and is not a target for a
  key swap; point callers at the inbox lane + the new `wake`/`claim`/`complete` receipt chain as the
  **sole sanctioned autonomous Antigravity route**.
- Do **not** retire the script file — its switchboard transport remains legitimate generic remote
  routing for non-Antigravity-identity purposes (this mirrors the disposition already applied to
  the retired Gemini npm lane, backlog `retired-gemini-dispatch-route-remains-executable`, which
  flagged the opposite mistake: a dead route left silently *executable*. Here the equivalent risk is
  a dead route left silently *documented as the primary path* — same class of drift, opposite
  surface).

### 3.4 What stays owner-driven vs. becomes agent-driven

| Action | Driven by |
|---|---|
| One-time Antigravity IDE OAuth session | Owner (already done per backlog history; unrelated to this gap) |
| Keeping the Antigravity IDE application running | Owner |
| Configuring the IDE workflow/rule that watches `.agent/collaboration/antigravity-inbox/` | **Owner — unresolved prerequisite, ACTIVATION-AUDIT.md line 52, unchanged by this design** |
| Optional manual `claim --actor owner-manual` when the owner is the de facto executor | Owner (explicitly supported, not hidden) |
| Wake-attempt logging, atomic claim CAS, output hashing, fail-closed(-visible) completion gate | Agent/repo — fully autonomous once implemented |
| Dashboard/liveness projection reading the receipt ledger instead of the current mtime-deletion heuristic | Agent/repo |

This design cannot make the IDE watch the folder — that remains a real, external, owner-side
configuration gap. What it *can* do is make whatever happens (owner-driven or IDE-driven)
attributable after the fact, which is the actual ask (a *claim receipt*, not a guarantee the IDE is
configured).

---

## 4. Scope, risk, implementer tier

**Proposed slice: `antigravity-lane-claim-receipt`** — standalone, not sequenced behind
`agent-connection-reliability` C1-C5.

- **File ceiling: 5 files.**
  1. `scripts/ai/aq-antigravity-inbox` — add `wake`, `claim` subcommands; extend `complete` to
     require/flag claim state; add receipt-writer helper.
  2. `scripts/ai/aq-collab-round` — optional: route its liveness check through the new receipt
     ledger instead of (or in addition to) the current mtime-deletion heuristic; no change to
     `_drop_antigravity`'s drop mechanics required.
  3. New: `scripts/testing/test-antigravity-claim-receipt.py` (or extend existing
     `test-antigravity-liveness.py`) — hermetic fixtures for: claim CAS exclusivity (two racing
     claims, one wins), completion-without-claim is flagged not silently clean, output hash mismatch
     is detected, wake attempt never counts as completion proof.
  4. `.agent/memory/issues-backlog.md` — close/update
     `antigravity-cli-wake-has-no-attributable-claim-receipt` referencing this design + eventual
     implementation.
  5. `.agents/plans/antigravity-lane-restoration/` plan-status file (this document + an
     authorization doc when the orchestrator activates it).

- **Risk tier: LOW.** Pure local Python file operations (JSON read/append, `os.rename` CAS,
  SHA-256), no network I/O, no credentials, no SOPS/secrets touch, no Nix, no systemd, no live
  registry-data mutation, no change to any provider's auth path. Fully reversible (additive
  subcommands; nothing existing is removed or behaviorally changed except `complete`'s new
  claim-check, which fails open/visible rather than closed/blocking).

- **Security-sensitive touchpoints to flag for the implementer:**
  1. `wake` shells out to an external `antigravity` binary — argv must be a fixed list, never string
     interpolation of task content (Rule 7 shell safety); reuse the existing `subprocess.run([...])`
     list-form pattern already used elsewhere in this script family (`aq-antigravity-inbox` has no
     subprocess calls today; `aq-collab-round` does — mirror its style).
  2. `claim`/`complete` must reuse `cmd_complete`'s existing path-containment check
     (`path.parent.resolve() != INBOX.resolve()`) to prevent path traversal via a crafted `name`
     argument — extend it to the new subcommands rather than re-deriving it.
  3. Receipts must store **hashes and paths only**, never full prompt/output content, keeping the
     ledger small and free of anything sensitive (none of this data is secret, but minimizing
     footprint is good hygiene per Rule 10 discipline).
  4. No API key, SOPS secret, or credential is introduced anywhere in this slice — verify at
     acceptance time (grep for `key|secret|token|credential` across the diff) since this is the one
     hard line the owner drew explicitly.

- **Recommended implementer tier (Rule 17, cheapest capable):** this is bounded, single-directory,
  single-concern Python CLI extension work with clear hermetic acceptance fixtures and no
  architectural ambiguity — **local (Qwen3-35B, `direct`/`agent` mode) or Codex headless is
  sufficient**; a flagship model is not required to implement it. Independent flagship (Antigravity
  itself, once it exists) or Codex should review before activation, matching the program's existing
  dual-review pattern (Codex + second-model-family).

- **Bootstrapping caveat (real, worth flagging explicitly):** Antigravity's own claim-receipt
  mechanism does not exist until this slice ships, so **the first review of this exact design cannot
  itself be verified through the mechanism it proposes** — any Antigravity verdict on this document
  will still arrive via the current unattributed inbox/manual path. A second, self-certifying round
  (Antigravity reviewing a *later* task through the new receipt chain) is the earliest point the
  fix can prove itself on its own terms.

---

## 5. Surprises / items needing owner or orchestrator attention

1. **The broker program's C3.3 "Antigravity adapter" is not this fix and is not close.** It is
   several unimplemented phases (C1 broker, C2 Claude canary) away from even starting. Treating this
   as satisfied-by-existing-plan would leave the owner's 2026-07-20 directive unaddressed for a long
   time; this design deliberately decouples the two.
2. **The HTTP/key path's 503 is not a bug — it is working as designed**, and already fails closed
   without masking as a silent local fallback (I verified this by tracing the exact exception-code
   branches in `_run_switchboard`). The only real defect there is stale docstring guidance that still
   points at a Google AI Studio key swap, which contradicts the no-key policy this task explicitly
   protects; a documentation correction is the whole fix, not a code change.
3. **No wake mechanism exists to repair — one must be built from scratch.** Repo-wide search found
   zero tracked-script matches for `reuse-window`; the incident's wake attempts were unlogged ad hoc
   invocations, not a failure of an existing feature. Scoping this as "restore/fix" undersells that
   it is new, small, additive code.
4. **The IDE-side watch configuration remains an unresolved, owner-only prerequisite**
   (`.agent/ACTIVATION-AUDIT.md` line 52, open since at least 2026-07-09 per backlog
   `antigravity-inbox-watcher-visibility-gap` / `[OPEN-OPERATOR] Antigravity lane never worked — IDE
   not wired to watch inbox`). This design's receipt chain makes *whatever happens* attributable; it
   cannot make the IDE watch the folder if it currently doesn't. Recommend the orchestrator confirm
   with the owner, at implementation time, whether the IDE-side workflow/rule is now configured —
   otherwise even a perfect receipt ledger will only ever show `wake_attempt` records with no
   matching `claim`, which is itself a useful (and currently invisible) diagnostic, but not yet an
   "autonomous reviewer."

---

`RECORD: design-only. No product-code, config, Nix, or credential changes were made or proposed for
immediate landing. No API key was added, proposed, or referenced as a fix path anywhere in this
document. Awaiting orchestrator scoping decision + independent flagship (and Codex, per program
convention) review before any implementation authorization.`
