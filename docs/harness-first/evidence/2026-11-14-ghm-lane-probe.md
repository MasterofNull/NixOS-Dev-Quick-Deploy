# Probe and capability-test candidate reviewer lanes on synthetic data first

Date: 2026-11-14
Task ID: HF-20261114-LANE-PROBE

## Objective
- Owner rule 2026-11-14: every new agent/model/lane is probed, tested and validated on synthetic data before real work or personal data. This slice is step A of `SECOND-REVIEWER-LANE-DESIGN.md` for candidate lane `ghm` (GitHub Models via the existing `gh` OAuth token).
- Delivered: `scripts/ai/probe-reviewer-lane` (model-agnostic: lane, endpoint, catalog, token command and model by args or the `LANES` table), `scripts/testing/test-probe-reviewer-lane.py`, and the owner rule in canon (`delivery-workflow` section 9 and summary), compiled into all agent files. No wiring into aq-land.
- Real result: `ghm` is NOT usable with this token. See Validation Evidence.

## Workflow/Session IDs
- Workflow ID: none (bounded slice)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated by the orchestrator to a Sonnet 5.5 implementer (Rule 17). Review is by a separate lane; the implementer does not self-review or merge.
- Minimal-code: reused `lib/delegation_dir.py` for the output dir; no existing lane-probe tool covered chat plus seeded-defect scoring (`aq-llm-speed-probe` is local-only throughput), so one new stdlib-only script.

## Commands Executed
```bash
python3 scripts/testing/test-probe-reviewer-lane.py
python3 scripts/ai/probe-reviewer-lane --lane ghm
python3 scripts/governance/canon-compile.py --write && python3 scripts/governance/canon-compile.py --check
python3 scripts/governance/check-agent-instruction-parity.py
bash scripts/governance/tier0.d/check-instruction-budget.sh
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Unit tests (10, stub transport, no network): parser (one valid disposition line only), corpus shape (8 defect plus 2 clean, no paths/identities), scoring pass/fail/boundary (4 of 5 hits with 1 false RC passes), 401/403/429/5xx/transport error all give `lane_unavailable` with no score, a catalog 200 that is not a model list is not entitlement, and the token-leak guard (token absent from result, stdout and files; a result containing it is refused; file mode 0600).
- Real probe, synthetic content only (`ghm`, model `openai/gpt-4.1`): `GET https://models.github.ai/catalog/models` and the chat completion both returned HTTP 200 with the body `OK\r\n` (not JSON), with and without the `application/vnd.github+json` and API-version headers. Result: `status: lane_unavailable`, `entitled: false` (entitlement unproven), no model list, no latency, no rate-limit headers, no capability score. This matches the design's earlier observation. Likely cause (unverified): the gh CLI OAuth token is not accepted for the Models inference API (needs a `models:read` grant or a different token type), so the front end answers a bare OK.
- A first attempt to inspect raw responses with curl and the token on the command line was blocked by the permission classifier; the script's own scrubbed diagnostics were used instead, and the token stayed in memory only.
- Capability score: not run (lane unavailable). The 10-case run path is covered by the stubbed tests only.

## Rollback Plan
- `git revert <sha>`. The script is not called by any other tool; probe result JSON lives under `.agents/delegation/outputs/lane-probes/` (mode 0600).

## Residual Risk
- `ghm` stays unproven; the design's fallback is step B (`local-2`), which this script can test through `--endpoint/--catalog/--token-cmd/--model`. A non-GitHub lane's catalog must return a JSON list of objects with `id`.
- The corpus is 10 toy diffs; it is a smoke bar, not the 15-PR gate-authority corpus the design requires for TRUST_CRITICAL.
- Whether a `models:read` token is acceptable under the no-API-keys rule is an open owner question; not tested.

## Hint Feedback
- No aq-hints used.
