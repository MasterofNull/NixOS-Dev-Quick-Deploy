---
doc_type: plan
id: acp-deploy-20260817
title: ACP deploy record — surface wired into the dashboard (dev-mode)
status: in-progress
parent_prd: approval-control-plane
slice: acp-deploy
date: 2026-08-17
---

# ACP deploy — UI/UX functioning (crypto deferred)

Owner-directed 2026-08-17: deploy the UI/UX functioning now; defer crypto/human-in-the-loop hardening
until the system matures.

**What:** registered `approvals.router` (`/api/approvals/*`) + `view_router` (`/approve`) in the live
dashboard app (`dashboard/backend/api/main.py`). Uses the route module's `FixtureApprovalStore` /
`FixtureSignerClient` defaults — real WebAuthn signing + a live store are deferred. Real runbook effects
stay STUBBED, so the dev-mode surface performs nothing unsafe.

**Activation checklist (the 5 lines — no separate plan):**
1. Turn on: the `main.py` router-registration is prepared in the working tree; it lands + goes live at
   the next `nixos-rebuild switch` (which also provisions the newly-added `psutil` dep the dashboard-compat
   gate needs), then a dashboard restart → `/approve` serves the view, `/api/approvals/*` responds.
2. Confirm it works: open `http://127.0.0.1:<dashboard>/approve` → 3 sample cards render; Approve/Deny flow round-trips against the fixture signer.
3. Roll back: remove the two `include_router(approvals_mod…)` lines + restart.
4. Deferred (dated 2026-08-17): real signer/store, WebAuthn enrollment, confined services, real atoms — the `harden` item.
5. Safe-by-construction until then: fixture signer + stubbed effects; no real privileged action occurs.
