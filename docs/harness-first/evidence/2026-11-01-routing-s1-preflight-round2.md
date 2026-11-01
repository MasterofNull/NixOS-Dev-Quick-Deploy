# Routing S1 preflight, round 2 (Codex findings)

Scope: `.agents/plans/agentic-routing/PLAN.md` S1 only. Uncommitted at time of writing.

## What changed
- Preflight measures the request as it will be sent. Agent mode builds the first `aq-agent-loop` request with the executor's own functions (system prompt, tool list, context message). Direct mode applies the same prompt augmentation `dispatch.py` applies. The server renders the chat template (`/apply-template`) and tokenizes it. Tool schemas and grammar are not added on that path: they are not sent as context.
- The byte fallback (`byte_upper_bound`) is the byte size of the whole request, schemas and grammar included, plus a 2048-token template margin. Tokens never exceed bytes, so it is an upper bound.
- `delegate-to-local` refuses on any non-zero preflight exit: 3 for oversize, 4 for a preflight failure (nothing is launched). If the preflight process died before recording, the shim re-invokes `local_preflight.py --record-error`, so the row is written by the Python registry writer, not the shell.
- Accepted jobs leave `<output>.preflight.json`; `dispatch_evidence.normalize_row` copies the measured value, limit, source and verdict into the registry row.
- `delegate-to-codex` records `model_effective: "unknown"` instead of the requested model.

## Tests
- `scripts/testing/test-dispatch-preflight.py`: 14 tests, OK. Wrapper-level tests use a launch sentinel (oversize refusal, preflight crash, bad args, accepted job evidence), plus request parity between preflight and the real `dispatch.py` request, an agent-mode accept in an 8192 window, and fallback counting of schemas.
- `scripts/testing/test-worktree-isolation.py`: PASS. Its local fixture stubs `local_preflight.py` (preflight has its own suite); assertions are unchanged.
- `scripts/governance/check-state-authorities.py --machine`: exit 0, no undeclared writer.

## Live run (llama n_ctx 8192)
- agent, "Say hi.": 6098 / 8192, accept (`apply_template+tokenize`)
- direct: 4323 / 8192, accept

## Known gaps
- Agent preflight covers only the first LLM call; later turns carry history and tool output.
- Agent measurement runs about 770 tokens above the orchestrator's 4527 figure (5298 prompt tokens); cause not isolated. Overcount, never undercount.
- Context assembler and embedded-assist prefetch call live services, so the launched prompt can differ slightly from the measured one.
- With llama down, agent mode falls back to the byte bound and is refused (about 43k bytes of schemas); direct mode is unaffected.
- hybrid/ralph modes are measured as a direct request.
