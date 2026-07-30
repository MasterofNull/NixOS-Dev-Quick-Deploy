# Foundation C — C3b R3 Freeze & Owner Activation

> **ACTIVATED + CONSUMED 2026-07-29** — owner activation.grant event `c4aaf0117ec84f8e` (agent=owner, subject aqos-foundation-c-c3b-r3-execution-cell-runner). Drift check CLEAN (subject fc15d90b + all 7 predecessors incl switchboard.nix 4811326e + HEAD 582113af all unchanged). Single-use key `…:v1:20260729` CONSUMED — build in progress (Claude-fast). Do not re-emit; a rebuild needs a fresh freeze+activation.


**Enforcement-tier.** R3 (default-OFF execution cell runner + bwrap) is the first C3b stage that
constructs and runs a real confined process. Design is independently reviewed PASS
(`c3b-r3-review/antigravity.md`; `R3_DESIGN_REVIEWED_PASS`) and committed. This packet FREEZES the
subject and defines the single-use owner activation that authorizes the R3 **build** (flag
default-OFF). **Standing authorization does NOT activate R3.** Turning the runner ON later
(`enable=true` + flag) is a FURTHER, separate owner act (R6 canary).

## Frozen subject
- **Idempotency key:** `aqos-foundation-c:c3b:r3-execution-cell-runner:v1:20260729`
- **Subject (byte-identical to the reviewed+committed design):**
  - `C3B-R3-DESIGN-AND-AUTHORIZATION.md` SHA-256
    `fc15d90b7d368718324af820f3a334dbdb12d2dee81db2c05a6e779344f4a7b3`
- **Build-base HEAD:** `582113af00078d02bdd11e43882ad849c2d58b46` (verify `git rev-parse HEAD`
  matches, and the subject hash is unchanged, before implementing).
- **Predecessor hashes (must be unchanged at build time — drift check):**
  - `scripts/ai/lib/execution_grant.py` → `29e9c1d6d2fa5cc7…` (R1)
  - `scripts/ai/lib/execution_cell_clone.py` → `a706f1270dbfce37…` (R2)
  - `scripts/ai/lib/capability_lease.py` → `a6f923924071618b…`
  - `scripts/ai/lib/capability_lease_issuance.py` → `bf9229eac6ba4c21…`
  - `ai-stack/switchboard/capability_lease_gate.py` → `4dce80fa49d7e346…`
  - `config/first-party-tools.json` → `a17650f228b4ff17…`
  - **`nix/modules/services/switchboard.nix` → `4811326e891cab2e…` (BYTE-PARITY ANCHOR — the
    runner may NOT change switchboard hardening; this hash MUST be identical post-build).**
- **Reviews:** design `c3b-r3-review/antigravity.md` (PASS) + `c3b-r3-review/claude.md`
  (aggregation); Opus-verified; codex confirmatory queued (Aug-4 return).

## What activation authorizes (the R3 implementation ceiling)
ONLY the build described in the frozen design §3–§9, flag DEFAULT-OFF, deny-closed, no switchboard
adoption (R5), no network (C4), no live traffic:
- NEW `ai-stack/switchboard/execution_cell_runner.py` — the socket-activated runner: UDS server
  (SO_PEERCRED), request protocol (verify grant via R1 public-key-only → create cell via R2 →
  bwrap-confine the bounded command → cgroup-tracked supervise → kill+fence), bwrap argv derived
  only from the verified grant, no unsandboxed fallback.
- NEW the out-of-cell validator (its own module or a `--validate` subprocess; its own minimal
  confinement per Q-R3-2) — byte/mode/symlink tree compare vs trusted base, ignores cell git
  config/hooks/attributes, declared-signed-paths-only.
- NEW `nix/modules/services/execution-cell-runner.nix` + EDIT `nix/modules/services/default.nix`
  (import) — dedicated unprivileged user/group + client group; socket unit; service unit with
  `NoNewPrivileges=true`, `CapabilityBoundingSet=""`, `ProtectSystem=strict`, StateDirectory,
  `RestrictNamespaces=CLONE_NEWUSER CLONE_NEWNS` (runner ONLY), `Delegate=true`, `RuntimeDirectory`;
  `enable` default false.
- EDIT `config/env-contract.yaml` — declare `CAPABILITY_EXECUTION_CELLS` (default "0").
- NEW decision/receipt schema (`config/schemas/…`) + NEW `scripts/testing/test-execution-cell-runner.py`
  (hermetic offline runner tests per §9).
- **MUST NOT touch:** `nix/modules/services/switchboard.nix` (byte-parity), the C2 gate enforcement
  path, or any live-traffic wiring.
- **Implementer:** cheapest-eligible (Claude-fast, Rule-17 recorded — bwrap/UDS/cgroup systems code
  above local's envelope), routed at activation time; independent review before commit.
- **Window:** ≤24h from activation.

## Owner activation (single-use — the step only you can take)
Run this to authorize the R3 build. Broad/standing authorization does NOT substitute for it.
In this session you can run it with a leading `!`, or from your terminal:

```
scripts/ai/aq-event emit --agent owner --type activation.grant \
  --subject aqos-foundation-c-c3b-r3-execution-cell-runner \
  --payload '{"idempotency_key":"aqos-foundation-c:c3b:r3-execution-cell-runner:v1:20260729","subject_design_sha256":"fc15d90b7d368718324af820f3a334dbdb12d2dee81db2c05a6e779344f4a7b3","build_head":"582113af00078d02bdd11e43882ad849c2d58b46","predecessors":{"execution_grant":"29e9c1d6d2fa5cc7","execution_cell_clone":"a706f1270dbfce37","capability_lease":"a6f923924071618b","capability_lease_issuance":"bf9229eac6ba4c21","capability_lease_gate":"4dce80fa49d7e346","first_party_tools":"a17650f228b4ff17","switchboard_nix_byte_parity":"4811326e891cab2e"},"implementer":"claude-fast","window_hours":24,"note":"C3b R3 execution-cell-runner build, flag DEFAULT-OFF; switchboard.nix byte-parity enforced; turning the runner ON is a separate later act"}'
```

After you emit it, the orchestrator will: verify the subject hash + all predecessor hashes + HEAD
are unchanged (drift check), route the cheapest-eligible implementer to build EXACTLY the ceiling
above (flag default-OFF), independently review, confirm `switchboard.nix` is byte-identical
(`4811326e…`), run tier0, and commit. Enforcement stays OFF until a further owner act.

## If you do NOT want to activate now
Valid stop: R0–R3 designs + R1/R2 code are shipped and enforce nothing; R3 simply waits here,
frozen, at zero cost. Nothing degrades.
