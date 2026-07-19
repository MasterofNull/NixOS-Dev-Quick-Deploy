# QPPR-A2 Amendment 1 existing-card visibility authorization checkpoint

**Authorization ID:** `auth-qa-provider-probe-reliability-a2-am1-20260719`
**Idempotency key:** `qa-provider-probe-reliability:a2:existing-card-visibility:am1:20260719`
**Status:** **PREPARED_ONLY / BLOCKED ON ACCEPTED A1 / NOT ACTIVATABLE**
**Prepared:** 2026-07-19
**Single use after final rebind:** first complete exact five-file candidate report

## 1. Exact bound prerequisites and unresolved A1 edge

| Subject | SHA-256 or Git object |
|---|---|
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` |
| A1 accepted commit | **UNRESOLVED — required before final rebind** |
| A1 implementation acceptance | **UNRESOLVED — required before final rebind** |

This checkpoint resolves C1A/C1B but intentionally cannot resolve A1. It is not eligible for
independent activation approval or owner activation. After A1 acceptance and commit, a minimal
final amendment must bind the exact A1 authorization, candidate, acceptance, commit, current branch
HEAD, and recomputed target predecessors below. Broad preauthorization cannot fill those subjects.

## 2. Exact maximum-five ceiling and current checkpoint

| # | Operation | Path | Current observed predecessor |
|---:|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent, including no symlink |

These exact five paths remain the ceiling. The four hashes and one absence are observation-only
until reconfirmed immediately after A1. Any unrelated intervening commit or byte/absence drift is a
hard stop requiring another reviewed rebind.

## 3. Frozen future grant

After final post-A1 rebind, independent review, and distinct owner activation, one named bounded
implementer may implement only design sections 4.1-4.2: one pure bounded passive projection reader;
the existing Phase-0 route's `projection_only=true` early-return branch; the fixed low-cardinality
`provider_probe` shape; exactly six accessible rows on the existing QA Phase 0 Status card; safe
text-only rendering; one visibility-aware, cancellable, single-flight one/two-second poller; and
focused offline API/browser DOM tests.

The reader and API branch are projection-only and return before QA cache, background-task,
immutable-evidence, provider, or execution effects. Projection cannot change Phase-0 status,
counts, badge, cache, or acceptance. No new route, card, control, store, dependency, environment
variable, or visual system is permitted. Dashboard parity and service coverage are mandatory in
the same atomic A2 commit.

## 4. Stops, final review, and activation

All stops in the original A2 authorization and rebind amendment remain mandatory. Stop on absent
A1 acceptance, non-adjacent branch state, any sixth file, predecessor/absence drift, foreign
overlap, live provider/network/API/browser action, QA/cache/evidence mutation, new route/card/store,
projection-as-authority, unsafe HTML, unbounded or symlink-following read, sensitive display, new
env/port/dependency, Nix/service/deploy/traffic action, staging, commit, rollback, or deletion.

The final post-A1 authorization subject requires an independent exact-hash flagship review. Only
then may the owner explicitly activate that final hash by naming one implementer and a window no
longer than 24 hours while affirming the five-file ceiling and stops. The A1 activation cannot
activate A2. A different agent/session must accept the exact five-file implementation; only the
orchestrator commits it immediately after A1.

Neither A1 nor A2 authorizes a real provider run, live API/browser vet, deployment, traffic,
cutover, or rollback. Those require the separate paired live-vetting grant.

`RECORD: PREPARED_ONLY AND NOT ACTIVATABLE. Accepted A1, final consecutive-state rebind,
independent review, and explicit owner activation remain mandatory.`
