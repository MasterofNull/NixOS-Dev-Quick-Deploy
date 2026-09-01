# Independent perspective — AQ-OS Installer & Quick-Deploy Experience PRD

Role: independent product + architecture + adversarial reviewer AND cross-distro researcher for a
NEW planning effort. Read-only on code; you MAY write ONE new perspective doc. Advisory only — the
orchestrator (Claude) owns, verifies, and folds your output; verify every factual claim you make
(you must not fabricate distro behavior — cite where you can).

## Read first (the consolidated direction)
- `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md` (authoritative v1 — golden-path direction)
- `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-claude.md` and `-codex.md` (source drafts)

## Product direction (owner-steered 2026-08-31)
ONE **golden path**: a super-tuned setup for professional dev + gaming + OPTIONAL local AI, that
adapts to the machine's hardware (detect specs → tune config, and if AI enabled, tune model/GPU-
layers/RAM-budget). Local-AI is optional and NEVER on the install critical path (a fresh machine
has no model yet). Modular `mySystem.*` engine stays underneath for experts. Exemplar: omarchy.

## Deliver: write `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-antigravity.md` covering
1. **Cross-distro research (cited):** how do the best beginner-friendly / golden-path installers
   actually work — archinstall, Calamares, omarchy, Universal Blue (Bluefin/Bazzite), NixOS's own
   installer, Fedora/Ubuntu? Specifically their (a) golden-path vs choice model, (b) hardware
   detection/tuning, (c) first-run onboarding, (d) safety/disk UX, (e) reproducibility. What should
   we borrow, and what should we deliberately do differently given we are declarative + agent-native?
2. **Gaps/risks** in the consolidated PRD the two prior drafts still miss (product AND engineering).
3. **The golden-path contents:** your recommendation for what the "AQ-OS Workstation" golden profile
   should actually include for pro dev + gaming, and the concrete hardware thresholds for the AI
   "recommended / limited / not-advised" call.
4. **Beginner-onboarding + accessibility** specifics (omarchy treats a11y as first-class).

Keep it grounded and cited. State clearly where you are uncertain. When done, `complete` this inbox item.
