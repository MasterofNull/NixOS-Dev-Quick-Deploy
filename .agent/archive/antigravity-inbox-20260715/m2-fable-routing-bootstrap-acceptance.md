# Flagship acceptance — M2 Fable-routing bootstrap

Review the owner-authorized three-file bootstrap candidate:

1. `.agents/plans/agent-ops-traceability-r0m/FABLE-ROUTING-BOOTSTRAP-AUTHORIZATION.md`
   SHA-256 `ae6f28204989d7ebbb495f22b1191e7589e718211a81786aab05672f9171daec`
2. `scripts/ai/delegate-to-claude`
   SHA-256 `fc2094caf0591d35bc10ed201ec07d6a52b37953dbca2d8e56562ddee6e36884`
3. `scripts/testing/test-delegate-claude-model-routing.py`
   SHA-256 `e01a7faa95f2c10f05e5d217538ad6db71ef65287927f18d0eda96b04e030326`

Independently verify exact scope, Bash/Python syntax, and the focused test. Threat-model malformed or
missing `config/model-coordinator.json`, unknown tiers, invalid model IDs, shell/argv injection,
registry JSON validity, requested/resolved identity truthfulness, default compatibility, background
and wait command construction, and whether any path can claim Fable without passing native Claude
CLI `--model claude-fable-5`.

Confirm this bootstrap changes only model selection/audit identity and does not activate M2A/M2B,
alter lifecycle semantics, fix registry concurrency, invoke Fable, or authorize M3/R1–R4. Return
`PASS`, `REQUEST_REVISION`, or `FAIL` with exact findings and commit/use readiness. Write
`.agents/plans/agent-ops-traceability-r0m/antigravity-fable-routing-bootstrap-acceptance.md`, then
complete this inbox item. Do not edit candidate files, stage, commit, dispatch Claude, invoke
inference, terminate processes, or alter live state.
