# QA-AUTOMATION Domain — Agent Instruction Surface

**Domain tag:** `qa-automation`
**State:** proposed
**Upstream authority:** `.agent/PROJECT-QA-AUTOMATION-PRD.md`

## 1. Domain Mandate
Autonomously discover edge cases, write property-based tests, and execute chaos engineering scenarios to harden the AI stack.

## 2. Methodology
- **Red Teaming:** Actively look for race conditions in agent memory storage and concurrent tool execution.
- **Test Generation:** Write tests that focus on boundaries, timeouts, and malformed inputs rather than just "happy paths."

## 3. Safety Guardrails
- **NO PROD DOS:** Chaos engineering tests must only run against designated testing ports, never the live control plane.
- Ensure all test artifacts and mock databases are cleaned up after execution.

## 4. AIDB Interaction
- **Namespace:** `qa-patterns`
- Store regression discoveries and fuzzing strategies here.
