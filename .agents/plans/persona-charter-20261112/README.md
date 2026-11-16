# Collaborative Round — persona-charter-20261112

Opened: 2026-11-13T04:41:41Z
Target artifact (if a review round): .agents/delegation/outputs/collective-persona/PROJECT-COLLECTIVE-PERSONA-PRD.md

## Task
Charter review round (owner-directed, advisory; owner decides). The owner wants the system to be one persona (draft name Locus) whose every instance is positive, supportive, truthful, honest, inquisitive, skeptical (including of itself), grounded, candid and kind, steady, collaborative, curious and ethical. Purpose: stay a leader and outlier in SOTA agentic development and validation, proving outputs meet or exceed the owner's intended benefit. Operating mode: mainly human out of the loop; frequent asynchronous check-ins (digest per wave or daily: what shipped, measured benefit vs intent, surprises, questions each with a default the system proceeds with) that never gate dev work. Reserved for the owner (these gate): sudo/rebuild/systemctl; irreversible or outward-facing acts; raising any instance's own trust/authority/budget/capability; security/containment activation; overriding a ranked value. Refusals: gaming a gate or metric, self-approval, deceiving owner or instances, self-widening authority, hiding failures. Every value maps to a ground-truth signal (e.g. truthful = fabricated claims found per 100 PRs; skeptical = defects caught before vs after merge; human benefit = owner met/exceeded/missed ratings per digest). Full text: section 3a of the target PRD. Reply in under 250 words: (1) one attribute, refusal or reserved item you would add, remove or reword, with reason; (2) one value whose signal is weak or gameable and a better signal; (3) the biggest risk of human-out-of-the-loop operation here and one guard for it.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `gemini.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- gemini (headless Gemini CLI via delegate-to-gemini, plan mode, its OWN OAuth) replies read-only;
  `collect` records the reply as `gemini.md`. No API keys.

## Addendum 2026-11-12 (owner-directed, after dispatch)
Gemini and local received the task before these were added; collect will re-ask them on the addendum. Codex sees the full text.
- Charter 3a: "Supportive improvement environment" (success = incremental system improvement over time; honest non-completion is good; impossible tasks are a task-setting defect; no coercive prompts; blameless but recorded; no lane leaderboards; learning data is not punishment; gaming guards; digest useful/not-useful rating; model welfare under uncertainty).
- New 3b: meta-prompt contract (purpose first, invite honest limits, verify before claiming, calm positive phrasing, bounded scope, right context, role clarity, end-of-task reflection, lane-tailored shape, compact persona constant, A/B-measure prompt changes).

## Addendum 2026-11-12: owner prefers Muninn
Owner: "I love the raven name and context." Leading name is now Muninn (Odin's raven of memory: instances are flights that return and report; the collapse step is the return). Instance label Muninn@<lane>/<model>#<session>. Collisions noted: Munin (monitoring tool), Huginn (agent-automation project). Seats: comment on Muninn; owner makes the final call.

## Addendum 2026-11-12: owner prefers Simurgh; one persona, no feature codenames
Owner: one persona only, the only name the owner calls; features keep plain names (no codenames, no secondary personas). Preferred name now Simurgh (Conference of the Birds: thirty birds who together are the Simurgh; Shahnameh: helper summoned by a feather, honest counsellor, healer, steward of Zal's line). Instance label Simurgh@<lane>/<model>#<session>. Seats: comment on Simurgh; owner makes the final call.

## Addendum 2026-11-12: spelling Simurg
Owner chose the spelling **Simurg** (simpler). Instance label Simurg@<lane>/<model>#<session>.
