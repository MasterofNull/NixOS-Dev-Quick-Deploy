# claude — PRD-Consensus sign-off

## 1. VERDICT
**APPROVE-WITH-CHANGES** — the design is sound and matches the ratified consensus; a few
interface/threshold specifics must be pinned before implementation so Phase 0 is buildable.

## 2. Required changes (before implementation)
- **C1 — Keystone interface contract (Phase 0).** The PRD names the `zero_trust` flag but not
  its wire contract. Specify: WHERE it is set (switchboard, on request ingest, from
  `secret_findings`), HOW it propagates (a request field / header the tool-filter AND the router
  both read), and its default (absent = false = normal). Both consumers must read ONE field.
- **C2 — Slice-3 acceptance threshold.** R3.5 gates GBNF rollout on "a measured invalid-rate
  drop" — give a provisional numeric bar (e.g. invalid-arg rate <2% under GBNF, repair-loop
  count 0 on the golden suite) so 3.1 has a pass/fail target, not a vibe.
- **C3 — Network capability mechanism.** R2.1 says net-off-by-default; specify how a legit
  network-needing task REQUESTS net — an explicit `--allow-net` capability gated by the
  action-policy (like the privileged-mode gate), audited. Otherwise research tasks silently break.

## 3. Risks the PRD missed
- **Nix-store path churn in bwrap binds.** The sandbox binds `/nix/store` paths that change hash
  every rebuild. Bind the store ROOT (`/nix/store` ro), never pinned hashed subpaths — else the
  sandbox breaks on the next switch. (Mirrors the AppArmor `/nix/store/**` glob rule.)
- **Grammar-generation failure fallback.** If `json_schema_to_grammar` fails on a complex/nested
  schema, the request must DEGRADE gracefully to non-grammar decode (log + proceed), never block
  the tool call. Add this as an explicit R3.1 requirement.
- **zero_trust false-negative.** If a secret enters mid-conversation (not the initial prompt),
  the flag must be re-evaluated per request, not latched once at task start.

## 4. PASS-2 angle
- **Slice 2 (ops/failure-recovery):** bwrap startup is cheap (~50-200ms) — not a concern.
  Debuggability: capture bwrap stderr + the sandboxed process's stderr into the task output log
  so failures inside the namespace are visible in `aq-tui-dashboard --focus`. Escape-hatch:
  `--allow-net` (C3) is the revocation-safe path; no persistent net grants.
- **Slice 3 (tokenomics):** a single repair loop = one FULL extra prefill+gen on the APU
  (~30-550s cold at 1-4 tok/s) — so GBNF's ~5-15% per-token constraint overhead is trivially
  worth it; the ROI is dominated by eliminated round-trips, not per-token cost. Swap only when a
  planning session exceeds ~N turns (measure N in 3.1). Remote is worth it only for >8k-context
  synthesis AND not `zero_trust` — otherwise keep it on the resident stack.
