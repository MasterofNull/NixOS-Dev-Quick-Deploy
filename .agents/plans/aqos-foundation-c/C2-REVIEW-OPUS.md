# C2 Tool-Lease Enforcement — Independent Design Review (Opus)

**Reviewer:** claude-opus-foundation-c-c2-reviewer (independent — did NOT author; author is fable-5).
**Reviewed record:** `.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md`
sha256 `a7361f13af8d596082ccd3017f2e32597e0a7173c89362cfcf024a99b0ad3e57` @ HEAD `4545e605` (2026-07-25).
**Scope:** DESIGN + AUTHORIZATION record (PREPARED_ONLY) — reviewed the design, not built code.
**Grounded against:** `ai-stack/switchboard/switchboard.py` (`_resolve_tool_lease` L1132,
`_normalize_local_tools` L1188, `_select_auto_tool_names` L1175, `_execute_local_tool_calling`
L1545, admission gate L1673, re-lease call L1690); `scripts/ai/lib/capability_lease.py` (`verify`
L272, `epoch_stale` L228, `resolve_key` L181); `scripts/ai/lib/capability_lease_issuance.py`
(`shadow_issue` L98); `DESIGN-PACKET.md` §8/§9.

---

## VERDICT: REVISE

The design is structurally sound — governance is correctly hash-bound, the F3 intent is faithfully
carried, the 4-file ceiling is reasonable, and the C0/C1 libs expose exactly the primitives the gate
needs (`verify` with the correct deny-closed check order, `epoch_stale`, `shadow_issue`). **But two
concrete fail-open paths exist under flag-ON that the record does not close, and both falsify the
central C2 claim that "a CapabilityLease is the authoritative admission condition."** Per the
fail-open audit (highest priority: *any* flag-ON admit-without-lease = BLOCKING), this cannot PASS as
written. Both are fixable additively within the 4-file ceiling.

---

## BLOCKING

### B1 — Fail-open: the initial tool-admission path is ungated; only voluntary re-lease is gated
**Where:** record §"The gate" + §"File ceiling" item 1 ("add the lease-gate filter INSIDE/after
`_resolve_tool_lease`… No other function changed") vs `switchboard.py` L1552, L1673, L1690.

The authoritative set that gates *actual tool execution* is `allowed_names`. It is set **initially**
by `_normalize_local_tools` at **L1552** (`tools_payload, allowed_names, working_set = _normalize_local_tools(...)`)
and every model tool call is admitted against it at **L1673** (`if tool_name not in allowed_names:`).
`_resolve_tool_lease` (**L1690**) only fires when the model *voluntarily* calls the virtual
`lease_tools` tool to **re-lease** its working set (`elif tool_name == VIRTUAL_TOOL_LEASE_NAME`).

The intent bundles that seed the initial set (`_TOOL_BUNDLES`, L914–976) carry **executable
privileged tools directly** — e.g. `run_command` is in `git`, `sys_ops`, and other bundles. So with
`CAPABILITY_LEASE_ENFORCEMENT=1`, a request classified as `git`/`sys_ops`/`harness_dev` receives
`run_command` in its **initial** `allowed_names` at L1552 and executes it at L1673 **without the
lease gate ever running** — the model never needs to call `lease_tools`. This is admission of a
write/exec-capable tool without a lease while enforcement is ON = **fail-open**, and it directly
falsifies the record's goal ("lease = authoritative admission condition in the live tool-resolution
path"). The gate as scoped is authoritative *only on re-lease*, which is optional.

**Additive fix (within 4-file ceiling):** anchor the gate at the true execution-admission
chokepoint rather than only the re-lease path. Cleanest: gate the `allowed_names` membership check
at **L1673** in `_execute_local_tool_calling` (flag-ON: a tool call is admitted only if `tool_name`
is in `allowed_names` **AND** carries a valid lease) — one chokepoint covers both the initial and
re-leased sets. Alternatively gate **both** `_normalize_local_tools` and `_resolve_tool_lease`. Either
keeps the file count at 4; the record's self-imposed "one function / `_resolve_tool_lease` only"
constraint must yield — that function is not the authoritative admission point. Update the record's
goal/ceiling text and add an acceptance test: *initial-bundle privileged tool with no lease →
DROPPED at execution even without a `lease_tools` call.*

### B2 — Fail-open via DEV-key fallback: `resolve_key()` never signals authority-unavailable
**Where:** record §"Authority-unavailable degrade (design S4)" vs `capability_lease.py:resolve_key`
L181–201, `verify` L272, `capability_lease_issuance.py:shadow_issue` L126–130/L188.

`resolve_key()` **never fails and never signals unavailability** — if `/run/secrets/aq-lease-signing-key`
(or `AQ_LEASE_SIGNING_KEY`) is missing/unreadable it silently returns the **deterministic public DEV
key** with `is_dev=True` (L201). `verify()` then validates DEV-key-signed leases as `VERIFY_OK`, and
`shadow_issue()` signs new leases with that same DEV key (L130/L188). Consequence: in production with
no real signing secret present, flag-ON would **admit leases validated under a publicly-known key** =
trust-root bypass = fail-open. The record's S4 text describes the *posture* ("authority unreachable →
minimal least-privilege degrade") but wires **no detection** — and the one signal the lib actually
exposes (`is_dev`) is exactly the missing-authority condition it fails to consume.

**Additive fix:** the gate MUST treat `resolve_key()` returning `is_dev=True` (no trust-rooted key)
as the S4 authority-unavailable condition **in enforcement mode** → degrade to minimal least-privilege
(safe read-only tools kept, all write/network/delegate/exec dropped) + LOUD log, **never** proceed
with DEV-key verification. State this explicitly in the record and add acceptance: *missing signing
key under flag-ON → least-privilege degrade, privileged tools dropped (not admitted under DEV key).*
(This is the concrete mechanism the abstract S4 posture currently lacks.)

---

## SHOULD-FIX

### S-a — Epoch source + unresolvable-epoch posture undefined (revocation leg can silently no-op)
**Where:** record §"The gate" epoch-stale bullet + §Acceptance "Revocation" vs `verify` L290
(`if current_epoch is not None and epoch_stale(...)`).

`verify(lease, key, current_epoch=None)` **skips** the epoch-stale check when `current_epoch is None`.
C2 claims the executor epoch check ships here (S1; F3 test (3) stale-lease-can't-revive), but the
record never names *where C2 reads the current epoch* (DESIGN-PACKET §8 C0 defines "the
policy/session-epoch counter" — C2 should cite it) nor the posture when that read fails. If the gate
passes `None` on an unreadable epoch, epoch-stale silently no-ops and a revoked lease is admitted =
fail-open on the exact revocation invariant this slice promises. **Fix:** name the C0 epoch source
the gate reads; require *unresolvable epoch → deny/degrade, never `current_epoch=None`.* Add this to
the revocation acceptance test.

### S-b — tool→candidate→admission mapping unspecified (enforce() not implementable as written)
**Where:** record §"The gate" ("admitted by a valid CapabilityLease issued by the C1 policy
(reusing `capability_lease_issuance` + `capability_lease.verify`)").

`shadow_issue()` requires `(audit_result, candidate)` per capability and `verify()` requires a lease
per tool. The hook has only tool **name strings** (`selected: set`). The record never specifies where
per-tool leases / candidate descriptors / admission verdicts come from at request time, so `enforce()`
cannot be built as specified. **Fix:** specify the source — e.g. a startup-issued per-tool lease table
built once by the C1 policy over the tool catalog, keyed by tool name; a name with no entry (or a
`would_issue=False` entry) is deny-closed. Name this table and its build point in the record.

### S-c — Guarded import + internal-exception-fails-closed not specified (off-is-inert + crash risk)
**Where:** record §"File ceiling" item 1/2 (new `capability_lease_gate.py` imports the C0/C1 libs).

The record says the new path sits behind `if CAPABILITY_LEASE_ENFORCEMENT` but does not state (a) the
gate import is **lazy/guarded** so flag-OFF never imports it — a top-level import that raises would
take down the live path *even with the flag OFF*, breaking off-is-inert; nor (b) that an exception
*inside* `enforce()` is caught and **fails CLOSED** (drops the affected tools), never leaking out of
the resolution path and crashing tool-calling. **Fix / safe pattern:** import `capability_lease*`
lazily inside the flag-ON branch (the existing `_LIB_PATH` at L11–13 already puts `scripts/ai/lib` on
`sys.path`, so a bare `import capability_lease` works — see N1); wrap the `enforce()` call in
`try/except` that on any internal error drops the affected tool(s) + LOUD log and never re-raises.
State both in the record and assert "gate module not imported when flag OFF" in the parity test.

### S-d — Remote tool-admission path not scope-declared
**Where:** record goal ("live switchboard tool-resolution path") vs `_filter_remote_tools_for_working_set`
L1240 / call site L2955.

Remote tool admission (remote-tool-calling profile) is neither gated nor explicitly deferred. The goal
statement reads broader than the local-only scope actually addressed. **Fix:** add one line explicitly
deferring remote-tool lease enforcement to a named later slice, so it is a *written* deferral (Rule 15)
rather than an unstated gap — or narrow the goal wording to "local tool-calling resolution path."

---

## NICE-TO-HAVE

- **N1 — Import mechanics already solved.** `_LIB_PATH = _REPO_ROOT/scripts/ai/lib` is inserted on
  `sys.path` at L11–13, so the gate can `import capability_lease` / `import capability_lease_issuance`
  directly with no new path insert. Note this in the record to avoid a redundant/incorrect path
  mechanism (and it de-risks the cross-package import concern for `capability_lease_gate.py`).
- **N2 — Strengthen the parity test** to assert the gate module is *not imported* (no import-time side
  effects) when the flag is OFF, in addition to output equality.

---

## Criterion-by-criterion

| # | Criterion | Result |
|---|-----------|--------|
| 1 | **Fail-open audit** | **FAIL** — B1 (initial-set bypass) + B2 (DEV-key fallback). S-a is a third latent fail-open on the revocation leg. Deny-closed posture is correctly *intended* but not *achieved* at the chosen hook. |
| 2 | **Off-is-inert** | Conditional PASS — achievable at the hook and a real parity test is specified, **but** only if the import is guarded (S-c). As written, an unguarded top-level import could change flag-OFF behavior. |
| 3 | **Hash-bound governance** | **PASS** — single-use owner activation naming SHA-256 + implementer + HEAD + ≤24h window (§Activation 2–3); flag-flip is a further owner act (§Activation 4); standing auth explicitly rejected (record L6–9). Correct. |
| 4 | **Ceiling / scope** | Mostly PASS — 4-file ceiling is sufficient and not over-broad; Nix-option deferral (env-read now, declare on activation) is Rule-13-consistent. **But** the "one function only" intra-file constraint conflicts with fixing B1 and must expand (still 4 files). |
| 5 | **F3 faithfulness** | Partial — S1 epoch check present but mechanism has the S-a gap; S3 (task-monotonic strip / can't-downgrade) faithfully carried as F3(2); S4 posture present but detection missing (B2); F3 tests (1)(2)(3) present and correctly assigned to C2. Intent faithful; two mechanisms need the fixes above. |
| 6 | **Integration risk** | Addressed by S-c (guarded import + fail-closed wrapper) and N1 (import path already wired). Not currently specified in the record; low effort to close. |

---

## Bottom line
Structure, governance, and F3 intent are sound and the reused C0/C1 primitives fit. **REVISE** on two
BLOCKING fail-open paths (B1 initial-admission bypass; B2 DEV-key trust-root bypass) that contradict
the slice's own goal, plus four SHOULD-FIX items that harden the epoch, issuance-mapping, import, and
remote-scope surfaces. All fixes are additive within the 4-file ceiling (the switchboard.py edit
spanning >1 function is the only structural change). Re-review the revised record before any freeze;
do **not** present an owner activation line until B1 and B2 are closed.
