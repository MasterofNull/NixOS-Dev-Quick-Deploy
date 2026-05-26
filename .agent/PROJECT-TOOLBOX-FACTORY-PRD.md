# PRD: Toolbox Factory (Dynamic Capability Expansion)

**Status:** Draft
**Goal:** Enable agents to autonomously generate, test, and register new skills/tools to the agentic OS.

---

## 1. Vision
The AI harness becomes truly autonomous when it can build its own tools. The Toolbox Factory is the service responsible for bootstrapping new capability modules that bridge the gap between "detecting an issue" and "implementing a verified fix."

## 2. Core Functional Requirements
*   **Factory Scaffolding**: Command to create a standard tool structure (`tool_name/`, `SKILL.md`, `__init__.py`, `tests/`).
*   **Dynamic Registration**: Tool modules must be registerable without a full system restart (using dynamic imports).
*   **Self-Testing**: Tools are generated with built-in tests that must pass before registration.

## 3. Workflow (SRC Loop)
1. **Request**: `ToolboxFactory.create(name, purpose, workflow_steps)`.
2. **Build**: Generate scaffold + test harness.
3. **Validate**: Run built-in tests.
4. **Register**: Add the tool definition to `ai-stack/agents/skills/` (the "Toolbox Registry").
5. **Monitor**: Add a dashboard card to track usage and failure rate of the tool.
