# QPPR-C1C publication acknowledgement implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1c-20260719`  
**Idempotency key:** `qa-provider-probe-reliability:c1c:publication-ack:20260719`  
**Required implementer:** `codex-subagent-qppr-c1c-implementer`  
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**  
**Single use:** consumed by the first complete exact two-file candidate report after activation

## 1. Exact subjects and inventory

| Subject | SHA-256 |
|---|---|
| C1C design packet | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` |
| decision-basis A1-AM2 review | `6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14` |
| accepted process owner predecessor | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| lifecycle-test predecessor | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| frozen observer test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

The implementation ceiling is exactly the two MODIFY paths named in the design section 2. Any
mismatch, third path, or substitution is a hard stop.

## 2. Exact grant after activation

Only `codex-subagent-qppr-c1c-implementer` may add the opt-in, mutually exclusive synchronous
publication acknowledgement interface and its deterministic lifecycle tests exactly as frozen in
the design sections 3 and 4. Existing publication and observer callers remain semantically
unchanged. No A1 candidate edit is included in this prerequisite.

The implementer may not delegate, stage, commit, deploy, or self-accept. Tests are offline local
fixtures only. No provider resolution/execution, network, heartbeat/evidence, Phase 0, API/browser,
A1/A2, service, Nix, deployment, traffic, rollback, or deletion is authorized.

Canonical session, skill, intent, resume, pulse, handoff, and task-registry records are traceability
control-plane evidence outside the two product paths. They must not contain product code or be
staged/committed with C1C and cannot be used to expand scope.

## 3. Review, activation, and completion

An independent flagship architecture/security/SRE/QA reviewer must issue final `PASS` over this
exact design and authorization. The owner must then activate this exact authorization SHA-256,
repeat required implementer `codex-subagent-qppr-c1c-implementer`, and provide a window no longer
than 24 hours. Any other identity or changed byte requires new review and activation.

The final report must include both candidate hashes, exact deterministic focused-test results,
unchanged observer-test hash, syntax/security evidence, reasoning/tradeoffs, and exclusions. A
different exact-hash reviewer must accept the candidate. Only the orchestrator may then run the
proportionate governance gate, stage, and commit.

C1C acceptance/commit does not activate A1. It only permits preparation of the final exact A1-AM3
post-prerequisite rebind. A2 remains blocked.

`RECORD: PREPARED_ONLY. C1C implementation and every adoption/live action remain unauthorized.`
