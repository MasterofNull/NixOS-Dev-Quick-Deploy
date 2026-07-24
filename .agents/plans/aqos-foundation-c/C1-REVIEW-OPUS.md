# C1 Independent Review — Shadow admission→issuance (SHADOW / LOG-ONLY)

**Reviewer:** claude-opus-foundation-c-c1-reviewer (independent; did not author/implement).
**Scope:** Foundation C **C1**, 4 new files. Spec: `.agents/plans/aqos-foundation-c/C1-IMPLEMENTATION-SPEC.md`.
**Date:** 2026-07-24.

## VERDICT: **PASS**

The additive / non-enforcing property is **structurally** sound, not merely promised. `aq-capability-intake` and the C0 `capability_lease.py` are byte-for-byte untouched; the shadow pass observes the admission verdict as read-only data and cannot alter, block, or feed back into the live gate. All 5 admission→lease mappings match the spec table **and** the exact verdict strings the intake producer emits. Issued shadow leases round-trip through C0 `verify()`. 45/45 tests pass; end-to-end subprocess run against the real registry exits 0. Findings below are all sub-blocking (honesty/hygiene/robustness), none compromise the additive guarantee and none issue a lease for a blocked/needs-review candidate.

---

## Item-by-item assessment

### 1. Additive / non-enforcing (STRUCTURAL) — PASS, no BLOCKING
- `git diff -- scripts/ai/aq-capability-intake` and `-- scripts/ai/lib/capability_lease.py`: **both empty**. All 4 C1 files untracked-new. File ceiling respected (exactly 4, no edits).
- Shadow consumes intake via subprocess `audit <id> --json` only. `cmd_audit` (intake:350-364) is pure-read: loads registry, computes reports, prints — **no ledger/state/registry write, no `open(...,'w')`, no approval mutation**. The observation cannot perturb live state.
- `cmd_run` (aq-capability-shadow:124-149) **always `return 0`**; the only non-zero path is `_collect_pairs` raising on the tool's *own* IO/arg error (bad registry, unknown candidate, subprocess failure, JSON parse) — caught at :127-129 → exit 1. A `blocked`/`needs-review` admission flows through `shadow_issue` as **data** (would_issue=False, printed, exit 0). Verified in code and by end-to-end run (11 records, exit 0).
- No path where the shadow layer blocks/alters/feeds back into admission or dispatch. **No BLOCKING finding.**

### 2. Policy correctness vs spec table — PASS (one NICE-TO-HAVE)
`_ADMISSION_POLICY` (issuance:39-45) is exact:
| admission | would_issue | tier | zt_behavior | verified |
|---|---|---|---|---|
| low-risk | True | 3 | none | ✓ |
| accepted-with-mitigations | True | 2 | none | ✓ |
| review-recommended | True | 1 | **strip** | ✓ |
| needs-review | False | — | (deny `needs-review`, lease null) | ✓ |
| blocked | False | — | (deny `blocked`, lease null) | ✓ |

- The 5 keys **exactly match** the strings `_admission()` emits (intake:255-276: `accepted-with-mitigations`/`blocked`/`needs-review`/`review-recommended`/`low-risk`) — so nothing silently fail-closes to would-deny on a spelling mismatch.
- `secret-or-token-required` ∈ risk_flags forces `strip` (issuance:150-151), tier unchanged — matches spec and test 4.
- Permissions build (issuance:79-95): `actions == list(tool_allowlist)`; `resources` gets `network` iff `permissions.network` truthy, `write` iff `_is_write_capable(writes)`; `constraints={"network":…,"writes":…}`. Correct.
- **NICE-TO-HAVE (write mis-classification):** `_REPORT_ONLY_WRITE_VALUES` (issuance:53) omits `scope-receipts-and-reports`, which **is** a real registry value (candidate `t3mp3st`) and reads as report/output-only. It is therefore classified **write-capable** and granted the `write` resource. Direction is *over*-surfacing (safe for a shadow observer — hides nothing), so not a security regression, but it is a genuine gap vs the registry vocabulary. **Fix before C2 reuses `_build_permissions` for enforcement:** either add `"scope-receipts-and-reports"` to the exclusion set, or invert to an explicit write-capable allowlist so unknown markers default to the conservative (non-write) side.

### 3. Purity / safety of `shadow_issue` — PASS (one SHOULD-FIX)
- **No input mutation:** builds fresh dicts, `list(tool_allowlist)` copies, `list(audit_result.get("risk_flags") or [])`. Test 6 deep-copies both inputs and asserts equality after — passes.
- **Total on messy inputs:** `candidate.get("permissions") or {}` / `... or []` handle None/missing; unknown/missing admission → early fail-closed deny record (issuance:123-135), never falls through to an issued lease. Empty tool_allowlist → `actions=[]`, still a valid/verifiable lease. Confirmed it does not raise.
- **Round-trip:** the 16 lease fields match `REQUIRED_LEASE_FIELDS` exactly; `cl.verify(lease, KEY) == VERIFY_OK` asserted in tests 1-4 and reproduced live. TTL = now+1h so never expired at issuance; `revocation_epoch=0`, int `trust_tier`/`version` pass `_is_malformed`.
- **SHOULD-FIX (DEV-key banner not preserved):** spec §policy says shadow leases are "signed with the C0 DEV key (shadow — **the DEV-key banner still applies**)." `shadow_issue` calls `cl.resolve_key()[0]` (issuance:153), **discarding `is_dev`**, and neither the record nor `cmd_run` surfaces it. C0's contract states callers "MUST surface that fact loudly." An operator reading the shadow log / `run` output cannot tell a would-issue lease is DEV-signed. Low severity (leases are inert, dev-key is the default posture until the SOPS slice), but it is a spec deviation on an honesty requirement. **Fix:** thread `is_dev` from `resolve_key()` into the record (e.g. `"dev_key": true`) and/or print the `DEV_KEY_BANNER` once in `cmd_run` when the resolved key is dev.

### 4. Shadow-log honesty — PASS
- `append_shadow_log` (issuance:188-209) is fail-open (bare `except: pass`) — appropriate for observability. Single `os.write` under `O_APPEND|O_CREAT` (one write() call) → POSIX-atomic, no interleave / no partial line on concurrent appenders. `json.dumps(..., sort_keys=True)` + trailing `\n` per record.
- Records are schema-valid (test 7 + `report` re-parses cleanly). A would-deny cannot be recorded as would-issue: `would_issue`/`lease`/`deny_reason` are set together from the deterministic policy tuple; deny branches hard-set `lease=None`.

### 5. Subprocess path (`run` without `--audit-json`) — PASS (one NICE-TO-HAVE)
- `_audit_via_subprocess` (shadow:65-89): `subprocess.run([sys.executable, str(INTAKE_SCRIPT), "--registry", …, "audit", candidate_id, "--json"], …)` — **list args, no `shell=True`**, absolute `INTAKE_SCRIPT`, 120s timeout. Candidate id is a subprocess argv element → **no shell injection** even for a hostile id.
- Non-zero intake exit → `RuntimeError` (shadow:81-84) → caught in `cmd_run` → exit 1, **before any `shadow_issue`** → cannot emit a fabricated would_issue on a subprocess failure. Correct degradation.
- **NICE-TO-HAVE (batch all-or-nothing):** `_collect_pairs` builds every pair before any record is written, so one failing candidate aborts the whole run and suppresses shadow-logging of the healthy ones. Fine as fail-loud, but per-candidate isolation (log the good, note the bad) would be more robust for a full-registry sweep.

### 6. Test integrity — PASS
- 45 real assertions, all pass (reproduced). Not vacuous: `verify()` round-trips are real C0 calls; purity test deep-copies and asserts both inputs unmutated; deny tests assert `lease is None` **and** `deny_reason ==` the expected string (not merely would_issue False); unknown-admission asserts fail-closed (would_issue False + lease None).
- **NICE-TO-HAVE:** `schema_validate_record` falls back to a structural check (required keys + allowed-key/`additionalProperties` + lease required/allowed) whenever the `jsonschema` `RefResolver` throws (shadow-record `$id` is a non-URI, so the cross-file relative `$ref` resolution is fragile under some `jsonschema` versions). The structural fallback is not vacuous, but it can mask a genuinely broken cross-file `$ref`. Consider asserting real `jsonschema` resolution succeeds at least once (or resolve via a filesystem base URI) so the fallback stays a safety net, not the silent default.

### 7. Schema correctness — PASS
- `capability-lease-shadow-record.schema.json`: `required` = exactly the 7 keys `shadow_issue` emits (`ts, candidate_id, admission, would_issue, lease, deny_reason, risk_flags`); `additionalProperties:false`. `admission`/`candidate_id`/`deny_reason` are `["string","null"]` (deny records carry null reason on issue, null candidate possible). `admission` intentionally un-enumerated so a future/unknown verdict validates as a deny record rather than failing schema — consistent with the fail-closed policy branch.
- `lease` = `oneOf[null, $ref capability_lease]` — disjoint alternatives, validates both the null (deny) and object (issue) cases. Cross-file `$ref` targets the sibling `capability-lease.schema.json` in the same `config/schemas/` dir. Emitted lease matches that schema (verified live).

---

## Repo hygiene (outside the 4-file diff)

- **SHOULD-FIX (gitignore):** default log path `.agent/collaboration/capability-lease-shadow.jsonl` is **NOT git-ignored** (`git check-ignore` → not ignored). Spec §policy explicitly calls it "gitignored/runtime — NOT committed." As-is, an operator running `aq-capability-shadow run` with the default log creates an untracked JSONL of DEV-signed shadow leases that a `git add -A` could commit. The 4-file ceiling prevented the implementer from adding the ignore rule in-slice, so flag as a **required follow-up**: add `.agent/collaboration/capability-lease-shadow.jsonl` (or `.agent/collaboration/*.jsonl`) to `.gitignore`, or default the log to an already-ignored runtime dir. (No artifact was leaked by this review — the end-to-end run used a temp path.)

## Summary of findings
| Severity | Finding | Location |
|---|---|---|
| BLOCKING | — none — | |
| SHOULD-FIX | DEV-key `is_dev` discarded; banner not surfaced (spec requires it) | issuance:153 / aq-capability-shadow cmd_run |
| SHOULD-FIX | Default shadow-log path not gitignored (spec requires) | .gitignore / issuance:59 |
| NICE-TO-HAVE | `scope-receipts-and-reports` (real `t3mp3st` value) mis-classified write-capable | issuance:53 |
| NICE-TO-HAVE | `_collect_pairs` aborts whole batch on one candidate's subprocess failure | aq-capability-shadow:92-121 |
| NICE-TO-HAVE | Schema test silently falls back to structural check if `RefResolver` throws | test:86-100 |

**Additive proof holds. No lease is issued for a blocked/needs-review candidate. Verdict: PASS.** Recommend the two SHOULD-FIX items be resolved in a bounded follow-up (both are 1-2 line changes) and the write-classification gap closed before C2 reuses `_build_permissions` under enforcement.
