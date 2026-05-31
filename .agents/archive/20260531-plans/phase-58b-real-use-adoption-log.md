# Phase 58B — Real-Use Adoption Log

**Date:** 2026-05-19  
**Owner:** Codex  
**Trigger:** User confirmed `nixos-rebuild switch` completed and asked to resume operations after memory/agent check-in.

## Coordination check-in

| Source | Result | Notes |
|---|---|---|
| `aq-prime` | PASS | Harness online; active plans include Phase 58B post-rebuild soak/default/evidence docs. |
| `aq-session-start` | PASS | Session context written to `.agents/scratchpad/session-context-20260518.md`. |
| `aq-memory search "Phase 58B promoted domains real-use adoption post rebuild"` | EMPTY | No matching memory facts; repo collaboration artifacts remain SSOT. |
| `.agent/collaboration/HANDOFF.md` | PASS | Latest handoff says Phase 58B + post-rebuild hardening complete; next step is real-use adoption. |
| `scripts/ai/delegate-to-gemini --list` | PASS/PARTIAL | Latest Gemini review task is `done` with PASS. Several older registry entries remain `running` despite stale/null PIDs; treat as registry hygiene, not active blockers. |
| `aq-collaborate list` | BLOCKED | Fails with local Postgres auth for user `postgres`; collaboration status was read from durable files/registry instead. |

## Post-rebuild harness health

| Check | Result | Evidence |
|---|---:|---|
| `aq-qa 0` | PASS | `67 passed · 0 failed · 0 skipped · 79s` |
| Hybrid coordinator | PASS | `GET http://127.0.0.1:8003/health` returned healthy with memory/tree/eval/capability flags enabled. |
| AIDB | PASS | `GET http://127.0.0.1:8002/health` returned `status=ok` with DB/Redis/pgvector/RAG OK. |
| Switchboard | PASS | `GET http://127.0.0.1:8085/health` returned `status=ok`, profiles loaded. |
| Local/Qwen shell alias source | PASS | `ai-stack/local-agents/builtin_tools/shell_tools.py` registers `run_shell_command` alias to `run_command`. |

## Lifecycle/default reconciliation

Current registry state is not the older “no defaults at all” posture. Commit `041dbaf6` intentionally promoted only `systems-software` to `default` after intent coverage was wired.

| Domain | Current lifecycle state | Default posture |
|---|---:|---|
| security-systems | promoted | Opt-in / explicit security intent routing |
| systems-software | default | Default for primary repo NixOS/Nix/shell/Python systems work |
| embedded-hardware | promoted | Opt-in / explicit embedded intent routing |
| mobile-web | promoted | Opt-in / explicit mobile-web intent routing; real Lighthouse remains enhancement |
| scientific-research | promoted | Opt-in / explicit scientific intent routing |
| gis-systems | promoted | Opt-in / explicit GIS intent routing |

## Real-use adoption checks

These checks used current repo/harness work where available. They are not a substitute for future product-level workloads, but they exercise the promoted/default domains against live post-rebuild state.

| Domain | Real-use task | Result | Notes |
|---|---|---:|---|
| security-systems | Local Semgrep rule over actual harness script `scripts/testing/mobile-web-masa-harness.py` for `subprocess(..., shell=True)` | PASS | No findings; shell fixture avoided external rule downloads. |
| systems-software | `statix check nix/modules/core/options.nix` + `shellcheck -S warning scripts/ai/aq-qa scripts/ai/delegate-to-gemini` | PASS after fix | First run found ShellCheck warnings in `aq-qa`; Codex patched low-risk lint issues and reran clean. |
| embedded-hardware | Validate actual `config/hardware-capability-matrix.json` plus Verilator/GHDL availability in `.#embedded` | PASS | Non-destructive; no JTAG/flash/write operations. |
| scientific-research | Deterministic lifecycle state summary from `config/capability-lifecycle-registry.json` in `.#scientific` | PASS | SHA-256 summary hash: `ca86b809cff03a7bff1f56881f5d64771c479cc444f4c6a64dbf03020cf650eb`. |
| gis-systems | CRS validation and EPSG:4326→EPSG:3857 transform of adoption GeoJSON fixture in `.#gis` | PASS | No repo GIS dataset exists yet; this remains controlled geospatial adoption evidence. |
| mobile-web | MASA harness scan of actual `dashboard/` source with fixture Lighthouse output | PASS/PARTIAL | `status=pass lighthouse=fixture masvs_findings=8 high=0`; real Lighthouse CLI still not required for promoted state. |

## Tool-friction hardening found during adoption

1. `scripts/ai/aq-qa` had ShellCheck warnings that made the systems-software adoption check fail under `-S warning`; patched.
2. `scripts/ai/delegate-to-gemini` help text still said default `auto_edit` even though implementation default is `yolo`; corrected.
3. `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` and `.qwen/SESSION-RULES.md` still documented Local/Qwen `run_shell_command` as blocked; corrected to document the alias.
4. `ai-stack/local-agents/builtin_tools/shell_tools.py` log message said three tools even after registering four; corrected.

## Follow-ups

1. Fix `aq-collaborate list` Postgres auth so collaboration status does not depend on reading files manually.
2. Add registry hygiene for stale `running` delegation entries with null/dead PIDs.
3. Keep only `systems-software` at default for now; do not default the remaining five domains without per-domain routing evidence.
4. Add real Lighthouse CLI support or explicitly preserve fixture mode as validation-only behavior for mobile-web.
