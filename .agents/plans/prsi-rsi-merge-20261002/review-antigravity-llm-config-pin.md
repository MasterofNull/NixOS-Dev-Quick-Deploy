# Advisory Investigation: llm_config.py SHA256 Pin Divergence

- **Investigator**: Antigravity (advisory investigation of authored change in `116b5ae5`)
- **Target File**: `ai-stack/mcp-servers/shared/llm_config.py`
- **Active SHA256**: `1901963582f45ec8be825713b881a93dcf1b6d4a8c6d6e2953a8d8ad1e82a5cd`
- **Current Pins**:
  - `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json`: expects `1150f16e6b5dfa495e54bb1a7c262aec3b17cf9de70f0f6df82044684d5916ab`
  - `config/local-inference-transport-policy.json`: expects `be5a098687c92c4345c80307175144887c262174afbf6da9fc2ca8012d961905` (revision `llm-config-20260713`)
  - `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`: matches `1901963582f45ec8be825713b881a93dcf1b6d4a8c6d6e2953a8d8ad1e82a5cd` (already updated in `116b5ae5`)

---

## 1. Exact Diff in `116b5ae5`

Command: `git show 116b5ae5 -- ai-stack/mcp-servers/shared/llm_config.py`

```diff
diff --git a/ai-stack/mcp-servers/shared/llm_config.py b/ai-stack/mcp-servers/shared/llm_config.py
index 6e5fa00e..ff99d2f7 100644
--- a/ai-stack/mcp-servers/shared/llm_config.py
+++ b/ai-stack/mcp-servers/shared/llm_config.py
@@ -53,6 +53,7 @@ ROLE_SYSTEM_PROMPTS: dict[str, str] = {
     "architect":    "[Role: architect] Draft architecture docs, flag risks, write PRDs. Requires orchestrator review before commit.",
     "implementer":  "[Role: implementer] Execute assigned slice only. Validate output. Propose commit. Do not re-scope goals.",
     "reviewer":     "[Role: reviewer] Explicit pass/fail verdict against criteria. Do not review your own work.",
+    "rsi":          "[Role: rsi] Root-cause incidents and friction, formulate minimal verified remediations with automated guards, and record findings in backlog and memory. Do not broaden scope.",
 }

 # Fable-parity behavioral block (~55 tok) — MICRO variant.
```

---

## 2. Canonical Local Payload Contract Analysis

The diff in `116b5ae5` added only the `"rsi"` role prompt to `ROLE_SYSTEM_PROMPTS`.

Impact on protected contracts:
1. **`chat_template_kwargs` / `enable_thinking: False` nesting**:
   - `build_llama_payload()` continues to produce `chat_template_kwargs: {"enable_thinking": False}` identically.
2. **Builder defaults**:
   - `repeat_penalty: 1.08`, `repeat_last_n: 64`, `cache_prompt: True`, `frequency_penalty: 0.0` are completely unchanged.
3. **System message & Existing roles**:
   - Default system message and existing roles (`orchestrator`, `architect`, `implementer`, `reviewer`) are untouched.
4. **Sampling parameters**:
   - `temperature: 0.7`, `max_tokens` fallbacks remain identical.
5. **Cross-adapter wire projections**:
   - Executing the canonical projection comparison from `test-local-inference-chat-batch-parity.py` against live payloads:
     - `All wire projections match golden: True`
     - `Cross-adapter parity checks pass: True`

**Contract Assessment**: The change is **100% CONTRACT-NEUTRAL**. It does not alter wire shape, sampling defaults, or existing projection semantics.

---

## 3. Test Execution Tails

### A. `python3 scripts/testing/test-local-inference-chat-batch-parity.py`
```
FAIL: local-inference-chat-batch-parity (golden fixture self-consistency)
 - live source drift: ai-stack/mcp-servers/shared/llm_config.py (predecessor hash mismatch — re-authorize)
```

### B. `python3 scripts/testing/test-local-inference-l2b.py`
```
PASS: 16 local-inference L2B checks
```

---

## 4. Re-pin Specification

Because the change is contract-neutral and solely adds the canonical `"rsi"` role definition needed by PRSI/RSI autonomous loops, the pins should be updated:

1. **`scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json`**:
   - Update `live_source_manifest["ai-stack/mcp-servers/shared/llm_config.py"]`:
     `"1901963582f45ec8be825713b881a93dcf1b6d4a8c6d6e2953a8d8ad1e82a5cd"`
   - Update `manifest_digest` (recomputed over sorted rows and sources):
     `"57a0f078c310cea1c014eacb3add6fbd9d81e653a59008cc0eb7c5d4ea76b8c5"`

2. **`config/local-inference-transport-policy.json`**:
   - Update `canonical_builder.sha256`:
     `"1901963582f45ec8be825713b881a93dcf1b6d4a8c6d6e2953a8d8ad1e82a5cd"`
   - Update `canonical_builder.revision`:
     `"llm-config-20261003"`

---

RECOMMENDATION RE-PIN
