# Collaborative Round — c3b-r5-review

Opened: 2026-07-30T15:11:15Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C slice C3b R5 (default-OFF switchboard
adapter + grant signing). Read-only. DESIGN review. This is ENFORCEMENT-TIER (build needs owner
activation + an R4 PASS). Highest bar. Substitute for codex (down to Aug-4; confirmatory on return).
VERIFY claims against real code — don't approve prose; don't fabricate.
READ: .agents/plans/aqos-foundation-c/C3B-R5-DESIGN-AND-AUTHORIZATION.md; R1 grant
(scripts/ai/lib/execution_grant.py — Ed25519, sign is TEST-ONLY currently), R3 runner
(ai-stack/switchboard/execution_cell_runner.py — public-key verify), the C2 gate
(ai-stack/switchboard/capability_lease_gate.py, _admit_tool_call in switchboard.py), the L2B golden
manifest (scripts/testing/fixtures/local-inference-l2b-payload-golden.json pins switchboard.py), the
SOPS/secrets pattern (grep secrets.nix / /run/secrets usage).
JUDGE (§8): 1. flag-OFF byte-parity — adapter fully inert, switchboard path unchanged. 2. R5 never
WIDENS C2 admission (consumes C2's verdict); deny-closed on ANY adapter/runner error. 3. GRANT
SIGNING: Ed25519 PRIVATE key from SOPS /run/secrets ONLY — NO key in any tracked file (Nix store is
public); key-unavailable → deny (NO unsigned/fallback grant); a DEV-signed grant is REJECTED by the
prod runner's public key. Is the key provisioning genuinely secret-safe and is R1's currently
TEST-ONLY sign() being promoted to a real signer handled correctly (who signs, with what key, where)?
4. the switchboard NEVER constructs a cell/bwrap/namespace itself — runner stays sole confiner;
switchboard hardening (RestrictNamespaces=true, 4811326e) unchanged except added credential access.
5. receipt projection low-cardinality + secret-free; AQ-QA Service-Coverage exercises the FULL
default-OFF path (not /health); dual-harness registration (phase0.py results.extend AND _aq-qa-bash).
6. L2B golden RE-PIN for switchboard.py in the SAME reviewed commit (drift discipline, as C2). 7. no
live traffic / no flag/enable flip / no cutover (R6); R4 PASS precondition. Weigh Q-R5-1 (distinct
adapter flag), Q-R5-2 (key rotation tied to revocation_epoch), Q-R5-3 (minimal cell-required vocab).
Any NEW fail-open, key leak, or C2-widening?
OUTPUT: `VERDICT: PASS`/`FAIL`/`REQUEST_REVISION` on line 1, then findings by severity with §ref +
concrete fix, + Q-R5-1..3 verdicts. No outcome authorizes build or activation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c3b-r5-review.md` and writes `antigravity.md`. No API keys.
