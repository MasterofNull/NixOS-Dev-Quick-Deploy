1. Repo spot-checks confirm:
   - Node appears in all four profile lists: `nix/data/profile-system-packages.nix:7,96,112,128`.
   - `scripts/upstream/track` is a Bash file; `track/REGISTER.json` would conflict.
   - `crates/contract-validator/src/main.rs:57–74` exposes the four reported checks, without a generic `contracts` check.
   - `check-owned-scope.sh:11–16` exits successfully when `OWNED_PATHS` is absent.
   - `config/model-coordinator.json:480` defaults reasoning to `claude-reasoning`, confirming the local-profile override requirement.
   - The authority YAML contains all three reported unresolved recovery owners.
   Corrections: census-refresh’s “D0 DONE” is wrong against frozen rev4: its six-role requirement includes Gemini binding acceptance, which the refresh reports revoked. `pi-agent.nix` contains `fakeHash`, but that proves placeholder hashes—not “never built.” Nixpkgs package availability alone also does not establish that local packaging is redundant.

2. **9 overlaps / 3 orphans is a provisional inventory, not a credible exhaustive measurement.** The census acknowledges four carried-forward rows without refreshed verification. Reading a shared registry does not itself create another decision owner; adding measurement output does not establish competing learning authority.
   Missing separate decisions include approval issuance/revocation/recovery, checkpoint and intent recovery, reservation/retry/reconciliation, contract-version compatibility, and upstream extraction/removal. Use one decision taxonomy and distinguish authoritative writes, admission decisions, readers and projections. Report **three documented recovery gaps; total unknown**.

3. **Sound conditionally.** Keep ownership, context membership and import permissions authoritative in `system-state-authorities.yaml`; contracts contain versioned interface definitions referenced from that registry.
   `CONFIG_SCHEMA_REGISTRY` must be a derived index or an explicitly separate schema lookup—not another hand-maintained ownership map. Require dangling-reference, duplicate-definition and incompatible-version failures. Schema validation, import restrictions and runtime ownership enforcement are complementary; none substitutes for the others.

4. **D-R5-1 — AGREE-WITH-CHANGES:** bind each waiver to the exact candidate and policy revision, scope, expiry and recorded assurance deficit.
   Preserve independently executable local checks. A waiver must not become an independent-review receipt or implicitly bypass protected-branch requirements.

   **D-R5-2 — DISAGREE:** retain C2 as written; provide a Node-free supported installation, with those CLIs outside its dependency closure.
   “Core only” changes the hard constraint and requires an explicit owner amendment. An exception list cannot establish C2 compliance; inspect build dependencies as well as runtime packages.

   **D-R5-3 — DISAGREE:** deliver the required Rust contract check and import-boundary CI enforcement in S1, retaining Python where useful.
   S9 is outside the frozen MVP, and delta.md additionally makes Rust conditional. The proposed sequence does not satisfy the brief without an explicit requirement deferral.

   **D-R5-4 — AGREE-WITH-CHANGES:** make aq-land-queue the sole queue implementation under the existing durable service, preserving **S2 → S1b** activation order.
   Reservation, fencing and authoritative reconciliation must precede automated landing activation. A restart-resumable local queue alone does not satisfy that contract.

   **D-R5-5 — AGREE-WITH-CHANGES:** use `scripts/upstream/REGISTER.json`, with its versioned schema under `contracts/`.
   Specify the authoritative source and projection direction relative to WORKAROUND-REGISTER. Cover patches outside Nix keywords and enforce owner-only extraction/submission decisions.

   **D-R5-6 — AGREE-WITH-CHANGES:** define explicit resource and usability budgets, then measure the complete lite installation on 16 GB.
   Include model, embedding/storage dependencies, closure size, shared GPU memory and offline provisioning. Removing identity services must preserve necessary authentication and authorization.

5. Rev5 still needs:
   - Reproducible offline journeys covering inference, review and governance, without hosted-model credentials or subscriptions.
   - Negative tests proving trusted CI rejects bypasses and candidate changes cannot weaken their own checker.
   - Complete contract coverage for HTTP, subprocess, event and dynamic calls—not merely Python imports and schema-file existence.
   - Evidence for C3 pinning and C5 compatibility across shipped dependencies; unresolved entries cannot count as PASS.
   - Exhaustive third-party patch discovery, enforceable extraction decisions/removal triggers, and a distinct developer-fleet versus student-install acceptance boundary.

Top risk I see: rev5 could declare compliance through scope exceptions and deferred enforcement while leaving the brief’s required local, Node-free, contract-guarded path unproven.
