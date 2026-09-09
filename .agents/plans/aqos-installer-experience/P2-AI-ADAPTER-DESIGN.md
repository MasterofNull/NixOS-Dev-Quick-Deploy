# P2 — Local AI-assist (optional): untrusted proposal adapter

**Status:** design (analysis-tier); implementation routed per Rule 17 (orchestrator does not self-implement).
**Phase:** p2 (tracker `aqos-installer-experience`); item `p2-ai-adapter`. **Dep:** p1-parity-suite (MERGED, main `06526ce8`).
**PRD SSOT:** `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md` (frozen sha in tracker).

## The one hard invariant
**The AI proposes; it never authorizes, and its output is untrusted input.** A local model suggests a
*selection* (which golden profile / roles / AI-on) given a redacted hardware summary + the choice catalog.
That suggestion is treated exactly like adversarial input: it is constrained on the way out and validated
on the way in, then shown to the human as a semantic diff against the golden default, and only a human
approval turns it into the same resolved lock the manual/guided path produces — which still passes the
same inert execution-verifier (activation_blocked, executable:false). AI is off the install critical path
and is primarily a post-install feature. Fully offline: local llama.cpp only, no network, no account.

## Why this is safe by construction (grounding)
Two independent layers, either sufficient, both required (defense in depth):
1. **Constrained decoding (structural):** the local model is called with a JSON-schema/GBNF grammar
   constraint (llama.cpp `json_schema`), so the *only* token sequences it can emit conform to the proposal
   schema — a closed object of enum-constrained selection fields. Raw Nix, shell, prose, secrets, or a
   disk-authorization field are not expressible; the grammar has no production for them.
2. **Strict post-parse validation (semantic):** never trust the constraint alone (a mis-wired call, a
   different backend, or a future model could bypass it). The proposal is re-parsed with the SAME strict
   resolver primitives (`parse_json_strict`, `additionalProperties:false`), every value checked against the
   module catalog's real IDs, and any string field scanned for Nix/shell/secret/path shapes → fail closed.

The proposal schema carries NO free-text and NO authorization field. It is a strict subset of the existing
resolver `selection` shape, so it flows straight into the already-built `normalize_adapter("ai", ...)`
branch (reads `payload["proposal"]`) — the "one engine" property from P1 extends to AI for free, and the
parity suite's real-producer pattern applies here too.

## Flow
```
redacted hw summary (p0 detector)  ─┐
choice catalog (p0 module catalog) ─┼─► local llama.cpp (json_schema-constrained, offline)
                                    │        │ untrusted proposal JSON (selection-only)
                                    │        ▼
                                    │   STRICT VALIDATOR  ──reject──► clean error, fall back to golden default
                                    │        │ accepted selection
                                    ▼        ▼
                            normalize_adapter("ai", {proposal}) ─► resolve_plan ─► resolved lock
                                    │
                                    ▼
                        SEMANTIC DIFF vs golden default  ──► human approve (explicit) ──► (same P0 verifier path)
                                                              AI never auto-applies
```

## Slice decomposition (implementer-sized; route cheapest-eligible)
- **p2a — proposal schema + strict validator** *(bounded, pure, no model call — routable to local or cheap Claude)*
  - `config/schemas/aqos-ai-proposal-v1.schema.json`: closed object, `selection` = {golden_profile (enum from
    catalog profiles), roles (array of catalog role IDs), include_local_ai (bool)}, `additionalProperties:false`
    at every level; NO free-text, NO auth field, NO host_target authority.
  - `scripts/ai/lib/aqos_ai_proposal.py`: `validate_proposal(raw_bytes, module_catalog)` → clean selection or
    a fail-closed rejection {reason}; rejects unknown fields, non-catalog IDs, and any string matching
    Nix/shell/secret/path heuristics; reuses `parse_json_strict`.
  - test: rejects raw Nix, shell, secrets, disk-auth, unknown profile/role, extra fields; accepts a clean selection.
- **p2b — constrained offline proposal call** *(depends p2a)*
  - `scripts/ai/lib/aqos_ai_propose.py`: build the llama.cpp request with `json_schema` = p2a schema +
    `enable_thinking:false`, POST to the injected local endpoint (env var, never hardcoded), timeout-guarded,
    offline-only; parse → hand to `validate_proposal`. No network egress beyond the local model.
  - test: schema is attached to the request; a mocked model reply that tries to inject shell is rejected by
    the validator even if the (mock) constraint is bypassed.
- **p2c — semantic-diff approve surface** *(depends p2a, p2b)*
  - render the approved AI selection vs the golden default as a plain-language diff (beginner-facing control
    surface, not a hash dump); explicit human approval required; on approve → `normalize_adapter("ai", ...)`
    → `resolve_plan`; never auto-apply.
  - test: no-approval → nothing resolved; approval → same lock a manual request with that selection produces.
- **p2d — real-producer parity + integration** *(depends p2a-c)*
  - extend the parity suite's real-producer pattern: the REAL proposal→validate→normalize("ai") path yields a
    byte-identical lock to the manual adapter for the equivalent selection (no fixture standing in for the AI).
  - the tracker `validation_goal`: adapter rejects raw Nix/shell/secrets/disk-auth; approve-trusted-plan test.

## Constraints honored
NixOS declarative-only; ports/URLs from injected env (never hardcoded); `enable_thinking:false`; offline;
no secrets in schema/proposal/log; fail-closed on unknown evidence; AI never on the install critical path
and never authorizes. Every slice gets an independent non-author review before it merges to main (trunk
protection), and Codex plays catch-up confirmatory on return (Rule 18).
