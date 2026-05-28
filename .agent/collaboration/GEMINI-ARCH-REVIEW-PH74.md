# Gemini Architect Review — Phase 74 Dispatch Refactor
**Date**: 2026-05-28  **Agent**: Gemini 2.5 Pro  **Role**: architect

## Verdict
APPROVE WITH AMENDMENTS

## Risk Assessment

| Phase | Risk level | Specific risk | Mitigation |
|-------|-----------|---------------|------------|
| A | Low | The extracted slot polling logic has subtle timing or state dependencies not immediately obvious from the code. | Implement unit tests for the scheduler class that mock the `/slots` API endpoint and verify correct handling of `is_processing` states and exit conditions. |
| B | Medium | Data corruption during migration from multiple JSON/MD files to a single registry. Race conditions from concurrent processes accessing the new registry file. | Implement file-locking (e.g., `fcntl`) within the `TaskRegistry` class. Create a dedicated, idempotent migration script to safely transfer data from the old files to the new structure, with validation checks. |
| C | Medium | Incorrect mapping of switchboard profiles to the `TaskConfig` dataclass, or mishandling of defaults when a profile is missing or incomplete. | Use a validation library like Pydantic for the `TaskConfig` and the loaded YAML structure. Write unit tests that load a sample `switchboard-profiles.yaml` and verify the correct creation of `TaskConfig` objects for each mode, including overrides. |
| D | Medium-High | Behavioral drift between the new Python runners and the original bash implementations. The unified `build_llama_payload` function may miss edge cases handled by the legacy inline logic. | Create a suite of integration tests that execute the old `delegate-to-local` script for `direct`, `hybrid`, and `agent` modes, capturing the final JSON payload sent to `llama.cpp`. The new `dispatch.py` must then be tested to assert it generates identical payloads for the same inputs. |
| F | Medium | Incorrect argument or environment variable propagation from the new bash shim to the Python entry point, breaking the contract with upstream callers. | Repurpose the integration tests from Phase D to run end-to-end, starting from the `delegate-to-local` bash script. This ensures the entire chain from shell to Python is correct. |

## Answers to Open Questions

**Q1 (TaskConfig auto vs explicit):**
`TaskConfig` should automatically load the default token budget and settings from `config/switchboard-profiles.yaml` based on the selected `mode`. However, it MUST also support explicit CLI flags (e.g., `--tokens`, `--timeout`) that override these defaults. This provides both convention and control.

**Q2 (Mode auto-selection — coordinator vs client):**
This should be a client-side decision, implemented within `dispatch.py`. The client has the immediate context of the user's prompt and local system constraints, allowing for a faster and more responsive decision without an extra network hop to the coordinator. The coordinator's job is orchestration, not intent detection on behalf of the client.

**Q3 (task_registry.py vs pending-update subprocess):**
`task_registry.py` MUST replace the `pending-update` script and its associated inline Python heredocs entirely. The goal is consolidation; calling out to a legacy script as a subprocess would create a leaky abstraction and fail to eliminate technical debt. The new class must handle all file I/O directly, using file locks to ensure atomicity.

**Q4 (run_ralph scope):**
`run_ralph` is IN SCOPE. The project's primary goal is to consolidate the dispatch mechanism. Leaving one mode (`ralph`) in the legacy 674-line bash script while refactoring the others would undermine the entire effort and lead to further fragmentation. Its logic must be migrated into `dispatch.py`.

**Q5 (HybridRunner deprecation):**
DO NOT deprecate `HybridRunner`. It serves a valid architectural purpose, allowing a client to leverage the coordinator's advanced capabilities (e.g., context augmentation) for a specific query without entering a full, multi-step agentic workflow. The implementation should be refactored into `dispatch.py`, but the capability must remain.

## Amendments Required Before Implementation

1.  **Scope Expansion:** The PRD must be updated to explicitly include the migration of `run_ralph` logic into the new `dispatch.py` framework.
2.  **Safety Mandate:** The implementation plan for `task_registry.py` must specify the use of a file-locking mechanism to prevent race conditions.
3.  **Testing Requirement:** The validation plan for Phase D must mandate the creation of payload-comparison integration tests to ensure zero behavioral drift from the legacy scripts.

## Additional Risks Not in PRD

1.  **Environment Discrepancy:** The legacy bash script may rely on subtle shell-specific behaviors or environment variables that are not explicitly documented. The new Python environment must be carefully configured to ensure perfect parity.
2.  **Performance Overhead:** Python startup time, while minimal, is greater than bash. For scenarios involving extremely rapid, repeated invocations, this could introduce a minor performance regression. A simple benchmark should be run comparing the old and new scripts' end-to-end execution time for a simple `direct` mode query.
3.  **Dependency Management:** The new Python library introduces dependencies that must be managed. The `flake.nix` file will need to be updated to include any new Python packages to ensure the development environment remains reproducible.

## Recommended Phase Order
The proposed order of **A → B → C → D → F** is correct and should be followed. It logically builds the new system from foundational components (scheduling, persistence, config) up to the core logic and final integration, minimizing risk at each step.
