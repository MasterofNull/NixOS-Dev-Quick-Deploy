# Track S S0-A — Claude Confirmatory Catch-Up Review

**Verdict:** `CONFIRM-PASS` (codex's PASS holds)
**Review class:** independent CONFIRMATORY catch-up pass (returning Claude lane, Rule 18)
**Reviewer:** `claude-opus-track-s-s0a-confirmatory` (Opus 4.8; distinct from implementer + from codex acceptance reviewer)
**Review date:** 2026-07-29
**Mode:** read-only — no edits, stage, or commit. Verified against source, not receipts.

## What this pass is

Codex independently reviewed Track S S0-A and its AM1 correction and issued the
authoritative acceptance signal (REQUEST_REVISION on the original candidate →
AM1 required-design → PASS). Per the agent-agnostic catch-up queue, this is the
returning-Claude confirmatory pass: re-derive the verdict from the actual files
and either confirm the PASS or surface a real defect. I confirm it. No defect
opens a follow-up; two advisory notes are recorded below (neither blocking).

## Subject verified (live working-tree hashes)

| Path | State | SHA-256 |
|---|---|---|
| repo HEAD | frozen | `107f7e8ab2452b4d89ff737b28966e35bf4f9e24` (matches) |
| `config/schemas/agent-capability-intake-candidates.schema.json` | new (`??`) | `d080957ba3da3282f424d6351496146cccbf664ee1d1fe3c10139313adf87c78` |
| `config/agent-capability-intake-candidates.json` | modified (`M`) | `ab5d56ac93bceb1991470c96c429a6ec86554ed5865bfaab5bcf6110ae0ae1fb` (= AM1 frozen registry input) |
| `scripts/ai/aq-capability-intake` | modified (`M`) | `cdf59fc53a5c569bd9fa5945eec34fec07aefa71fdda0c1783b9a1bc78242f83` |
| `scripts/testing/test-capability-intake.py` | modified (`M`) | `cd4aaebf4d21ff570f3ab5433fef0d56575e9ad975af9b810214502884f7259c` |

The uncommitted slice is the union of the original S0-A ceiling (schema/registry/test)
and the AM1 corrective ceiling (schema/CLI/test) — exactly four files, all inside the
two hash-bound authorizations. Registry stayed byte-frozen at `ab5d56ac…` across AM1
as the AM1 authorization required. No fifth path, no writer overlap.

## Confirmed axes

### 1. Scope & egress escape — CONFIRM-PASS
PRD §2 makes default mode passive/offline; active probes require a signed scope
receipt from the **existing** `t3mp3st` validator (PRD §2, plan gate 3) with no second
signer/normalizer/receipt store. Verification rejects replay, clock skew,
CNAME/IPv4/IPv6 expansion, redirect escape, DNS rebinding, shared CDN/cloud, and
wildcard ownership; public targets denied absent a separate program-scope receipt.
At S0-A itself there is **no egress surface at all** — all three new records are
`network:false`, `disabled-external-repo`, `disabled-until-intake`, zero tools.
Egress enforcement code is honestly deferred to S2; S0-A cannot reach anything.

### 2. No-hack-back canaries — CONFIRM-PASS (design-level; enforcement is S3)
PRD §2/§7 give an explicit no-retaliation guarantee: no Trojan into attacker systems,
no intrusion-based identification, no probing outside owner authority. Canaries are
ingress-only, inert, initiate no counter-connection, grant no privilege; synthetic
credentials are cryptographically outside every production trust root; collectors are
ingress-only with no callback/counter-connection. Automated-response ceiling is
alert→preserve→isolate→revoke→block→reviewed-report, explicitly barred from deploying
code to or interrogating the source. Correct as a contract. Note faithfully: at S0-A
no canary code exists — the guarantee is enforced-by-design at the contract layer and
lands as running guards in S3. Stated honestly as such; not overclaimed as live code.

### 3. Piyaz A2A / tracker / vector-RAG-DAG without authority duplication — CONFIRM-PASS
PRD §3, plan "Piyaz" section, and the registry record all state piyaz "creates no
lifecycle or data authority" and route accepted patterns to owning tracks via
clean-room extraction. The record carries risk flag `authority-duplication`, state
`proposed`, `review_status: incomplete`, empty tools, all-false permissions, and
`activation_notes` denying A2A/tracking/vector-RAG-DAG access. No second source of
truth is created. Strong.

### 4. Sn1per / RAPTOR quarantine — CONFIRM-PASS
`sn1per-reference`: `quarantined` / `no-runtime`; `raptor-loop-hunt-reference`:
`proposed` / `source-audit-required`. Both `disabled-external-repo`,
`disabled-until-intake`, empty args, empty tool_allowlist, `network:false`,
`filesystem:none`, `writes:false`, `secrets:false`. Not present in the normal
executable path — stronger than "sandboxed": simply absent/not-installed. Risk flags
carry `active-exploitation`, `privileged-install`, `custom-eula-restrictions`,
`autonomous-loop`, `prompt-injection`, `scope-escape`, `tool-execution`,
`resource-exhaustion`. No vendor/install/exec/pattern-use is admitted.

### 5. Evidence custody — CONFIRM-PASS (design-level)
PRD §5: raw evidence goes only to an encrypted quarantine store with a separate
access authority, content digest, trusted collection time, chain-of-custody events,
retention/expiry, deletion approval, and legal-hold override. Derived reports are
redacted and **content-bound to the raw evidence digest** — this is the report≠record
binding. Models receive only a minimum sanitized projection; raw evidence never enters
prompts/Git/memory/dashboards/bounty by default. Sound. Custody code lands S3/S4; S0-A
handles no evidence.

### 6. BOD-inspired ordering — CONFIRM-PASS
PRD §6 is a deterministic lexicographic policy: active-exploitation/KEV → public
exposure → automatability → impact → confidence/criticality → compensating controls →
stable asset id then finding digest tie-break. CVSS is evidence, not the sole
authority; unknowns map to the more-urgent class but never authorize active testing;
evidence-preservation urgency overrides patch order when compromise is plausible.
Deterministic and total. The resolver itself is S0-B/S5; S0-A ships no resolver.

### 7. Disclosure / bounty gates — CONFIRM-PASS
PRD §8 / plan S4: verify `SECURITY.md`/program before contact; freeze policy URL+scope
at test time; private duplicate-search only (no public leak pre-disclosure); no
disclosure before the program timeline; immutable owner-approval receipt per
submission; no autonomous external submission; accidental/malformed submission triggers
a bounded retraction playbook that preserves original evidence (no silent history
rewrite); payments/identity/legal are owner-only. Gated correctly.

### 8. S0-A closed-schema compatibility — CONFIRM-PASS (verified in code + live run)
`additionalProperties:false` on every object the registry owns (root, `policy`,
`install`, `permissions`, `toolSchema`, `candidate`). All 14 records validate under
`Draft202012Validator` + `FormatChecker`; negative vectors reject unknown keys, wrong
types, malformed permission enums, malformed URLs, unbounded tool names, and duplicate
IDs. The two codex blocking revisions are both resolved and exercised through the
**production** path:
- **Duplicate-ID rejection** — `_load_registry` (CLI lines 46-51) rejects the first
  repeated `id` in order, even when the duplicate objects differ, before any list/audit
  selection; `test_production_registry_rejections` drives a differing-object duplicate
  through the CLI and asserts exit 2 + empty stdout + stable
  `duplicate candidate id` classification.
- **Bounded `propertyNames`** — schema line 86 (`candidate.tool_schemas` map keys) and
  line 53 (`toolSchema.properties` map keys), pattern-bounded to `maxLength:128`; the
  test drives an over-bound top-level key and an over-bound nested property key through
  the CLI and asserts `schema validation failed` rejection.
Live run: `list`=14 records; new records derive `review-recommended` (never `low-risk`
/ `accepted-with-mitigations`); `t3mp3st` still `accepted-with-mitigations`;
`git diff --check` clean; `test-capability-intake.py` → `PASS`.

### 9. Service Coverage sequencing — CONFIRM-PASS
S0-A creates no service/route/metric and makes no Service Coverage claim (design §8).
Plan S1 is explicitly blocked until each already-enabled scanner (Semgrep/OSV/Trivy/
Syft-Grype) is audited for a real integration-path `aq-qa` check, visible Command
Center state, bounded metrics, and rollback — "existing admission is not Service
Coverage evidence." Safe sequencing.

### Authorization hash-bound / owner-gated / fail-open — CONFIRM-PASS
Authorization + AM1 authorization are single-use, exact-subject, fail-closed preflight
(HEAD + all baseline hashes + no writer overlap + no prior consumption), and grant no
authority until an independent PASS **and** an explicit owner activation naming the
exact SHA-256, one implementer, and a ≤24h UTC window. `S0-A-AM1-ACTIVATION.md` records
the 2026-07-27 owner direction with the exact authorization/candidate-revision hashes —
not self-activating. Registry preserved byte-frozen (`+81/-0`, only the three new
records; `t3mp3st` absent from every diff hunk). No fail-open: the CLI loader now fails
**closed** — schema-invalid or duplicate-ID registries raise `ValueError` → `exit 2`
with empty stdout before any candidate is reported. report≠record is closed both in the
loader (validate-before-use) and in the PRD contract (report digest bound to raw
evidence).

## Advisory notes (non-blocking — do NOT gate the commit)

- **A. AM1 acceptance receipt not persisted in the plan dir (LOW, ledger hygiene).**
  The only acceptance artifact on disk is `S0-A-CANDIDATE-ACCEPTANCE.md` =
  REQUEST_REVISION against the *original* candidate (schema `f22d4f3b…`). There is no
  recorded independent-PASS artifact bound to the *AM1 post-change* hashes
  (schema `d080957b…`, CLI `cdf59fc5…`, test `cd4aaebf…`). The AM1 authorization
  requires an independent PASS on those exact hashes before a commit action is
  prepared. This confirmatory pass supplies that evidence; recommend persisting the
  AM1 PASS receipt (codex's + this one) with the exact post-change hashes into the plan
  dir so the activation ledger is self-contained. Governance completeness only — the
  artifacts themselves are sound.

- **B. Antigravity advisory review is untrusted and factually loose (INFORMATIONAL).**
  `antigravity-track-s-review.md` scores every axis 10/10 and asserts specifics that do
  not match S0-A reality — e.g. offensive tools "completely isolated within sandboxed
  containers/namespaces with read-only target volumes and audited execution logs"
  (there are no containers at S0-A; sn1per/raptor are simply absent, which is more
  conservative than claimed) and evidence "cryptographic hashing (SHA-256) and
  append-only log structures" (design-only, unimplemented at S0-A). Consistent with the
  standing note that Antigravity is advisory/untrusted and fabricates detail. Its PASS
  must not be counted as substantive independent verification; the codex
  REQUEST_REVISION→AM1→PASS loop plus this confirmatory pass are the real signal. The
  actual dispositions are safe (more conservative than Antigravity described), so this
  does not change the verdict.

## Conclusion

`CONFIRM-PASS`. Codex's PASS holds against source. The S0-A + AM1 slice is closed-schema,
fail-closed, owner-gated, metadata-only with zero runtime/egress authority, preserves
all 11 baseline records and `t3mp3st` byte-for-byte, and directly resolves both codex
blocking revisions through the production path. No defect surfaced; no follow-up opened.
Advisory notes A/B are recommendations, not gates. Review-only — no stage/commit.
