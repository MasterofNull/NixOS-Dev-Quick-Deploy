# Foundation B1 L2B-B Implementation Authorization Amendment 1

**Authorization ID:** `auth-local-inference-l2b-b-am1-20260722`

**Idempotency key:** `local-inference:l2b-b:am1:20260722:single-use`

**Status:** `PREPARED_ONLY — SUSPENDED BY PRE-REVIEW SUBJECT DRIFT; NON-ACTIVATABLE`

**Prepared repository HEAD:** `142ad8b7ef83808430ee5df70812e9ae6d519c3c`

**Governing amendment:** `L2B-B-RECOVERY-REFREEZE-AM1.md`, SHA-256
`16d12dfea34c4600e69e44be6d232d05753dbe0e690a26e419660f251ea64b98`

## 1. Non-authority and activation prerequisites

This prepared record grants no permission to edit, dispatch, stage, commit, deploy, contact a
provider, or use a network. Before concurrent drift, activation would have required all of the
following:

1. The orchestrator canonically closes `l2b-b-20260720` as stale/failed; it may not be resumed.
2. A fresh independent reviewer, distinct from this record's author and the proposed implementer,
   recomputes and records the exact SHA-256 of this authorization and its governing amendment,
   verifies every binding below against the current tree, and ends an exact-subject review with
   `VERDICT: PASS`. Historical reviews do not satisfy this prerequisite. The expected review record
   is `.agents/plans/local-inference-l2b-b/L2B-B-AM1-AUTHORIZATION-REVIEW.md`.
3. The owner issues a new activation record naming this authorization's exact raw SHA-256,
   idempotency key, `codex-subagent-l2b-b-am1-implementer`, an activation start, and an expiry no
   more than 24 hours later. Activation cannot be retroactive.
4. Immediately before dispatch and again before the first write, prepared HEAD, all three MODIFY
   hashes, both absence assertions, and all frozen governance hashes match exactly.

Any failed prerequisite leaves this record `PREPARED_ONLY` and requires stop, not repair-in-place.
The governing amendment records that the first pre-write replay already failed after a separate
owner reactivation produced foreign implementation drift. Therefore AM1 is permanently suspended;
the checklist below is retained as exact recovery evidence, not a path to activation.

## 2. Exact five-file implementation ceiling

| Operation | Path | Required pre-state |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | SHA-256 `37e6d76ec73b00ffc7b759f94e34e10e85bfee5c676b8fbc15527cfaa5309bdc` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | SHA-256 `2ceee6bbed15ab3722902309f08976c827c5685819bcc25e6eb7daa5587f029d` |
| MODIFY | `assets/dashboard.js` | SHA-256 `ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7` |
| NEW | `config/schemas/local-inference-payload-v1.json` | absent |
| NEW | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | absent |

The following are frozen governance inputs, not implementation candidates and not part of the
five-file write ceiling:

| Path | Required SHA-256 |
|---|---|
| `.agents/plans/local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md` | `2e41981f6bce0250a3bda14f599cf65e7c93301c022428528a07809ed589abda` |
| `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` | `468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe` |
| `.agents/plans/stream-auth-rereview/claude.md` | `c2de6df2124c381abb6791162b3951f59b045ec55e21d5e06b5394bd9c8ae6a0` |
| `.agents/plans/local-inference-l2b-b/L2B-B-RECOVERY-REFREEZE-AM1.md` | `16d12dfea34c4600e69e44be6d232d05753dbe0e690a26e419660f251ea64b98` |

An edit, creation, move, deletion, mode change, or substitution involving any sixth implementation
path is an immediate fail-stop. Pre-existing foreign B3 staged changes are out of scope: do not
unstage, modify, include, validate as L2B-B, or commit them.

## 3. Exact implementation grant

After valid activation, the named Codex implementer may use patch edits only on the five ceiling
paths to produce one offline candidate that:

1. applies Unicode NFC normalization recursively to payload string values and object keys;
2. makes serialization deterministic through canonical object-key ordering while preserving array
   order and supported OpenAI-compatible payload semantics;
3. rejects NaN, positive/negative Infinity, schema-invalid payloads, and conflicting normalized
   keys before the existing dispatch boundary with closed reason `REJECTED_SCHEMA_INVALID` and no
   sensitive internal detail;
4. never reads, injects, logs, or forwards cloud credentials, bearer tokens, API keys, filesystem
   secrets, or ambient endpoint configuration;
5. adds a valid Draft 2020-12 payload schema and deterministic chat/completion golden fixtures;
6. expands the existing L2B focused oracle from 8 to exactly 14 offline checks, including canonical
   chat and completion payloads, malformed/non-finite input, Unicode/key-collision behavior, schema
   refusal, and dashboard fail-closed projection; and
7. extends the existing AI Services card only to display normalization/payload health already
   available from the L2B health object. It adds no endpoint, poller, request, listener, authority,
   or client-side source of truth.

This grant does not authorize live inference, model loading, VRAM probing/allocation, network, DNS,
socket, provider, browser, credential, database, subprocess in production code, new dependency,
environment variable, port, URL, route, store, writer, queue, service, Nix, deployment, restart,
traffic, rollback, staging, commit, delegation, deletion, or self-review. The exact offline validation
processes below are the only process execution allowed to the implementer.

## 4. Exact pre-write and offline validation commands

The implementer runs the pre-write block from the repository root before any edit and reruns it after
every pause before resuming. Any non-zero result or unexpected output is a hard stop.

```bash
test "$(git rev-parse HEAD)" = "142ad8b7ef83808430ee5df70812e9ae6d519c3c"
printf '%s  %s\n' \
  '37e6d76ec73b00ffc7b759f94e34e10e85bfee5c676b8fbc15527cfaa5309bdc' 'scripts/ai/lib/local_inference_transport.py' \
  '2ceee6bbed15ab3722902309f08976c827c5685819bcc25e6eb7daa5587f029d' 'scripts/testing/test-local-inference-l2b.py' \
  'ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7' 'assets/dashboard.js' \
  '2e41981f6bce0250a3bda14f599cf65e7c93301c022428528a07809ed589abda' '.agents/plans/local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md' \
  '468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe' '.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md' \
  'c2de6df2124c381abb6791162b3951f59b045ec55e21d5e06b5394bd9c8ae6a0' '.agents/plans/stream-auth-rereview/claude.md' \
  '16d12dfea34c4600e69e44be6d232d05753dbe0e690a26e419660f251ea64b98' '.agents/plans/local-inference-l2b-b/L2B-B-RECOVERY-REFREEZE-AM1.md' \
  | sha256sum -c -
test ! -e config/schemas/local-inference-payload-v1.json
test ! -e scripts/testing/fixtures/l2b_b_golden_payloads.json
```

After the five-file candidate is complete, the implementer runs this separate offline validation
block. Any non-zero result, prohibited-match output, or count other than 14/14 is a hard stop.

```bash
python3 scripts/testing/test-local-inference-l2b.py
python3 -m py_compile scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py
python3 -m json.tool config/schemas/local-inference-payload-v1.json >/dev/null
python3 -m json.tool scripts/testing/fixtures/l2b_b_golden_payloads.json >/dev/null
node --check assets/dashboard.js
git diff --check -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py assets/dashboard.js config/schemas/local-inference-payload-v1.json scripts/testing/fixtures/l2b_b_golden_payloads.json
if git diff --unified=0 -- scripts/ai/lib/local_inference_transport.py assets/dashboard.js \
  | rg -n '^\+.*(socket|requests|urllib|httpx|aiohttp|subprocess|os\.system|Popen|https?://)'; then
  echo 'prohibited production connectivity/process surface added' >&2
  exit 1
fi
```

The focused test must truthfully report 14/14 checks. No `aq-qa`, Tier-0, curl, browser, service,
provider, or live endpoint command is permitted under this implementation grant. Broader governance
validation, if later required, belongs to the orchestrator after independent candidate acceptance.

## 5. Single-use, replay, expiry, and drift controls

- The prepared authorization has no active window. Only the later owner record creates one, and its
  duration must be positive and at most 24 hours.
- The first canonical dispatch/claim by the exact named implementer consumes the idempotency key.
  Provider failure, cancellation, timeout, or interruption does not permit replay; recovery requires
  a newly numbered amendment with fresh hashes and review.
- Any first write consumes the grant even if the candidate is incomplete or later rejected.
- No parallel, substitute, retroactive, inherited, or resumed implementer is allowed. Identity
  substitution requires a new amendment and fresh independent review.
- Recheck HEAD, pre-state, absence, identity, and unexpired window before the first write and after
  every pause. Any mismatch, new foreign overlap, sixth path, dirty ceiling path, or governance hash
  drift suspends the grant immediately.
- A completed candidate freezes the exact five post-state SHA-256 values. Further byte change,
  including review-driven correction, requires a new amendment; this grant cannot reopen.

## 6. Candidate report and independent acceptance

The implementer stops without staging or committing and reports:

- activation ID, idempotency key, identity, and timestamps;
- all prepared pre-state checks and exact five post-state SHA-256 values;
- a five-path-only diff inventory and confirmation that frozen governance/B3 bytes were untouched;
- exact output from every allowed validation command, including the truthful 14/14 count;
- explicit confirmation that no prohibited live, provider, network, credential, staging, commit,
  delegation, or sixth-path action occurred.

A fresh acceptance reviewer from a different agent/session than the implementer must independently
recompute the five candidate hashes, inspect the exact diff against this authorization, rerun every
offline validation command, verify no out-of-scope or security/connectivity surface, and issue an
explicit last-line verdict:

`VERDICT: PASS — exact five-file L2B-B-AM1 candidate satisfies all authorization criteria`

Any `FAIL` or `REQUEST_REVISION` leaves the candidate unaccepted and requires a new amendment for
further edits. Only after an independent PASS may the orchestrator run separately authorized broader
gates, stage only the accepted five-file candidate plus its governance evidence, and commit.

`RECORD: PREPARED_ONLY/SUSPENDED five-file offline L2B-B-AM1 grant; it failed its pre-review drift
oracle and is non-activatable. A newly numbered post-disposition refreeze is required; all prior
tasks, windows, reviews, and hashes remain non-replayable.`
