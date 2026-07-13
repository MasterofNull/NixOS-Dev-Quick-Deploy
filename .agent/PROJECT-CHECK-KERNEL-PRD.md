# PRD — Check Kernel (CK): World-Class Lint + Agentic Verification SSOT

**Status**: DRAFT / PREPARED_ONLY — for multi-agent review (round `check-kernel`, foldable into
`unified-program`); explicit owner activation required before implementation.
**Owner lane**: claude-fable-5 (analysis/orchestration). **Date**: 2026-07-13.
**Origin**: owner request (research linters + agentic workflow; source video: IndyDevDan,
"FORGET Loop Engineering. Agentic Engineering is about THIS") + Antigravity ARE plan (received
2026-07-13, reviewed in §6).
**Program binding**: Track V (VF-1 oracles / VF-2 tiers / VF-3 verifier / VF-6 ratchet) +
Foundation B1 contracts; realizes ref-arch §15 delivery-gate mechanics. Registered in
`UNIFIED-PROGRAM-PLAN.md` §4.

---

## 1. Thesis (research-grounded)

The industry conclusion of the "loop engineering → agentic engineering" shift is exactly our VF
thesis: agents converge when the loop hands their output to **deterministic verifiers** —
compilers, linters, type checkers, tests — with exit codes as the gate, never LLM
self-evaluation. Beyond gating, linters are **steering**: custom rules encode architecture
constraints directly where agents operate, turning review nits into machine-enforced rails
(Factory.ai pattern). Harness-engineering guidance layers this as preventive controls (blocked
before commit) + corrective controls (structured findings fed back into the loop).

For this to work here, checks must be **one kernel, not eighty scripts**: one contract, one
registry, one runner, many surfaces (pre-commit, CI, agent loop, Phase-0, dashboard). Today we
have world-class *coverage* and near-zero *unification*.

## 2. Current-state inventory (measured 2026-07-13)

| Surface | Count / state | Problem |
|---|---|---|
| `scripts/governance/` scripts | **80** | overlapping ad-hoc checkers; discovery via grep; no shared contract |
| `tier0-validation-gate.sh` gates | **19** inline bash functions (9 language syntax + structure/header/env/contract/SSOT gates) | monolith; syntax-only depth (no lint/format/type); adding a gate = editing the monolith |
| `config/validation-check-registry.json` | **99 checks**, has schema (id/trigger_paths/command) + `run-focused-ci-checks.sh` runner | the proto-SSOT — but only path-triggered CI checks; tier0 gates, QA phases, and lint tools live outside it |
| `harness_qa` phases + `_aq-qa-bash` | dual Python/Bash registration | known bug pattern (0.10.x ID collisions, C0.3 amendment churn); registration is manual ×2 |
| `.pre-commit-config.yaml` | wraps tier0 + hygiene hooks | fine as a shell; logic belongs below it |
| Lint/format tools | ruff, shellcheck, statix, deadnix, alejandra, mypy **installed but NOT wired into any gate**; treefmt/shfmt/biome absent | Antigravity's availability claim verified ✅ |
| JS/dashboard (`assets/*.js`, vanilla) | **zero linting** | AQ-OS D10 adjacent; untouched by ARE plan |
| VF oracles (PREPARED_ONLY) | per-task acceptance commands | must be CheckSpecs, not a parallel format |

Verdict: the SSOT seed exists (`validation-check-registry.json`). The consolidation is promoting
it to the kernel and demoting everything else to entries or profiles of it.

## 3. Target design — one Check Kernel

### 3.1 CheckSpec contract (extends the existing registry schema; L1A-style versioned schema)

```yaml
id: python-ruff-lint            # unique, kebab-case
class: lint                     # syntax|format|lint|type|structure|contract|security|eval|oracle
tier: T0                        # VF-2 risk tier of the FAILURE (what it blocks)
trigger: {paths: ["**/*.py"], mode: changed}   # changed|staged|all|event
command: ["ruff", "check", "--output-format=json", "{files}"]
fix_command: ["ruff", "check", "--fix-only", "{files}"]   # nullable; idempotent+safe fixes only
enforce: warn                   # warn → enforce, per-check ratchet with dated target
budget: {timeout_s: 30, max_rss_mb: 256}
owner: <lane/team>              # every check has an owner (no orphan rules)
surfaces: [pre-commit, ci, agent-loop, phase0, dashboard]
output: {format: json, findings_schema: ck.finding.v1}
```

### 3.2 One runner, many surfaces

`aq check [--profile pre-commit|ci|agent-loop|full] [--scope staged|changed|all] [--fix] [--json]`

- **tier0 gate** becomes a thin wrapper: `aq check --profile pre-commit --scope staged`. The 19
  inline gates migrate to registry entries (batched; the monolith shrinks to bootstrap + summary).
- **Phase-0 registrations are GENERATED** from the registry for both `phase0.py` and
  `_aq-qa-bash` — the dual-registration bug class (promoted pattern) is eliminated by
  construction, not discipline.
- **Agent loop**: after every edit burst, the implementer lane runs
  `aq check --profile agent-loop --scope changed --fix --json`; structured findings (file, line,
  rule, message, fix-applied?) feed the retry loop (Rule 6 budget). Exit code is the oracle.
- **VF-3 verifier** re-executes the *same command* for acceptance — report ≠ record holds because
  agent and verifier share one kernel and compare finding hashes, not prose.
- **Dashboard**: kernel emits one JSON result artifact per run (projection surface); scorecard
  renders per-class pass rates and the enforce/warn ratchet position. Blank `--` = bug.
- Execution semantics: changed-file scoping, content-hash result caching, parallel within budget,
  deterministic ordering, `aq-evidence` (VF-7) wrapping for hash-bearing runs.

### 3.3 Tool layer (all Nix-declared, Rule 13 — versions identical for every lane)

| Language | Format | Lint/analysis | Notes |
|---|---|---|---|
| Python | `ruff format` | `ruff check` (+ `mypy` later, separate ratchet) | ruff replaces flake8/isort/black class |
| Nix | `alejandra` | `statix`, `deadnix` | flake devShell pins versions |
| Shell | `shfmt` (add) | `shellcheck` | wrapper-policy rules stay custom checks |
| JS (dashboard) | `biome format` (add) | `biome lint` | single static binary, closes the zero-lint gap |
| Docs/JSON/YAML/TOML | existing syntax gates → registry entries | doc-frontmatter/link checks → registry | already scripted, just re-homed |
| **Repo-custom** | — | 80-script corpus triaged → registry entries with owners, or archived | the real consolidation |

**treefmt (treefmt-nix)** becomes the single format entrypoint under the kernel (`aq check
--class format` delegates to it); `nix flake check` gains format/lint parity so CI and local
agree by construction.

### 3.4 Agentic workflow — lint as steering, not just gating

1. **Custom rules encode the harness's HARD constraints** as machine checks: no hardcoded
   ports/URLs (options.nix SSOT), no raw `grep/ls/cat/find` in scripts, `enable_thinking:false`
   in llama payloads, payload-SSOT imports, no secrets in tracked Nix, PULSE/RESUME write bans
   (projection discipline). Several exist as bespoke scripts today — they become owned,
   tiered CheckSpecs that *steer agents in-loop* instead of failing them at commit.
2. **Distillation ratchet (VF-6) feeds the kernel**: a review finding or incident recurring ≥3×
   auto-files "promote to check" intake items. The promoted-bug-patterns file becomes a source of
   rule candidates, each with an owner and a test.
3. **Ratchet policy** (the world-class part most rollouts miss): every new check starts
   `enforce: warn` with a measured baseline; enforcement flips per-directory once that scope is
   clean ("clean-list ratchet"), with a dated target. No big-bang red wall; the trajectory is
   monotonic and dashboard-visible.
4. **Fix-first loop**: agents always run `--fix` before reporting; only unfixable findings consume
   model attention. Fixers must be idempotent and tool-native (`ruff format`, `ruff check
   --fix-only` safe rules, `alejandra`, `biome format`); no LLM auto-fixes inside the kernel.

## 4. What this consolidates (nothing lost)

tier0 19 gates → registry entries · 99 registry checks → unchanged (schema extended) · 80
governance scripts → triaged {registry entry | library behind an entry | archived per Rule 12} ·
harness_qa Phase-0 lint/gate checks → generated from registry · `.pre-commit-config.yaml` → thin
shell (kept) · VF oracles → CheckSpecs with `class: oracle` · future eval gates (Product E) →
`class: eval` entries. One contract, one place to look, one way to add a check.

## 5. Rollout phases

| Phase | Content | Gate |
|---|---|---|
| **CK-0** | Ratification round + **baseline measurement**: run all §3.3 tools repo-wide in report mode; publish violation counts per tool per directory (no blocking) | round consensus |
| **CK-1** | Antigravity ARE plan, amended (§6): ruff/shellcheck/statix/deadnix/alejandra wired as registry-driven kernel entries with `--fix`, `enforce: warn`, staged-scope; JSON to dashboard | T1; owner activation |
| **CK-2** | Registry unification: CheckSpec schema v1; tier0 gates migrate; Phase-0 dual registration generated; `aq check` runner | T2 (governance surface, subject-bound) |
| **CK-3** | treefmt-nix + shfmt + biome added declaratively (flake devShell); format ratchet begins per-directory | T1 |
| **CK-4** | Agent-loop wiring: `agent-loop` profile in delegation payloads + aq-loop; VF-3 verifier consumes kernel; steering rules wave 1 (HARD constraints); ratchet dashboard | T1 |

Enforcement flips (warn→enforce) are separate, dated, per-check decisions — never bundled with
tool introduction.

## 6. Review of the Antigravity ARE plan (first lane contribution — recorded)

**Verdict: APPROVE-WITH-AMENDMENTS → becomes CK-1.** Verified: all five claimed tools are
installed; staged-scope `--fix`; JSON gate status for dashboard — all sound and consistent with
this PRD.

Amendments (blocking):

1. **No new inline gates in the monolith.** ARE adds `gate_python_lint`/`gate_bash_lint`/
   `gate_nix_lint` as more bash functions — that deepens the 19-gate/80-script sprawl this PRD
   exists to end. Implement as registry entries executed through the kernel path (CK-2 may land a
   minimal runner first or CK-1 uses the focused-CI runner interim).
2. **No day-one strict blocking.** "Failing formatting checks will now block commits" across the
   repo without a baseline would halt all lanes on thousands of legacy violations. Baseline first
   (CK-0), warn-mode, staged-files-only enforcement, then per-directory ratchet.
3. **JS gap**: dashboard assets get biome (CK-3); ARE covers only Python/Bash/Nix.
4. **mypy is a separate ratchet** (type debt ≠ style debt; different burn-down).
5. **Lane eligibility**: Antigravity is currently implementation-INELIGIBLE (owner policy);
   ARE is design input — implementation routes to codex/opus with a sealed oracle.
6. **tier0 is a governance surface**: CK-1/CK-2 edits require T2 authorization with subject
   binding; evidence via `aq-evidence` (VF-7) once available.

## 7. Acceptance criteria (program-level)

- One schema validates every check; `aq check --list` enumerates 100% of live checks with owner,
  tier, class, enforce state; zero checks defined outside the registry (CI-verified).
- Phase-0 lint/gate registrations generated — dual-registration bug class structurally impossible.
- Pre-commit p95 wall time ≤ current tier0 baseline + 20% at CK-1, and ≤ baseline by CK-4
  (caching + changed-scope); budgets measured per C0.3-style protocol.
- Agent-loop profile returns structured findings; implementer first-pass lint yield measured per
  lane (feeds VF-5 outcome ledger).
- Violation counts trend monotonically down on the dashboard; every enforce-flip has a dated
  decision record.
- All tools Nix-declared same cycle as adoption (Rule 13); no `nix run`/ad-hoc installs.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Pre-commit latency creep | changed-scope default, content-hash cache, budgets in CheckSpec, p95 gate in §7 |
| Format churn colliding with in-flight lanes (Codex L2B) | staged-scope only; no repo-wide format until CK-3 ratchet; freeze window coordination via RESUME |
| Rule fatigue / warn blindness | warn budget per profile; warn→enforce ratchet with dates; every rule has an owner or is deleted |
| `--fix` vs anti-gaming | fixers are deterministic tool-native only; verifier re-runs post-fix; no LLM-authored auto-fixes in kernel |
| 80-script triage stalls | batched local-lane audit slices (measured envelope: single-file classification passes) |
| Registry becomes a god-file | schema versioned (L1A pattern); entries owned; split by class if >300 entries |

## 9. Review protocol

Lanes review this PRD + the ARE plan together: score §3 design 1–10, contest amendments in §6,
claim CK phases per eligibility, and answer: (a) interim runner for CK-1 — focused-CI runner or
minimal `aq check` first? (b) ratchet unit — directory or module? (c) biome vs eslint for the
dashboard. Consensus ≥3/4 → owner activation per phase. Antigravity's ARE submission is recorded
as the first review artifact.

## 10. Sources

- IndyDevDan — "FORGET Loop Engineering. Agentic Engineering is about THIS" (owner-supplied video)
- Factory.ai — Using Linters to Direct Agents: https://factory.ai/news/using-linters-to-direct-agents
- Augment Code — Harness Engineering for AI Coding Agents: https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents
- numtide/treefmt-nix: https://github.com/numtide/treefmt-nix · flake.parts module: https://flake.parts/options/treefmt-nix.html
- git-hooks-nix (flake.parts): https://flake.parts/options/git-hooks-nix.html
- NixOS Asia — treefmt-nix auto-formatting: https://nixos.asia/en/treefmt
- Simon Shine — lefthook + treefmt + Nix: https://simonshine.dk/articles/lefthook-treefmt-direnv-nix/
- Addy Osmani — Self-Improving Coding Agents: https://addyosmani.com/blog/self-improving-agents/
- Loop-engineering field guides (verifier-exit-code pattern): https://bdtechtalks.com/2026/06/22/ai-loop-engineering/ · https://tosea.ai/blog/loop-engineering-ai-agents-complete-guide-2026
