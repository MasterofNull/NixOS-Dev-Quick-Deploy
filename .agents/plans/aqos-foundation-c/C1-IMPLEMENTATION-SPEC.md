# Foundation C — C1 Implementation Spec + Authorization (shadow admission→issuance)

**Parent design:** `DESIGN-PACKET.md` (rev2) §8 C1. **Builds on:** C0 (`0319488b`,
`scripts/ai/lib/capability_lease.py`). **Author:** fable-5. **Idempotency key:**
`aqos-foundation-c:c1:shadow-admission-issuance:v1:20260724`.

**Class:** SHADOW / LOG-ONLY, additive, offline-first, **no enforcement, no edit to the
live admission path**. C1 observes the existing `aq-capability-intake` admission verdict
and records the CapabilityLease that WOULD be issued (or the denial that would apply) — it
changes no verdict, blocks nothing, and the pre-existing capability-intake + keystone
`zero_trust` protections remain the sole authoritative gate (design S5). Report-only ⇒
same standing-authorization basis as C0/B1, drift-verified.

**Decoupling rule (why no edit to `aq-capability-intake`):** the shadow pass CONSUMES the
audit result (`aq-capability-intake audit <id> --json`) as data and never mutates the
admission code. Zero risk to the live security gate; the additive property is structural,
not merely promised.

## File ceiling (exactly 4 — all NEW; no edits to existing files)
1. `scripts/ai/lib/capability_lease_issuance.py` — the shadow policy (pure, deterministic).
2. `scripts/ai/aq-capability-shadow` — CLI: `run` (produce shadow records), `report` (summary).
3. `config/schemas/capability-lease-shadow-record.schema.json` — the shadow-record contract.
4. `scripts/testing/test-capability-lease-issuance.py` — tests.

## Admission → lease policy (file 1) — `shadow_issue(audit_result, candidate, key) -> record`
Pure function of the audit result dict (fields from `audit_candidate()`: `id`, `admission`,
`risk_flags`, `tool_audits`, and the candidate's `tool_allowlist` + `permissions`). Maps:

| `admission` | would_issue | lease shape |
|---|---|---|
| `low-risk` | yes | trust_tier 3, `zero_trust_behavior=none` |
| `accepted-with-mitigations` | yes | trust_tier 2, `zero_trust_behavior=none` |
| `review-recommended` | yes (constrained) | trust_tier 1, `zero_trust_behavior=strip` |
| `needs-review` | **no** | would-deny, reason=`needs-review` |
| `blocked` | **no** | would-deny, reason=`blocked` |

When issuing, build a CapabilityLease (C0 schema) via `capability_lease`:
- `permissions.actions` = the candidate's `tool_allowlist` (the tools it may call).
- `permissions.resources` = `["network"]` if `permissions.network` else `[]`, plus
  `["write"]` if `permissions.writes` truthy (report-only writes excluded).
- `permissions.constraints` = `{"network": permissions.network, "writes": permissions.writes}`.
- `zero_trust_behavior=strip` ALSO when `"secret-or-token-required"` ∈ risk_flags (conservative).
- `issued_to` = `f"candidate:{id}"` principal ref; `source="capability-intake-shadow"`;
  `issued_at`=now; `expires_at`=now+1h (shadow leases are short-lived); `revocation_epoch=0`;
  signed with the C0 DEV key (shadow — the DEV-key banner still applies).
Return a **shadow record**: `{ts, candidate_id, admission, would_issue, lease|null,
deny_reason|null, risk_flags}`. `append_shadow_log(record, path)` = atomic append to a
JSONL at a runtime path (default `.agent/collaboration/capability-lease-shadow.jsonl`,
gitignored/runtime — NOT committed); never raises on a bad path (fail-open logging is fine
here — it's observability, not a gate).

## CLI (file 2) — `aq-capability-shadow`, report-only
- `run [--registry <file>] [--candidate <id>] [--audit-json <file>] [--log <path>] [--json]`
  — for each candidate, obtain its audit (via `aq-capability-intake audit <id> --json` as a
  subprocess, or read `--audit-json`), `shadow_issue`, append to the log, print the records.
  NEVER changes any exit code based on admission — always exits 0 unless the tool itself errors.
- `report [--log <path>] [--json]` — summarize: counts by admission, would-issue vs
  would-deny, top risk_flags. Pure read of the JSONL.

## Shadow-record schema (file 3)
draft-2020-12 for the record above; `additionalProperties:false`; `lease` is either null or
a `$ref` to the C0 `capability-lease.schema.json` CapabilityLease (relative `$ref` or an
inlined subset — implementer's call, but it MUST validate the golden records).

## Tests (file 4) — real assertions, offline (synthetic audit dicts; no subprocess/network)
- `low-risk` audit → would_issue=true, lease built, permissions.actions == tool_allowlist,
  network/write resources+constraints correct, `zero_trust_behavior=none`, lease VERIFIES ok (C0 verify).
- `accepted-with-mitigations` → trust_tier 2, issues, verifies.
- `review-recommended` → issues but `zero_trust_behavior=strip`, trust_tier 1.
- `secret-or-token-required` in risk_flags on an otherwise-issuable candidate → `strip`.
- `needs-review` and `blocked` → would_issue=false, lease=null, deny_reason set, NO lease object.
- **Additive proof:** `shadow_issue` is pure — it returns a record and does not raise/alter
  the input audit dict; running it does not require or mutate the live admission path.
- Shadow log append: two records → two valid JSONL lines; schema-validates each record.
- The issued shadow lease respects C0 monotonicity if attenuated from a parent (optional).

## Out of scope (deferred, written)
No enforcement, no verdict change, no switchboard/dispatch wiring, no cells/network-profiles,
no OTel spans, no SOPS key. Turning the shadow lease into the AUTHORITATIVE gate is **C2**
(hash-bound, single-use owner activation). C1 only observes + records.

## Reviewer / next
Implementer = cheapest-eligible (multi-file > local envelope ⇒ Claude fast tier, Rule 17
override recorded). Independent review of the RESULT (additive-proof + policy correctness +
no live-path edit). never-skip-local. codex confirmatory audit queued.

## Post-review fix (2026-07-24, pre-C2)
The C1 Opus review flagged (NICE-TO-HAVE) that `_build_permissions`'s report-only-writes
exclusion set omitted the real registry value `scope-receipts-and-reports` (t3mp3st),
mis-classifying it as write-capable (safe in shadow — over-surfaces — but a real over-grant
once C2 reuses this under enforcement). Fixed: added `scope-receipts-and-reports` to
`_REPORT_ONLY_WRITE_VALUES` + a regression test (`test_scope_receipts_and_reports_not_write_capable`),
57/0. **Rule-17 deviation recorded:** made directly by the orchestrator because no eligible
implementer lane was available at the time — local agent-mode tool execution failed
(emitted an unexecuted text tool-call, `tool_calls: []`), the Claude flagship lane hit its
session limit (reset 11:40am 2026-07-25), and codex was in quota cooldown. Bounded 1-value
+ 1-test change; independent confirmation deferred to the queued codex C1 catch-up audit.
