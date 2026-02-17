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
  `scripts/aqd`
- `AQD_CLI_CONVERTER_VERSION`
  `0.2.0`
- `AQD_CLI_CONVERTER_SCOPE`
  `skill validate/init/package + mcp scaffold/validate/test/evaluate/logs/deploy-aidb`

## Update Procedure

1. Resolve and validate the target SDK revision.
2. Replace `<PINNED_COMMIT_SHA>` with the exact commit SHA.
3. If converter behavior changes, bump `AQD_CLI_CONVERTER_VERSION`.
4. Run:
   - `./scripts/lint-skill-external-deps.sh`
   - `./scripts/validate-skill-references.sh`
   - `./scripts/aqd --version`
5. Commit lock updates with the skill-doc changes in the same PR.
