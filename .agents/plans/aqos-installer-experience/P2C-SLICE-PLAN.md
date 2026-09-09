# P2c — semantic-diff approval surface (installer AI/guided proposal)

**Phase:** p2 (Local AI-assist). **Deps (DONE, on main):** p2a `aqos_ai_proposal.validate_proposal`, p2b `aqos_ai_propose.propose_selection`, resolver `normalize_adapter`/`resolve_plan`/`compile_projection`, p1 golden profile + `aqos-guided-install`.
**PRD:** `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md`. **Design:** `P2-AI-ADAPTER-DESIGN.md` (slice p2c).
**Routed to:** cheapest-eligible implementer (Rule 17). **Reviewer:** independent non-author before merge.

## Objective (the missing linchpin)
Make a proposed installer selection (AI **or** guided) require an explicit **human approval via a
plain-language semantic diff** before it is resolved/applied — the "AI proposes, the human approves,
AI never authorizes" gate. Today p2a validates an untrusted proposal and p2b generates one offline,
but nothing lets a human SEE and APPROVE what will change. p2c closes that loop and delivers the
HARD beginner-friendly-human-control-surface requirement.

## The one hard invariant
Nothing resolves or applies until a human approves. On reject/timeout → nothing happens (fail-safe).
The approval carries a PLAIN-LANGUAGE diff (no hashes/jargon), not an expert CLI.

## Grounding — build on the Approval Control Plane (minimal-code, do NOT reinvent approval)
- `scripts/ai/lib/approval_request.py` — the `aq.approval-request.v1` closed record schema +
  `transition` + `RUNBOOK_REGISTRY` (typed effects). **Emit an approval request through this.**
- `scripts/ai/lib/approval_executor.py` — audited executor that runs a record's runbook effect ONLY
  once `status == "approved"`. **The apply path is a runbook effect, gated on approval.**
- `scripts/ai/aq-approve <id>` / `aq-approve-headless` — the human approval CLIs (+ the WebAuthn/
  biometric surface). **Reuse these; add no new approval mechanism.**
- Resolver `compile_projection(lock, ...)` — renders the resolved plan; use it (and the golden
  default's projection) as the diff BASIS. `normalize_adapter("ai", proposal)` → `resolve_plan` is
  the resolve step that runs ONLY after approval.

## Design / flow
```
proposal (p2b propose_selection OR guided answers)
   -> validate_proposal (p2a)                # untrusted -> clean selection or reject
   -> render SEMANTIC DIFF: proposed selection vs golden default (plain language, from projection)
   -> EMIT aq.approval-request.v1 (approval_request.py) carrying the diff + a runbook effect
      whose effect = normalize_adapter("ai", proposal) -> resolve_plan (NOT run yet)
   -> human approves via aq-approve / aq-approve-headless / WebAuthn
   -> on approved: approval_executor runs the runbook effect -> resolved lock (still inert P0 verifier path)
   -> on reject/timeout: nothing resolved (fail-safe)
```

## Files (smallest correct change)
- `scripts/ai/lib/aqos_install_diff.py` (NEW) — `render_selection_diff(proposed_selection, default_selection, module_catalog) -> str`: plain-language diff (profile changed / role added-removed / AI on-off with an honesty note on marginal hardware / "no change"). Reuse the wording shape from the p2c design; no hashes/jargon. Pure, no side effects.
- `scripts/ai/aqos-approve-install` (NEW, thin CLI) OR extend `aqos-guided-install` with an `--approve` path: takes a validated proposal, renders the diff, emits the `aq.approval-request.v1` via approval_request.py with a runbook effect that resolves the plan; prints the request id + how to approve (`aq-approve <id>`). NEVER resolves inline.
- Register the runbook effect (installer-resolve) in `approval_executor.py` / `RUNBOOK_REGISTRY` (typed, safe-handler-table style — no eval), effect = `normalize_adapter("ai") -> resolve_plan` for the approved selection.
- `scripts/testing/test-aqos-p2c-approve.py` (NEW).

## Validation / acceptance
- No-approval path: emitting a request resolves NOTHING (assert no resolved lock produced pre-approval).
- Approval path: after `aq-approve <id>`, the executor produces the SAME resolved lock a manual
  request with that selection produces (byte-identical via jcs) — proves approve==manual==one engine.
- Reject/timeout: fail-safe, nothing applied.
- Diff is plain-language (assert no raw hashes in the human diff string; covers profile/role/AI cases).
- No secrets/PII in the request; reuses ACP (no new approval mechanism); mock any WebAuthn/HTTP in tests.

## Notes
- Minimal-code: reuse approval_request.py + approval_executor.py + aq-approve; reuse compile_projection
  for the diff basis. Do not build a parallel approval path.
- Frontier gap: the taxonomy has no "human-control-surface/approval" concept (context relevance=0) —
  add a `human-control-surface` concept in a follow-up so future approval-related slices are grounded.
- This is the approval gate P4 (bare-metal, the only irreversible step = disk erase) will depend on.
