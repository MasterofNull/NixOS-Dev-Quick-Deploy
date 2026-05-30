
### [Implementer]

*   **Q1 (Overhead):** Acknowledged. The role string will be conditionally added to the prompt context, guarded by `if task.role and modality != EMBEDDED`.
*   **Q2 (Assignment):** Acknowledged. The `Task` model in `ai-stack/agents/types.py` will be updated with `role: Optional[str] = None`. The coordinator will populate this from the `ExecutionModality`'s `eligible_roles`.
*   **Q3 (Orthogonality):** Acknowledged. `AgentType` in `ai-stack/agents/types.py` will be renamed to `ExecutionModality`.
*   **Q4 (Embedding):** Acknowledged. The prompt construction logic will explicitly skip adding the role for the `EMBEDDED` modality.

**Top 3 Concerns:**

1.  **Prompt Contamination:** The exact format for injecting the role needs to be standardized. A simple `"role": "implementer"` JSON-like string in the system prompt seems least likely to confuse the model, but needs testing across different base models.
2.  **Configuration Drift:** We're touching four distinct areas: task definition, prompt construction, coordinator logic, and configuration. A partial deployment will lead to inconsistent behavior. The changes must be deployed atomically.
3.  **Handoff Protocol:** The `AUTONOMOUS-AGENT-HANDOFF-PROMPT.md` must be updated to include the `role` field. The parsing logic in the receiving agent needs to be robust to its absence during the transition period.

**Missed Gap:** The current design assumes the coordinator *assigns* a role. What if a task *requires* a specific role for a security-sensitive operation? We need a way for a task to declare `required_role: str` which the coordinator must satisfy, failing the task if it can't.

### [Security Reviewer]

*   **Q1 (Overhead):** Acceptable, as long as the role is treated as metadata and not a command.
*   **Q2 (Assignment):** This is the weakest link. The coordinator becomes a trusted authority for role assignment. Its logic must be heavily scrutinized.
*   **Q3 (Orthogonality):** This is a good separation of concerns. `ExecutionModality` defines *what* an agent can do, `role` defines *with what authority*.
*   **Q4 (Embedding):** Correct. This prevents vector space poisoning.

**Top 3 Concerns:**

1.  **Role Spoofing via Prompt Injection:** A malicious user could include `"role": "admin"` in their prompt. The system prompt must be carefully constructed to delineate user input from system-injected metadata. The LLM must be instructed to ignore role declarations from the user prompt.
2.  **Privilege Escalation:** If a low-privilege `ExecutionModality` (e.g., a 'chat' agent) can be assigned a high-privilege `role` (e.g., 'systems_integrator'), it might be able to access tools or data it shouldn't. The mapping of `ExecutionModality` to `eligible_roles` must be strictly defined and enforced.
3.  **Denial of Service:** An attacker could craft tasks that trigger complex or ambiguous role assignments, causing the coordinator to enter lengthy decision loops or fail open, granting default (and potentially elevated) privileges.

**Missed Gap:** There is no audit trail. We need to log every time a role is assigned to a task, what the task was, and which agent performed it. This is critical for forensics after a security incident. `inference_telemetry` is the place for this.

### [Performance Engineer]

*   **Q1 (Overhead):** 25-40 tokens is a non-trivial cost, especially for smaller models or faster interactions. This overhead is per-turn, so it accumulates. We must validate this on the target hardware.
*   **Q2 (Assignment):** The coordinator's role assignment logic adds latency. This lookup (Modality -> eligible_roles) must be a fast, in-memory operation. Reading from YAML on every request is not an option.
*   **Q3 (Orthogonality):** The rename to `ExecutionModality` is just a string change; no performance impact.
*   **Q4 (Embedding):** Crucial. Adding tokens to embedding requests would increase compute/IO for zero value.

**Top 3 Concerns:**

1.  **KV Cache Invalidation:** Injecting a dynamic role string into the system prompt can reduce the effectiveness of the KV cache, as the prompt prefix is no longer static. For a small, fixed set of roles this might be manageable, but it's a concern.
2.  **Coordinator Bottleneck:** The added logic for role assignment increases the processing time for every single task dispatched by the coordinator. We need to benchmark this to ensure it doesn't become a central bottleneck.
3.  **Token Budget Management:** The extra 25-40 tokens per turn eats into the context window available for the actual task. For high-throughput or long-running tasks, this could lead to premature context truncation.

**Missed Gap:** The `switchboard-profiles.yaml` defines configurations for different models and scenarios. The performance impact of role injection might vary significantly across these profiles. The overhead needs to be measured for at least a 'fast' (e.g., Haiku) and a 'smart' (e.g., Opus) profile.

### [Systems Integrator]

*   **Q1 (Overhead):** The overhead is a necessary cost for the feature.
*   **Q2 (Assignment):** This is the core of the integration. The coordinator needs a new `RoleManager` component that loads the `ExecutionModality` -> `eligible_roles` mapping at startup.
*   **Q3 (Orthogonality):** This clarification is vital for clean system design and prevents future confusion between an agent's technical capability and its operational authority.
*   **Q4 (Embedding):** Correct. This keeps the embedding service clean and single-purpose.

**Top 3 Concerns:**

1.  **Circular Dependencies:** The coordinator dispatches tasks to agents, but now it needs to know about agent modalities to assign roles. We must ensure this doesn't create a circular dependency between the dispatcher and the modality definition.
2.  **Configuration Loading:** The `switchboard-profiles.yaml` and the new `ExecutionModality` role mappings need to be loaded and validated at startup. A failure to load or parse these files should prevent the system from starting.
3.  **Dynamic Updates:** How do we update role assignments? If we change `config/switchboard-profiles.yaml`, does the coordinator need a restart? We should aim for a hot-reload mechanism.

**Missed Gap:** Error handling. What happens if a task has a `role` that is not in the `eligible_roles` for its `ExecutionModality`? The system must reject the task with a clear error message, not fail silently or assign a default role. This is a contract violation.

### [QA Engineer]

*   **Q1 (Overhead):** The overhead itself is not a bug, but its presence or absence must be verifiable.
*   **Q2 (Assignment):** The assignment logic is the primary target for testing.
*   **Q3 (Orthogonality):** The rename helps clarity, making tests easier to write and understand (e.g., `test_modality_X_can_be_assigned_role_Y`).
*   **Q4 (Embedding):** A key negative test case: `test_embedding_request_never_contains_role`.

**Top 3 Concerns:**

1.  **End-to-End Validation:** We need a test that creates a task, sends it to the coordinator, verifies the correct role is assigned and injected into the LLM prompt, and checks that the agent's output reflects awareness of that role.
2.  **Negative Test Cases:** We need to test for failure modes: a role that is not eligible, a malformed role string in the config, a task that tries to specify a forbidden role.
3.  **Role-Based Tool Access:** The ultimate test of success is whether role assignment correctly controls access to tools. We need a test with a protected tool that only an agent with a specific role can access.

**Missed Gap:** How do we mock the LLM's "awareness" of a role? We can't rely on the actual model output being deterministic. We should add a debug endpoint or a special "echo" tool that the test agent can call, which returns the role it was given. This provides a deterministic way to verify the role was injected correctly.

### [DX Engineer]

*   **Q1 (Overhead):** The overhead is acceptable if it enables a powerful feature. The key is making it invisible to the developer unless they need it.
*   **Q2 (Assignment):** The mapping in a YAML file is a good start. It's declarative and easy for developers to understand.
*   **Q3 (Orthogonality):** Excellent change. `ExecutionModality` is much clearer than `AgentType` and avoids the "is it a type of agent or a role?" ambiguity.
*   **Q4 (Embedding):** Makes sense. Developers shouldn't have to worry about this.

**Top 3 Concerns:**

1.  **Discoverability:** How does a new developer on the team know which roles are available and which modalities can use them? The `role-matrix.md` is good, but this information should also be available via a CLI command or a dedicated, easily findable schema file.
2.  **Ergonomics of Definition:** Editing the central YAML file to add a new role or change a mapping could become a bottleneck. We should consider a more modular approach, perhaps allowing new agent definitions to declare their own supported roles.
3.  **Debugging:** When a task fails due to a role mismatch, the error message needs to be extremely clear. It should state "Task rejected: ExecutionModality 'CHAT' is not eligible for role 'security_reviewer'. Eligible roles are: ['observer']".

**Missed Gap:** There's no "dry run" or validation tool. A developer should be able to run a command like `nix run .#validate-roles` that checks the consistency of all role definitions, mappings, and usages in the configuration files without having to start the whole system.

---

### [PRD Draft]

**Title:** Agent Role Standardization and Enforcement

**Problem Statement:** The current AI harness lacks a formal concept of operational roles, making it difficult to enforce granular permissions, audit actions, or manage the authority of different agentic capabilities. All agents effectively run with the same default level of privilege, posing a security risk and limiting functional specialization.

**Goals:**

*   Introduce a `role` field on the `Task` object to represent the specific authority under which a task is executed.
*   Implement a system where the coordinator assigns a role to a task based on the agent's `ExecutionModality` and a centrally-defined policy.
*   Ensure the assigned role is securely injected into the agent's prompt context and can be used to control access to tools and resources.

**Non-Goals:**

*   Implement a full user-level authentication and authorization system. This PRD is focused on inter-agent and system-level roles.
*   Create a graphical user interface for managing roles. This will be a configuration-as-code system.

**Implementation Plan:**

*   **P1**: `{"priority": "P1", "title": "Update Task Definition", "file": "ai-stack/agents/types.py", "change": "Rename AgentType enum to ExecutionModality. Add 'role: Optional[str] = None' to the Task model. Add 'required_role: Optional[str] = None'.", "validation": "Unit tests for the updated Task model.", "owner": "gemini"}`
*   **P1**: `{"priority": "P1", "title": "Create Role Eligibility Configuration", "file": "config/role-eligibility.yaml", "change": "Create a new config file mapping ExecutionModality to a list of eligible roles (e.g., 'CHAT: [observer, researcher]').", "validation": "Schema validation for the new config file.", "owner": "gemini"}`
*   **P1**: `{"priority": "P1", "title": "Implement Role Assignment in Coordinator", "file": "ai-stack/local-orchestrator/orchestrator.py", "change": "In the task dispatch logic, load role-eligibility.yaml at startup. When a task is received, check its required_role or assign a default eligible role based on its ExecutionModality. Reject task if no valid role can be assigned.", "validation": "Unit tests for the coordinator's role assignment logic, including negative cases.", "owner": "claude"}`
*   **P2**: `{"priority": "P2", "title": "Inject Role into LLM Prompt", "file": "ai-stack/mcp-servers/shared/llm_config.py", "change": "Modify build_llama_payload() to conditionally add the assigned role to the system prompt if 'task.role' is set and modality is not EMBEDDED.", "validation": "Unit test to verify the prompt is correctly modified when a role is present.", "owner": "qwen"}`
*   **P2**: `{"priority": "P2", "title": "Add Role to Handoff Protocol", "file": ".agents/AUTONOMOUS-AGENT-HANDOFF-PROMPT.md", "change": "Add an optional 'role' field to the handoff markdown structure.", "validation": "Manual inspection of handoff files generated by role-aware agents.", "owner": "claude"}`
*   **P2**: `{"priority": "P2", "title": "Add Role to Audit Log", "file": "ai-stack/mcp-servers/shared/inference_telemetry.py", "change": "Add the assigned 'role' to the structured log entry for every task execution.", "validation": "Integration test that runs a task and verifies the telemetry output contains the correct role.", "owner": "gemini"}`
*   **P3**: `{"priority": "P3", "title": "Create Role Validation Tool", "file": "scripts/validate_roles.py", "change": "Create a new CLI script that loads all role-related configuration and checks for inconsistencies.", "validation": "Run the script against valid and invalid configurations.", "owner": "gemini"}`
*   **P3**: `{"priority": "P3", "title": "Implement Role-Gated Tool Access (Example)", "file": "tests/role_gated_tool_test.py", "change": "Create a test-only tool and an integration test that demonstrates an agent with the correct role can access it, while an agent with the wrong role cannot.", "validation": "The test passes.", "owner": "qwen"}`

---

### [Open Questions]

1.  What should the default behavior be if a `required_role` is specified on a task, but the assigned `ExecutionModality` is not eligible for that role? Should it fail, or should it try to find a different `ExecutionModality` that *is* eligible?
2.  How will the initial set of roles and eligibility mappings be determined? Is the `docs/architecture/role-matrix.md` the source of truth, or does it need to be updated?
3.  For the DX Engineer's concern about a modular approach to role definition: should we pursue this now, or defer it to a future iteration? A central file is simpler for V1 but could become a bottleneck.
4.  Should the role be an enum for type safety, or is a string sufficient? An enum would be safer but requires more coordination to update.
