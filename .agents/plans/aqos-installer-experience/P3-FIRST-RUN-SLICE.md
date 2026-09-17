# p3-first-run — beginner welcome (P3 slice 2)

**Phase:** p3. **Deps (DONE):** p3-rollback (`scripts/ai/aqos-rollback` + `aqos_rollback.py`),
VM dogfood (golden profile boots). **Next:** p3-living-manual. **PRD:**
`.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md`. Reviewer: independent non-author before merge.

## Goal (one concern)
A **first-boot welcome** that orients a brand-new AQ-OS user in plain language — zero jargon, offline,
no expert CLI. Answers exactly three beginner questions:
1. **What is installed / what can I do now?** (the golden profile: what it gives them)
2. **How do I get help?** (points at the living manual once it lands; for now the quick-start + dashboard)
3. **How do I undo a bad change / roll back?** (plain-language pointer to `aqos-rollback`, the safety net)

## Minimal-code: REUSE, do not build new (Rule 20b)
- **Dashboard welcome surface already exists** — `OnboardingManager.showWelcome()` + `.welcome-banner`
  (see `scripts/ai/test-ux-improvements.sh`, `scripts/testing/test-dashboard-command-lenses-ui.py`).
  Reuse it; add the three beginner answers as its content, do NOT introduce a second welcome widget.
- **`docs/user-guides/quick-start.md`** is the canonical plain-language quick-start — link it, don't fork it.
- **`aqos-rollback`** (p3-rollback) is the rollback surface — the welcome POINTS at it, never re-implements it.
- First-run **detection** must be declarative/idempotent (a marker file the golden profile writes on first
  multi-user boot, checked before showing the banner) — reuse the marker pattern the aqos-vm dogfood host
  already uses (`systemd oneshot`, `wantedBy multi-user.target`), not an ad-hoc runtime write (Rule 13).

## Scope / constraints
- Offline only (no network). Plain language, no hashes/flags/jargon in user-facing text.
- Ports/URLs from env, never hardcoded. NixOS declarative-only for any first-run marker/service.
- One concern: the welcome + its three answers + first-run-once gating. NOT the living manual (next slice),
  NOT new rollback logic, NOT a redesign of the dashboard.

## Definition of done (DoD Rule 15)
- **Integrated:** welcome shown from the live first-boot path (golden profile), reachable in the VM dogfood.
- **On:** enabled in the golden `aqos-workstation` profile (gated so it shows once, then not again).
- **Real-world validated:** extend `scripts/testing/aqos-vm-dogfood.sh` (or a bounded test) to assert the
  first-run marker + welcome content resolve in the built VM — same disposable, no-sudo path.
- **Observable:** first-run state visible (marker present/consumed) — dashboard or health surface.
- **Intervenable:** user can dismiss/re-show; operator can reset the first-run marker declaratively.
- ACTIVATION-AUDIT entry + PM tracker update.

## Test
First-run marker fires once (present on first boot, consumed after), welcome content contains the three
beginner answers and the correct `aqos-rollback` pointer, all offline/in-VM (no real rebuild, no sudo).
