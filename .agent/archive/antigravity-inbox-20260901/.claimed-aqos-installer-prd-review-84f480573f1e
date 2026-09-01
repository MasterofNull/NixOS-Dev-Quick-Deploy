# Flagship design review — AQ-OS Installer Experience consolidated PRD

Role: independent flagship product + architecture + adversarial-concurrency + SRE reviewer. Read-only
on code. Advisory only: the orchestrator (Claude) owns, verifies, and folds your output — verify every
factual claim; do NOT fabricate distro behavior.

## Exact candidate (fail on hash mismatch)

```text
bfd870d7f4ae06ce193ec67c7b3847a24cc72e40ad9580c8d7c335993b1550ca  .agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md
```

Also read for context: `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-claude.md`, `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-codex.md`,
and `.agents/plans/aqos-installer-experience/tracker.json`.

## Product direction (owner-steered 2026-08-31)
ONE golden path: super-tuned professional dev + gaming + OPTIONAL local AI, hardware-adaptive, local-only
(AI never on the install critical path), modular mySystem.* engine underneath for experts. Exemplar: omarchy.

## Deliverable

Output: .agents/plans/aqos-installer-experience/antigravity-prd-review.md

Write your verdict to that file, then `complete` this inbox item.

Explicitly adjudicate:
1. Does the golden-path + optional-hardware-tuned-AI + deterministic-install design hold up, or is there a
   product or engineering flaw the claude/codex drafts still miss?
2. Cross-distro (cited, verify): what do archinstall, Calamares, omarchy, Universal Blue (Bluefin/Bazzite),
   and the NixOS installer do for golden-path vs choice, hardware detection/tuning, first-run onboarding,
   disk-safety UX, and reproducibility — what to borrow, what to deliberately differ on.
3. The config-contract + 4-layer parity design (codex section 5-6): sound? gaps? failure modes?
4. Golden profile contents recommendation (pro dev + gaming) and concrete hardware thresholds for the AI
   recommended/limited/not-advised call.
5. Beginner onboarding + accessibility specifics.

State clearly where you are uncertain. This is design-only; no implementation authorized.
