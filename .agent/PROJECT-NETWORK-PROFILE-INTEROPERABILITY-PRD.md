---
title: Network Profile Interoperability PRD
status: DESIGN_ONLY
date: 2026-08-09
owner: hyperd
---

# Network Profile Interoperability

## 1. Problem and evidence

`nix/modules/core/network.nix` currently installs `10-wifi-reliable-dns`. On every Wi-Fi
`up` or `dhcp4-change`, it replaces the link DNS with public resolvers and assigns the
catch-all `~.` route. This was originally an availability mitigation for DHCP resolvers
that answer incorrectly. It is not connection-aware: NetworkManager may report
`CONNECTED_SITE`, a captive portal, limited connectivity, or a split-DNS enterprise/local
network when the override is applied.

That universal mutation can make a usable local or portal network look broken. It also
obscures the operator's ability to distinguish a Wi-Fi association problem from a resolver
policy decision. The observed repeat condition is `connected (site only)`, not evidence
that systemd-resolved, the firewall, DHCP, or credentials should be weakened.

## 2. Goal

Retain NetworkManager, systemd-resolved, DNSSEC policy, the stub resolver, and the
availability benefit for explicitly trusted full-internet networks while making resolver
override a bounded, observable, reversible policy decision.

Delivery has two explicit runtime modes. `mode=legacy` is the deployment default through
N2 and reproduces the current dispatcher behavior exactly: on Wi-Fi `up` and
`dhcp4-change`, configure the existing public resolver list and `~.`. `mode=policy` is
landed but cannot be selected before the separately owner-activated N3 canary. Within
`mode=policy`, the default decision is **preserve DHCP/link DNS**. A public-DNS override
is allowed only when all of the following are true:

1. the connection is locally configured as an eligible trusted/full-connectivity profile;
2. NetworkManager's sanitized connectivity fact is `full`;
3. no split-DNS fact is present; and
4. the policy evidence is fresh within its fixed TTL.

Every other condition (unknown, portal, limited, site-only, split DNS, malformed state,
expired state, or evaluation/command failure) must revert/retain link configuration and
publish a non-secret degraded reason.

## 3. Scope and non-goals

### In scope

- A pure, deterministic policy resolver and versioned, closed decision schema.
- A host-local eligibility source that does not export SSID, BSSID, profile UUID, IP,
  DNS server, gateway, hostname, credential, or raw NetworkManager output.
- Passive policy-health collection and a single read-only machine projection.
- Phase-0 and dashboard coverage for the same closed, sanitized projection.
- Expiry, rollback, and two-network canary criteria.

### Explicitly out of scope

- Changing Wi-Fi credentials, security modes, firewall rules, VPN, DNSSEC, DoT, or
  systemd-resolved's global hardening.
- Sending probes, profile identifiers, resolver addresses, raw journal records, or network
  state to a remote provider.
- An automatic trust decision based on SSID, local subnet, reachability, or captive-portal
  content.
- Live enforcement, a rebuild, a switch, or connection changes in the design slices.
- Any dashboard button that mutates networking. The dashboard is status and runbook only.

## 4. Policy contract

### 4.1 Closed eligibility inputs

The pure resolver accepts only this normalized object (`network.dns-policy-input.v1`):

| Field | Allowed values | Source boundary |
|---|---|---|
| `connection_class` | `trusted_full`, `untrusted`, `unknown` | host-local policy lookup; identifiers never leave that lookup |
| `connectivity` | `full`, `portal`, `limited`, `site`, `none`, `unknown` | normalized NetworkManager state |
| `dns_topology` | `ordinary`, `split`, `unknown` | boolean/topology classifier; no domains or server values |
| `evidence_age_bucket` | `fresh`, `stale`, `unknown` | monotonic age compared to fixed TTL |
| `link_kind` | `wifi`, `other` | dispatcher fact |

Unknown keys, types, or enum values fail closed as `unknown`; the eligibility resolver
never parses raw dispatcher arguments, profile names, or command output.

### 4.2 Closed eligibility and transition outputs

The pure eligibility resolver returns `network.dns-policy-eligibility.v1` with exactly
`schema_version`, `eligible`, `reason`, and `lease_duration_s`. It does not inspect prior
effects or choose an executor command.

A second pure transition function owns effect lifecycle. It accepts the eligibility plus
closed executor-owned state:

- `prior_effect`: `none`, `pending_apply`, `active_override`, `pending_revert`, or `unknown`;
- `receipt_state`: `missing`, `pending_apply_fresh`, `active_fresh`,
  `pending_revert_fresh`, `expired`, or `invalid`;
- `event`: `admit`, `refresh`, `downgrade`, `link_down`, `watchdog`, or `restart`; and
- `mode`: `legacy` or `policy`.

It returns `network.dns-policy-decision.v1` with exactly:

`schema_version`, `action`, `reason`, `lease_ttl_s`, `rollback_required`, and
`telemetry_state`.

`action` is one of `preserve_link_dns`, `apply_public_override`, `refresh_override`,
`revert_override`, or `legacy_override`.
`reason` is one of `trusted_full`, `untrusted_profile`, `portal`, `limited_or_site`,
`split_dns`, `stale_evidence`, `unknown_state`, `non_wifi`, or `legacy_mode`.

The only permit is:

```text
link_kind=wifi ∧ connection_class=trusted_full ∧ connectivity=full
∧ dns_topology=ordinary ∧ evidence_age_bucket=fresh
→ eligible=true
```

Only a policy-mode transition from that eligibility and safe prior executor state may
produce `apply_public_override`.

In `mode=policy`, all other eligibility combinations preserve link DNS when the prior
effect is definitely `none`, and revert when the prior effect or receipt is pending,
active, expired, invalid, or unknown. Unknown state conservatively reverts. Replayed
`admit`/`refresh` events for the same fresh active receipt are idempotent and may refresh
the receipt but cannot stack effects. Restart rehydrates only a valid same-boot receipt;
missing, cross-boot, invalid, expired, or ambiguous receipts cause revert. Downgrade,
link-down and watchdog expiry always cause revert. In `mode=legacy`, the transition emits
only `legacy_override` for the current Wi-Fi events so N2 can prove exact current behavior.

### 4.3 Trust and expiry

Trust is an owner-managed, root-owned local allowlist capability, not inferred from a
network name or reachability. Its canonical path is
`/var/lib/aq-network-policy/private/trusted-profiles.json`, in a root-owned `0700`
directory with a root-owned `0600` regular file. It may contain NetworkManager profile
UUIDs only for local matching; those identifiers never enter resolver output, status,
logs, test evidence, API or dashboard. Updates take a stable root-owned `0600` lock at
`/run/lock/aq-network-policy/trusted-profiles.lock`, write a `0600` temporary regular file
in the same directory, validate the closed schema, `fsync` file, atomically rename, and
`fsync` the directory. Symlinks, wrong ownership/mode, parse failure, lock timeout, or
write failure yield `connection_class=unknown` and prohibit an override.

The executor's sole effect receipt is
`/run/aq-network-policy/private/override-lease.json`, under a root-owned `0700` directory
as a root-owned `0600` regular file. It contains a closed schema version, boot ID,
validated interface name, policy revision, monotonically increasing receipt revision,
state (`pending_apply`, `active`, `pending_revert`, `inactive`), monotonic issue/expiry
values and an action digest. These private fields are
never projected. Exactly one receipt is retained: before applying an effect the executor
atomically publishes `pending_apply`; before reverting a possible effect it atomically
publishes `pending_revert`; after apply success it atomically publishes `active`; after a
successful revert it atomically replaces that with identifier-free `inactive`. Receipt
writes use a stable root-owned `0600` lock, same-directory `0600` temporary file,
validation, file `fsync`, rename and directory `fsync`. Failure before a durable pending
receipt prohibits apply; failure after pending or uncertain apply triggers revert and a
closed degraded projection.

The public maximum effect lifetime is **90 seconds**. An internal receipt expires 55
seconds after the last fresh permit, reserving the remaining budget for an independent
watchdog. A root-owned timer starts within 5 seconds of boot and runs every 10 seconds
with at most 1 second of jitter; its complete recovery transaction has a 15-second
deadline, including lock wait, bounded revert and durable publication. Thus a normally
scheduled expiry completes its revert transaction by 81 seconds, leaving nine seconds of
margin even if no dispatcher event arrives. The timer is independent of dispatcher lifecycle and runs on
restart; invalid/missing/cross-boot/expired/unknown effect state is handled as revert.
Timer/service failure publishes degraded state and an `OnFailure` emergency revert unit;
the implementation must not claim a hard guarantee across kernel or PID 1 unavailability.

Each eligible full result refreshes the lease. Link-down, connectivity downgrade, policy
removal, parser error, restart ambiguity, or expiry restores the NetworkManager-provided
link configuration. The enforcement mechanism must use
`resolvectl revert <interface>` (or an equivalent documented resolved operation) rather
than write `/etc/resolv.conf` or alter global resolved security settings.

### 4.4 Bounded acquisition

The runtime acquisition adapter accepts only a validated dispatcher interface token
matching `^[A-Za-z0-9_.:-]{1,32}$` and proves it is Wi-Fi through local sysfs. It invokes
only these fixed argv shapes without a shell (where `IFACE` is the validated token):

```text
["nmcli", "--terse", "--fields", "CONNECTIVITY", "general"]
["nmcli", "--get-values", "GENERAL.CON-UUID", "device", "show", IFACE]
["resolvectl", "domain", IFACE]
```

The first supplies NetworkManager connectivity, the second is consumed only inside the
private trust lookup, and the third is a read-only per-link split-domain query. Each has a two-second
deadline, captures at most 16 KiB combined output, uses a fixed locale/environment
allowlist, and rejects truncation. Exit, timeout, permission, missing-command, oversized,
or parse errors map only to closed enums; stderr and raw output are never persisted or
projected. This adapter performs no DNS, HTTP, captive-portal or provider request.

### 4.5 Serialized effect-operation transaction

Every path that can apply, refresh, revert, recover, or adjudicate a possible DNS effect
(dispatcher, watchdog, downgrade/link-down, duplicate event, emergency recovery and
restart recovery) must acquire one stable exclusive `flock` on
`/run/lock/aq-network-policy/effect-operation.lock`. The lock inode is root:root `0600`,
created without pre-lock truncation, and is never renamed or replaced. The kernel releases
the advisory lock when a process crashes; the persistent inode carries no PID ownership
claim and cannot become a stale logical lease.

The exclusive lock spans the entire transaction:

```text
bounded current-fact acquisition
→ receipt read/validation
→ pure eligibility + transition decision
→ durable pending_apply or pending_revert receipt
→ bounded resolvectl apply/revert
→ durable active or inactive final receipt
→ final health publication
```

No effect command may run before its pending receipt is durable. After the pending receipt
and before the effect, the lock holder publishes `transitioning`. No final health state may
publish before the corresponding final receipt is durable; it is derived from that exact
in-memory final receipt without exposing its revision. `policy_state=overriding` is
legal only after an `active` receipt; a pre-effect health update, if emitted, is
`policy_state=transitioning`. If final health publication after apply fails, the same lock
holder immediately performs the fail-safe revert sequence rather than leave a dark
override. If final receipt publication after an effect command is uncertain, recovery
treats the effect as present and reverts.

Nested lock order is globally fixed:

1. effect-operation lock (outermost, effect paths only);
2. trusted-profile mapping lock (read snapshot, then release);
3. receipt lock (read/write, then release); and
4. health lock (publication only after the receipt lock is released).

No code may acquire an earlier lock while holding a later lock. Trust replacement takes
only the mapping lock. Passive N1 collection takes only the health lock and is disabled
before policy mode activates. In policy mode, only an effect-lock holder may publish
authoritative health. Policy-mode N2 effect paths always take the outer effect lock and
follow the order above.

Effect-lock acquisition has a two-second first-attempt deadline. Dispatcher/refresh paths
that cannot acquire it fail safe without applying and return a bounded local contention
result without overwriting authoritative health. Watchdog/recovery paths retry the
same stable lock every 250 ms for at most five seconds, then invoke the closed OnFailure
path; they never bypass the lock to mutate resolved state. Current-fact acquisition occurs
inside the effect lock with the existing two-second per-command and a four-second total
budget. Every resolved mutation has a five-second deadline, and the complete normal
transaction, including acquisition, mutation, receipt and health, is capped at 15 seconds.
Timeout or uncertainty transitions to `pending_revert` and
an idempotent revert while the same lock remains held.

Receipt revision is allocated only while the effect lock is held. A delayed event never
uses a pre-lock connectivity or trust snapshot: it reacquires current facts and the latest
receipt under the lock. Consequently an apply based on an older observation cannot land
after a higher-revision revert. Duplicate apply requests observe the active receipt and
become an idempotent refresh/no-op. Watchdog and refresh serialize; whichever acquires the
lock second must decide from the first operation's durable final receipt and newly acquired
facts.

On process crash, the kernel releases the effect lock. On service or host restart, recovery
first reacquires that same lock. `pending_apply`, `pending_revert`, invalid, expired,
cross-boot, missing-with-unknown-effect, or otherwise ambiguous state is handled as
effect-present and reverted before any new apply is eligible. An `active` same-boot fresh
receipt may be refreshed only after new current facts independently re-earn eligibility.

## 5. Observability and data minimization

One root-written read-only projection at `/run/aq-network-policy/health.json`,
`network.dns-policy-health.v1`, is the authority for CLI, Phase-0, API and dashboard.
It uses the same stable-lock, regular-file, owner/mode, bounded-write, `fsync` and atomic
rename rules as the receipt, but excludes every private receipt/trust field. Readers do
not independently interrogate NetworkManager or resolved. It contains only closed
low-cardinality fields:

- `policy_state`: `preserving`, `transitioning`, `overriding`, `reverted`, `degraded`, `unavailable`;
- `connectivity`: the six-value normalized enum;
- `reason`: the closed reason enum;
- `freshness`: `fresh`, `stale`, `unknown`;
- `lease`: `active`, `expired`, `not_applicable`, `unknown`;
- `last_transition_age`: `lt_30s`, `lt_2m`, `lt_15m`, `gte_15m`, `unknown`;
- `transition_count_bucket`: `0`, `1`, `2_5`, `6_plus`, `unknown`;
- `acquisition_error`: `none`, `unsafe_interface`, `missing_command`, `timeout`,
  `nonzero`, `permission`, `too_large`, or `malformed`; and
- `schema_version`.

It contains no identifiers, addresses, domains, credentials, process arguments, free-form
errors, timestamps, or raw commands. The collector stores only the bounded projection,
not an event log. A failure to read state becomes `unavailable`, never a fabricated
healthy value.

The dashboard renders a Network Resilience card with state, reason, freshness, lease and
last-transition bucket plus a link to the local runbook. Phase-0 invokes the same local
machine projection and fails if the schema is missing, invalid, stale when an override is
reported, or inconsistent (`overriding` with any non-permit reason). No health check makes
an external DNS, HTTP, captive-portal, or provider request. NetworkManager's existing
external connectivity check is an input owned by NetworkManager; it is not credited as
this feature's integration probe or availability evidence.

## 6. Security, safety, and rollback invariants

1. **Least authority:** only the NetworkManager dispatcher/timer execution path may change
   per-link resolved state; dashboard, Phase-0, CLI, and policy resolver are read-only.
2. **Fail safe:** uncertainty restores/preserves DHCP/link DNS; it never defaults to public
   resolver routing.
3. **Bounded effect:** in policy mode, the independent watchdog completes the bounded
   revert transaction no later than 90 seconds after the last fresh positive local decision under a functioning kernel
   and service manager; no dispatcher heartbeat is required.
4. **No identity telemetry:** profile matching occurs before redaction and cannot be
   reconstructed from status, logs, metrics, or dashboard payloads.
5. **No global regression:** the `/etc/resolv.conf` stub, resolver hardening, firewall and
   NetworkManager-to-resolved integration remain unchanged.
6. **No remote orchestration:** no automatic remediation, external probe, provider call, or
   DNS test is part of the feature.

Rollback has two distinct meanings. Before N3, `mode=legacy` is the deployment default and
must be exact current behavior. During an N3 policy canary, fail-safe abort first reverts
the affected link and leaves `mode=policy` with no eligible trusted profile so link DNS is
preserved. A separately authorized declarative rollback may restore `mode=legacy`; that
restores the old universal override and is therefore reported as compatibility rollback,
not as the fail-safe network state. Neither path disables systemd-resolved or the firewall.

## 7. Acceptance criteria

- Pure vectors prove every enum combination and malformed input fails closed.
- `portal`, `limited`, `site`, `split`, `unknown`, stale and non-Wi-Fi inputs never permit
  the public DNS/`~.` override.
- A valid trusted/full/ordinary/fresh input permits exactly one bounded override decision.
- Expiry and downgrade vectors require a rollback decision.
- Idempotent admit/refresh replay, restart with every receipt state, pending-apply/revert
  crash, watchdog-without-dispatcher, fake-clock boundary and command-timeout vectors pass.
- Deterministic barrier-controlled races prove admitted apply versus downgrade/revert,
  watchdog versus refresh, duplicate apply, and crash/restart before and after lock release
  converge to the latest safe receipt; no apply can land after a newer revert.
- Telemetry and API/dashboard payload validation prove secrets and identifiers cannot appear.
- Phase-0, its Bash compatibility check, and the dashboard consume the same versioned
  projection and detect schema/semantic disagreement.
- The first live enforcement occurs only after explicit owner activation and the two-network
  canary in the program plan passes; no design or implementation authorization implies it.

## 8. Delivery sequencing

The execution plan is `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`.
N0 is pure/offline; N1 provides passive Service Coverage; N2 lands `mode=policy` while
retaining `mode=legacy` as the exact deployment default; only N3 may select policy mode
for an owner-operated canary/cutover. Each is independently
reviewed and hash-bound before implementation.
