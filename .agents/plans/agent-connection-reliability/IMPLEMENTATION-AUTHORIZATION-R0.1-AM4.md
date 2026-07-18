# Implementation Authorization Amendment 4 — R0.1 Privacy Assertion Correction

Authorization ID: `auth-agent-connection-reliability-r0.1-am4-20260718`
Idempotency key: `agent-connection-reliability:r0.1:privacy-assertion-am4:20260718`
Parent: `auth-agent-connection-reliability-r0.1-am3-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded slices required to finish the reliability goals.

## Recovery evidence

AM3 completed and consumed after removing the FIFO hang. The full focused suite now terminates in
1.905 seconds with 113/114 passing. The sole failure is an inherited overbroad test assertion in
`test_r01_21_tui_injects_machine_facts_and_renders_state`: it requires the substring `legacy` to be
absent from the entire compatibility-facts JSON, but the closed public contract intentionally contains
`oversized_legacy_rows` and `legacy_oversized_rows_present`. The assertion therefore rejects public
schema vocabulary rather than testing private record-content redaction.

## Frozen AM3 candidate

1. `scripts/ai/lib/task_registry.py`
   `9285658eef68eb07a29e39db9f7fd9b43c51c2c827522d168d3ec5a86aa7b284`
2. `scripts/ai/aq-delegation-registry`
   `0e56ebcf10fe1d4a022b0f413e761a17ccf58b30278602c9f5c87cdcef6d39eb`
3. `scripts/ai/lib/agent_ops_projection.py`
   `3edf0cea2811176493fa0eb60885071c4064aa6442792f9e67e62a57878afcd3`
4. `config/schemas/agent-ops-projection.schema.json`
   `a58680b29eb3893e4446d113af8dee5c3a15d0aa69d623355de6252eb643a466`
5. `scripts/ai/aq-tui-dashboard`
   `8bab94bb7f7f1d2eb5757494be0bee2d5807a9a94e52578c3e7bd4790b10051f`
6. `scripts/testing/test-agent-ops-projection.py`
   `a60e819fd42b47c5160f32eb815a7b95a88f2fa4d2610e87876327935efa5cc2`
7. `scripts/testing/harness_qa/phases/phase0.py`
   `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`

Any mismatch is a hard stop.

## Exact grant

One bounded Codex implementer may edit only file 6. Replace the generic substring assertion with a
unique private task/content canary and prove that exact canary is absent from projected compatibility
facts and rendered monitoring state. Public closed vocabulary, counts, health, reason codes, and TUI
labels must remain unchanged. Run the isolated test, full focused suite, relevant Phase-0 check,
Python compilation, schema validation, and diff hygiene. Any production-code or second-file change
requires AM5.

## Consumption, acceptance, and exclusions

The first completed exact seven-hash report consumes AM4; interruption without a completed report
does not. No staging, commit, deployment, delegation, or self-review. Integration requires an
independent exact-subject PASS and Tier-0.

No production behavior, registry data/migration, wrapper/broker/service, web implementation,
Nix/deployment, live traffic, C0.6/C1-C5, prompt/memory, or eighth file is authorized.

`RECORD: prepared single-use test-only correction lease.`
