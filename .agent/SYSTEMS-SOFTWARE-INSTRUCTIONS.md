# Systems-Software Domain — Agent Instruction Payload

**Domain tag:** `systems-software`
**State:** proposed (2026-05-18)
**Upstream authority:** `.agent/PROJECT-SYSTEMS-SOFTWARE-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `systems-software` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

This instruction surface applies whenever an agent operates in the `systems-software` domain — i.e., performing:

- NixOS module authoring, review, or refactoring (`nix/modules/**`, `flake.nix`)
- Shell script development (`scripts/**`, `*.sh`)
- Nix static analysis (statix, deadnix, alejandra)
- Systemd service configuration within NixOS modules
- Hardware capability assessment and Nix option derivation
- Deployment tooling invocation (`nixos-quick-deploy.sh`, `aq-qa`, `aq-report`)
- Nix-related knowledge retrieval from AIDB (`nix-systems-patterns` namespace)

Agents outside this domain MUST NOT modify `nix/modules/core/options.nix` (port SSOT) or `nix/modules/profiles/ai-dev.nix` (feature flags) without escalating to the orchestrator.

---

## Eligible Task Classes

Reference: `docs/architecture/local-agent-task-eligibility.md`

| Task class | Eligible agents | Notes |
|---|---|---|
| Nix lint (statix/deadnix/alejandra on ≤4 files) | Qwen (Tier A) | Bounded; deterministic |
| Shell lint (bash -n on ≤4 scripts) | Qwen (Tier A) | Always allowed |
| NixOS module option addition (≤400 lines) | Qwen (Tier B) | Review-gated; validate with nix-instantiate |
| Nix option rename / structural refactor | Qwen (Tier B) | Review-gated; must check all `config.*` refs |
| `nixos-rebuild switch` decisions | Claude only | High-impact system operation; confirm with user |
| Feature flag additions to ai-dev.nix | Claude/Gemini | Architectural; Gemini review gate required |
| Hardware capability matrix changes | Claude/Gemini | Policy; Gemini review gate required |
| Deployment cadence decisions | Claude (orchestrator) | Batch deploy policy: 3–5 slices before rebuild |

Qwen MUST NOT:
- Invoke `nixos-rebuild switch` or `nixos-quick-deploy.sh`
- Modify `nix/modules/core/options.nix` without orchestrator instruction
- Add `mkForce` to shared modules (use `mkDefault`; let host override)
- Run `nix build` / `nix eval` against unchecked expressions (may trigger network fetches)

---

## Tool Preferences

### Preferred tools (ordered)

1. `scripts/governance/nix-static-analysis.sh --non-blocking` — primary: statix + deadnix + alejandra
2. `nix-instantiate --parse <file>` — fast parse check without eval; always available
3. `bash -n <script>` — always available; mandatory before any shell script commit
4. `shellcheck <script>` — preferred over bash -n when available (provision in systems-software.1)
5. `scripts/governance/discover-system-facts.sh` — refresh hardware/facts baseline
6. `agrep "<pattern>" nix/` — search Nix sources before editing
7. `als nix/modules/` — list module structure before authoring
8. `acat <file>` — bounded read of Nix source before editing
9. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

### Search order (Nix codebase)

```
agrep "<option-name>" nix/       # find option/config references first
als nix/modules/                  # discover module structure
acat nix/modules/core/options.nix # read port SSOT before any port usage
```

Never hardcode a port or URL encountered in code — always trace to `nix/modules/core/options.nix`.

### Forbidden

- `nixos-rebuild switch` from Claude Code shell (sudo setuid missing)
- `bare pip install` in Nix context
- Hardcoded ports, URLs, secrets in Nix or shell source
- `--no-verify` on any git commit
- `mkForce` in shared modules without explicit orchestrator approval
- Running `nix build` on expressions that import from network without user confirmation

---

## AIDB Namespace Binding

**Namespace:** `nix-systems-patterns`

- **Read:** Before authoring a new Nix module option, query the namespace for prior patterns: `POST /query` with `{"query": "<pattern description>", "mode": "local"}` and namespace filter.
- **Write:** After resolving a Nix challenge or establishing a new pattern, store it via MemoryBroker: `POST /api/memory/facts` with metadata `{"namespace": "nix-systems-patterns", "domain": "systems-software"}`.
- **Dedup:** MemoryBroker returns `{"status":"skipped"}` when content already indexed — treat as success.
- **Seeding:** `nix/modules/` directory will be indexed into this namespace in `systems-software.3`. Until then, use `agrep` for Nix pattern lookup.

---

## Architecture Constraints (non-negotiable)

These are inherited from `docs/architecture/canonical-kernel-declaration.md` and project policy:

1. **Port SSOT** — `nix/modules/core/options.nix`; never hardcode port values in Nix or Python
2. **NixOS-first** — all service config via Nix modules; `nixos-rebuild switch` required for code deployment
3. **Feature flags** — `nix/modules/profiles/ai-dev.nix` (`mkDefault true`); host overrides via `mkForce` in host-specific config only
4. **`deploy-options.local.nix` is gitignored** — secrets/overrides only; policy = git-tracked
5. **Batch deploy cadence** — 3–5 repo-only slices before `nixos-quick-deploy.sh`; deploy early only for runtime activation blockers

---

## Review Requirements

Per `docs/architecture/gemini-review-gate.md`:

| Work category | Gate required |
|---|---|
| New Nix module options (non-trivial schema change) | Gemini review gate |
| Feature flag additions to `ai-dev.nix` | Gemini review gate |
| `nixos-quick-deploy.sh` procedure changes | Gemini review gate |
| Hardware capability matrix policy changes | Gemini review gate |
| Shell script lint pass (bash -n clean, no behavioral change) | No gate required |
| Nix formatter/style-only changes (alejandra) | No gate required |

---

## Routing Preference Summary

| Query type | Profile | Notes |
|---|---|---|
| Nix eval / lint / static analysis | `local-tool-calling` | Tools are local |
| Module authoring query | `default` | Qwen can draft; local sufficient |
| Architecture / policy review | `remote-reasoning` | NixOS module system is complex |
| Deployment coordination | `local-tool-calling` | nixos-quick-deploy.sh + aq-qa are local |

Use the `route` field in `/query` requests to enforce profile selection (explicit `route` wins over intent classification).

---

## Activation Checklist (for orchestrator)

Before marking the domain `implemented`:

- [ ] `shellcheck` provisioned in `nix/modules/profiles/ai-dev.nix`
- [ ] `systems-software` intent class added to `config/intent-routing-map.json`
- [ ] `nix-systems-patterns` AIDB namespace seeded with ≥20 Nix patterns from `nix/modules/`
- [ ] `scripts/automation/aidb-reindex.sh` includes `nix-systems-patterns` indexing step
- [ ] `systems-software-health` check updated to test statix/shellcheck invocation

Before marking the domain `validated`:

- [ ] Gemini review-gate PASS on one NixOS module change routed through domain
- [ ] `aq-qa systems-software-health` exits 0 in CI
- [ ] No P0/P1 regressions in `aq-qa 0`
