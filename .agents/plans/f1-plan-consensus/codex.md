# F1 Plan Consensus — codex

Verdict: APPROVE_WITH_CHANGES.

The F1.1-F1.5 slice breakdown correctly realizes the ratified direction: durable `round.json`, typed contribution envelopes, idempotent lane dispatch, late-local `AMEND`, deterministic aggregation, golden orchestration tests, and a non-breaking `aq-collab-round` migration. It is implementation-ready, but three corrections should be made before execution so the slices do not encode avoidable drift from the ratified design.

## Assessment

1. The slice breakdown is structurally correct. F1.1 establishes the state core, F1.2 formalizes contribution recovery, F1.3 adds idempotent lifecycle behavior and `AMEND`, F1.4 tests orchestration failure modes, and F1.5 migrates the CLI while preserving markdown compatibility.

2. The main design gap is schema completeness. The plan names the key manifest fields, but it should explicitly include quorum timeout metadata, contribution registry fields, conflict object shape, aggregate output path/hash, and per-lane terminal/error statuses. Without those, F1.3/F1.5 will invent local conventions under schedule pressure.

3. Sequencing is mostly sound, but F1.3 depends on the F1.2 envelope extractor and on F1.1 manifest fields that are not yet fully specified. The non-breaking F1.5 migration is safe only if it treats existing markdown rounds as legacy read-only inputs and never rewrites or normalizes their contribution files during collection.

4. Module placement should be `scripts/ai/lib/round_state.py`, with `scripts/ai/lib/contributions.py` or equivalent for envelope extraction. That is the right reuse point for `aq-collab-round` now and future coordinator integration later, without coupling core round logic to `ai-stack/local-agents`, which is too lane/runtime-specific.

5. The plan should add explicit compatibility tests for legacy rounds before any CLI write behavior changes. A live `factory-critique` collection check is useful, but a fixture-based legacy markdown round test should be part of F1.4/F1.5 so safety does not depend on mutable workspace state.

## Top 3 Required Plan Changes

1. Freeze the schema contract in F1.1 before implementation:
   - Add explicit `lane.status` enum: `pending|dispatching|running|submitted|failed|timed_out|amended`.
   - Add `quorum_policy.timeout_seconds` or `deadline` semantics, `timeout_action`, and required-agent failure behavior.
   - Add `contributions[]` registry keyed by `agent_id` plus `idempotency_hash`.
   - Add typed `conflicts[]` shape and aggregate metadata: `aggregate_path`, `aggregate_hash`, `locked_at`.

2. Move legacy compatibility earlier:
   - F1.4 should include a fixture representing an existing markdown-only ratified round.
   - F1.5 `collect` must be read-only for legacy `<agent>.md` files and must write only derived sidecars or `round.json` when explicitly migrating.
   - Add an assertion that repeated `collect` on legacy rounds does not modify original markdown files.

3. Split reusable modules under `scripts/ai/lib/`:
   - `round_state.py` for manifest schema, transitions, atomic persistence, and invariant checks.
   - `round_contribution.py` for envelope schema and text-only fallback extraction.
   - Keep CLI code in `scripts/ai/aq-collab-round` as a thin adapter. Future coordinator code should import the library, not shell out to the CLI.

## Residual Risks

The plan should define whether `AMEND` is a transient transition or a durable state that can survive process death. I recommend durable: write `state=AMEND`, append history, evaluate concurrence/conflict, then transition back to `CONSENSUS_LOCKED` or `CONFLICTS_IDENTIFIED`.

The plan should also require malformed sidecars to become typed lane failures, not silent fallback to markdown unless the sidecar is absent. A present-but-invalid `<agent>.json` is an integrity signal and should be surfaced.

With the three corrections above, the plan faithfully implements the ratified F1 design and is safe to proceed slice by slice.
