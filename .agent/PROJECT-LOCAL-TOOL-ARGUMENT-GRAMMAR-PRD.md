# Local Tool Argument Grammar PRD

Status: IMPLEMENTED_PENDING_LIVE_DOGFOOD
Owner: Codex orchestrator
Date: 2026-08-28
Evidence task: `local-20260828-094134-6kogc5`

## Problem

The live self-improvement dogfood task used `AQ_LOCAL_GBNF=1`, but its second
model turn emitted `read_file` without `file_path`. The envelope parsed and reached
the handler because the current grammar constrains only the function name and treats
`arguments` as a generic object. That invalid call consumed 382 seconds after the
first read and helped exhaust the 1,200-second task wall without an edit.

## Objective

Generate a deterministic function-coupled grammar from the exact enabled tool
parameter schemas so every grammar-admitted call contains that tool's required
arguments while retaining its declared optional arguments.

## Acceptance contract

- Grammar input is the enabled `{tool_name: parameters_schema}` mapping, not names alone.
- Each tool becomes one or more closed envelope alternatives coupling its exact function
  name to its own argument schema.
- Every required argument is present. Optional arguments remain available through
  deterministic canonical-order subset alternatives; they are not silently removed or
  made mandatory.
- Empty-argument tools admit exactly `{}`. Unknown arguments and cross-tool argument
  shapes are rejected.
- Malformed schemas, unknown required keys, unsupported combinatorial expansion, and
  explicitly requested grammar-build errors fail closed with bounded diagnostics.
- Grammar cache identity binds canonical tool parameter schemas, so same-name schema
  changes rebuild the grammar.
- No tool capability, handler, safety policy, runtime deployment, or mutation authority
  changes.

## Bounded implementation

1. `ai-stack/local-agents/tool_grammar.py` — validate schemas and construct bounded
   function-coupled `oneOf` alternatives including optional subsets.
2. `scripts/ai/lib/grammar_cache.py` — compile strict non-empty `oneOf`; distinguish
   explicit closed empty objects from generic objects.
3. `ai-stack/local-agents/agent_executor.py` — pass enabled schemas, schema-bind cache,
   and fail closed when requested grammar cannot be built.
4. `scripts/testing/test-tool-grammar.py` and
   `scripts/testing/test-tool-call-grammar.py` — schema coupling, required/optional,
   empty-tool, cache-drift, malformed/fail-closed, and real matcher vectors.

## Validation and live gate

- Focused grammar suites and executor regressions.
- Existing edit-verification, capability reachability, reliability, and L2B gates.
- Tier0 pre-commit and independent exact-subject review.
- One bounded post-commit dogfood retry; no bulk/overnight queue until a valid edit and
  typed completion receipt are observed.

## Exclusions

- This slice does not claim model promotion.
- It does not tune model weights, quantization, GPU layers, context, or global token
  budgets.
- Generic runtime JSON-Schema validation before every handler is a separate defense-in-
  depth slice if evidence still shows invalid calls outside grammar-enabled lanes.

## Independent code review

- Reviewer: Codex `/root/local_runtime_audit` (independent of implementation)
- Verdict: `PASS`
- Exact five-file code subject SHA-256: `504429f83ccaf185d14b0b9fec2d2a9264256ccbf6c80c676273d388b4eac615`
- Focused evidence: grammar/schema matcher suites 24/24 PASS; L3 P0 13/13 PASS;
  actual full registry compiled 46 enabled tools into a deterministic 40,756-byte
  grammar.
- Completed: reliability receipt re-pin and Tier0 pre-commit (44 PASS, 0 FAIL).
- Remaining: final staged-subject review, commit, then one bounded live dogfood retry.
