# Orchestrator/Coordinator Handoff — Claude (Opus 4.8) → Codex

Date: 2026-09-01 · Owner-directed: "handoff the coordinator role to our codex model teammate."
Outgoing coordinator: claude-opus-4.8 · Incoming: codex

You (Codex) are now the coordinator: open/close sessions, route roles, review, and commit final
integration. Per Rule 18 roles are agent-agnostic — route each role to the available+eligible+
independent+cheapest lane; keep the local (Qwen) lane always engaged.

## System state (post-reboot, verified healthy)
- The machine was shut down and rebooted; the AI stack **auto-started on boot** and is fully serving:
  llama :8080=200, embed :8081, aidb :8002, coordinator :8003, switchboard :8085, dashboard :8889 all 200.
- Model is resident (fresh boot). No sudo in the Claude shell — nixos-rebuild / systemctl restart need the
  owner's terminal (they run via `!` prefix). If llama drifts to swap under load, ask the owner to
  `sudo systemctl restart llama-cpp` (proven fix: reloads the ~24GB model resident on this 27GB box).
- git: on branch `plan/aqos-installer-experience` (HEAD 5a43c0f7); `main` = `origin/main` = 0898bfa5, synced.

## Two live threads

### 1. Dev cycle — local dogfooding (RUNNING)
- Fresh dogfood run active: **pid 19846** (log under the session scratchpad; `.agents/delegation/dogfood-ledger.jsonl`).
- Watch results via `scripts/ai/aq-coach-events` (surfaces the edit-verify coaching telemetry — merged this session).
- Local's ceiling is the verify/scaffold loop, not throughput; landed edits are non-destructive when scaffolded.
  The destructive-deletion guard + edit-verify coach are LIVE (guard never fired in prod yet = good).

### 2. AQ-OS Installer Experience refactor — golden path (PRD v1 done; ready for v2)
Owner direction (2026-08-31): ONE **golden path** — super-tuned pro dev + gaming + OPTIONAL local AI,
hardware-adaptive; local-only, AI never on the install critical path; modular `mySystem.*` engine
underneath for experts. Exemplar: omarchy. **Lighter/alternate model swap is OUT (owner-decided).**

Artifacts (all on THIS branch):
- `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-claude.md` (product/experience), `-codex.md` (your 488-line
  engineering draft: config-contract SSOT, 4-layer parity, 12 corrections), `-CONSOLIDATED.md`
  (v1, FROZEN sha256 `bfd870d7f4ae06ce193ec67c7b3847a24cc72e40ad9580c8d7c335993b1550ca`).
- `.agents/plans/aqos-installer-experience/tracker.json` — 6 phases P0–P5, 9 slices w/ deps + validation
  goals; PM projector shows all DESIGNED 10% (status projected from git, never hand-typed).
- `.agents/plans/aqos-installer-experience/antigravity-prd-review.md` — **Antigravity PASS (adopt with
  enhancements)**, hash-verified. Untrusted-advisory: verify its claims. Key adds to fold: (a) live-ISO
  driver-detection must use `lspci -nn`/`/sys/bus/pci` PCI-IDs, not active kernel modules; (b) a
  RAM/VRAM sizing table driving the AI recommended/limited/not-advised call; (c) more in the 107-line doc.

**Your first coordinator moves on this thread:**
1. Fold Antigravity's review (+ a bounded local module-catalog slice, tracker item `p0-module-catalog`,
   run it when the APU frees) into **PRD v2** (CONSOLIDATED). Re-freeze (new hash) after v2.
2. Then start **P0**: `aqos-install-plan-v1.schema.json` + the trusted resolver + the deterministic
   hardware detector (see codex draft §5 + antigravity's PCI-ID mitigation). Route implementation to the
   cheapest capable lane (Rule 17) — you designed the contract, so you may implement or route.
3. Merge the plan branch to `main` — my recommendation was HOLD until v2 so main gets one clean drop;
   your call.

## Workflow rules in force (owner-set this session)
- **Review-before-commit (agents up):** prepare → review → validate → commit; independent review GATES the
  commit on the UNCOMMITTED change. Agent-down fallback: commit-to-branch + queue review, never block.
- **Cheapest-eligible implementer (Rule 17):** don't self-implement bounded slices when a cheaper lane fits.
- **Plain-language summaries to the owner:** what was found, how fixed, why it matters; no jargon/hashes.
- **Trunk protection:** main needs the bound Review-Disposition envelope (sha256 of staged diff + non-author
  Reviewed-by); un-reviewed → branch.

## This session's merged work (context)
- Destructive-deletion guard (`8fb7f693`, 5-round review), coach-events observability CLI (`6705a454`),
  nightly training-loop service-context fix (`4fedde70`, validated live 11/12), dead-code cleanup
  (`a2465867`), session-start `--machine` JSON mode (`0898bfa5`). All on main.

## Catch-up (Rule 18)
On return, work committed while you were away is in `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` for your
confirmatory audit — advisory unless you find a real defect (then a bounded follow-up, never rewrite history).

— Thank you. The seat is clean: stack healthy, both threads live, all three PRD lanes contributed, v2 is
the clear next step.
