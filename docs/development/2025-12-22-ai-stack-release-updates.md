# Improvement Proposal: AI Stack Release Updates
**Created:** 2025-12-22
**Status:** Proposed
**Owner:** Codex

---

## Summary
Evaluate updating AI stack components (Podman, Qdrant, llama.cpp, Open WebUI, MCP tools) to the latest releases to improve stability and features.

## Evidence
- Discovery report: `docs/development/IMPROVEMENT-DISCOVERY-REPORT-2025-12-22.md`
- Current stack health: `~/.local/share/nixos-system-dashboard/llm.json`

## Proposed Change
Review and potentially upgrade to the latest releases:
- Podman v5.7.1
- Qdrant v1.16.3
- llama.cpp b7510
- Open WebUI v0.6.43
- mcp-nixos v1.0.3
- openskills v1.3.0

Scope: container images and tool wrappers only. No NixOS base changes.

## Impact
- Performance: possible improvements from upstream fixes.
- Reliability: patch/security fixes in recent releases.
- Maintenance: align with community supported versions.
- Security: reduce exposure to known issues in older releases.

## Risks & Mitigations
- Risk: upstream breaking changes.
- Mitigation: upgrade one component at a time and validate with `scripts/ai-stack-health.sh`.

## Rollback Plan
- Revert container image tags or `docker-compose.yml` to previous versions.
- Restart stack and re-run health checks.

## Approval Required
User approval to change versions and rebuild containers.

## Sources & References
- https://github.com/containers/podman/releases/tag/v5.7.1
- https://github.com/qdrant/qdrant/releases/tag/v1.16.3
- https://github.com/ggml-org/llama.cpp/releases/tag/b7510
- https://github.com/open-webui/open-webui/releases/tag/v0.6.43
- https://github.com/utensils/mcp-nixos/releases/tag/v1.0.3
- https://github.com/numman-ali/openskills/releases/tag/v1.3.0

---

## Decision
**Approved by:**  
**Date:**  
**Notes:**  
