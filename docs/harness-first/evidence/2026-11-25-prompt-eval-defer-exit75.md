# aq-prompt-eval defers with exit 75 on consecutive timeouts

Restores the item PR #834 described but never committed.

- Root cause: a single llama slot; under saturation every eval case waits its full timeout, so the unit ran ~1h and failed.
- scripts/ai/aq-prompt-eval: AQ_PROMPT_EVAL_MAX_CONSECUTIVE_ERRORS (default 3) consecutive timeouts stop the run, write no score for the aborted prompt, and exit 75 (EX_TEMPFAIL). A success or non-timeout error resets the count; non-timeout error streaks still abort with exit 1.
- nix/modules/roles/ai-stack.nix: ai-prompt-eval has SuccessExitStatus = [0 75], so a deferral is not a unit failure; the next timer run retries.
- Tests: test-aq-prompt-eval-defer.py (new); test-prompt-eval-transport-guard.py now expects 75 for all-timeouts and still asserts the backend is called exactly the limit number of times.
- Activation: the Nix change takes effect on the next rebuild (owner act).
