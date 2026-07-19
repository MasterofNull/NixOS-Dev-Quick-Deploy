# QPPR-C1C-AM2 authorization review

**Reviewer:** `codex-subagent-qppr-c1c-am1-final-reviewer`
**Role:** independent flagship architecture / security / SRE / QA reviewer
**Reviewed:** 2026-07-19
**Verdict:** PASS

## Exact subjects

| Subject | Required SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| C1C-AM2 observable fail-stop amendment | `02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc` | `02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc` | exact |
| C1C-AM2 PREPARED_ONLY authorization | `0145aabac0d538831940c86d30bd750e6d4484e9ee06238bd7636c34269d1135` | `0145aabac0d538831940c86d30bd750e6d4484e9ee06238bd7636c34269d1135` | exact |
| process-owner predecessor | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | exact |
| lifecycle-test predecessor | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` | exact |
| frozen observer test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | exact |

The SHA-256 of the literal required identity
`codex-subagent-qppr-c1c-am1-implementer` is exactly
`40ae41866aa866e85656b6f682ef01367a51a867d234007887aa49eba82f5873`.

## Architecture, security, and SRE adjudication

The amendment resolves the prior unobservable-transition defect. A validated caller-owned,
nonblocking, close-on-exec status pipe carries bounded low-cardinality sequence records. The pure
authoritative classifier depends only on a valid sequence-1 `running` record, the bound same-host
monotonic deadline, observer monotonic time beyond that deadline, and absence of a valid sequence-2
acknowledgement. It does not depend on callback-owned state, wall time, PID inspection, or an
impossible marker from the blocked lifecycle thread. Missing or invalid evidence is `unavailable`,
not healthy or completed, and classification cannot downgrade after violation.

The returning path preserves the accepted <=5-second restoration/redelivery SLO for `completed` and
`cancelled`. A late return emits `contract_violation` and permanently fail-stops before handler or
mask restoration, signal redelivery, invocation-lock release, ordinary return, later provider start,
or a second writer. A never-returning callback remains blocked at the same safety boundary; the
external monotonic classifier supplies the authoritative violation state. Neither violation path
claims finite redelivery. Explicit owner SRE ratification of this safety-over-liveness exception is
therefore correctly mandatory.

The deterministic evidence requirements are sufficient and non-timing-fragile: injected classifier
time and event barriers prove exact sequence behavior, missing sequence-2 classification, late-return
permanent fail-stop, no restoration/redelivery/lock release/return/second provider/writer, strict
invalid/backward/duplicate/post-terminal rejection, and exact isolated-fixture termination and reap.
Legacy publication, C1B observer behavior, cleanup ordering, and healthy-path SLO evidence remain
frozen.

## Authorization and downstream gates

The grant has an exact two-MODIFY-file ceiling and exact predecessor hashes. It binds the required
implementer and identity hash, is single-use, consumes its idempotency key on the first complete exact
candidate report, and hard-stops on drift, expiry, identity mismatch, or replay. Owner activation
must name the reviewed authorization hash, repeat identity and hash, explicitly ratify the exception,
and provide an activation window no longer than 24 hours.

The focused lifecycle and observer suites, Python compilation, observer hash, bounded diff check, and
changed-file security scan are frozen as exact acceptance commands. They are appropriately deferred
to implementer and independent exact-candidate acceptance; this design review performed no candidate
test or live action. Tier-0 remains orchestrator-only after candidate `PASS`.

A1-AM3's four-file recovery remains NON-ACTIVATABLE until C1C-AM2 is ratified, activated,
independently accepted, committed, and followed by a final exact byte rebind. A2 and every provider,
network, live Phase-0, service, deployment, traffic, and rollback action remain blocked.

VERDICT: PASS — C1C-AM2 provides enforceable observable fail-stop classification, bounded evidence, replay-safe authorization, and preserves all downstream gates
