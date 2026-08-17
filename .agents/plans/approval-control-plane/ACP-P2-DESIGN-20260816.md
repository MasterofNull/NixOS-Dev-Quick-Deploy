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
