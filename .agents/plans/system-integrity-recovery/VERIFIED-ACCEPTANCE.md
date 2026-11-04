# Verifiable owner acceptance in plan tracker.json (design, MVP)

Status: DESIGN rev3 (rev2 addressed Codex `codex-20261030-104844-nmbvae`; rev3 addressed `codex-20261030-105109-yk8zz8`; rev4 addressed `codex-20261030-111413-zhgwlq`; rev5 addresses `codex-20261030-111538-15shx7`; R-sections below OVERRIDE any conflicting earlier text, later revs overriding earlier). Owner decision 2026-10-30. Author lane: Claude (design only, no code changed).
Orchestrator decisions: applies to all 135; owner batch approval targets the SIGNED path (activation chain rev7 envelopes with new `accept` / `wave-accept` / `reject` ops); `recorded` is interim evidence and never means owner-verified.
Subject: `acceptance: {status: accepted, by: "hyperd", ...}` is self-asserted text. `scripts/ai/aq-pm-tracker` `_is_owner_acceptor` (line ~635) trusts the literal and projects SHIPPED.

## 0. Findings that change the brief

1. **135 owner acceptances are unbacked, not ~54.** 54 came from `d33064f5` (tools 15 + services 23 + requirements 16). The other 81 came from earlier/later commits (`7d92701b`, `95906b55`, `1f6b72a4`, `d2124062`, `508d5ebc`, ...; 7 carry `by: "hyperd (owner directive 2026-09-26)"`). All have the same shape `{status, by, date, note}`, no approval reference. Earlier cleanups (`4f66bfaa`, `b5e51e60`, `c8543466`) already removed other fabricated ones, so this is a recurring class. The design covers all 135; the owner can still start with the 54.
2. **`aq-approve` records are same-user forgeable.** Everything it writes is owned by the agents' own OS user: attention queue `.agents/attention/ATTENTION.json` and `ATTENTION_ARCHIVE.jsonl` (repo checkout, gitignored), and `/var/lib/nixos-ai-stack/optimizer/prsi/approval-inbox-audit.jsonl` (`hyperd users 0644`). The audit line hardcodes `"by": "owner"` and the actor is `pwd.getpwuid(uid)`, i.e. the same `hyperd` an agent runs as. Any agent can append an approved archive line or an audit line. `review` requires a TTY, but an agent can also hold a TTY (activation-pipeline rev4 reached the same conclusion). So an aq-approve record is **evidence of a decision, not authentication of the owner**.
3. **The existing, already-designed trust anchor is the activation chain** (`.agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md` rev7): root-owned Ed25519 key, `sudo aq-activation-sign` needing a freshly typed password (sudo `timestamp_timeout=0`, merged in `1e121747`), root-owned hash-chained log in `/var/lib/aq-activation/log/`, store-installed verifier `activation_verified(...)`. It is not built yet (branch `feat/activation-signing-core` is currently at main `1e121747`, no diff to read).
4. **`UNVERIFIED` is already a projected status** (untrusted-author hold, 40%, `_STATUS_PCT_FLOOR`, kanban column, `held` counters). A new status named like it would collide. Hence the flag design in section 2.
5. The 135 acceptances are not all "good". The activation triage (`.agents/delegation/outputs/activation-triage/{capabilities,services-tools,remaining}.json`) covers 130 of them: LIVE vs NEEDS-WIRING / NEEDS-ENABLE / BROKEN / NOT-RUNTIME (5 verdict classes, per-item `dims` evidence). 5 items have no triage row (3 in `aqos-requirements-inventory`, 1 in `aqos-services-inventory`, 1 in `capability-integration`). Many will deserve a reject.

## Rev5 changes vs codex-20261030-111538-15shx7

| # | Finding (MEDIUM) | Rev5 change | Where |
|---|---|---|---|
| 1 | Amendment B promised to reject delete-and-recreate of identical bytes, which is unobservable (same git tree) | All delete-and-recreate claims and tests removed; rejection defined only on observable state (a)-(e); unchanged full allowlist and identical recreated bytes explicitly permitted | R4 (rev5 amendment C, supersedes B's failure list) |

## Rev4 changes vs codex-20261030-111413-zhgwlq

| # | Finding (sev) | Rev4 change | Where |
|---|---|---|---|
| 1 | No-reintroduction vs stale base (MEDIUM) | Gate fetches origin/main (fail closed); candidate must be a subset of the intersection of the allowlist at the merge-base AND the current origin/main tip | R4 (rev4 amendment A) |
| 2 | Bootstrap predicate not exact (MEDIUM) | Bootstrap passes only under one exact predicate; every other state is judged by amendment C (rev5) | R4 (rev4 amendment B) |
| - | R1 overclaim (softened) | `--expect` binds the supplied digest; it does not prove display occurred (accepted limit of `recorded`) | R1 |

R1, R3 and the rest of rev3 were accepted by Codex and are unchanged.

## Rev3 changes vs Codex codex-20261030-105109-yk8zz8

| # | Finding (sev) | Rev3 change | Where |
|---|---|---|---|
| 1 | Decision authority across logs (HIGH) | Signed decisions govern exclusively once any verified one exists; recorded can never supersede, clear or satisfy them; independent counters, no cross-log ordering | R3 (rev3 amendment) |
| 2 | Recorded approval not bound to display (MEDIUM) | `aq-approve approve N --expect <full wave digest>` required for `pm-acceptance` entries; mismatch refuses | R1 (rev3 amendment) |
| 3 | Allowlist reintroduction (MEDIUM) | Subset-or-equal vs baseline plus mandatory no-additions check against the trusted integration base (origin/main merge-base, not caller-selectable, unavailable fails closed) | R4 (rev3 amendment) |

Rev2 table below is retained for history; R2, R5, R6, R7 were accepted by Codex and are unchanged.

## Rev2 changes vs Codex codex-20261030-104844-nmbvae

| # | Finding (sev) | Rev2 change | Where |
|---|---|---|---|
| 1 | Batch approval not bound to what owner saw (HIGH) | Immutable frozen wave with `wave_digest`; show, approve and sign operate on that exact digest; payload change = new wave | R1 |
| 2 | Rejection lacks stale-state guard (HIGH) | Reject also requires matching acceptance hash; stale items preserved with allowlist entries; conflicts reported | R2 |
| 3 | Hash binding does not stop replay (HIGH) | Sequenced decision log; verification checks the LATEST decision per (plan,item); later reject supersedes earlier approve | R3 |
| 4 | Allowlist bootstrap/comparison contract (HIGH) | Baseline of the 135 tuples frozen in a committed file whose digest is pinned in the tier0 check; missing/recreated/duplicate/unavailable-base all fail | R4 |
| 5 | Signed fail-closed contract (MEDIUM) | `signed` only on successful verification under a healthy trust boundary; malformed signed refs are validation errors; no fallback to `recorded` | R5 |
| 6 | Labels/counts inconsistent for ACTIVATED (MEDIUM) | Status preserved in every label; marker only on SHIPPED; `shipped_unverified` defined; coverage list; dated deferral for templates | R6 |
| 7 | Slices miss promised tests/observability (MEDIUM) | Slice deliverables extended; slices 1-2 declared interim recorded-evidence delivery | R7 + section 8 |

### R1. Frozen wave (supersedes rev1 section 3 "Queue content" and "On approve")
- `aq-pm-acceptance-queue push` builds a **wave** document, written once and never edited: `{schema, wave_id, plan, class, items:[{id, acceptance_sha256, triage_file, verdict, triage_row_digest}]}`, items sorted by id. `wave_digest = sha256(canonical JSON of the wave document)`. The wave file is stored append-only under `.agents/attention/waves/<wave_digest>.json` (host) and the same bytes are committed later in the decision record.
- The attention entry only points at the wave: `payload = {wave_digest}`, plus a human summary. Dedup/in-place update is **disabled** for `source=pm-acceptance`: if the item set, any acceptance hash or any evidence digest changes, `push` creates a NEW wave and entry and marks the old entry superseded (resolved `deferred`, never approvable). Re-push for TTL renewal only extends `expires_at` when the recomputed `wave_digest` is identical.
- `show` prints the full item table AND the `wave_digest`; the handler recomputes the digest from the stored wave file at approve time and refuses on mismatch (file altered, entry payload altered, or wave replaced). Numbered `approve N` therefore binds to the digest the owner saw only if `show`/`list` printed it: `list` shows the first 12 hex of `wave_digest` per entry and the approve audit line records the full digest.
- Signed flow: `sudo aq-activation-sign --wave <wave_digest>` loads the same stored wave bytes, displays every item and the digest, and the signed envelope (`op: "wave-accept"` or `"wave-reject"`) includes `wave_digest` and the sorted item tuples. The verifier only counts an item decided by a wave when its exact tuple is in the signed list.
- Tests: mutate the wave file, the entry payload, the item set, an evidence digest and an acceptance hash between `show` and `approve`/`sign`; every case refuses and signs/approves nothing.

**Rev3 amendment (recorded approval binding).** For `source=pm-acceptance` entries `aq-approve approve N` is REFUSED unless `--expect <full 64-hex wave_digest>` is given (the digest comes from `aq-approve show`, which prints it in full; `list` prints only the prefix). The handler checks, in order: `--expect` equals the full digest; the stored wave file hashes to it; the entry's `payload.wave_digest` equals it. Any mismatch refuses and records a failed audit line. `--expect` binds the digest the caller supplies to the stored wave; it does NOT prove that a display occurred (an agent running as the owner's user can read the digest itself). That is an accepted limitation of `recorded` (the signed path shows and signs the exact wave under the owner's sudo password). (Chat door: the same flag; `deny` needs no digest but records the digest it acted on.) A display-session token is not used (extra state, same guarantee). Test: after `show`, substitute the entry pointer with a different but internally valid wave (its own file hashes correctly); `approve N --expect <old digest>` refuses; `approve N` without `--expect` refuses; with the new digest it works only if the owner re-ran `show`.

### R2. Rejection and staleness (supersedes rev1 reconcile bullets)
- `reconcile` handles BOTH outcomes per item only when the tracker item's current `acceptance_sha256` equals the wave tuple's hash. Otherwise the item is `stale`: tracker untouched, its allowlist entry preserved (rejected or approved alike), and the item is reported in a conflict list printed by `reconcile` and included in the PR body. Removal from the allowlist happens only for items actually changed.
- A stale item is re-queued in a fresh wave (new hash), never decided by the old wave.
- Tests: reject-after-change (acceptance edited after the wave froze: reject does not delete the newer block; conflict reported; allowlist entry intact); approve-after-change; partial wave (some stale, some current).

### R3. Current-decision rule (supersedes rev1 section 2 "Binding hash" as sole authority)
- Decisions are sequenced. Signed path: the activation-chain envelope `seq` (monotonic, hash-chained, root-owned). Recorded path: an append-only decision log `.agent/approvals/acceptance/LOG.jsonl` (committed, one line per decision: `{dseq, plan, item, acceptance_sha256, decision, wave_digest, record}`, `dseq` strictly increasing, verified contiguous; any gap, duplicate or edit of a prior line fails).
- Effective decision for `(plan, item)` = the highest-sequence decision across the applicable log for that key (any hash). An `approved` ref is valid only if (a) its hash equals the current acceptance hash AND (b) it IS the latest decision for that key. A later `rejected` decision, or a later approve of a different hash, supersedes it. A rejection is permanent for that hash: restoring the old block and the old `approval_ref` stays invalid until a NEW approve with higher sequence.
- Signed ops: `accept`, `wave-accept`, `reject`, `wave-reject`; per-item state machine (none -> accepted -> rejected -> accepted only by a later individual or wave accept with higher `seq`), mirroring the rev7 grant/revoke machine. A `wave-accept` cannot clear a `reject` with a lower or equal seq.
- Tests: approve -> reject -> restore old block and old ref (must fail); approve -> reject -> new approve (passes); approve -> change block -> approve new hash (old ref fails, new passes); log gap/duplicate/edited line fails.

**Rev3 amendment (decision authority; overrides the "highest sequence across the applicable log" sentence above).** The two logs have independent counters and are NEVER ordered against each other (no cross-log `dseq` vs `seq` comparison; a huge forged `dseq` has no meaning against a signed `seq`).
- If ANY verified signed decision exists for `(plan, item)`, only the latest verified signed decision governs. Recorded decisions cannot supersede, clear, revoke or satisfy it; they are ignored for that key (and a recorded decision that contradicts it is reported as `conflict` in `assurance_reason`).
- Recorded decisions govern only when NO signed decision exists for the key, and then yield at most `recorded` assurance (latest recorded decision by `dseq`, hash match required, per rev2 R3).
- "Verified" means the R5 conditions hold; signed decisions that fail verification do not count as existing (the key falls back to recorded rules only if the chain itself is healthy and the signed op is simply absent; an unhealthy boundary gives `unverified` per R5).
- Tests: signed approve then fabricated recorded reject with a huge `dseq` -> still governed by the signed approve (`signed`); signed reject then fabricated recorded approve with a huge `dseq` -> still rejected (acceptance invalid); no signed decision, recorded approve then recorded reject -> rejected; signed absent and recorded approve -> `recorded` only.

### R4. Allowlist baseline and comparison contract (supersedes rev1 validator rule 2 and tier0 item 2)
- The 135 `(plan, item, acceptance_sha256)` tuples are generated once, sorted, into `config/pm-tracker-unbacked-owner-acceptances.baseline.json` (committed in slice 1). The tier0 check script itself contains the baseline file's `sha256` as a literal (`BASELINE_SHA256=...`) and, when the Nix-built check exists, the same digest is injected from Nix. Changing the baseline therefore requires editing the gate script, which is review-visible.
- The live allowlist `config/pm-tracker-unbacked-owner-acceptances.json` must satisfy: (1) is a strict subset of the baseline tuples; (2) no duplicate tuples or duplicate `(plan,item)` keys; (3) file present and parseable, else FAIL when present at base (per amendment C(a); removal of entries is valid only with the matching tracker change, C(e)); (4) base comparison via the existing merge-base/ref resolution is a second check only; an unavailable or unresolvable base FAILS CLOSED (no "treat current as base" exception once the baseline exists). The baseline pin, not the git base, is the root of trust, so a caller cannot weaken it by choosing a base.
- Mandatory invocation: `aq-pm-tracker --check-owner-acceptance` is called unconditionally from `check-pm-tracker.sh` (no skip when the tracker script is missing, unlike the existing SKIP branch, which must FAIL for this check), from `tier0-validation-gate.sh --pre-commit`, and from the CI workflow that runs tier0. A CI/pre-commit lint asserts the call line exists.
- Tests: add a tuple, replace a hash, delete the allowlist, duplicate tuple, unavailable base, tampered baseline vs pinned digest, removed gate invocation line.

**Rev3 amendment (reintroduction).** Rule (1) becomes "subset-or-equal vs the frozen baseline" (equality is valid at bootstrap). Add a mandatory historical no-additions check: every `(plan,item,acceptance_sha256)` tuple in the candidate allowlist must be present in the allowlist at the trusted integration base. The base is resolved ONLY by the gate: `origin/main` merge-base then `origin/main` tip (the existing `_resolve_legacy_base` order); there is no flag, env var or argument to choose a base, and the check function takes no base parameter outside tests. Unresolvable base, missing file at base once the baseline exists, or a git error -> FAIL closed. Consequence: a tuple removed in a merged commit can never return, even with the old acceptance block restored, because it is absent at the base.
- Tests: bootstrap (candidate equals baseline, base lacks the file but baseline pin present) passes; remove a tuple on main then a branch reintroduces it with the acceptance block restored -> fails; a caller-supplied weaker base (env var, CLI flag, `--base HEAD`) is rejected/ignored and the check still compares against origin/main.

**Rev4 amendment A (stale-branch reintroduction; supersedes the base rule in the rev3 amendment).** The gate first runs `git fetch origin main` (bounded timeout); failure to fetch, or no resolvable `origin/main`, FAILS closed (no offline pass). It then reads the allowlist at BOTH the merge-base and the freshly fetched `origin/main` tip. Every candidate tuple must be present in BOTH, i.e. candidate is a subset of (allowlist@merge-base ∩ allowlist@tip). A tuple removed on main after the branch point is absent at the tip, so a stale branch cannot restore it with its acceptance block. The base remains gate-resolved only (no flag/env/argument). Test: branch before removal; remove the tuple on main; on the stale branch restore the tuple and the acceptance block -> fail; same branch rebased and still carrying the tuple -> fail; offline (fetch fails) -> fail.

**Rev4 amendment B (exact bootstrap predicate; replaces the "equality allowed at bootstrap" wording and the "treat current as base" exceptions).** Bootstrap passes if and only if ALL hold: (1) the baseline file `config/pm-tracker-unbacked-owner-acceptances.baseline.json` does NOT exist at the merge-base and does NOT exist at the origin/main tip; (2) the allowlist file does NOT exist at the merge-base and does NOT exist at the tip; (3) the candidate tree introduces both files; (4) the baseline file's sha256 equals the literal pinned in the gate; (5) the allowlist tuple set EQUALS the baseline tuple set (no duplicates). Any other state is judged ONLY by amendment C. (Superseded: earlier wording about delete-and-recreate; identical recreated bytes are the same git tree and are treated as unchanged.) Tests: initial bootstrap (both absent at base, candidate adds both, digest pinned, sets equal) passes; bootstrap with a different digest or unequal sets fails.

**Rev5 amendment C (observable-state rejection; supersedes the failure list and test list of amendment B).** After bootstrap the gate FAILS if and only if one of the following observable conditions holds (no other condition, and no claim about file history that git cannot show):
- (a) the baseline file or the allowlist is missing in the candidate while present at the origin/main tip or the merge-base;
- (b) the baseline file's sha256 differs from the pinned literal;
- (c) inconsistent historical presence: exactly one of the two files exists at the tip or at the merge-base, or presence differs between merge-base and tip in any way other than "absent at both then bootstrapped" / "present at both and unchanged";
- (d) outside bootstrap, any candidate tuple is not in (allowlist@merge-base ∩ allowlist@tip), or is not in the baseline, or is duplicated;
- (e) an allowlist removal (tuple present at merge-base or tip, absent in candidate) without the corresponding tracker change in the same diff: the item's acceptance block removed, or an `approval_ref` added that validates under R3/R5. A removal with no such tracker change fails; the allowlist cannot be shrunk to hide an unbacked acceptance that still exists.
Explicitly permitted: an unchanged full allowlist after bootstrap (all 135 tuples present is the normal post-bootstrap state); identical recreated bytes (same git tree, unobservable, treated as unchanged); a candidate that leaves both files untouched.
Tests: (1) initial bootstrap passes; (2) bootstrap with wrong digest or unequal sets fails; (3) unchanged full allowlist after bootstrap passes; (4) file missing in candidate but present at tip fails (a); (5) baseline bytes edited so digest != pinned literal fails (b); (6) base with only one of the two files after bootstrap fails (c); (7) added/replaced tuple, duplicate tuple, stale-branch reintroduction (amendment A scenario) fail (d); (8) allowlist tuple removed with no tracker change fails (e), the same removal with the acceptance block removed passes, and with a valid `approval_ref` added passes; (9) unavailable base or failed fetch fails closed. (The earlier delete-and-recreate test is dropped: it is unobservable.)

### R5. Signed fail-closed contract (supersedes rev1 section 1 degrade text)
- `acceptance_assurance` returns `signed` only if ALL hold: the ref is a well-formed signed form; the installed verifier validated the chain to the root-owned head; the signature verifies against the store allowlist; op/domain/identity/wave membership match; the item's latest decision (R3) is accepted with matching hash; and the effective-authority audit result (sudo boundary) reported healthy. If the trust boundary is unhealthy or unverifiable, every signed ref evaluates to `unverified` with `assurance_reason`; it is never reported as `recorded` or `signed`.
- A ref that matches neither the recorded nor the signed shape, carries both shapes, has unknown keys, or has a malformed signed form is a **validation error** (`--check` fails), never a fallback to `recorded`. A signed ref is never satisfied by a recorded record.
- Signer slice review must establish and test: envelope binds `(plan,item,acceptance_sha256,wave_digest)` under a domain-separated `accept`/`reject` prefix (operation separation from grants); revocation by `reject`; the sudo boundary audit result consumed by the verifier. Until slice 3 exists none of this is claimed.

### R6. Labels, counts, coverage (supersedes rev1 `status_label` and counters)
- `status_label = "<projected status>" + marker`, where the projected status is never rewritten: ACTIVATED stays `ACTIVATED`, SHIPPED stays `SHIPPED`, UNVERIFIED (hold) stays `UNVERIFIED`. Marker `" (unverified)"` is appended ONLY when status is SHIPPED and assurance is `unverified`; `" (recorded)"` only when status is SHIPPED and assurance is `recorded`; ACTIVATED items carry no marker (their authority is the activation grant) but the raw `acceptance_assurance` field is still emitted.
- `shipped_unverified` = count of items with status exactly SHIPPED and assurance `unverified`; ACTIVATED and held items are excluded. Also emit `shipped_recorded`. Existing `shipped` and `held` semantics are unchanged.
- Required coverage: `project()` per-plan JSON, `--all-json` aggregate (per-plan and program totals), `GET /api/pm/progress` passthrough (field survives `pm.py`), human output (`aq-pm-tracker <plan>` and `--all`), dashboard chip/kanban/counter, a plan with a provenance-hold item (status UNVERIFIED keeps its own marker rules), and an ACTIVATED item with an unbacked acceptance.
- Factory templates `templates/factory-kit/pm-tracker/projector.py` and `templates/factory-gate-bundle/pm-tracker/projector.py`: dated deferral, owner = orchestrator lane (Claude), recorded in `.agent/WORKAROUND-REGISTER.md` as `{symptom: template projector lacks acceptance_assurance, root cause: generated copies of the projector, fix-path: regenerate/sync templates from scripts/ai/aq-pm-tracker after slice 2 lands, class: parity, severity: medium}`, due 2026-11-30, plus a backlog entry; the template self-tests must not claim the new field.

### R7. Slice scope additions (see section 8, which is updated)
Slice 1 and 2 are INTERIM recorded-evidence delivery: nothing in them proves the owner decided; labels say `recorded`/`unverified`. Owner-authenticated acceptance depends on slice 3 and the signer audit.

## 1. Decision: which trust anchor

Two verification levels behind ONE verifier function, `acceptance_assurance(plan, item) -> "signed" | "recorded" | "unverified"`.

| Level | Backing | Who can forge it | Ships |
|---|---|---|---|
| `recorded` (L1) | approval_ref to a committed decision record derived from an `aq-approve` resolution; hash-bound to the exact acceptance block | any process running as the owner's OS user (it can write the archive, the record file and compute the hash) | slice 1-2 |
| `signed` (L2) | approval_ref to an owner-signed envelope (`op: "accept"` / `"wave-accept"`) in the root-owned activation chain, verified by the store-installed verifier | nothing running as the owner's user: needs the root key, which needs the owner's typed sudo password | slice 3, after the signer ships |

Recommendation: **build the L1 plumbing now, make L2 the target, and keep the two honestly labelled.** L1 stops fabrication by accident, by a careless agent, and by drift (a hand-typed "accepted" no longer works; each acceptance must trace to a real decision record naming the exact items and hashes). It does NOT stop a deliberately adversarial agent with the owner's uid. That boundary is stated in the dashboard label (`recorded`, not `verified`) and here. Reusing the activation chain for L2 (rather than inventing a second signer) avoids a second key, second verifier, second sudo path; it only adds two ops to the envelope grammar.

Why not make aq-approve itself the final anchor: its stores are all same-uid writable (finding 2). Hardening them would mean a second root-owned store, i.e. rebuilding the activation signer.

Forgery boundary, stated plainly:
- L1: a same-uid agent can fabricate a record, a hash and an archive line. Detection only (the owner can see "recorded" and that no signed envelope exists). Mitigations that are cheap: record file lives in git, so the forgery is a visible PR diff that needs independent review (Reviewed-by trunk protection); the host-side check cross-reads the local archive/audit and flags a record with no matching resolved alert (catches a forged file with no archive line, not one with both).
- L2: not forgeable without the owner's fresh sudo password, provided the sudo boundary audit passes (activation-pipeline item 3). If that audit fails, nothing is `signed` (see R5): items show `unverified`/`recorded`, never silently promoted.

## 2. Tracker schema

Owner acceptance block gains one field:

```json
"acceptance": {
  "status": "accepted", "by": "hyperd", "date": "2026-10-30", "note": "...",
  "approval_ref": {"record": ".agent/approvals/acceptance/attn-3f9a....json",
                   "sha256": "<64 hex of the record file bytes>"}
}
```
L2 form (slice 3): `"approval_ref": {"envelope_seq": 17, "envelope_sha256": "<64 hex>"}`.

Binding hash (`acceptance_sha256`): sha256 of canonical JSON (sort_keys, `(",",":")`) of `{"plan": <dir name>, "item": <id>, "acceptance": <block minus approval_ref>}`. Editing note/date/by, or moving the block to another item, changes it and invalidates any reference.

Decision record (committed, written by the reconcile step in a PR, never hand-edited), `.agent/approvals/acceptance/<alert-id>.json`:
```json
{"schema": 1, "kind": "tracker-acceptance", "alert_id": "attn-...", "decision": "approved",
 "resolved_at": "...", "resolved_by": "hyperd:owner", "door": "chat", "tag": "ab12cd34",
 "plan": "aqos-tools-inventory",
 "items": [{"id": "tool-rtk", "acceptance_sha256": "...",
            "triage": {"file": "capabilities.json", "verdict": "NEEDS-WIRING", "digest": "<sha256 of that triage row>"}}]}
```

Validator rules (`validate_manifest`, owner branch, currently `continue` at line ~884; `--check` of every tracker):
1. owner acceptor with `approval_ref` -> structural check (record path repo-relative under `.agent/approvals/acceptance/`, no `..`, 64-hex hash, file exists, sha256 of bytes equals ref, `schema==1`, `decision=="approved"`, record lists `(plan, item)` with `acceptance_sha256` equal to the recomputed hash). Any failure is an error (not a warning).
2. owner acceptor WITHOUT `approval_ref` -> allowed only if `(plan, item, acceptance_sha256)` is in `config/pm-tracker-unbacked-owner-acceptances.json` (frozen allowlist of the 135, remove-only, same mechanics as `config/pm-tracker-legacy-acceptances.json`; reuse `_resolve_legacy_base` and the `legacy_additions` pattern). Otherwise error: "owner acceptance has no approval_ref; request one through aq-approve". Allowed entries count as a WARN `N unbacked owner acceptances (grandfathered)`, like `GRANDFATHERED_ACCEPTANCES`.
3. `_is_owner_acceptor` keeps its meaning (it only classifies who the block claims to be). Its comment is updated: trust comes from rules 1-2, not from the literal.

"Unverified" representation: **a flag, not a new status.** `status` stays `SHIPPED` (or `ACTIVATED`), so precedence, `_STATUS_PCT_FLOOR`, rollup, `shipped` counters, kanban columns and the existing `UNVERIFIED` hold keep working. The projection adds, per item:
- `acceptance_assurance`: `"signed"` | `"recorded"` | `"unverified"` | `null` (no owner acceptance involved)
- `status_label`: see R6 (the projected status is always preserved; the marker applies to SHIPPED only).
and per plan / aggregate: `shipped_unverified` (count) next to `held`. Rollup pct is unchanged (owner asked for a label, not a score cut; revisit if wanted: one constant). If an item is also under the untrusted-provenance hold, status is `UNVERIFIED` as today and the flag is still reported.

Where it is computed: a new pure helper `acceptance_assurance(item, plan)` called from `project()` and the aggregate builder (the two places that build item dicts, around lines 515-530 and 590-605). `project_item` / `project_item_full` are NOT edited (see section 5).

Consumers to update (found by `rg SHIPPED|UNVERIFIED`):
| Consumer | Change |
|---|---|
| `scripts/ai/aq-pm-tracker` human printers (lines ~932, ~982) | print `, N SHIPPED (unverified)`; item lines use `status_label` |
| `dashboard/backend/api/routes/pm.py` | none (passes `--all-json` verbatim); add a test that the field survives |
| `assets/aqos-progress-tracker.html` (chip `data-status`, kanban, `STATUS_ORDER` at line ~560, CSS lines ~330, ~377) | chip keeps `data-status="SHIPPED"`, add `data-assurance`; dashed green border + text `(unverified)` / `(recorded)`; header counter. No new kanban column |
| `scripts/testing/test-dashboard-program-progress.py`, `test-pm-tracker-untrusted-hold.py`, `test-pm-tracker-acceptance-authority.py` | extend |
| `scripts/ai/lib/refactor_status.py` | no acceptance parsing today (only comments at line 181); no change. Re-verify with `--check-owner-gates` |
| `templates/factory-kit/pm-tracker/projector.py`, `templates/factory-gate-bundle/pm-tracker/projector.py` | template copies of the projector; out of scope for MVP (generated kits). Record in WORKAROUND-REGISTER / backlog per Rule 16 parity; do not leave silently divergent |
| `scripts/ai/aq-plans-index` (`DONE_MARKERS`) | text markers for plan docs, unrelated; no change |

## 3. Batch approval flow

Queue content (generator `aq-pm-acceptance-queue push`, new small CLI; idempotent via `dedup_key`):
- One attention-queue entry per (plan, triage-verdict-class). Classes: `evidence-clean` (all dims ok, verdict LIVE) and `needs-attention` (NEEDS-WIRING, NEEDS-ENABLE, BROKEN, NOT-RUNTIME, no triage). Roughly 19 plans -> about 30 entries. Rationale: the numbered inbox approves or denies a whole entry, so entries must be homogeneous enough that "approve all" is a sane decision. LIVE-clean batches are the fast path; the needs-attention ones are where the owner will mostly reject.
- Entry fields (existing `push()` API; nothing new in `attention_queue.py`): `source="pm-acceptance"`, `autonomy_boundary="human_gate"`, `executor="tracker_acceptance"` (puts it in the inbox "approval" section, `approval_inbox.collect_with_status` line ~134), `severity` by class, title `<plan>: accept N items (<class>)` (<=80 chars), `payload = {plan, items:[{id, acceptance_sha256, triage_file, verdict, digest}]}`, `detail` = one line per item with verdict and the failing/unknown dims and `next_action` from triage, `why` = "owner acceptance has no approval record", `ttl_s=604800` (max). Because TTL max is 7 days, `push` is re-run (dedup updates in place, `expires_at` renewed) by the same weekly job that already pushes alerts; an expired entry just reappears.
- Owner sees: `aq-approve` lists numbered entries; `aq-approve show attn-...` prints the per-item evidence; `aq-approve review attn-...` prompts y/N (TTY). `show` is extended (existing `_print_apparmor_rules` pattern) to print a `tracker_acceptance` payload table: item, verdict, dims, next action. The batch numbers work as today: `aq-approve approve 3 4 --tag T --door chat` / `deny 5`. Per-item exceptions inside an entry are not supported in the numbered flow (MVP); the owner denies the entry and the generator re-pushes a narrower one, or the item stays in the unbacked allowlist.
- On approve: `_EXECUTOR_TABLE["tracker_acceptance"]` handler only validates the payload shape and returns True (side effect-free: aq-approve runs in the main checkout, which must not have tracked files edited). The approval itself is the claimed -> `approved` archive line plus the inbox audit line (door, tag, note).
- On deny: existing `attention_queue.resolve(..., "rejected")` path; nothing else at approve time.
- Applying decisions: `aq-pm-acceptance-queue reconcile --worktree <path>`, run by an agent in a slice worktree, reads resolved `source=pm-acceptance` entries from `ATTENTION_ARCHIVE.jsonl` and the audit log, then in the worktree:
  - approved: writes the decision record file (section 2) and sets `approval_ref` on each listed item whose current `acceptance_sha256` still equals the payload hash (if it changed, skip and report: stale);
  - rejected: deletes the `acceptance` block from those items (projection falls back to IN-PROGRESS 85 via `_gate`), with a one-line note in the item `editorial_note`: "owner declined acceptance <date>, record <alert id>";
  - removes the item from `config/pm-tracker-unbacked-owner-acceptances.json` in both cases (approved items are now backed; rejected items have no acceptance).
  The agent opens one PR per reconcile batch (Rule: PR only, bundle). Review-Disposition and non-author Reviewed-by apply as usual; the committed decision records make that diff reviewable.
- New acceptances after the migration use the same path: an agent that wants an item accepted pushes a one-item `pm-acceptance` entry with its own evidence (attestation), the owner approves, reconcile writes the ref. An agent can no longer land a `by: "hyperd"` block without `approval_ref` (validator rule 2).

## 4. tier0.d check

Extend `scripts/governance/tier0.d/check-pm-tracker.sh` (it already runs `--check-legacy-allowlist` and `--check-untrusted-items`) with `aq-pm-tracker --check-owner-acceptance`, exit 1 on any of:
1. owner acceptance with neither a valid `approval_ref` nor an allowlist entry whose `acceptance_sha256` matches (this is the "diff adds or changes an owner acceptance" case, expressed on state, so it also catches history-shaped tricks and edits to the note/date of a grandfathered one);
2. `config/pm-tracker-unbacked-owner-acceptances.json` gained an entry vs merge-base (remove-only; same base-resolution and fail-closed rules as `check_legacy_allowlist`);
3. a decision record file changed or deleted vs base while referenced (records are append-only).
Gate hygiene (Rule 19): this fails only on a regression the change introduces; the 135 grandfathered items WARN, never block.
Lint companion (cheap): `repo-structure-lint` allows `.agent/approvals/acceptance/`.

## 5. Coordination with `feat/activation-signing-core`

That branch edits `aq-pm-tracker::project_item` (the `activation.grant` substring match at ~line 475 and the `accepted`-based ACTIVATED at ~473 both go away behind `activation_verified`). It is in review and at present has no diff against main in the worktree.
- Implementation of this design must be cut from main AFTER that branch merges, then rebased once. Slice 1 deliberately does not touch `project_item`/`project_item_full`; the only shared-hunk risk is the item-dict construction in `project()` / the aggregate builder and `_is_owner_acceptor` neighbourhood if the signing branch also edits `validate_manifest`. Expect small textual conflicts there; resolve by keeping both.
- Semantic interaction: after signing-core, ACTIVATED needs a signed grant, SHIPPED for an accepted item still comes from the `accepted` boolean in `project_item`. `acceptance_assurance` is orthogonal (a label on SHIPPED), so no logic conflict. Ensure the new field is not read by the signing verifier (never let `approval_ref` influence ACTIVATED).
- Slice 3 reuses the signing-core envelope code (new ops `accept` / `wave-accept`, same chain, same `activation_verified`-style verifier module) and must follow the signer MVP round trip.

## 6. Risks

| Risk | Mitigation |
|---|---|
| L1 gives a false sense of security | Labelled `recorded` not `verified`; section 1 states the boundary; L2 is the stated target; when L2 ships, unbacked and `recorded` items both show non-final labels until signed |
| Owner approves LIVE-clean batches without reading, masking weak evidence | Entries carry per-item dims and `next_action`; needs-attention class is separate so "approve all" is never applied to NEEDS-WIRING / BROKEN by accident |
| Rejection storm drops many items from SHIPPED to IN-PROGRESS 85 and the program rollup falls | Intended and honest; announce before reconcile; rollup shown with `shipped_unverified` beside it during the transition |
| Allowlist hash drift (an unrelated edit to a note) re-flags a grandfathered item | Treated as intended: any edit to an owner acceptance needs a real approval |
| Attention TTL max 7 days expires pending entries | Re-push is idempotent; entries are generated state, not the source of truth (the trackers are) |
| Agent writes decision record + archive line itself (L1 forgery) | Visible in the PR diff, independent review required; host check cross-reads archive/audit; closes at L2 |
| Reconcile run twice / stale hashes | Skips items whose current hash differs from the payload; refuses to overwrite an existing record |
| Two projectors diverge (factory-kit templates) | Registered in WORKAROUND-REGISTER with fix-path; not silently ignored |
| Collision with the `UNVERIFIED` hold status | Flag design avoids it; both reported independently |

## 7. Acceptance tests

Unit (`scripts/testing/test-pm-tracker-acceptance-authority.py` extended, offline):
1. owner block without `approval_ref`, not in allowlist -> `validate_manifest` error.
2. same block, `(plan,item,sha)` in allowlist -> passes with WARN, projection `SHIPPED`, `acceptance_assurance="unverified"`, `status_label="SHIPPED (unverified)"`, rollup pct unchanged.
3. valid `approval_ref` (record present, hash matches, item+sha listed, `decision=approved`) -> assurance `recorded`, label `SHIPPED (recorded)`.
4. tamper matrix, each is an error: wrong record sha; record lists different item; edited `note`/`date`/`by`/moved block (sha mismatch); `decision: rejected`; path `..` / absolute / outside `.agent/approvals/acceptance/`; record missing; schema != 1.
5. allowlist gains an entry vs base -> `--check-owner-acceptance` fails; entry removed -> passes; base unresolvable -> fails closed.
6. a hold (`UNVERIFIED` provenance) item still projects `UNVERIFIED` and reports its assurance flag.
7. non-owner acceptors with receipts are unaffected (existing tests stay green).
Queue/flow (`test-pm-acceptance-queue.py`, temp `ATTENTION_QUEUE_DIR` + `AQ_APPROVAL_INBOX_DIR`):
8. `push` creates one entry per (plan, class) for the fixture, is idempotent on re-run, and entries appear in the "approval" section of `approval_inbox.collect_with_status`.
9. `aq-approve approve N --tag T --door chat` -> entry `approved` in archive + audit line; `deny` -> `rejected`.
10. `reconcile` on approve writes record + `approval_ref` and drops the allowlist entry; on reject deletes `acceptance`; stale hash is skipped and reported; re-run is a no-op.
11. `--check-owner-acceptance` on the reconciled worktree passes.
Live (owner host, Rule 15 attestation): `aq-pm-tracker --all-json` shows the 135 as `unverified` before and the approved subset as `recorded` after; `GET /api/pm/progress` and `/aqos-progress-tracker` render the label (browser check); `aq-approve list` shows the entries; health-spider/dashboard count `shipped_unverified`; intervention = deny / dismiss in the same inbox.
Slice 3: forge test (planted record/archive/audit line by an agent) -> stays `recorded`, never `signed`; owner-signed wave envelope -> `signed`; broken chain -> fail closed to `unverified`.

## 8. Slice plan (cheapest eligible implementer; each after `feat/activation-signing-core` merges)

Slice 1 - schema, validator, projection, gate (INTERIM recorded-evidence delivery; Sonnet implementer; reviewer from another lane)
- `scripts/ai/aq-pm-tracker`: `acceptance_sha256`, `approval_ref` verification, owner-branch rule, `acceptance_assurance` + `status_label` + `shipped_unverified` in `project()` and aggregate, printers, `--check-owner-acceptance`.
- `config/pm-tracker-unbacked-owner-acceptances.json` (generated once from a scan; the 135 entries below).
- `check-pm-tracker.sh` wiring; `assets/aqos-progress-tracker.html` label; tests 1-7; docs (`pm-tracker-standard/DESIGN.md` section on acceptance assurance).
- Activation attestation: integrated (projector + tier0), ON (gate runs every commit), validated (live `--all-json`), observable (dashboard label + count), intervenable (owner approves/denies).

Slice 2 - frozen waves, queue, aq-approve integration, reconcile (INTERIM recorded-evidence delivery; Sonnet; needs slice 1)
- `scripts/ai/aq-pm-acceptance-queue` (push, reconcile) with the aq-usage hook; `tracker_acceptance` entry in `aq-approve` `_EXECUTOR_TABLE` and payload rendering in `show_alert`; tests 8-11; then the owner works the inbox and an agent runs reconcile in a worktree and opens the PR(s). Includes `.agent/approvals/acceptance/` in structure lint.

Slice 3 - signed assurance, the owner-authenticated path and the batch-approval target (after the signer MVP round trip; maybe Fable/Opus-reviewed since it is trust-bearing)
- Envelope ops `accept` / `wave-accept` in the activation chain; verifier returns `signed`; `aq-pm-acceptance-queue sign-wave` prints the one `sudo aq-activation-sign` command for all approved L1 items; L1-only items show `recorded` (or are downgraded to `unverified` by an owner decision once signing is live); forge tests.

Rev2 additions to slice deliverables (R7):
- Slice 1 adds: baseline file + pinned digest + mandatory gate wiring (R4) and tests; R5 shape validation (unknown/ambiguous/dual-shape refs rejected); R6 label/count rules with coverage for aggregate JSON, `pm.py` API passthrough test, human output, dashboard, provenance-hold plan, ACTIVATED+unbacked item; referenced-record modification and deletion tests (record bytes edited or removed -> validation error); append-only enforcement for `.agent/approvals/acceptance/` (tier0 compares to base: no edits/deletes of existing record or LOG lines); health-spider probe + dashboard counter publishing `shipped_unverified`, `shipped_recorded`, and "owner-verified (signed) count = 0 until slice 3" so verification visibility is real, with an alert if unbacked count rises; WORKAROUND-REGISTER entry for templates (R6).
- Slice 2 adds: wave freezing/digest binding and mutation tests (R1), stale-aware two-outcome reconcile and tests (R2), sequenced decision log and replay tests (R3).
- Slice 3 adds: signed ops `accept`/`wave-accept`/`reject`/`wave-reject`, fail-closed contract and tests (R5), forge tests, and the sudo-boundary health input to the verifier.

Not in scope: changing rollup weighting, non-owner acceptor receipts, factory-kit template projectors (registered), ACTIVATED semantics (owned by the activation pipeline).

## 9. Affected items (135 owner acceptances with no approval reference)

Source: scan of `.agents/plans/*/tracker.json` for `acceptance.status == accepted` and `by` in {`hyperd`, `hyperd (...)`} (the exact `_is_owner_acceptor` test), joined to the three activation-triage JSON files. Regenerate with the same scan when building the allowlist; counts: 54 from `d33064f5` (tools 15, services 23, requirements 16), 81 from other commits.

- `approval-control-plane` (9; triage verdicts: {'LIVE': 2, 'NEEDS-WIRING': 7}): prd, designs, p0, p1, p2, p3, p1b, p4, deploy-ui
- `approval-inbox-20261002` (3; triage verdicts: {'LIVE': 2, 'NOT-RUNTIME': 1}): s1, s2, s3
- `aqos-capabilities-inventory` (6; triage verdicts: {'NEEDS-WIRING': 6}): cap-workflows-engine, cap-workflow-canon, cap-role-orchestrator, cap-role-implementer, cap-role-reviewer, cap-commands
- `aqos-installer-experience` (11; triage verdicts: {'LIVE': 9, 'NEEDS-WIRING': 2}): p0-schema, p0-resolver, p0-mysystem-fieldset, p0-hardware-detector, p0-module-catalog, p0-ai-fit-policy, p0-execution-verifier, p1-golden-profile, p1-guided-tui, p1-parity-suite, p2-ai-adapter
- `aqos-requirements-inventory` (16; triage verdicts: {'NOT-RUNTIME': 5, 'none': 3, 'BROKEN': 4, 'NEEDS-WIRING': 1, 'LIVE': 3}): req-foundation-a, req-foundation-b, req-foundation-c, req-approval-control-plane, req-product-d, req-product-e, req-product-f, req-product-g, req-track-v, req-track-s, req-flat-factory, req-herdr, req-hard-rules, req-agent-parity, req-observability-parity, req-guest-init-evaluation
- `aqos-services-inventory` (23; triage verdicts: {'LIVE': 16, 'NEEDS-WIRING': 5, 'none': 1, 'BROKEN': 1}): svc-aidb, svc-coordinator, svc-switchboard, svc-drop-daemon, svc-otel-tempo, svc-aidb-reindex, svc-crystallize, svc-pgvector, svc-health-spider, svc-stack-health, svc-mcp-process-watch, svc-security-audit, svc-npm-monitor, svc-mcp-integrity, svc-audit-sidecar, svc-autonomous-improvement, svc-training-ingest, svc-local-training-loop, svc-prompt-eval, svc-lore-sync, svc-nvd-sync, svc-knowledge-sync, svc-qa-pipeline
- `aqos-tools-inventory` (15; triage verdicts: {'NEEDS-WIRING': 7, 'LIVE': 7, 'BROKEN': 1}): tool-rtk, tool-headroom, tool-lean-ctx, tool-delegate-local, tool-delegate-codex, tool-delegate-antigravity, tool-aq-loop, tool-mcp-coordinator, tool-mcp-aidb, tool-mcp-github, tool-osint-bbot, tool-osint-maigret, tool-osint-mosaic, tool-aq-pm-tracker, tool-aq-event
- `capability-integration` (10; triage verdicts: {'BROKEN': 1, 'none': 1, 'LIVE': 4, 'NEEDS-WIRING': 3, 'NEEDS-ENABLE': 1}): ci-1, ci-2, ci-3, ci-4, ci-5, ci-6, ci-7, ci-8, ci-9, ci-10
- `coordination-safety-worktree-isolation` (3; triage verdicts: {'LIVE': 2, 'NOT-RUNTIME': 1}): cs-1, cs-2, cs-4
- `ecc-parity-integration` (4; triage verdicts: {'LIVE': 2, 'NEEDS-WIRING': 2}): p0-b, p0-c, p0-e, p1
- `factory-gate-templates` (4; triage verdicts: {'NEEDS-WIRING': 4}): ft-4, ft-5, ft-6, ft-7
- `factory-shared-toolchain` (1; triage verdicts: {'LIVE': 1}): st1-owner-activation
- `frontier-evidence-intake` (7; triage verdicts: {'NEEDS-WIRING': 5, 'LIVE': 2}): fa-1-backlog, fa-1b-sources, fa-1c-relevance, fa-2-context-seams, fa-3-autofold, fa-4-scan-refresh, fa-5-parity-backstop
- `herdr-agent-operations` (2; triage verdicts: {'NOT-RUNTIME': 1, 'NEEDS-ENABLE': 1}): h0-intake, h1-package
- `local-context-supply-chain` (3; triage verdicts: {'LIVE': 3}): csc-assembler, csc-readfile-gate, csc-nocommit-structural
- `network-profile-interoperability` (4; triage verdicts: {'LIVE': 2, 'NEEDS-ENABLE': 1, 'NEEDS-WIRING': 1}): n0, n1, n2, n2-gate
- `portfolio-classification` (3; triage verdicts: {'LIVE': 1, 'NEEDS-WIRING': 1, 'NOT-RUNTIME': 1}): coverage-dashboard, reconcile-plan-classifications, route-child-work
- `prsi-rsi-merge-20261002` (7; triage verdicts: {'LIVE': 7}): m1, m2, m3, m4, m5, m6, m7
- `rsi-takeover-20261002` (4; triage verdicts: {'LIVE': 2, 'NOT-RUNTIME': 1, 'NEEDS-WIRING': 1}): r1, r2, r3, resume-ttl
