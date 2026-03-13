# Skill Dependency Lock

Last Updated: 2026-02-16
Owner: Phase 27 governance track

Purpose: keep external skill documentation references deterministic. Skills must consume URLs from this file and must not embed floating branch links (for example `main` or `master`).

## MCP Builder External Docs

- `MCP_PYTHON_SDK_README_URL`  
  `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/<PINNED_COMMIT_SHA>/README.md`

- `MCP_TYPESCRIPT_SDK_README_URL`  
  `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/<PINNED_COMMIT_SHA>/README.md`

## AQD CLI Converter Lock

- `AQD_CLI_CONVERTER_IMPL`
  `repo-native-wrapper`
- `AQD_CLI_CONVERTER_ENTRYPOINT`
  `scripts/ai/aqd`
- `AQD_CLI_CONVERTER_VERSION`
  `0.2.0`
- `AQD_CLI_CONVERTER_SCOPE`
  `skill validate/init/package + mcp scaffold/validate/test/evaluate/logs/deploy-aidb`

## Shared Skill Source Lock

- `AGENTSKILL_LEARN_REPO`
  `https://github.com/agentskill-sh/learn`

- `AGENTSKILL_LEARN_COMMIT`
  `4f415d34e1c1be9b31bd6498d73948a16676fbc9`

- `AGENTSKILL_LEARN_SKILL_URL`
  `https://raw.githubusercontent.com/agentskill-sh/learn/4f415d34e1c1be9b31bd6498d73948a16676fbc9/SKILL.md`

## Update Procedure

1. Resolve and validate the target SDK revision.
2. Replace `<PINNED_COMMIT_SHA>` with the exact commit SHA.
3. If converter behavior changes, bump `AQD_CLI_CONVERTER_VERSION`.
4. Run:
   - `./scripts/governance/lint-skill-external-deps.sh`
   - `./scripts/testing/validate-skill-references.sh`
   - `./scripts/ai/aqd --version`
5. Commit lock updates with the skill-doc changes in the same PR.
