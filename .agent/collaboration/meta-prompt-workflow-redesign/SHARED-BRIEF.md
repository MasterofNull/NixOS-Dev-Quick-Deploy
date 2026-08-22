# Meta-prompt exercise — the shared question (owner-directed 2026-08-21)

Three agents (Claude / Codex / Gemini-Antigravity) each write an INDEPENDENT meta-prompt answering the
same question. The three are then combined into ONE collaborative meta-prompt that drives a redesign of
our dev workflow, loops, roles, and harness architecture.

THE QUESTION:
"Simplify our workflows, loops, roles, and harness architecture — meet in the middle — while running a
MUCH stricter, more thorough process for system-critical and failure-prone areas. Address this at its
root core."

CONTEXT (what triggered this): a fast Claude-orchestrator→Sonnet-implementer→local-dogfood→commit loop
this cycle SILENTLY dropped PRD/plan ceremony + catch-up-queue registration + owner communication for a
large batch of local-agent-reliability work — technical gates (tests/tier0) were kept, governance +
communication gates were not, and the owner couldn't steer because it wasn't declared. Root failure =
uniform-heavy process invites silent selective compliance.

YOUR META-PROMPT SHOULD (independently — do NOT copy Claude's framing; argue with it):
- Name the root cause as YOU see it (may differ from Claude's "uniform process invites silent dropping").
- Propose how to tier rigor by risk (or reject tiering for a better model).
- Say what the minimum un-skippable gate is at every tier.
- Say how to make the risk-tier choice un-gameable (e.g. a security change can't be filed as trivial).
- Say what we should DELETE/simplify (roles, rules, ceremony, observability sprawl).
- Say how the owner stays in the loop cheaply.
- Push back on where Claude (flagship, and the lane that just failed) likely drew boundaries wrong.

Claude's contribution is at .agent/collaboration/meta-prompt-workflow-redesign/claude-meta-prompt.md —
read it to argue against, not to echo. Output your meta-prompt as markdown. Advisory; the owner + the
combination step decide. This is a governance/architecture decision — full independence is the point.
