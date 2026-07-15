# Antigravity Acceptance Review: M2 Fable-routing Bootstrap

**Date**: 2026-07-15
**Reviewer**: Antigravity (Flagship Architecture, Security, and SRE Reviewer)
**Status**: `PASS` (Candidate Approved for Commit & Use)

---

## 1. Executive Summary & Verdict

We issue a formal **`PASS`** for the **M2 Fable-routing Bootstrap** candidate.

The three-file candidate conforms exactly to the authorized plan and provides a secure, fail-closed resolution path for model-coordinator mappings. It has been verified for syntax correctness, passes all focused tests, and is ready for commit.

### Subject Hash Verification
* **FABLE-ROUTING-BOOTSTRAP-AUTHORIZATION.md**: `ae6f28204989d7ebbb495f22b1191e7589e718211a81786aab05672f9171daec` (Matches!)
* **scripts/ai/delegate-to-claude**: `fc2094caf0591d35bc10ed201ec07d6a52b37953dbca2d8e56562ddee6e36884` (Matches!)
* **scripts/testing/test-delegate-claude-model-routing.py**: `e01a7faa95f2c10f05e5d217538ad6db71ef65287927f18d0eda96b04e030326` (Matches!)

### Scope & Authorization Constraints
> [!IMPORTANT]
> The bootstrap candidate is approved for commit. It changes only model selection and audit identity. M2A/M2B (full wrapper/registry rewrite), lifecycle semantic changes, registry concurrency fixes, and M3/R1–R4 remain strictly **UNAUTHORIZED**.

---

## 2. Test Execution & Verification Evidence

All requested verification suites have been executed and passed:
* **`test-delegate-claude-model-routing.py`**: `Ran 4 tests... OK` (4/4 passed). Test coverage successfully exercises default tier preservation, invalid model fail-closed behavior, unknown tier blocking, and flagship registration writes.
* **Bash Syntax**: Verified cleanly via shellcheck standards.
* **Python Syntax**: Inline snippet and test file verified cleanly.

---

## 3. Threat Modeling & Security Adjudication

### A. Failure Gating & Fallbacks
* **Coordinator Missing/Malformed**: If `config/model-coordinator.json` is absent, invalid JSON, or missing the expected keys, the python helper returns a non-zero exit status, causing `resolve_model_tier` to call `die`, halting execution before launching the provider or writing to the registry.
* **Tier Gating**: Model tiers are strictly validated using a bash case statement allowing only `""|flagship|flagship_fallback|balanced|fast|creative`. Any unknown tier terminates execution immediately.

### B. Shell & Argument Injection Protection
* **Argument Passing**: The tier string is fed directly to Python via `sys.argv[2]`, preventing shell word-splitting or command evaluation.
* **Regex Gating**: Resolved model identifiers are validated against `re.fullmatch(r"claude-[a-z0-9][a-z0-9.-]{1,63}", model)`. Any model ID string containing shell operators, newlines, or command arguments (e.g. `--model`) is rejected, preventing command injection into the Claude binary invocation array.

### C. Fable-Routing Gating
* Claiming Fable tier routing is restricted to explicit selection via `--model-tier flagship` (or equivalent tier mapping in `model-coordinator.json`) or directly setting `--model claude-fable-5` on the command line. No other paths can claim Fable execution.

---

## 4. Next Steps

1. **Complete Inbox Task**: Complete the inbox drop `m2-fable-routing-bootstrap-acceptance.md`.
2. **Commit Stage**: Stage and commit the three bootstrap files.
