# QPPR-A2 existing-card visibility implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a2-20260718`
**Idempotency key:** `qa-provider-probe-reliability:a2:existing-card-visibility:v1:20260718`
**Status:** **PREPARED_ONLY / REVISION 3 / BLOCKED ON C1A+C1B+A1 / NOT ACTIVATABLE**
**Prepared:** 2026-07-18
**Single use after rebind:** first complete exact five-file candidate report

## 1. Frozen subjects and unresolved predecessor

| Subject | SHA-256 |
|---|---|
| `.agents/plans/qa-provider-probe-reliability/A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/C1A-IMPLEMENTATION-AUTHORIZATION.md` | `2d4bf8e7efe45a2b85a1f5ad5b2aad3e26791529fa09a465451aa0f0f1759251` |
| `.agents/plans/qa-provider-probe-reliability/C1B-IMPLEMENTATION-AUTHORIZATION.md` | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` |
| `.agents/plans/qa-provider-probe-reliability/A1-IMPLEMENTATION-AUTHORIZATION.md` | `336f454aa0e9c5e31f7fc7f10c5fee6a41d10d4e54588d8572a6c1ed9ec738e9` |

A2 cannot be reviewed for activation or activated until C1A, C1B, and A1 have exact accepted commits and
hash-bound acceptance records. A separately reviewed amendment must bind those subjects, the final
A1 commit, and the exact four existing A2 predecessor hashes as they exist immediately after A1.
This explicit rebind protects the required consecutive-commit boundary from concurrent drift.

## 2. Exact five-file ceiling

| # | Operation | Path | Current observed predecessor |
|---:|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent |

These hashes are design observations, not activation bindings. The required A2 amendment freezes
their post-A1 values.

## 3. Exact grant after rebind and activation

One bounded implementer may implement only packet sections 4.1–4.2: a pure bounded heartbeat reader;
the passive `projection_only=true` branch on the existing Phase-0 route that returns before cache,
task, evidence, or execution logic; the fixed low-cardinality `provider_probe` projection; six
accessible rows in the existing QA card; the bounded 1-second-active/2-second-idle single-flight,
visibility-aware cancellable poller; safe text-only rendering; and focused offline API/real-browser
DOM tests. No new endpoint, card, control, cache authority, acceptance store, visual system,
dependency, environment variable, or provider execution is permitted.

The immutable QA result remains the badge/count authority. Projection data cannot convert SKIP or
failure to PASS. Missing, stale, malformed, symlinked, oversized, future-dated, or sensitive content
must yield explicit unavailable/stale state. The browser uses existing styles and `setText`, remains
readable at desktop and narrow viewports, and exposes full invocation meaning accessibly.

## 4. Mandatory stops and exclusions

Stop without workaround on absent C1A/C1B/A1 acceptance, non-adjacent commit state, missing rebind review,
any sixth file, substitution, predecessor drift, foreign dirty overlap, new route/card/store,
provider/network/evidence write, mutable acceptance from heartbeat, `innerHTML` projection data,
projection polling that reaches active QA/cache/background execution, >2-second visible cadence,
overlapping/uncancelled requests, unbounded/symlink-following read, secret/raw-output/PID/argv/path display, new env/port/dependency,
Nix/systemd/service/broker/cgroup/deploy/traffic/rollback/deletion, staging, commit, or live browser/API
action.

The implementer cannot delegate, stage, commit, deploy, or self-accept. It reports all five exact
hashes, important UI/backend reasoning, focused offline results, and exclusions. Reviewer edits
create a new subject and require a different reviewer.

## 5. Review, consecutive commit, and activation

After exact rebind review, owner activation must name the amended authorization hash, one implementer,
activation and <=24-hour expiry times, and unchanged ceiling/stops. A different agent/session reviews
the exact five-file candidate. Only the orchestrator stages and commits, immediately after A1 with
no unrelated intervening commit.

Neither commit activates the feature. A separate paired activation/vetting grant must authorize any
real provider run, API call, browser session, deployment, traffic, or rollback and record all five
Definition-of-Done dimensions. A2 failure blocks A1 activation.

`RECORD: PREPARED_ONLY AND NOT ACTIVATABLE. Accepted C1A+C1B, accepted A1, consecutive-state rebind,
and independent review remain mandatory.`
