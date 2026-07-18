# Implementation Authorization Amendment 3 — R0.1 Codex Hang Recovery

Authorization ID: `auth-agent-connection-reliability-r0.1-am3-20260718`
Idempotency key: `agent-connection-reliability:r0.1:codex-hang-recovery-am3:20260718`
Parent: `auth-agent-connection-reliability-r0.1-am2-20260717`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded slices needed to finish the reliability goals.

## Recovery evidence

Monitored task `claude-20260717-174439-n6ye93` changed none of the seven frozen files. It repeatedly
ran the focused suite into the FIFO-substitution hang and produced no completion report or output
artifact. The orchestrator terminated the task without accepting a candidate and reconciled its
registry row from `running` to `stale`. AM2 is therefore retired unconsumed; it must not be replayed.

The hang is localized: `_m2a_compat_scan_impl()` opens the registry with
`O_RDONLY | O_CLOEXEC` before `fstat()`. An attacker-substituted FIFO blocks in `open()` and never
reaches the existing non-regular-file rejection. The adjacent strict reader already uses
`O_NONBLOCK` for this exact pre-validation boundary.

## Frozen baseline and exact lease

The seven AM2 hashes remain exact:

1. `scripts/ai/lib/task_registry.py`
   `e5d26404e2782347e84f3b60f1a1c9d8a1bdaf56cd80c53beb9e7fb47f4903cb`
2. `scripts/ai/aq-delegation-registry`
   `0e56ebcf10fe1d4a022b0f413e761a17ccf58b30278602c9f5c87cdcef6d39eb`
3. `scripts/ai/lib/agent_ops_projection.py`
   `3edf0cea2811176493fa0eb60885071c4064aa6442792f9e67e62a57878afcd3`
4. `config/schemas/agent-ops-projection.schema.json`
   `a58680b29eb3893e4446d113af8dee5c3a15d0aa69d623355de6252eb643a466`
5. `scripts/ai/aq-tui-dashboard`
   `8bab94bb7f7f1d2eb5757494be0bee2d5807a9a94e52578c3e7bd4790b10051f`
6. `scripts/testing/test-agent-ops-projection.py`
   `87c611a6748b6b7ad0a3a379e233e2355557264fd99482326e1cf889fa698786`
7. `scripts/testing/harness_qa/phases/phase0.py`
   `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`

One bounded Codex implementer may edit only files 1 and 6. The other five remain hash-frozen evidence
surfaces and must not change. The implementer shall:

1. add `O_NONBLOCK` to the compatibility reader's pre-validation open flags while preserving regular
   file reads and all typed errors;
2. make the FIFO adversarial case watchdog-bounded so a regression fails instead of wedging the
   agent lane, without weakening the expected `registry_source_not_regular` result;
3. run the full focused suite, relevant Phase-0 check, Python compilation, schema parsing, and diff
   hygiene; and
4. stop and request AM4 if any different semantic change is required.

## Consumption and acceptance

The first completed exact seven-hash report consumes AM3. Interruption without a completed report
does not. The implementer may not stage, commit, deploy, delegate, or self-review. Integration
requires an independent exact-subject PASS from a different agent/session plus Tier-0 evidence.

## Exclusions

No registry migration/data mutation, wrapper/broker/service changes, web dashboard implementation,
Nix/deployment, live traffic, C0.6, C1-C5, prompt/memory changes, or eighth file is authorized.

`RECORD: prepared single-use Codex recovery lease; AM2 retired unconsumed and non-replayable.`
