# Multi-Agent Round — Slice 2 (Zero-Trust Sub-Agent Sandboxing) + Slice 3 (GBNF Grammar Gate + Model Multiplexing)

Orchestrator: claude-opus-4-8, 2026-07-06. Protocol: `.agent/WORKFLOW-CANON.md` Step 3
Extension (flat collaborative design). Engage ALL agents: **codex, claude, local[Qwen],
gemini/antigravity**. Methodology (per user SSOT): in each PASS, EVERY agent plays the SAME
expert-team baseline; run MULTIPLE passes for angle diversity; model diversity comes from
the agents, not from assigning different roles. Aggregate via `aq-collaborate`.

## Round structure
- PASS 1 (this dispatch): the baseline below, each agent independently, no cross-visibility.
- Consolidation → consensus sign-off → PASS 2 (a second baseline/angle) → plan drafts.

---

## SLICE 2 — Zero-Trust Sub-Agent Execution Sandboxing
**PASS-1 expert-team baseline (every agent plays all three):**
security-architect · NixOS-systems-engineer · red-teamer.

**Grounded current state (build on, do not re-derive):**
- Delegation-boundary gates already exist: A2A action-policy (`config/agent-action-policy.json`
  + `scripts/ai/lib/agent_action_policy.py`), outbound secret scan (`a2a_guard`), dispatch
  budget, shared `a2a-audit.log`. These gate the BOUNDARY (which mode launches), not RUNTIME.
- **`bwrap` (bubblewrap) is available** on the host. AppArmor is used pervasively
  (`nix/modules/core/base.nix`, `roles/ai-stack.nix`).
- RULE 14: `ReadWritePaths` + `ProtectHome` is a bind-mount, NOT a DAC bypass — kernel checks
  inode uid/gid/mode against the service UID. RULE 13: NixOS declarative-only.
- Gap: once a sub-agent runs in `edit`/`yolo`, it executes arbitrary scripts against the host
  FS; no per-sub-agent runtime confinement; no zero-trust tool-catalog lock when a task
  touches secrets.

**Research questions (answer in the PASS-1 brief):**
1. bubblewrap vs AppArmor (vs both, layered) for the sub-agent executor under NixOS — declarative,
   scoped to the workspace + read-only Nix store, revocable. Which enforces zero-trust with least
   friction on the single-APU host?
2. How to bind the tool-catalog lock to the secret-scan finding (a credential-bearing task must
   lose privileged tools like `reload-model`/`proposals/apply`) — at the switchboard, the
   coordinator, or the runtime?
3. DAC-correct declaration (RULE 13/14): where do the profiles live, what owns the workspace, how
   is it reset on every activation?
4. Threat model + red-team: what does a compromised/misaligned sub-agent try, and does the design
   stop it (path escape, secret exfil, privileged-tool reach, resource exhaustion)?
5. Reuse: can this sandbox double as the Slice-4 eval sandbox?

## SLICE 3 — Local Inference Reliability: GBNF Grammar Gate + Model Multiplexing
**PASS-1 expert-team baseline (every agent plays all three):**
inference-systems-engineer · LLM-runtime-specialist · performance-engineer.

**Grounded current state:**
- Switchboard does NOT wire GBNF/`json_schema`/`response_format` grammar today; it forwards tool
  schemas (`switchboard.py:1010`) but the model can still emit invalid JSON.
- Invalid tool-JSON is silently dropped at `agent_executor.py:1743` (`JSONDecodeError → continue`)
  → repair loops that burn the single APU slot. Reported ~15% invalid-arg rate.
- llama.cpp on Renoir APU: single slot (parallel=1), n_gpu_layers ≤ 12, ~1-4 tok/s. Models
  available: Qwen3 4B / 8B / 35B-A3B / 35B-MTP (`roles/ai-stack.nix:541-585`) → model-stacking
  has real targets.

**Research questions:**
1. GBNF wiring: per-request vs per-profile grammar at the switchboard boundary; generate a JSON
   grammar from each tool's schema; llama.cpp `grammar` param mechanics + latency cost. Does it
   eliminate the repair loop?
2. Model multiplexing: a systemd-bound swapper watching the switchboard queue — swap weights in
   the llama.cpp slot when active targets shift. Swap latency vs slot-lock on the APU; when is a
   swap worth it vs routing to a smaller resident model?
3. Model-stacking routing: which task classes route to 4B/8B (trivial/validation) vs 35B
   (planning) vs remote — and how does this interact with the Slice-2 zero-trust lock on remote?
4. Measurement: golden tool-call suite to quantify the invalid-JSON rate before/after GBNF; tok/s
   and slot-lock budgets.

---

## Dispatch plan (PASS 1)
- **local[Qwen]**: `delegate-to-local --mode agent` — grounded research pass, both slices.
- **codex**: `delegate-to-codex` — same baseline, both slices.
- **antigravity/gemini**: `delegate-to-antigravity` — same baseline, both slices.
- **claude**: own PASS-1 brief (orchestrator also contributes as a full expert team).
- Respect dispatch budget (20/agent/5min) + active collaborators (codex/gemini currently live).
- Outputs land in `.agents/delegation/outputs/`; aggregate via `aq-collaborate`.

## Consensus + next
Consolidate the 4 PASS-1 briefs → identify agreement/conflict → consensus sign-off → decide
PASS-2 baseline (likely performance/tokenomics for Slice 3, operational/failure-recovery for
Slice 2) → plan drafts → plan consensus. Then PRD + phased plan per slice.

---
## PASS-1 dispatch status (2026-07-06)
- **local[Qwen]**: `local-20260706-191450-47g9qb` — RUNNING (direct reasoning).
- **codex**: `codex-20260706-191450-kffs57` — RUNNING.
- **claude**: PASS-1 brief below (orchestrator as a full expert team).
- **gemini/antigravity**: remote lane BLOCKED — switchboard `remote-free` returns HTTP 400
  "Please pass a valid API key" (missing/invalid remote key; not 429/402 so local fallback did
  not trigger). [ISSUE] remote-llm-api-key-invalid — the OpenRouter/Google key at
  `/run/secrets/remote_llm_api_key` is missing or stale; switchboard needs a valid key + restart.
  Engaging gemini via the FILE/GIT A2A path instead: this brief on disk is its drop-point.
  Aggregate gemini's contribution when its agent picks it up.

## claude PASS-1 brief

### SLICE 2 (security-architect · NixOS-systems-engineer · red-teamer)
1. **Layered, bubblewrap primary.** AppArmor (already pervasive) stays as the outer service-MAC,
   but it is profile-per-binary and brittle for a sub-agent running arbitrary scripts. `bwrap`
   gives a per-invocation namespace sandbox — recommend wrapping the `edit`/`yolo` executor:
   `--unshare-all --die-with-parent`, workspace bind rw, `/nix/store` ro, tmpfs elsewhere,
   **network off by default**. Declarative via a Nix `writeShellScript` bwrap wrapper baked into
   the privileged delegate paths.
2. **Bind at the switchboard + enforce at runtime (defense-in-depth).** When `a2a_guard` flags a
   secret, set a per-task `zero_trust` flag; the switchboard strips privileged tools
   (reload-model, proposals/apply, model-swap) from that request's catalog; agent_executor refuses
   them if flagged; coordinator audits. A credential-bearing task also never routes remote (ties Slice 3 Q3).
3. New `nix/modules/services/sub-agent-sandbox.nix`; workspace owned by primaryUser; bwrap runs as
   the invoking user (no setuid) so DAC holds; `system.activationScripts` (deps=["users"]) reasserts
   workspace 0700/owner every activation (RULE-14 pattern). The sandbox is ephemeral per-invocation.
4. **Red-team**: path escape → namespace + no host bind blocks it; secret exfil → outbound scan +
   net-off + audit; privileged-tool reach → the catalog lock; resource exhaustion → systemd scope
   MemoryMax/CPUQuota/TasksMax + dispatch budget. Residual: research tasks needing network → gate
   network as a policy-approved capability, not default-on.
5. **Yes — reuse as the Slice-4 eval sandbox.** Same ephemeral bwrap+resource-scoped runtime;
   parameterize (eval = net-off + golden-task mount). Build once.

### SLICE 3 (inference-systems-engineer · LLM-runtime-specialist · performance-engineer)
1. **Per-request GBNF generated from each tool's JSON schema, at the switchboard**, applied when a
   request carries tools + targets a local profile. llama.cpp ships `json_schema_to_grammar`;
   grammar-constrained decode coerces valid tool JSON at the source, eliminating the ~15% repair
   loop. Constrained sampling adds minor per-token cost but SAVES a whole repair prefill+gen on the
   single slot → net APU win. Cache compiled grammars per tool-set.
2. **Resident small model, not per-request swap.** Reloading the 35B on a 4GB/12-layer APU costs
   tens of seconds of slot-lock — too slow to swap per task. Keep a 4B/8B resident for
   trivial/validation/tool-call work; load 35B only for planning sessions; reserve the swapper for
   coarse session-level mode changes. MEASURE swap latency before any swap-per-task design.
3. **Routing**: trivial/format/tool-arg → 4B/8B (resident, GBNF); planning/multi-step → 35B;
   high-value planning → remote ONLY when the remote lane works AND the Slice-2 zero-trust lock
   permits (secret-bearing → never remote). Extends the existing complexity→lane routing (Phase A).
4. **Measurement**: golden tool-call suite through the switchboard with/without GBNF — invalid-JSON
   rate, repair-loop count, tok/s, slot-lock time. Gate GBNF rollout on a measured invalid-rate
   drop. Wire as an aq-qa check + aq-inference-bench extension.

**Cross-slice dependency**: Slice-2's zero-trust remote lock and Slice-3's remote routing are the
same decision point — build the per-task `zero_trust` flag once, consumed by both.

## gemini PASS-1 brief

### SLICE 2 (security-architect · NixOS-systems-engineer · red-teamer)
1. **Dynamic Sandbox Isolation**: Layer Bubblewrap (`bwrap`) as the primary execution sandbox with AppArmor protecting the outer boundary. Enforce `--unshare-all --die-with-parent` with read-only `/nix/store` and `/etc` mounts, an isolated `/tmp`, and no network access. Bind ONLY the task-specific git repository workspace, never the user's home directory.
2. **Immutable Tool Catalog Lock**: When `a2a_guard` flags secret findings, the Switchboard must tag the task with `zero_trust = true`. Under this lock, the Switchboard must enforce a strict, reduced tool list—removing mutating or high-risk tools like `reload-model`, `proposals/apply`, shell execution, and remote model delegation.
3. **Declarative State & DAC Enforcement**: Add a new declarative module `nix/modules/services/sub-agent-sandbox.nix` that configures state roots and triggers a systemd service wrapper. Ensure `system.activationScripts` (with `deps = ["users"]`) maintains strict ownership boundaries (`0700` directories) to prevent POSIX DAC bypasses.

### SLICE 3 (inference-systems-engineer · LLM-runtime-specialist · performance-engineer)
1. **Per-Request GBNF Grammars**: Dynamically generate GBNF grammar at the Switchboard from the schema list of the active tool catalog. Since the active catalog matches dynamic permission scopes, pre-compiled global grammars are too coarse. GBNF constrained decoding must coerce valid `{name, arguments}` JSON tool calls, bypassing the expensive 15% local model repair loop.
2. **Grammar Cache**: Cache generated GBNF grammar strings using tool-set schema hashes. Caching compiled grammars removes redundant conversion overhead on the llama.cpp host.
3. **Resident Multiplexing & Adaptive Routing**: Swapping 35B models on a 4GB shared VRAM APU slot blocks the system. Run a resident small model (e.g., 8B) for trivial classification, grammar-based tool argument formatting, and JSON repair, reserving the 35B model and remote routing strictly for high-context planning.


---
## PASS-1 CONSOLIDATION + CONSENSUS (2026-07-06)
Contributions: **claude** ✅, **codex/gpt-5.5** ✅ (grounded, 82k tok), **local[Qwen]** ✗ (0-byte
output — silent direct-mode failure; retried), **gemini** ⏳ (file-A2A pending).

### Strong agreement (2/2 independent passes — high confidence)
**Slice 2:**
- **Layered, bwrap-primary + AppArmor/systemd envelope.** Both reached this independently. Codex
  anchored it: the harness ALREADY uses bwrap for the aider subprocess
  (`ai-stack/mcp-servers/aider-wrapper/server.py:476`) — reuse that shape (ro `/nix/store`, rw
  workspace, isolated `/tmp`, `--die-with-parent`). AppArmor stays the outer service MAC; do NOT
  try to express per-task workspaces in AppArmor (higher friction, less revocable).
- **Tool-catalog lock at the switchboard, bound to `secret_findings`; coordinator = signal,
  runtime = defense-in-depth.** Anchors: coordinator records findings at `agent_service.py:134`;
  switchboard owns tool schemas + virtual leases + allowed-tool filtering at `switchboard.py:1008`
  & `:1641`. On secret findings → mint a reduced IMMUTABLE tool set (drop reload-model,
  proposals/apply, shell-like, endpoint-mutation, remote-escalation); runtime rejects out-of-catalog.
- **DAC-correct (RULE 13/14):** per-agent state roots under `/var/lib`, owned by the executing
  user; `install -d -o <user> -m 0750` + activation reset; task-scoped repo bind, NOT whole home;
  do not lean on `ReadWritePaths` for permissions.
- **Red-team controls:** symlink/path-escape → canonical validation + reject cross-boundary
  symlinks; secret exfil → never bind `/run/secrets`/home/ssh + net-off by default; resource →
  systemd MemoryMax/TasksMax + `--die-with-parent` + dispatch budget.
- **Eval sandbox = strictest profile of the same runtime** (ro inputs, writable result dir only,
  no secrets/net/privileged tools). Build once.

**Slice 3:**
- **GBNF per-request at the switchboard, from the FINAL (post-filter/lease/secret-lock) tool
  schema set — not per-profile/global.** Both agreed. Coerces valid `{name, arguments}` at decode,
  killing the ~15% argument-JSON repair loop at the source.
- **Resident small model (4B/8B) + controlled 35B swaps, NOT constant swapping.** Swapping the
  35B on the single APU slot is only worth it for BATCHES of heavy planning. Reuse the existing
  active-model-symlink pattern (`ai-stack.nix:863`; catalog `:539`).
- **Model-stacking routing:** 4B = JSON repair/classification/schema-validate; 8B = bounded repo
  Q&A/routine tool steps; 35B(-MTP) = architecture/multi-file/high-risk; remote = large-context —
  but **secret-lock blocks/downgrades remote**.
- **Golden tool-call measurement suite gates rollout:** invalid-arg rate, repair count,
  time-to-valid-call, tok/s, slot occupancy, per-tier budgets; INCLUDE secret-bearing negative
  cases proving reload-model/proposals/apply are absent from the generated grammar.

### Complementary (codex added, claude missed)
- The existing aider bwrap + model-symlink patterns (concrete reuse targets).
- **GBNF fixes tool-argument JSON but NOT malformed SSE chunks** silently dropped at
  `agent_executor.py:1741` — that is a SEPARATE reliability fix, tracked distinctly.

### Conflicts
- None. The two independent passes are fully consistent → strong signal the direction is sound.

### CONSENSUS SIGN-OFF (PASS 1)
Direction ACCEPTED. **Keystone decision (cross-slice): build ONE per-task `zero_trust` flag,
derived from `secret_findings` at the switchboard, consumed by BOTH the Slice-2 tool-catalog lock
AND the Slice-3 remote-routing block.** This is the shared substrate — implement first.

### PASS-2 baseline (angle diversity)
- Slice 2: **operational / failure-recovery + performance** — sandbox startup cost on the APU,
  revocation, debuggability, escape-hatch for legit network tasks.
- Slice 3: **tokenomics / measurement** — quantify the repair-loop cost saved vs grammar overhead;
  swap-latency budget; when remote is worth it.
Re-engage local (via --mode agent or single-slice prompts) + gemini (file-A2A) in PASS 2. Then
PRD + phased plan per slice, starting with the shared `zero_trust` flag.
