---
doc_type: design-packet
id: acp-p2-design-20260816
title: ACP-P2 — the approval surface (beginner-friendly human control)
status: draft
parent_prd: approval-control-plane
slice: acp-p2
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: command-center-dashboard
reviewer: pending
date: 2026-08-16
---

# ACP-P2 — the approval surface

Third ACP slice. The human-facing control the whole plane exists to deliver: pending authorizations as
plain-language cards, a one-tap approve gated by the P1 WebAuthn service, and a Details drill-in for the
curious. This is the "act" surface (HERDR/dashboard observe; ACP acts). Builds on ACP-P0's record
(`dee72d38`) + the ACP-P1 signer contract (`ACP-P1-DESIGN-20260816.md`). Ratified PRD R2.

## The one experience
A beginner opens the Command Center, sees "1 thing needs your OK", reads a plain sentence
("Activate the scheduler-context issuer? This lets the system issue signed scheduling permits."), and
either taps **Approve** (security-key / fingerprint) or **Deny**. No hash, key, path, or command is ever
shown unless they open **Details**. Zero system knowledge, zero coaching. That is the whole bar.

## What it renders (and what it must never render)
- Reads pending `aq.approval-request.v1` records via the operator-context projection (integration
  contract #1, already ratified) — the surface is a VIEW, never a second authority.
- Shows ONLY Layer-1 `summary` by default: `title`, `what`, `why`, an `impact` chip (low/medium/high),
  a `reversible` marker. The P0 privacy invariant already guarantees no hex/key/path/socket/"sha256" can
  appear in Layer-1, so the surface is structurally beginner-safe — it cannot leak crypto even by bug.
- **Details** drill-in reveals Layer-3 `technical_trail` (design hash, target files, grant subject) for
  the curious — clearly separated, never required to make the decision.
- Impact drives prominence: `high` is visually distinct (not alarming, but unmissable); `reversible`
  is surfaced as reassurance.

## The approve flow (binds to P1 — no crypto in the human's hands)
```
[Approve] tap
  -> surface calls acp-signer.service.sign(request_id)  (P1; UDS via the dashboard's client group)
  -> the SERVICE fetches the canonical record itself + derives the WebAuthn challenge (WYSIWYS, P1)
  -> browser WebAuthn prompt fires (user_verification=required) -> human taps key / biometric
  -> service verifies single-use assertion, signs canonical_hash, returns the signature
  -> the executor (P0/P1) runs the bounded runbook; surface shows "Approved -> running -> done"
[Deny] tap -> transition pending->denied (no assertion needed); surface shows "Denied"
```
The surface NEVER handles the challenge, the assertion, or any key — it triggers the browser WebAuthn
ceremony and calls the service. What the human read (Layer-1) is bound by `canonical_hash` to what the
service signs and the executor runs (P0 finding #7 + P1 invariant 6), so the card cannot lie.

## Beginner-friendly + accessible requirements (the acceptance bar)
- Plain language, active voice; button says exactly what happens ("Approve", then a toast "Approved").
- No jargon, no crypto, no CLI affordance anywhere in the default path (PRD R2 / memory
  feedback-beginner-friendly-human-control-surface).
- WCAG AA: keyboard operable, visible focus, prefers-reduced-motion respected, screen-reader labels on
  every control, contrast AA in light + dark.
- Errors explain what to do ("Your security key wasn't detected — try again or use another key"), never
  a stack trace or code.
- A denied/expired/failed request is shown honestly with a plain reason; nothing silently disappears.

## Validation goals
- **privacy-render** — given any valid record, the default view contains no Layer-3 content and no
  hex64/path/key/socket/"sha256" (DOM assertion) — belt-and-suspenders over the P0 record invariant.
- **decision-clarity** — a usability check: a non-expert can identify the correct request and what
  approving does, from Layer-1 alone (scripted scenario assertions on rendered text).
- **approve-binds-to-signer** — Approve calls `sign(request_id)` and NEVER passes bytes/hash; the
  WebAuthn ceremony is browser-driven; the surface holds no key material.
- **deny-path** — Deny transitions pending->denied with no assertion and is clearly reflected.
- **a11y** — keyboard-only approve/deny, focus order, ARIA labels, reduced-motion, AA contrast both
  themes.
- **state-honesty** — pending/approved/running/done/denied/expired/failed each render a truthful,
  plain-language state; no false "done".

## Review fold — local Qwen (`n147vs`, verdict: Layer-1/Details + approve flow sound; hardenings)
- **Plain-language lint on Layer-1 (beyond the crypto privacy scan).** P0 forbids hex/key/path in
  `summary`, but plain *jargon* ("issuer", "context", "epoch") isn't crypto yet still confuses a
  beginner. Runbook summary templates (P0) must be written in true plain language; add a review check
  that Layer-1 text avoids unexplained system terms. The surface renders faithfully; the plainness is
  enforced at the template.
- **Real-time signer status — no "pending forever".** The card reflects the live P1 signer/executor
  state (awaiting-tap / verifying / running step k/n / done / failed), driven by the operator-context
  projection, so a stalled approval is visibly stalled with a next action, never a silent spinner.
- **a11y specifics (added to the acceptance bar).** Approve/Deny carry descriptive screen-reader labels
  ("Approve: activate the scheduler-context service"); focus moves predictably after approval (to the
  result/toast) and returns sanely on cancel; WebAuthn timeout/cancel is an explicit, actionable error
  state ("No response from your security key — try again"); AA contrast verified for every impact card
  variant (low/medium/high) in both themes.

## Review fold — Antigravity (CONDITIONAL PASS) + local (`n147vs`)
Build authorized subject to folding these (orchestrator-verified):
- **[KEY — DOM-tampering / clickjacking] The surface must run in an agent-uncontrollable browser session.**
  A compromised agent in the user session could inject scripts and show "Enable timezone sync" while
  calling the signer for "Revoke production key"; the native WebAuthn prompt shows only RP-ID + a raw
  hash, so the human cannot detect the swap. Mitigation (now a build requirement): the dashboard approval
  view runs in an ISOLATED kiosk browser session (dedicated systemd-run/kiosk Chromium) under a strict
  CSP (no inline scripts, no eval, no extensions, no third-party origins); the approval surface is served
  same-origin and cannot be reframed. This is what makes the browser leg trustworthy — without it, P2's
  WYSIWYS is only as good as the (compromised) DOM.
- **[Render-vs-Sign] Reinforce the P0 #7 binding at the signer.** The signer (P1) verifies `summary`
  byte-equals `render_summary(runbook, params)` (already enforced in P0 `validate`); the surface renders
  that same bound summary. Any action-affecting field not represented in what the human sees aborts. Note:
  `technical_trail` is hashed but non-executed; the Details view still shows it so nothing signed is unseen.
- **[Live-sync / no double-tap] (sharpens local + Antigravity 3).** A prominent Live-Sync connection
  indicator; on a dropped backend connection the UI overlays a warning and DISABLES Approve/Deny, so a
  silent stale "Awaiting tap" cannot lead to repeated taps / unintended double-execution. (The signer's
  single-use request_id ledger is the hard backstop; this is the UX guard.)
- **[Plain-language error mapping] (sharpens local).** Every WebAuthn/crypto/execution exception
  (`InvalidSignatureError`, UV-not-satisfied, timeout) maps to a plain-language error card with a physical
  recovery step ("Please re-insert your security key and touch the blinking light") — never a raw error.
- **[Micro-copy] (Antigravity 5).** Inline text under Approve explains the physical action ("Tapping
  Approve will ask you to scan your fingerprint or touch your security key"), so a beginner is not
  surprised by the OS/browser prompt.

## Scope fence (NOT in P2)
No P1 service internals (consumes its contract), no runbook engine (P3), no recovery (P1b), no headless
CLI (P4). P2 is the surface: read projection -> render cards -> approve/deny -> call signer -> reflect
state. Visual polish uses the artifact-design bar AT BUILD; this packet fixes the contract + the
beginner-friendly/a11y/privacy acceptance bar, not the pixels.

## Dispatch (Rule 17)
Architect: this packet (flagship). Build: cheapest healthy implementer whose capability satisfies a
dashboard UI + a11y slice (NOT the orchestrator); front-end build pairs with the artifact-design skill.
Per never-go-down, design review routes to local + Antigravity now; Codex binding on return; build is
gated on P1 landing (the signer the approve flow calls) + owner activation of the surface.

## Review request (independent, per slice)
Assess: (1) is "render Layer-1 only, Details for Layer-3" sufficient to keep the surface beginner-safe;
(2) does the approve flow keep ALL crypto out of the human's hands while preserving WYSIWYS; (3) is the
a11y/beginner acceptance bar complete for a true beginner; (4) any state the surface could render
dishonestly or any place jargon/CLI could leak into the default path.
