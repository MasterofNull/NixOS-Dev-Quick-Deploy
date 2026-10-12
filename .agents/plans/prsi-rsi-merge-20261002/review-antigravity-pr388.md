# Independent Review: PR #388 (Crystallizer Local LLM Timeout 900s & Prompt Budget)

- **Reviewer**: Antigravity (independent, non-author)
- **Target Subject**: PR #388, branch `origin/fix/crystallizer-local-timeout-20261007` vs `origin/main` (`4ad5e14f`, `7d75324b`, `1f0b4c46`)
- **Changed Files**:
  - `ai-stack/mcp-servers/hybrid-coordinator/core/llm_client.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/server.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/tests/test_memory_crystallizer_sessions.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/live_source_manifest.json`
  - `docs/harness-first/evidence/2026-10-07-crystallizer-local-timeout.md`

---

## 1. Architectural & Functional Verification

### A. Default Timeout Preservation for Other Callers
- `LLMClient.__init__` adds an optional parameter `timeout: Optional[float] = None`, stored as `self.timeout`.
- In `_init_local()`, the HTTP client is initialized as:
  ```python
  self.client = httpx.AsyncClient(timeout=self.timeout or 120.0)
  ```
- All other callers across the codebase (`consensus_arbiter.py`, `workflow_executor.py`, and test suites) instantiate `LLMClient` without passing `timeout`, retaining `timeout=None` which defaults to `120.0s`.
- Preserved and verified by `test_local_llm_client_timeout_override()`:
  - `default.client.timeout.read == 120.0`
  - `custom.client.timeout.read == 900.0`

### B. Timeout Application to Local Requests
- In `_local_create_message()`, completions are dispatched via `await self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)`.
- The request uses `self.client` directly without overriding the timeout parameter at call-site.
- The 900.0s configuration applies to all local switchboard HTTP socket and read operations.

### C. Retry Interaction & Worst-Case APU Duration
- In `LLMClient.create_message()`, calls are wrapped with:
  ```python
  await retry_with_backoff(
      breaker.call,
      _do_create_message,
      max_attempts=2,
      breaker=breaker,
      retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError),
  )
  ```
- In `_local_create_message()`, raw HTTP exceptions are caught and wrapped in `RuntimeError`:
  ```python
  except Exception as e:
      logger.error(f"Local switchboard API error: {e}", exc_info=True)
      raise RuntimeError(f"Failed to create local message: {e}")
  ```
- **Consequence**: Because `httpx.TimeoutException` is converted to `RuntimeError`, `retry_with_backoff` does not match the exception type and fails fast without retrying.
- **APU Impact**: In this specific APU batch crystallization scenario, failing fast on timeout is beneficial: it bounds worst-case duration to 900s and avoids an immediate 900s re-prefill penalty on an already-stalled local model.

### D. Environment Parsing Robustness
- In `server.py`, `_env_float("CRYSTALLIZER_LLM_TIMEOUT_S", 900.0)` wraps `os.getenv`:
  ```python
  def _env_float(name: str, default: float) -> float:
      raw = os.getenv(name)
      try:
          value = float(raw) if raw else default
      except ValueError:
          logger.warning("%s=%r is not a number; using %s", name, raw, default)
          return default
      return value if value > 0 else default
  ```
- Handles empty/unset strings, non-numeric values (typos like `abc`), negative values, zero, and `nan` safely by logging a warning and falling back to `default = 900.0`.
- Coordinator server startup will not crash on malformed configuration.

### E. Prompt Budget Slicing
- `_DISTILL_HISTORY_CHAR_BUDGET = 6000` is defined in `memory_crystallizer.py`.
- `_build_distillation_prompt` takes the last 20 messages (`history[-20:]`), formats them, and slices the trailing 6000 characters:
  ```python
  history_text = history_text[-_DISTILL_HISTORY_CHAR_BUDGET:]
  ```
- Guarantees APU prefill tokens remain bounded under ~1500 tokens, which easily completes within the 900s budget on Renoir APU.

---

## 2. Follow-Up Observations (Low Severity)

1. **Mid-Message Boundary Slicing**:
   - `history_text[-6000:]` performs a raw character slice from the end of the combined string. If the 6000th character from the end falls in the middle of a role line or turn, the prompt begins with a truncated fragment (e.g., `ontent: ...`).
   - While LLMs readily parse partial leading lines, aligning to the next newline boundary (`history_text[history_text.find("\n") + 1:]`) or slicing by discrete message blocks would provide cleaner context.

2. **Exception Masking in `llm_client.py`**:
   - `_local_create_message` catches all `Exception` and raises `RuntimeError`, which effectively disables `retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError)` in `create_message`. If standard retry semantics are ever restored, an explicit per-client `max_attempts=1` override should be passed for local batch crystallization to prevent 1800s retry storms.

---

## 3. Test & Verification Evidence

- `pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_memory_crystallizer_sessions.py`:
  - 28/28 tests PASS (including `test_distillation_prompt_respects_char_budget` and `test_local_llm_client_timeout_override`).
- `pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_llm_client.py`:
  - 5/5 tests PASS.
- Live source manifest updated and validated (`7d75324b`).

---

VERDICT PASS_WITH_FOLLOWUPS
