---
title: Network Profile Interoperability Program Plan
status: DESIGN_READY
date: 2026-08-09
parent_prd: .agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md
---

# Network Profile Interoperability — bounded delivery plan

## Program guardrails

This plan addresses the repeated `connected (site only)` condition without weakening
systemd-resolved, NetworkManager, firewall, DNSSEC policy, or Wi-Fi authentication.
It is a design and sequencing record, not authorization to modify a connection, resolve a
name, issue a network request, rebuild, deploy, or switch.

Before each implementation authorization, freeze the exact existing-file SHA-256 values,
working-tree overlap report, implementer, independent reviewer, and single commit owner.
All slice commands must be offline unless an owner separately activates N3.

| Slice | State | Purpose | Prerequisite |
|---|---|---|---|
| N0 | DESIGN_READY | Pure policy/schema/vector kernel | independent design PASS |
| N1 | BLOCKED_ON_N0 | Passive health projection + mandatory Service Coverage | N0 independent acceptance PASS |
| N2 | BLOCKED_ON_N1 | Land policy executor/watchdog; deployment remains exact `mode=legacy` | N1 integration acceptance PASS + owner implementation activation |
| N3 | OWNER_ONLY | Two-network live canary then scoped cutover | N2 acceptance + explicit owner activation |

## N0 — pure resolver contract

### Objective

Create the side-effect-free source of truth for `network.dns-policy-input.v1`,
`network.dns-policy-eligibility.v1`, `network.dns-policy-decision.v1`,
`network.dns-policy-health.v1`, and deterministic eligibility/effect transitions. Pure
eligibility is separate from a pure executor transition over closed prior-effect, receipt,
event and mode state. N0 has no NetworkManager dispatcher, timer, Nix module, service,
system call, dashboard, Phase-0, state file, profile lookup, or connection access.

### Exact implementation ceiling (four new files)

1. `scripts/ai/lib/network_dns_policy.py` — pure enums, closed validators, resolver,
   telemetry sanitizer; no imports that invoke commands or network I/O.
2. `config/network-dns-policy.schema.json` — Draft 2020-12 closed schemas and constants,
   including the 55-second receipt lease and 90-second maximum-effect ceiling.
3. `scripts/testing/fixtures/network-dns-policy-vectors.json` — permit, deny, expiry,
   malformed, redaction and idempotence vectors only.
4. `scripts/testing/test-network-dns-policy.py` — offline vector/oracle test.

### Required tests

- all closed input/output schemas reject extra keys and non-enums;
- only the single permit tuple returns `eligible=true`, and only eligible policy
  transition state can return `apply_public_override`;
- every non-permit returns `eligible=false` and the transition preserves/reverts, never
  public routing;
- stale, malformed, expired, missing and unknown prior state require safe action;
- replayed admit/refresh is idempotent; restart, pending-apply/revert crash, downgrade, link-down,
  watchdog-without-dispatcher, fake-clock boundaries and expiry vectors conservatively revert;
- deterministic pure interleaving vectors cover apply/downgrade, watchdog/refresh,
  duplicate apply and crash/restart receipt order; and
- supplied values resembling SSIDs, UUIDs, IPs, domains and secrets cannot survive the
  telemetry sanitizer; and
- resolver is deterministic and does not import subprocess, socket, requests, urllib,
  dbus, or NetworkManager modules.

### Stop conditions

Stop and request a design amendment on a fifth path; any stateful/runtime import; any
profile identifier in fixture output; a changed TTL; dashboard/Phase-0/Nix work; staging,
commit, process, provider, network, deployment or system activation.

## N1 — passive projection and Service Coverage

### Objective

Ship visibility before behavior change. A passive dispatcher observation path may classify
the already-existing NetworkManager/resolved facts and publish one bounded local status
record. It must not call `resolvectl dns`, a mutating `resolvectl domain`,
`resolvectl revert`, alter DNS, or influence routing. The only `resolvectl domain IFACE` permitted in N1 is the
read-only no-domain-argument query defined below; any argv that supplies a domain is a
prohibited mutation.

### Exact implementation ceiling (nine paths)

1. `nix/modules/core/network.nix` — add only a disabled-by-default/passive observability
   option and a read-only dispatcher hook; retain current enforcement bytes until N2.
2. `scripts/ai/lib/network_dns_policy.py` — add a bounded acquisition adapter that emits
   N0 input facts. Its entire command allowlist is `nmcli --terse --fields CONNECTIVITY
   general`, `nmcli --get-values GENERAL.CON-UUID device show IFACE`, and read-only
   `resolvectl domain IFACE`: fixed argv only, validated interface, two-second timeout,
   16-KiB combined output ceiling, fixed locale/environment allowlist and closed redacted
   errors. Pure eligibility/transition functions remain the sole decision owners.
3. `scripts/ai/aq-network-policy` — read-only machine/status facade; no mutation verb.
4. `scripts/testing/test-network-dns-policy.py` — passive parser, persistence, and CLI
   fixtures using synthetic local input.
5. `scripts/testing/harness_qa/phases/phase0.py` — one integration check against the
   machine facade, registered in the existing Phase-0 owner.
6. `scripts/ai/_aq-qa-bash` — matching shell compatibility check with the same outcome
   mapping; no duplicate state authority.
7. `dashboard/backend/api/routes/aistack.py` — read-only sanitizing API projection.
8. `assets/dashboard.js` — Network Resilience card and degraded/unavailable states.
9. `docs/operations/network-profile-interoperability.md` — operator interpretation and
   non-destructive diagnostics; no raw profile examples.

### Service Coverage contract

N1 is complete only when all three ship in the same atomic commit: (a) passive local
projection at `/run/aq-network-policy/health.json`, (b) an integration-path Phase-0 plus Bash compatibility check, and (c) live
dashboard card using the API projection. The check reads a local status record only; it
does not perform network reachability, DNS queries, captive-portal requests or scans.
The root writer uses a stable `0600` lock, root-owned `0700` directory, `0600` regular
file, bounded validation, file `fsync`, same-directory rename and directory `fsync`.
CLI/API/dashboard are readers of this sole projection and must not re-query NM/resolved.
NetworkManager's existing external connectivity request is not this feature's probe and
earns no Service Coverage credit.

### Metrics and display

Display the PRD's closed health object with an explicit `unavailable` state. Add no
high-cardinality labels, time series keyed by interface/profile, raw error strings, or
operator action button. Dashboard/Phase-0 disagreement is a failing condition, not an
assumed healthy fallback.

### Stop conditions

Stop on a tenth path; any DNS mutation or `resolvectl` action; any persistent raw NM/DBus
output; any profile/SSID/IP/domain in API/UI/test artifact; an external probe; a new remote
endpoint; missing dual Phase-0 registration; deploy/rebuild/stage/commit outside the
authorized acceptance chain.

## N2 — legacy-default policy executor with expiry

### Objective

Land the N0-governed executor only after N1 proves the projection contract. N2 introduces
`mode=legacy|policy`, with **`legacy` as the deployment default**. Legacy mode is exact
current behavior: Wi-Fi `up|dhcp4-change` installs the current public resolver list and
`~.`. Policy mode's default action preserves link DNS and is present but not selectable
until N3 owner activation. N2 is the first slice allowed to implement the per-link
resolved operations, but its offline implementation authorization does not run them.

### Exact implementation ceiling (six paths)

1. `nix/modules/core/network.nix` — declarative mode, root-private trust/receipt paths,
   executor and independent watchdog service/timer ownership, exact legacy branch, policy
   branch, stable effect-operation lock, hardening and bounded expiry/revert semantics.
2. `scripts/ai/lib/network_dns_policy.py` — a narrow executor adapter that consumes an
   already-validated decision; it cannot re-decide policy and performs no network probing.
3. `scripts/testing/test-network-dns-policy.py` — fake command runner proves permitted,
   downgrade, error and expiry sequences; no host resolver mutation.
4. `scripts/ai/aq-network-policy` — land the root-only, activation-gated trust replacement
   interface, but do not invoke it before N3.
5. `config/network-dns-policy.schema.json` — add the closed trust and receipt schemas.
6. `docs/operations/network-profile-interoperability.md` — rollback/canary runbook update.

The N2 authorization may not expand the ceiling. The private trust map is exactly
`/var/lib/aq-network-policy/private/trusted-profiles.json` (root:root, directory `0700`,
regular file `0600`). Its stable lock is
`/run/lock/aq-network-policy/trusted-profiles.lock` (root:root `0600`). The sole active
lease receipt is `/run/aq-network-policy/private/override-lease.json` in a root:root
`0700` directory, regular file `0600`; it retains one
pending_apply/active/pending_revert/inactive receipt and
no history; its lock is `/run/lock/aq-network-policy/override-lease.lock`. The health
projection retains exactly one current sanitized record and uses
`/run/lock/aq-network-policy/health.lock`. All locks are root:root `0600`. All three writers
use a stable lock inode, same-directory `0600` temporary
regular file, schema validation, file `fsync`, atomic rename and directory `fsync`.
Symlink, ownership/mode, lock, validation or persistence failure denies apply and triggers
revert when an effect may exist. The mapping/receipt cannot be displayed or logged.

All effect-capable paths additionally share the stable, never-replaced root:root `0600`
inode `/run/lock/aq-network-policy/effect-operation.lock`. Its exclusive `flock` spans
bounded current-fact acquisition, latest receipt read, pure decision, durable pending
receipt, bounded resolved mutation, durable final receipt, and final health publication.
Lock order is effect-operation -> mapping -> receipt -> health; mapping/receipt locks are
released before the next nested class, and reverse acquisition is prohibited. Trust
replacement takes mapping only; passive N1 publication takes health only and is disabled
before policy activation. In policy mode only an effect-lock holder may publish health,
and its final health is derived from the durable final receipt without exposing the
high-cardinality revision. Crash releases
the kernel lock but never proves the effect absent; restart reacquires it and reverts every
pending, invalid, expired, cross-boot, missing/ambiguous state before considering apply.

The only trust-map mutation interface is
`aq-network-policy trust replace --input PATH --machine`, runnable as root only and
blocked until N3 activation. It reads at most 64 KiB from a root-owned, non-symlink,
non-group/world-writable regular file, validates before taking the stable lock, and never
echoes profile identifiers. Its closed result is only `updated`, `invalid_input`,
`unsafe_metadata`, `lock_timeout`, or `durable_write_failed`, mapped respectively to exit
0, 2, 3, 4, or 5. Missing mapping is retained as `unknown`, never auto-created with trust
data. Nix may create empty private directories and locks but must never embed profile
identifiers or trust-map content in a derivation or the Nix store.

The receipt lease is 55 seconds. The independent watchdog starts within five seconds of
boot, runs every 10 seconds with maximum one-second jitter, has a five-second resolved
mutation deadline, and a 15-second end-to-end recovery deadline. It therefore completes
the normally scheduled expiry transaction by 81 seconds under a functioning kernel and
service manager even without a dispatcher event. Restart inspects the boot-bound receipt;
missing, invalid, cross-boot, expired or ambiguous effect state reverts. An `OnFailure`
unit attempts emergency revert and publishes a closed degraded outcome. When an invalid
or missing receipt cannot identify an affected link, policy-mode recovery enumerates only
locally present, sysfs-proven Wi-Fi interfaces and issues bounded `resolvectl revert` for
each; it does not query or modify non-Wi-Fi links. Legacy mode never runs this watchdog,
which preserves exact current behavior.

Effect-lock first acquisition is bounded to two seconds. Dispatcher/refresh contention
cannot apply and returns only a sanitized local contention result without overwriting
authoritative health; watchdog/recovery retries every
250 ms for at most five seconds and then follows OnFailure, never mutating without the
lock. The three fixed acquisition commands retain their two-second individual limit and
have a four-second total budget while the effect lock is held. A resolved mutation has a
five-second deadline and the complete transaction is capped at 15 seconds. Timeout/uncertainty
converts to a same-lock `pending_revert` plus idempotent revert path.

### Required behavior evidence

- fake trusted/full/fresh/ordinary state applies per-link DNS and `~.` exactly once;
- portal, limited, site, split, unknown, malformed and stale cases execute revert/preserve,
  never the public override;
- link-down, downgrade, replay, restart and watchdog-without-dispatcher sequences are
  idempotent and fake-clock tests prove revert begins within the 90-second ceiling;
- a durable pending receipt precedes apply; crash/restart between pending, apply and active
  publication always reverts or safely proves no effect;
- pre-effect health is `transitioning`; final health follows the durable final receipt;
  `overriding` cannot publish before `active`, and failed post-apply health publication
  triggers same-lock revert;
- barrier-controlled concurrency tests deterministically interleave admitted apply versus
  downgrade/revert, watchdog versus refresh, duplicate applies, and crash/restart while
  the stable lock is held and after it is released. Receipt revisions and in-lock current
  fact reacquisition prove no old apply can land after a newer revert;
- executor error leaves or restores link configuration and records only a closed degraded
  reason; and
- `mode=legacy` is argv/event/side-effect compatible with the current declared
  configuration; `mode=policy` is not activated and its default decision preserves link DNS.

### Stop conditions

Stop on absent trusted-profile/receipt persistence contract, non-atomic/unsafe ownership,
a missing/replaceable/pre-truncated effect lock, reverse lock ordering, any effect outside
the exclusive transaction, health-before-final-receipt publication, an unbounded lock or
acquisition wait,
a global resolved change, a write to `/etc/resolv.conf`, a DNS/HTTP probe, an attempt to
infer trust, a timer lacking the stated cadence/jitter/deadline/restart behavior,
any dashboard or Phase-0 expansion, a seventh path, failed fake-runner test, live command, rebuild,
deployment, or activation without an owner authorization.

## N3 — owner-only two-network canary and cutover

N3 is intentionally not pre-authorized by this design. It is the only slice allowed to
change the deployed mode from `legacy` to `policy`, and begins only after explicit owner
activation names two physically available test conditions:

1. **Trusted full network:** a locally configured eligible profile with ordinary DNS and
   NetworkManager `full`. Confirm bounded override, fresh health, and normal local service
   reachability through existing health checks.
2. **Compatibility network:** a captive portal, limited/site-only, or split-DNS network.
   Confirm `preserving`/`reverted`, no public `~.` override, and usable portal/local/network
   behavior as observed by the owner.

Canary evidence contains only policy enums and result PASS/FAIL; it excludes network names,
addresses, domains, resolver values and credentials. The owner, not automation, supplies
physical network access and observes portal/local behavior. A failure performs the N2
fail-safe abort first: revert the affected link and remove policy eligibility while staying
in policy mode so link DNS is preserved. A separately activated configuration rollback to
`mode=legacy` restores exact pre-feature behavior, including its universal override; the
dashboard must label that state `legacy`, not `safe`. Either failure path preserves only
sanitized evidence and blocks cutover.

## Review and acceptance matrix

| Gate | N0 | N1 | N2 | N3 |
|---|---|---|---|---|
| Independent architecture/security/SRE design review | required | required | required | required |
| Independent implementation acceptance | required | required | required | owner witnesses |
| Pure/offline vectors | required | required | required | retained |
| Phase-0 + Bash compatibility | not applicable | required | regression | live evidence only after owner activation |
| Dashboard card/API parity | not applicable | required | regression | observed |
| Rebuild/deployment | prohibited | prohibited | prohibited until N3 | owner-only |
| External network traffic | prohibited | prohibited | prohibited | explicit two-network canary only |

## Verdict-ready statement

`VERDICT: PASS_DESIGN — the program preserves resolver hardening while replacing a universal
Wi-Fi DNS mutation with a closed, expiring, privacy-preserving, observable policy. The
revision separates eligibility from executor state, makes unknown/replay/restart safe,
defines private atomic receipts and an independent watchdog, and preserves exact legacy
deployment semantics until owner-only N3 activation. N0 is
eligible for a separate design/implementation authorization; N1–N3 remain blocked by the
stated gates and no slice authorizes live network changes.`
