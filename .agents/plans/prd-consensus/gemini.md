# gemini — PRD-Consensus sign-off

## 1. VERDICT
**APPROVE-WITH-CHANGES** — The requirements are highly aligned with multi-agent consensus, but we require specific GBNF fallbacks and explicit task-level capability lease rules before implementation begins.

## 2. Required changes (before implementation)
- **C1 — Schema Compilation Failure Fallback (Slice 3)**: If `json_schema_to_grammar` fails due to unsupported JSON schema constructs (such as highly nested anyOf/oneOf or recursive references), the request must fall back gracefully to unconstrained decoding instead of crashing the tool-call chain.
- **C2 — Task-Level Capability Leases (Slice 2)**: Sandbox network confinement should be complete by default. If a sub-agent execution requires temporary network access (e.g., for external RAG queries or package search), it must present a time-bound cryptographic token signed by the coordinator. We reject any global "network-enabled profile" to prevent data exfiltration.
- **C3 — Keystone API Definition (Phase 0)**: Declare `zero_trust: bool = false` in the base Switchboard request model. The switchboard must enforce this constraint by stripping mutating/privileged tools from the schema list passed to model decoders.

## 3. Risks the PRD missed
- **Renoir APU VRAM Swap Thrashing**: While per-request model swaps are out-of-scope, running both 8B and 35B models concurrently under local llama.cpp can lead to high memory paging/thrashing since the APU is capped at 4GB shared VRAM. We must implement a strict pool manager that unloads inactive models from memory before initializing new sessions if memory headrooms are exceeded.
- **Dynamic Re-Evaluation of zero_trust**: If secrets or API keys are written to the workspace mid-conversation by a sub-agent, the `zero_trust` flag must be re-evaluated on the next turn, rather than remaining set at initial task-start values.
- **Path Escapes via Double-Slashes/Dot-Dots**: Inside the Bubblewrap configuration, sanitizing workspace binds is critical. Paths must be canonicalized using absolute pathname resolution before they are bound, explicitly rejecting `..` traversal.

## 4. PASS-2 angle
- **Slice 2 (ops/failure-recovery)**: 
  - Startup Overhead: Bubblewrap namespace creation overhead is negligible (<5ms), but filesystem resolution under `--bind` flags can add latency on rotative drives or slow filesystem mounts. We recommend pre-caching static `/nix/store` mapping structures.
  - Diagnostics: Standard error from bwrap execution failures must be categorized (e.g. `policy_denied`, `out_of_memory`, `timeout`) and streamed directly to `a2a-audit.log` for debugging and dashboard inclusion.
- **Slice 3 (tokenomics/measurement)**:
  - GBNF Constraints Savings: Compile tool schema list into a single hash to cache GBNF grammars. Verify GBNF saves ~1.5s per invalid tool call on the 35B model.
  - Swap latency: Clamp systemd swaps if concurrent tasks are queued within a 20-second active window to protect slot lockups.
