# Phase 1: Fix SystemD Environment Quoting Issue

## Objective
Fix SystemD warnings regarding invalid environment assignments in `ai-hybrid-coordinator.service`.

## Scope
- `nix/modules/services/mcp-servers.nix`

## Step Plan
1. **Update `nix/modules/services/mcp-servers.nix`**:
   - Change `AI_SEMANTIC_CACHE_WARM_QUERIES` assignment to quote the entire string.
   - Change `AI_WEB_RESEARCH_USER_AGENT` assignment to quote the entire string.
   - Change `AI_BROWSER_RESEARCH_USER_AGENT` assignment to quote the entire string.
   - Update `singleLineEnv` call for `AI_LOCAL_SYSTEM_PROMPT_IDENTITY` to ensure the entire assignment is quoted if it contains spaces.

2. **Validation**:
   - Run `nix-instantiate --parse` or similar to check Nix syntax (if possible).
   - Use `aq-qa 0` to check harness health (if available).
   - In a real environment, we would run `nixos-rebuild dry-activate` or check the generated service file.

## Acceptance Criteria
- SystemD no longer logs "Invalid environment assignment" warnings for these variables.
- Environment variables are correctly set in the service.
