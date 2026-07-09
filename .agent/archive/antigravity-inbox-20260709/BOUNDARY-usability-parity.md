# Boundary: Usability Parity Collaboration

Scope: `.agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md`
Collaboration board: `collab_1`
Plan: `plan-collab_1-1783573787`

Antigravity/Gemini is authorized for planning and review only in this pass.

Allowed:
- Write or update `.agents/plans/usability-parity/antigravity.md`.
- Add analysis notes under `.agents/plans/usability-parity/`.
- Contribute proposal references through `scripts/ai/aq-collaborate`.

Not allowed without a new explicit implementation slice:
- Edit `nix/`, `dashboard.html`, `assets/dashboard.js`, `scripts/ai/`, `ai-stack/`, or service files.
- Commit, amend, rebase, reset, or change git identity/config.
- Restart services, run rebuilds, or change AppArmor/NixOS runtime policy.
- Broaden scope beyond UI/CLI/operator-usability parity planning.

If implementation is needed, propose the slice first with files, acceptance criteria,
validation commands, rollback plan, and dashboard/aq-qa visibility gates.
