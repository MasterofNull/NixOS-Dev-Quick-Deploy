# Capability Intake PRD

## Objective
Add a security-gated intake workflow for high-value external plugins, skills, MCP servers, and CLI tools so agents can discover, review, and promote capabilities without directly installing untrusted code.

## Scope
- Maintain a curated candidate registry in `config/agent-capability-intake-candidates.json`.
- Provide a deterministic audit CLI at `scripts/ai/aq-capability-intake`.
- Reuse the existing `ToolSecurityAuditor` for tool-level metadata checks.
- Produce machine-readable reports for agent fan-out and reviewer gates.
- Seed first-wave candidates:
  - Playwright MCP / skill
  - Semgrep MCP
  - GitHub MCP read-only
  - OSV-Scanner
  - Trivy
  - Syft/Grype SBOM pair
  - MCP admission controller
  - Observability query skill
  - NixOS specialist tool pack
  - Code intelligence graph layer

## Non-Goals
- Do not enable new MCP servers by default.
- Do not add secrets, tokens, or external account configuration.
- Do not vendor third-party code into this repo during intake.
- Do not grant write-capable tools until an explicit promotion slice approves them.

## Admission Gates
Every candidate must pass these gates before activation:
1. Source provenance: official or well-maintained upstream, pinned revision/version available.
2. Install safety: no curl-pipe, unpinned latest, or unexplained shell execution in the activation path.
3. Tool allowlist: only declared tools are enabled; write/network/shell tools require explicit justification.
4. Supply-chain scan: SBOM/dependency scan result attached where applicable.
5. Runtime isolation: AppArmor/systemd sandbox or equivalent if the tool executes external code.
6. Observability: status/health/audit output visible to `aq-report` or dashboard before promotion.
7. Rollback: config disable path documented.

## First Slice Acceptance
- `scripts/ai/aq-capability-intake list` prints all candidates.
- `scripts/ai/aq-capability-intake audit --all --json` emits JSON with risk flags and tool audit summaries.
- Tests cover high-risk and low-risk candidates.
- Delegation task files exist for deeper review of the highest-value first wave.
