> **Status (2026-10-15):** frozen, PLAN_READY_WITH_FOLLOWUPS (v2.1; confirmatory review applied).
> **Landed:** AUTH-S1 coordinator guard (PR #524, commit 7f1f7282 `fix(security): coordinator Host/Origin/content-type guard ... (AUTH-S0)`; that commit and `middleware/http_guard.py` use the v1 numbering "AUTH-S0", which is v2 AUTH-S1 for the coordinator). Switchboard and dashboard guards (rest of S1) are still open.
> **This slice (feat/agent-auth-s0-s2):** AUTH-S0 (constant-time compare, required-key fail-closed, audit no longer logs the raw credential, Tempo gRPC loopback) and AUTH-S2 (policy file, matcher, shadow engine, Nix options, metrics, stats/explain, policy lint, benchmark). Evidence: `docs/harness-first/evidence/2026-10-15-agent-auth-s0-s2.md`.
> **Supporting documents (not copied):** v1 `agent-auth-DESIGN.md` (inventory, threat model, scope catalogue 4.1-4.5) and the two reviews live in `.agents/delegation/outputs/sota-designs-20261014/` (gitignored). This file is v2.1 verbatim below the header; v1 sections it cites are v1's.

# Agent Authentication and Authorization, v2 (responds to adversarial review F1-F11)

Status: PLAN_READY_WITH_FOLLOWUPS, frozen for AUTH-S0, S1, S2 and AUTH-S8, S9 (v2.1, confirmatory review `agent-auth-DESIGN-v2-REVIEW.md` applied). S3-S7 and S10 are PLAN_READY_WITH_FOLLOWUPS: build them with the v2.1 requirements below. Date 2026-10-14. Supersedes v1 only where this file says so; v1 (`agent-auth-DESIGN.md`) is kept and its inventory (v1 section 1), threat model (v1 section 2), option comparison (v1 section 3 table) and scope catalogue (v1 section 4.1-4.3) remain valid and are not repeated. Review: `agent-auth-DESIGN-REVIEW.md`.

## v2.1 changes (confirmatory review N1-N5)

| ID | Change | Where |
|---|---|---|
| N1 | First S3 acceptance test: the coordinator unit can read `/proc/<owner-pid>/cgroup`; short-lived CLI race handled by a bounded retry-free resolution path plus an unknown-rate gate from a 10k-client burst test; deny body carries a retry hint | 2.1 step 6, 8.1 S3, 9 |
| N2 | S5 (enforce) depends on S7 per client: no client loses `X-API-Key` access to a route before it is migrated; per-client migration checklist | 8.1, 8.3 |
| N3 | Until the key file is tightened the owner agent can still obtain `admin` through the readable key; the table row is corrected; key tightening is an explicit step after S7 | 1, 5.3, 8.3 |
| N4 | Lockdown restart exit drops in-memory coordinator state; shadow-to-enforce flip is the same owner-class DoS class and is accepted | 6.2 |
| N5 | Switchboard uses an `httpx` UDS transport for its single `GET /hints`; the `memory.write` default for `service:switchboard` is dropped | 5.2, 8.1 S4 |
| F4 residual | Approved elevated scope is effectively held by the launching agent's process tree (`ptrace_scope=1`); pid-namespace case for the broker specified | 3.4 |

## Outline (sections are filled one at a time below)

- 0. Changes from v1 (F1..F11 table, accept/reject with reasons)
- 1. Corrections to v1 facts found while answering the review
- 2. Caller identity, hardened (F1, F2): full cgroup path match, raw SO_PEERPIDFD, honest boundary statement
- 3. Grant issuer, narrowed and deferred (F3, F4, F11): strictly-narrower minting, new key, issuer-generated run_id, peer-bound tokens
- 4. research.fetch and SSRF (F5): pinned-IP connect, per-hop re-check, tighten-only switches
- 5. Switchboard and API-key containment, pulled forward (F6)
- 6. Mode lifecycle (F7, F8, F9): shadowUntil, red health, lockdown exit, clock handling
- 7. Performance gate (F10)
- 8. Revised slice plan and MVP cut (F6, F11)
- 9. Hostile test additions
- 10. Owner decisions (revised)

## 0. Changes from v1

All eleven findings are accepted. Two are accepted with a different mechanism than the reviewer suggested (F4 group, F9 treatment); the reasons are given in the row.

| ID | Sev | Reviewer finding | Disposition | Change in v2 | Section |
|---|---|---|---|---|---|
| F1 | HIGH | Suffix cgroup match lets an owner `systemd-run --user --unit=X` spoof a service class | Accepted | Match the FULL path `/system.slice/<unit>.service` only, from an explicit list of full paths in the policy. Anything under `/user.slice/`, `user@*.service`, `session-*.scope` is `owner-agent`. New hostile test using the user manager | 2.2, 9 |
| F2 | MED | `SO_PEERPIDFD` not exposed by Python; start-time fallback weak; owner-uid services are not a boundary | Accepted | Raw constant 77 via `getsockopt`, pidfd-based liveness check around the `/proc` read, any failure resolves to `unknown` (no fallback). Explicit statement that `service:*` classes on owner-uid services (switchboard, dashboard) are attribution and least-privilege, not a boundary against a same-uid agent | 2.1, 2.3 |
| F3 | HIGH | `self_service` mint is open to any owner-uid caller; key name collides; `aiSvcMode` makes the key owner-readable | Accepted | `self_service` is only allowed when the requested scope set is a strict subset of the caller's own rights, resolved by the issuer itself; the closed list of self-service profiles is given; `no_delegate` scopes never mintable. New secret name `aq-agent-auth-signing-key`, `0400`, owner = issuer user, not the `aiSvcMode` pattern. CLI renamed `aq-agent-auth` to stop colliding with the existing "grant" vocabulary (`aq-grant-signing-key`, `secrets.nix:87-97`) | 3.1-3.3 |
| F4 | MED | `run_id` caller-chosen; sandbox socket reachable by the owner | Accepted in intent, different mechanism | `run_id` is generated by the issuer and bound to the requesting launcher's peer identity; the token is bound to the broker's peer identity (pid + start time via pidfd) and checked on the sandbox listener. The reviewer's "group the owner is NOT in" is rejected because the broker is an owner-uid child and could not connect; it stays a follow-up only if the broker ever gets a dedicated uid | 3.4 |
| F5 | MED | SSRF check resolves once, connects later (TOCTOU); env off-switch; `enforce_ssrf = transport is None` | Accepted | Pinned-IP connect through a validating aiohttp resolver, per-hop re-check kept, `HYBRID_BLOCK_PRIVATE_EGRESS` made tighten-only (ignored when false under enforce), test seam no longer disables SSRF in production code, headless-browser fetch split into its own scope and not defaulted. Default `research.fetch` for `owner-agent` flips only after S6 | 4 |
| F6 | MED | Switchboard is an unauthenticated confused deputy holding the coordinator key; S9 is last | Accepted | New slice AUTH-S4 before enforce: switchboard gets the L0 guard, its coordinator identity is narrowed to a low-risk class, and the coordinator `api-key` mode loses non-admin scopes under enforce. Until then the doc states scope enforcement is bypassable via `:8085` and via the readable API key. Unverified services get a dated probe task | 5, 8 |
| F7 | MED | Shadow can become permanent | Accepted | Nix `shadowUntil`; after it passes the health-spider is RED (not WARN), metric and tracker signal; no silent auto-enforce. Compat window and bridge TCP-fallback removal are tied to `shadowUntil` as a default, not an owner decision | 6.1 |
| F8 | MED | Lockdown has no runtime exit | Accepted | Stated plainly; owner exit is one command (`sudo systemctl restart ai-hybrid-coordinator`, which clears the tmpfs mode file and returns to the Nix-declared mode); lockdown recovery allow-set defined so recovery tooling keeps working | 6.2 |
| F9 | LOW | Clock skew not addressed | Accepted as a one-paragraph statement (no new mechanism) | Single host, monotonic deadlines for cache entries, 60 s cache cap against wall-clock steps | 6.3 |
| F10 | LOW | 0.10 ms gate not measurable with curl | Accepted | In-process aiohttp test-client benchmark, n >= 5000 after warmup, with-versus-without middleware, p50/p95/p99 gate; curl numbers are informational only | 7 |
| F11 | minimal | Issuer only needed for delegated callers; possible over-build | Accepted | Issuer deferred until aq-confine S2d is scheduled; UDS classes need no token (unchanged); MVP cuts: audit-sidecar mirror, hints-engine lesson feed, new dashboard panel. Verified that `verify_authoritative` does not check `source` (section 1) but holders cannot attenuate Ed25519 leases themselves, so narrowing is issuer-mediated | 1, 3.5, 8 |

## 1. Corrections to v1 facts

Verified on 2026-10-14 while answering the review. These replace the corresponding v1 statements (several v1 `[UNVERIFIED]` items are now resolved).

| Topic | v1 said | Now verified |
|---|---|---|
| Cell-runner path | `execution_cell_runner.py:545-570` (bare) | `ai-stack/switchboard/execution_cell_runner.py:545-570` is the `SO_PEERCRED` helper. `scripts/ai/lib/revocation_epoch_transport.py:68` and `workflow_deviation_transport.py:83` carry the same pattern |
| Research module | "`extensions/web_research.py` duplicates the module" | `ai-stack/mcp-servers/hybrid-coordinator/web_research.py` is a 2-line shim; the real module is `.../extensions/web_research.py` (428 lines). No dedupe slice is needed |
| SSRF strength | `[UNVERIFIED]` | Shared guard is `ai-stack/mcp-servers/shared/ssrf_protection.py`. It resolves once with `socket.getaddrinfo` (`:80`) and returns; a resolution failure blocks (`:81-84`). Policy comes from env: `HYBRID_OUTBOUND_ALLOWLIST` (default empty), `HYBRID_BLOCK_PRIVATE_EGRESS` (default true, can be set false, `:42`), `HYBRID_ALLOW_PLAINTEXT_HTTP`. The caller (`extensions/web_research.py:156-157`) validates, then the HTTP client resolves again at connect: a DNS-rebinding TOCTOU. Redirects ARE re-validated per hop (`:165-166`), but with the same resolve-once weakness. `enforce_ssrf = transport is None` (`:312`) disables the guard whenever a transport is injected |
| Grant verifier | "unknown whether `verify_authoritative` accepts source `agent-grant`" | `capability_lease.verify_authoritative` (`scripts/ai/lib/capability_lease.py:361-446`) requires `sig_scheme == ed25519`, resolves `issuer_key_id`/`key_id` in the supplied key set, checks the key is active and the signature; it does not inspect `source`. So a separate key set (own file) is the domain separator, not the `source` field |
| Attenuation | "holders can attenuate" | `attenuate(parent, delta, key)` signs the child with a caller-supplied `key` through `sign()` (`capability_lease.py:191,505-530`), the HMAC path [Ed25519 child signing UNVERIFIED]. A holder has no Ed25519 private key, so narrowing must be issuer-mediated. Reuse `attenuate`'s subset checks (`_check_constraints_tighten`, `:457`) as the narrowing rules, not as a holder-side operation |
| `SO_PEERPIDFD` | "availability UNVERIFIED" | `hasattr(socket, "SO_PEERPIDFD")` is False in the system Python 3.13 here; `os.pidfd_open` exists. Kernel 7.2.10 supports the option (reviewer; raw constant 77 on Linux). Must be verified by a `socketpair`/`AF_UNIX` test as the first act of AUTH-S3 |
| API key as bypass | "`admin` via key path" | In `resolve_auth_context` (`middleware/auth.py:200-207`) a valid key yields mode `api-key`, which today carries every profile including `worktree-guarded`. Since the owner uid reads the key (`secrets.nix:95-110`), the `api-key` mode is a complete bypass of any per-scope policy until it is narrowed (section 5.3). **Correction (N3):** v1's class table showed `owner-agent` with no `admin`; that is true only after the key file is tightened. Until then the owner agent can read the key and obtain `admin` (all unlisted `/control/*` and `/api/*`, the largest mutating set), so the v1 table's `admin` column for `owner-agent` must be read as "yes, via the readable key, until step K in 8.3" |
| Secret naming | "mirror `lease-signing-authority` / `aiSvcMode`" | `aq-grant-signing-key` is the C3b execution-grant key (`nix/modules/core/secrets.nix:87-97`), mode `aiSvcMode` (`root:ai-stack 0440`). The new key needs a new name and a stricter mode (section 3.2) |

## 2. Caller identity, hardened (F1, F2)

### 2.1 Resolving the peer (F2)

Applies to every unix-socket listener. Executed once per accepted connection, result cached on the connection object (class is fixed for the connection's life).

1. `SO_PEERCRED` -> `(pid, uid, gid)` using the existing helper pattern (`ai-stack/switchboard/execution_cell_runner.py:545-570`).
2. `getsockopt(SOL_SOCKET, 77, 4)` (raw `SO_PEERPIDFD`, because `socket.SO_PEERPIDFD` is absent) -> a pidfd. The constant is defined once in `peer_identity.py` as `_SO_PEERPIDFD = 77` and covered by a startup self-test (connect a `socketpair`/loopback UDS to ourselves, expect our own pid back).
3. Read `/proc/<pid>/cgroup` and `/proc/<pid>/stat` field 22 (start time), then run the liveness check `signal.pidfd_send_signal(pidfd, 0)`. A success after the read proves the pid was not recycled during the read. Compare the pid from step 1 with the pid reported through `/proc/self/fdinfo/<pidfd>` (`Pid:` line); a mismatch is a failure.
4. Any failure (option unsupported, `ENOPROTOOPT`, fdinfo mismatch, process already gone, `/proc` unreadable) resolves to class `unknown`: health only, plus an alert. There is no start-time-only fallback; a kernel lacking the option means UDS authorization degrades to `unknown`, which is visible and safe, not silently weaker.
5. Short-lived clients (N1). `curl`, `aq-hints` and `aq-resume` can connect, send and exit before the server reads `/proc`. Because the pidfd from step 2 is taken at accept time it still refers to that process even after exit; a process that is a zombie or not yet reaped still has a readable `/proc/<pid>/cgroup`. If the process has already been reaped, the cgroup is read from the pidfd's own `/proc/self/fdinfo/<pidfd>` data only for the pid check, and the cgroup read fails: the connection resolves to `unknown` for that request only (not cached for the peer, since the connection is closing). Mitigations, in order: (a) the listener calls the resolver immediately in the accept callback before reading the request; (b) the deny body for an `unknown` caused by `reason=peer_gone` carries `retryable: true` and a hint to retry (the client helper `aq_http` retries once automatically on that reason, idempotent GETs only); (c) a measured gate: in a burst test of 10k short-lived clients the `unknown` rate must stay under 0.1 percent, and any `peer_gone` request is read-only in effect because `unknown` only ever gets health, so the race can degrade convenience, never widen access.
6. First S3 acceptance test (N1): as the coordinator's service user (`ai-hybrid`), read `/proc/<pid>/cgroup` and `/proc/<pid>/stat` of a process owned by the owner uid. If this fails (`hidepid`, `ProtectProc=`, or a hardening option on the unit), S3 stops there and the Nix unit is fixed first (`ProtectProc=default`, `ProcSubset=all`); the design does not substitute a weaker identity source. No `ProtectProc`/`hidepid` setting was found in `mcp-servers.nix` [grep-based, UNVERIFIED until the test runs].
7. The pidfd and start time are kept on the connection so later checks (peer-bound tokens, section 3.4) compare against the same process identity.

Connection semantics: a connection inherits the class of the process that opened it. A keep-alive connection whose file descriptor is later passed to another process keeps the opener's class. This is accepted for same-uid callers and is a recorded residual for `service:*`.

### 2.2 Class from cgroup (F1)

The class table is data in `config/agent-auth-policy.json`:

```
"units": {
  "/system.slice/ai-gap-auto-remediate.service":        {"class": "service:timer-gap-remediate", ...},
  "/system.slice/command-center-dashboard-api.service": {"class": "service:dashboard", ...},
  "/system.slice/ai-switchboard.service":               {"class": "service:switchboard", ...}
}
```

Rules, evaluated in this order:
1. The cgroup path from `/proc/<pid>/cgroup` (the unified `0::` line) must be EQUAL to a listed full path. No suffix, prefix, glob or `endswith(".service")` matching. Unit names in the table are written as full paths so the table, not code, defines the set. Template and `Slice=`-grouped units are listed by their exact resolved path.
2. Any path beginning `/user.slice/` (this covers `user@1000.service/app.slice/...`, `session-*.scope`, `user@1000.service/background.slice/...`) is `owner-agent` when `uid == owner`, otherwise `unknown`.
3. Any other path under `/system.slice/` that is not listed resolves to `unknown` when uid is not the owner, and to `owner-agent` with a `reason=unlisted_unit` audit field when uid is the owner (an unlisted owner-uid system service is treated as the least-privileged owner class, never as a named service class).
4. `uid != owner` on `agent.sock` is `unknown` unless the uid is explicitly mapped (none by default).

Why this holds: an unprivileged user cannot create a unit under `/system.slice/`; `systemd-run --user --unit=ai-gap-auto-remediate` lands in the user manager's tree (`/user.slice/user-1000.slice/user@1000.service/app.slice/ai-gap-auto-remediate.service`), so rule 2 classifies it as `owner-agent` regardless of its name. A user could in principle start a unit through a polkit-authorised system manager action; that requires owner sudo/polkit, which is outside the threat model (root-equivalent).

### 2.3 What the classes are and are not (F2, stated plainly)

- `switchboard` and the dashboard API run as the owner uid (switchboard pid 4929 and uvicorn pid 4930 observed as `hyperd`; `nix/modules/services/mcp-servers.nix` `svcUser`). An owner-uid agent process can ptrace or inject into them whenever Yama allows it (`ptrace_scope=1` only restricts non-descendants; a shared parent such as the same shell or editor is enough), can read their `/proc/<pid>/environ`, and can run code in their cgroup only with privilege but does not need to: it can simply connect to `agent.sock` as `owner-agent`.
- Therefore `service:switchboard` and `service:dashboard` are NOT a security boundary against a same-uid agent (threat T1). They provide: (a) attribution in the audit log, (b) least privilege between honest components and containment of accidents (a bug in the dashboard cannot accidentally call `safety.loosen`), (c) a boundary against other uids and against sandboxes. A real boundary against T1 requires one of: moving these services to dedicated uids, or confining the agent with aq-confine. Both are outside MVP and are recorded as a follow-up, not claimed as delivered.
- The only classes that are real boundaries against a compromised owner-uid agent are those whose services run under a different uid: `ai-hybrid` (the coordinator itself), the dedicated authority users (lease, epoch, scheduler-context, and the future agent-auth issuer), and `llama`.
- Consequence for decisions: do not put any scope in a `service:*` default that you would not give to `owner-agent` and then claim it is protected. Section 5 applies this to the switchboard.

## 3. Grant issuer, narrowed and deferred (F3, F4, F11)

Scope of this section: tokens exist only for DELEGATED callers (aq-confine sandboxes and spawned sub-agents). UDS-only `owner-agent` and `service:*` classes need no token and no issuer (unchanged from v1 and confirmed by F11). The issuer is therefore built with the sandbox slice, not before (section 8).

### 3.1 What may be minted (F3)

The issuer resolves the requester's class itself (same `peer_identity` code, same cgroup rules as section 2; it never trusts a class claimed in the request) and applies three rules:

1. **Strict subset.** A profile is mintable without approval only if its scope set is a STRICT subset of the requester's own current rights (the class default from the policy file, minus anything revoked), with every constraint at least as tight (TTL, rate, resources). Equal or wider sets need an approval receipt (3.3).
2. **Closed self-service list.** The only profiles marked `self_service: true` in the policy file are:
   - `sandbox-readonly`: `read.hints`, `read.status`, `prsi.read`, `safety.tighten`.
   - `child-readonly`: the same set, for sub-agents spawned by `agent_spawner`, with `max_children = 0`.
   No other profile may carry `self_service`. A tier0 lint fails the build if a `self_service` profile is not a strict subset of `owner-agent` defaults or contains a `no_delegate` scope.
3. **`no_delegate` scopes are never mintable:** `safety.loosen`, `admin`, grant/mode management, `memory.write` without the server-side provenance stamp. A grant can carry `memory.write` only when the policy marks the profile `stamped: true`; the coordinator then records `writer_class=sandbox`, `writer_run_id`, `grant_jti` on the row.

Honest consequence, stated for the owner: a prompt-injected owner-uid agent can mint `sandbox-readonly` for itself. That token is weaker than what it already has, so this grants nothing. It cannot mint anything broader without an owner `aq-approve`. The issuer protects against sandboxes and spawned children being given more than their parent has; it is not a defence against the owner-uid agent itself (that is aq-confine's job).

Parentage: every minted grant records `parent` = `class:<resolved class>` (when minted for a class) or the presented parent `jti` (when minted for a child of an existing token). A child token's scopes must be a subset of its parent token's scopes and its `exp` must not exceed the parent's; the issuer verifies the parent token's signature and revocation state before minting. Narrowing is issuer-mediated (section 1, attenuation row); the subset logic reuses `capability_lease._check_constraints_tighten` (`scripts/ai/lib/capability_lease.py:457`).

### 3.2 Key, secret and service identity (F3)

- New SOPS secret name `aq-agent-auth-signing-key`. It is NOT `aq-grant-signing-key` (the C3b execution-grant key, `nix/modules/core/secrets.nix:87-97`) and not the lease signer key.
- Declared in `secrets.nix` with explicit `mode = "0400"`, `owner = "aq-agent-auth-issuer"` (the issuer's own system user), `group = "aq-agent-auth-issuer"`. It must NOT use the `aiSvcMode`/`aiSvcOwner`/`aiSvcGroup` pattern (`root:ai-stack 0440`, `secrets.nix:65-70,87-110`), which makes the key readable by the owner uid through group `ai-stack`. Acceptance test: `test ! -r /run/secrets/aq-agent-auth-signing-key` as the owner uid, and the issuer starts only if the file is owned by its own uid with no group/other bits.
- Public keys live in a NEW file `config/aqos/agent-auth-signer-keys.json` (not `lease-signer-keys.json`). Because `verify_authoritative` does not look at `source` (section 1), separate key sets are the domain separator: a lease signed by the lease authority can never verify as a grant, and vice versa. A domain-tag prefix `aq.agent-auth-grant/1` is also included in the signed canonical bytes.
- Names: unit `aq-agent-auth-issuer`, socket `/run/aq-agent-auth-issuer/control.sock` (path from a Nix option), client group `aq-agent-auth-clients`, CLI `aq-agent-auth` (replaces v1's `aq-grant`, whose name collides with the execution-grant vocabulary). Nix module `nix/modules/services/agent-auth-issuer.nix` mirrors the structure of `lease-signing-authority.nix` (dedicated user, UDS, default `enable = false`) but not its secret handling or its "ignore the request body" semantics.
- Owner act: add the SOPS key (`sops <secrets file>`), then enable the unit. The issuer fails closed and mints nothing if the key is absent or has wrong permissions.

### 3.3 Approvals above the default

An above-default request (equal or wider than the requester's rights, or a profile not marked `self_service`) creates an attention-queue `human_gate` item via `attention_queue.push` (`scripts/ai/lib/attention_queue.py:237`) and a new `aq-approve` executor `agent_scope_grant` in `_EXECUTOR_TABLE` (`scripts/ai/aq-approve:126-130`). The owner approves with `aq-approve approve N` (the approver prompts, per repo rules). The executor records an approval receipt `{ticket, requester_identity, run_id, scopes, exp}`; the issuer mints only against a receipt whose `requester_identity` matches the live requester and whose scopes match exactly. Approved scopes are bound to the run and expiry; they are the only way a grant exceeds the owner-agent ceiling. Receipt storage and signature format [UNVERIFIED; follow the `confine_egress_grant` executor pattern in the aq-confine design].

### 3.4 Run and token binding (F4)

- **`run_id` is issuer-generated**, never caller-chosen. The request enum is `{profile, ttl, parent_jti?}`; the response is `{run_id, token}`. The issuer records `run_id -> {requester uid, requester pidfd start time, requester cgroup, profile, exp}`.
- **Launcher authority.** Only the recorded requester (the aq-confine launcher process identity) or an owner `admin` revoke may `revoke run_id` or ask for its status. Another owner-uid process cannot name or mint a token for someone else's live `run_id` because it cannot choose the id.
- **Broker registration.** After the launcher starts the per-run egress broker it calls `register_peer(run_id, broker_pid)`; the issuer reads the broker's identity through a pidfd it obtains with `pidfd_open` while confirming the broker is a child of the launcher (`PPid` equals the launcher pid) and records `bound_peer = (pid, start_time)`. The token carries `bound_peer_hash`.
- **Token hand-off.** The token goes launcher -> broker over an inherited file descriptor (pipe), never an environment variable or file. The broker has an empty environment (aq-confine design). The sandboxed process never receives it.
- **Verification on the `sandbox` listener.** The coordinator resolves the connecting peer with section 2.1; the token is accepted only if (a) signature/epoch/revocation pass, (b) `constraints.listener == "sandbox"`, (c) the peer's `(pid, start_time)` hash equals `bound_peer_hash`. A copy of the token used from any other process is denied and raises a high alert (`wrong_peer`). Cost: one comparison per new connection.
- **Why not "a group the owner is not in" (reviewer's alternative):** the broker is an owner-uid child, so excluding the owner from the socket group would exclude the broker. Peer-bound tokens plus issuer-generated ids give the same replay resistance without a new uid. If the broker later gets a dedicated uid, put `sandbox/` in that uid's group and keep the token binding as defence in depth.
- **Approved elevated scopes are effectively held by the launching agent's process tree (F4 residual).** `kernel.yama.ptrace_scope` is 1 on this host, which allows an ancestor to ptrace its descendants; the launching agent is an ancestor of the broker. It can inject into the broker and use the broker's already-bound connection, which defeats the peer binding. Treat any approved elevated scope as granted to that whole process tree for the run, and approve accordingly. The peer binding still stops every process outside that tree.
- **Pid-namespace case.** `SO_PEERCRED` and `SO_PEERPIDFD` report the pid in the receiver's pid namespace (0 or a translated value when the peer is in another namespace). If the broker runs in a different pid namespace than the coordinator, `bound_peer` is built from the pidfd identity and the cgroup path instead of the numeric pid: the broker registers with the issuer by passing a pidfd (SCM_RIGHTS) from which the issuer reads `fdinfo`/start time in its own namespace, and the coordinator compares the process identity it derives from its own `SO_PEERPIDFD` pidfd (start time plus cgroup path as seen in the coordinator's namespace) rather than the number. A peer whose pid is 0 or untranslatable resolves to `unknown` and the token is denied (`wrong_peer`). The broker in aq-confine v3 is a host-namespace child of the launcher (the sandbox, not the broker, is namespaced), so this is a guard, not the expected path [broker pidns UNVERIFIED against aq-confine v4].
- **Residual (stated):** an owner-uid ancestor of the broker (the agent that launched the sandbox) can inspect its memory under Yama (`ptrace_scope=1` permits ptrace of descendants) and steal the token. Mitigated by: the token is bound to the broker peer so a stolen copy fails from any other process; self-service profiles are weaker than the owner-agent's own rights anyway; elevated approved scopes are short-lived, run-bound and audited. Not mitigated: code injected into the broker itself.

### 3.5 Why defer (F11)

The issuer has no consumer until aq-confine S2d exists. v2 therefore: (1) builds the listener classes, peer identity, policy, shadow/enforce, SSRF fix and switchboard containment first (sections 4, 5, 8); (2) schedules the issuer slice (AUTH-S10) together with the aq-confine S2d slice and not earlier; (3) until then the `sandbox` listener is not created and sandboxes get only the aq-confine `llama` forward. If the issuer is later judged too much code, the fallback is a static, per-run, launcher-written deny/allow table in the broker (L7 path allowlist already designed as aq-confine S2d), with the coordinator `sandbox` listener restricted to `read.hints`/`read.status` and no tokens at all. That fallback loses per-run revocation at the coordinator and run-attributed audit; the design records that tradeoff for the reviewer of S10.

## 4. research.fetch and SSRF (F5)

Producer facts are in section 1. The coordinator fetches with `httpx.AsyncClient` (`ai-stack/mcp-servers/hybrid-coordinator/extensions/web_research.py:21,331`), validates with `shared.ssrf_protection.assert_safe_outbound_url` before each hop (`:156-157`, redirects `:165-166`), and the validator resolves with `getaddrinfo` once (`ai-stack/mcp-servers/shared/ssrf_protection.py:80`). The HTTP client resolves the name again when it connects. An attacker-controlled DNS name that answers a public address to the validator and `127.0.0.1` to the client defeats the check.

### 4.1 Pin the resolved IP at connect time

Change in `extensions/web_research.py` (one helper plus a few lines in the fetch loop), keeping `httpx` (public API only, no private pool internals):

1. New `shared/ssrf_protection.py::resolve_pinned(host, port) -> list[str]`: `await loop.getaddrinfo` (not the blocking call inside the async handler), unwrap IPv4-mapped IPv6, then require EVERY returned address to be `ipaddress.ip_address(x).is_global` (positive logic, as in the aq-confine design), additionally reject NAT64 `64:ff9b::/96` and 6to4 `2002::/16`; any non-global record fails the whole name (no "pick the public one" from a mixed answer). Returns the validated address list.
2. In each hop: validate scheme/allowlist with the existing `assert_safe_outbound_url`, call `resolve_pinned`, then issue the request to the IP literal (IPv6 in brackets) with the original name in the `Host` header and `extensions={"sni_hostname": host}` so TLS verifies the certificate against the original host name and the socket connects to the address that was validated. No second DNS lookup exists for the connection.
3. `allow_redirects` stays off and the existing manual loop is kept; every redirect target runs steps 1-2 again (redirect to `http://127.0.0.1/` or to a name that resolves privately fails at the hop).
4. `httpx.AsyncClient(trust_env=False)` so `HTTP(S)_PROXY`/`ALL_PROXY` in the unit environment cannot route the connection through a proxy that is itself on a private address; `verify` stays on; response size and total-time caps stay as today.
5. Test seam: replace `enforce_ssrf = transport is None` (`web_research.py:312`) with an explicit keyword used only by tests that import the module directly; the handler path always passes `enforce_ssrf=True` and rejects an injected `transport` unless `AQ_TEST_MODE=1` is set in the environment. Same change for `extensions/browser_research.py:156`.

### 4.2 Switches become tighten-only

- `HYBRID_BLOCK_PRIVATE_EGRESS` (`shared/ssrf_protection.py:42`): when the Nix-provided `AQ_AGENT_AUTH_MODE` is `enforce` or `lockdown`, the value is ignored and private ranges are always blocked; in `shadow`/`off` a `false` value is honoured but emits a warning, the metric `ssrf_off_switch_active=1` and a health-spider RED. The only supported way to relax egress for a specific host is the allowlist semantics below, never the global off switch.
- `HYBRID_OUTBOUND_ALLOWLIST`: a non-empty allowlist restricts further (tighten). It does not bypass the global-address requirement; an allowlisted name still must resolve to global addresses unless the policy file lists an explicit `local_service` exception with its own scope (none planned; local services are reached by their own named paths, never through `research.fetch`).
- `HYBRID_ALLOW_PLAINTEXT_HTTP`: default false stays; enabling it is honoured only outside enforce.
- Nix: assert at eval time that no unit sets `HYBRID_BLOCK_PRIVATE_EGRESS=false` when `agentAuth.mode` is enforce or lockdown [grep of current Nix for existing settings UNVERIFIED; first task of S6].

### 4.3 Headless browser fetch is a separate, non-default scope

`/research/web/browser-fetch` only pre-checks the top-level URL (`extensions/browser_research.py:104-105`) and disables checks whenever a runner or transport is injected (`:156`). Sub-resource requests, JS redirects and DNS answers inside the browser are outside that check [how `browser_runner` isolates its network is UNVERIFIED]. Therefore v2 defines scope `research.browser`, granted to no class by default (owner approval via the section 3.3 path), until the browser's network is forced through a pinned-IP local proxy (follow-up slice, not MVP). `research.fetch` covers only `/research/web/fetch` and `/research/workflows/curated-fetch` (the latter uses the same fetch function [UNVERIFIED, confirm in S6]).

### 4.4 Default for `owner-agent` (decision 3, conditional)

The policy file carries `"research.fetch": {"owner-agent": {"default": false, "default_after_slice": "AUTH-S6"}}`. Shipping order: S6 lands (pinning, tighten-only, tests) -> `research.fetch` becomes a default grant for `owner-agent` in the same release as S6's enforce flip. Before that the observable behaviour for owner agents does not change (shadow only), so there is no dev-speed regression and no premature widening. Sandbox, `legacy-loopback` and `unknown` never get it by default.

### 4.5 S6 tests (replace v1 SSRF suite)

Literals `127.0.0.1`, `::1`, `0.0.0.0`, `169.254.169.254`, RFC1918, `100.64.0.0/10`, `::ffff:127.0.0.1`, `64:ff9b::7f00:1`, `2002:7f00:1::`, decimal/hex/octal host forms; a DNS name whose first answer is public and second private (mixed answer) is blocked; **rebinding test**: a local DNS stub that answers a public address on the first query and `127.0.0.1` afterwards cannot cause a connection to loopback because the connect uses the validated address; redirect chain public -> private blocked at the hop; redirect to a name that rebinds blocked; `HTTP_PROXY=http://127.0.0.1:...` in the environment is ignored; `HYBRID_BLOCK_PRIVATE_EGRESS=false` under enforce is ignored; a legitimate public HTTPS URL still passes with correct certificate verification against the original host name.

## 5. Switchboard and API-key containment, pulled forward (F6)

### 5.1 The problem restated

The switchboard (`:8085`) accepts any request, runs as the owner uid, holds the coordinator API key (`ai-stack/switchboard/switchboard.py:717-723`, sends it at `:2474`) and exposes `/v1/{path:path}` for every method (`:3107`) including a tool-calling loop with built-in tools. Any caller who cannot do X directly on the coordinator can ask the switchboard to do X in-band. Independently, the coordinator `api-key` mode (valid key) is a full bypass of any scope table (section 1) and the key is readable by the owner uid. So per-scope enforcement on the coordinator is only as strong as the weakest of: the switchboard, the API key, and the legacy TCP listener.

Until the actions in 5.2-5.3 are enforced, the doc states plainly: **scope enforcement on the coordinator is bypassable via `:8085` and via the readable API key.** Shadow data collected before then must not be read as a security result.

### 5.2 Switchboard (AUTH-S4, before any coordinator enforce flip)

1. **Guard.** The `loopback_guard` middleware (Host/Origin/content-type) is applied to the switchboard FastAPI app as well (S1 covers this guard; S4 flips it from shadow to enforce for the switchboard).
2. **Narrow its coordinator identity.** The switchboard calls the coordinator over `agent.sock` as `service:switchboard` (section 2.2), whose policy default is `read.hints` and `read.status` only (N5: the earlier `memory.write` stamped `via=switchboard` default is dropped; the review found no caller for it, so least privilege wins). Its only coordinator call is `GET /hints` (`ai-stack/switchboard/switchboard.py:2479`, via `_hints_client.get`); the UDS connection uses an `httpx` unix-domain-socket transport (`httpx.AsyncHTTPTransport(uds=...)` on `_hints_client`), not the stdlib `aq_http` helper. It does NOT hold `research.fetch`, `qa.run`, `orchestrate`, `safety.*` or `admin`. Because the switchboard cannot know which downstream caller caused a tool call, it must not hold more than the least privilege any of its callers is entitled to; it loses the key entirely (`HYBRID_API_KEY_FILE` is removed from its unit, `nix/modules/services/switchboard.nix:563`).
3. **Gate its own tool loop.** The built-in tools exposed through `/v1/*` are admitted by the existing capability lease gate (`ai-stack/switchboard/capability_lease_gate.py`, `CAPABILITY_LEASE_ENFORCEMENT`, deny-closed, `SAFE_READ_ALLOWLIST` for the degraded path). S4 turns that gate on for TCP callers (class `legacy-loopback`) so unauthenticated TCP callers get only the safe-read tools; callers on a switchboard UDS listener (clients that support it) get the owner-agent tool set. Whether the gate can be switched on without breaking current agent tool use [UNVERIFIED; first task of S4: measure with the gate on in observe mode].
4. **Not claimed:** the switchboard still runs as the owner uid, so an owner-uid agent can bypass it by using `agent.sock` directly. That is consistent with section 2.3: the switchboard is not a boundary against T1; S4 only ensures it is not a laundering path for LOWER classes (sandbox, legacy TCP, browser, other uids).

### 5.3 API-key mode under enforce

- In `enforce`, mode `api-key` maps to scope set `{admin}` only (read of admin stats, mode tightening). It no longer implies `memory.write`, `orchestrate`, `qa.run`, `research.*` or `safety.*`. Callers that used the key for those move to their socket class in S7.
- `no-api-key-configured` (`auth.py:194-198`) becomes a startup error under enforce, as in v1.
- Sequencing (N2): the narrowing above takes effect per family only after that family shows zero non-admin `api-key` traffic in the shadow log AND every client that sends the key for it has been migrated (8.3). Merely finishing S4 does not flip it.
- Key tightening (N3, step K in 8.3): until the key file is tightened the owner agent can still obtain `admin` by reading it; tightening is possible only after the MCP bridge, CLIs, dashboard and switchboard no longer read it, because they all run as the owner uid.
- After S7 completes for all in-repo clients, rotate the key and tighten its file mode (owner act via sops) so only the services that still need it (aidb/ralph/docs, which run as their own users) can read it. The owner uid reading the key stops being a bypass at that point; until then it is listed as an open risk with a date in the tracker.
- Constant-time compare (`hmac.compare_digest`) and removal of the raw token from audit rows are done in S0 (unchanged from v1).

### 5.4 Services still unverified (F6 tail)

Ralph (`:8004`), aider-wrapper (`:8090`), docs (`:8096`), llama.cpp (`:8080/:8081`) and the dashboard API route auth are still `[UNVERIFIED]` because probes from the investigation shell reached only `:8003`. Deferral with a date: the S9 task "probe and classify" is scheduled before the first enforce flip (target 2026-10-21) and runs as the owner from a normal shell: for each port, an unauthenticated GET of a read endpoint and a POST of an invalid body to a mutating endpoint, recorded in the tracker. Services found open are added to the capability table and given Host/Origin guards in S9. Until probed they are treated as `legacy-loopback` reachable and not relied upon.

## 6. Mode lifecycle (F7, F8, F9)

### 6.1 Shadow must expire (F7)

- Nix options under `mySystem.aiStack.agentAuth` (declared next to the port registry, `nix/modules/core/options.nix`): `mode` in `shadow | enforce | lockdown` (`off` exists only until S2 lands and is then removed from the enum by a Nix assertion), `shadowUntil` (string `YYYY-MM-DD`, REQUIRED when `mode = "shadow"`; an eval assertion fails the build if it is null), `legacyTcpWritesUntil` (default derived: `shadowUntil` + 90 days), `loopbackGuardMode`.
- The unit receives `AQ_AGENT_AUTH_MODE`, `AQ_AGENT_AUTH_SHADOW_UNTIL`, `AQ_AGENT_AUTH_LEGACY_UNTIL` as environment. Dates are compared at runtime (Nix has no clock).
- After `shadowUntil` while still in shadow: (1) metric `agent_auth_shadow_expired = 1`; (2) `aq-health-spider` check `agent-auth-shadow` goes RED (not WARN) with the text "shadow window expired on <date>; flip to enforce or extend via Nix"; (3) a `human_gate` attention-queue item is filed once per day; (4) the PM tracker for this plan carries the detection signal `agent-auth-shadow-expired` (Rule 20: status is projected, never typed). There is deliberately NO silent auto-enforce: flipping unprepared families on a timer would break agents, which is the failure this design must avoid. Extending the window is a visible Nix commit, so it cannot happen quietly.
- Rule 19 corollary respected: the expiry is a runtime health signal, not a tier0 `--pre-commit` blocker (tier0 only WARNs freshness-class checks).
- Compat window (default, not an owner decision): `legacy-loopback` (TCP) loses all non-read scopes after `legacyTcpWritesUntil`. The MCP bridge keeps its TCP fallback until that date and the fallback is removed in the release that follows it. The bridge needs the stdlib UDS client (`aq_http`) first (S7); `.mcp.json` `HYBRID_URL` becomes a `unix://` URL with TCP fallback while the window is open.
- Enforcement is per family, not all-or-nothing: the policy file carries `"mode_per_family": {"safety.loosen": "enforce", ...}` so S5 can flip the safest families while others are still shadow; `shadowUntil` applies to whichever families are still shadow.

### 6.2 Lockdown and its exit (F8)

Stated plainly: the runtime mode file (`/run/aq-coordinator/mode`) is tighten-only, so lockdown has no runtime way back by design. Exiting lockdown is an owner act with exactly one command:

```
sudo systemctl restart ai-hybrid-coordinator
```

The unit declares `RuntimeDirectory=aq-coordinator` with `RuntimeDirectoryPreserve=no`, so a restart removes the tmpfs mode file and the service returns to the Nix-declared mode (`shadow` or `enforce`). A change to the declared mode itself is the normal `nrs` flow. This follows the repo rule that sudo/systemctl are owner acts and that runtime state must not outlive activation (Rules 13/14): nothing persistent was written, so nothing needs a Nix counterpart.

Lockdown recovery allow-set, always available to `owner-agent` and `service:*`, so recovery tooling keeps working: `/health*`, `/readyz`, `/metrics`, `GET /status`, `GET /stats`, `GET /hints`, `/query`, `GET /admin/v1/auth/stats`, `GET /admin/v1/auth/explain`, and `POST /admin/v1/auth/mode` (tighten only). `aq-resume`, `aq-hints`, `aq-agent-auth explain|list` therefore still work in lockdown.

Restart side effect (N4): the restart drops all in-memory coordinator state (session safety modes in `evidence_safety_handlers.py`, rate-limiter counters, circuit-breaker state, token/verification caches, the revocation deny set held in memory). Persisted state (memory, RAG, queues) is unaffected. The deny set is therefore persisted to `/var/lib/ai-stack/hybrid/telemetry/agent-auth-deny.json` on every change and reloaded at start, and session safety modes already default to a safe value on restart [UNVERIFIED; check in S5]. The owner agent can equally flip `shadow` to `enforce` at will (tighten-only); this is the same accepted DoS class.

Abuse note: any `owner-agent` can enter lockdown (tighten is open to the owner class), so an injected agent can cause a denial of service on writes. This is accepted as fail-safe: the cost to the owner is one restart, entry is audited, and the entry raises a high alert naming the caller and `run_id`.

### 6.3 Clock handling (F9)

Single host, one clock. Token expiry (`exp`) is compared against `time.time()` with no skew allowance for `exp` and a 5 s allowance for `nbf`. Cached verification results store a monotonic deadline `min(exp - now, 60 s)` computed with `time.monotonic()`, so an NTP step cannot extend a cached entry beyond 60 s and cannot make it outlive its token by more than 60 s. The epoch poll uses monotonic timing for its 1 s refresh and the 30 s staleness cut-off. Revocation by jti/run/class is checked on every request and does not depend on clocks.

## 7. Performance gate (F10)

The v1 baseline (curl-inclusive, n = 12, a 524 ms first-hit outlier, 9-24 ms tail clusters) is informational only. It cannot resolve a 0.10 ms difference and must not be used as a gate.

Gate (script `scripts/testing/bench-agent-auth-middleware.py`, run in tier0 as non-blocking WARN and in the S2/S3 acceptance as a blocker):

1. In-process `aiohttp.test_utils.TestClient` against two apps with the same trivial handler: A = current middleware list (`router.py:217-221`), B = A plus the authorization middleware (shadow and enforce variants). Same process, same event loop.
2. 500 warmup requests, then n >= 5000 measured requests per variant in interleaved blocks of 500 (A, B, A, B, ...) to cancel thermal and GC drift. Timing with `time.perf_counter_ns()` around each request. Garbage collection is left on; the p99 gate exists to catch allocation regressions.
3. Pass criteria on the same host: delta p50 <= 50 us, delta p95 <= 100 us, delta p99 <= 250 us, for cached-class and cached-token paths.
4. Separate micro-benchmarks: peer resolution over a real `UnixSite` with 2000 new connections (p95 <= 0.4 ms including `/proc` reads and pidfd checks); cold token verification with 2000 distinct tokens (p50 <= 0.4 ms, consistent with the measured 0.26 ms Ed25519 verify); policy match (<= 10 us); revocation lookup (<= 2 us).
5. Informational end-to-end run on the live coordinator with a Python `http.client` loop (not curl), n >= 5000 over TCP and over UDS to `/health`, recording whether the host was cold or warm. UDS is expected to be no slower than TCP; this is reported, not gated.
6. The result is written to `docs/harness-first/evidence/<date>-agent-auth-bench.md` for the activation attestation.

## 8. Revised slice plan and MVP cut (F6, F11)

### 8.1 Order (changes from v1: switchboard containment moved before enforce, SSRF decoupled, issuer deferred and merged with the sandbox integration)

| Slice | Content | Depends on | Lane (Rule 17) | Review | Rollback |
|---|---|---|---|---|---|
| AUTH-S0 | `hmac.compare_digest` at `auth.py:201`; stop writing the raw token to audit rows (`http_server_impl.py:506-507`); empty-key startup error when `AI_STACK_REQUIRE_API_KEY`; Tempo `grpc_listen_address` loopback (`nix/modules/services/monitoring.nix:21`); log the findings in `issues-backlog.md` | none | haiku/sonnet | self + tier0 | revert |
| AUTH-S1 | `loopback_guard` (Host allowlist, Origin reject, content-type/`X-AQ-Client`) as shared middleware on coordinator, switchboard and dashboard API; shadow first (`X-AQ-Would-Deny`) | S0 | sonnet | independent | `loopbackGuardMode=off` |
| AUTH-S2 | `config/agent-auth-policy.json`, matcher, shadow engine, `mode`/`shadowUntil` options, metrics, `GET /admin/v1/auth/stats` and `explain`, tier0.d lint (every route family has a scope; every scope has guidance; every `self_service` profile is a strict subset) | S0 | sonnet | independent | mode shadow/off |
| AUTH-S3 | `UnixSite` listener `agent`, `peer_identity.py` (section 2: raw `SO_PEERPIDFD`, full cgroup path match, fail-to-unknown), `aq_http` client helper with the one-shot `peer_gone` retry, `RuntimeDirectory`. First test: coordinator unit reads `/proc/<owner-pid>/cgroup` (2.1 step 6); burst test of 10k short-lived clients with unknown-rate under 0.1 percent | S2 | sonnet | independent security review | stop UDS listener |
| AUTH-S4 | Switchboard and API-key containment (section 5): switchboard guard to enforce, switchboard on `service:switchboard` over `agent.sock` through an `httpx` UDS transport for its single `GET /hints` (`switchboard.py:2479`) with `read.hints`/`read.status` only and no key, lease gate for TCP callers, coordinator `api-key` mode reduced to `{admin}` under enforce | S1, S3 | sonnet | independent | per-item flags |
| AUTH-S5 | Enforcement (per family, and per client: depends on S7 for every client that still sends `X-API-Key` to that family, see 8.3): per-family flips, guided deny bodies (structured, validated by schema), `lockdown`, `safety.tighten` monotonic rule, `memory.write` provenance stamp, fail-closed for `no-api-key-configured`. Does not flip `research.fetch` default | S2, S3, S4, and S7 per client (8.3) | sonnet | independent | per-family flag to shadow |
| AUTH-S6 | SSRF pinning (section 4), tighten-only switches, test-seam fix, `research.browser` scope, then flips `research.fetch` default for `owner-agent` | S0 (independent of S2-S5) | sonnet (or Codex) | independent | restore previous fetch path behind flag |
| AUTH-S7 | Client migration to `aq_http` + UDS: MCP bridge, dashboard, timers/units, CLIs, Qwen loop; Nix env defaults point to sockets with TCP fallback until `legacyTcpWritesUntil` | S3 | sonnet/haiku | live test per client | TCP fallback |
| AUTH-S8 | Ops MVP: audit JSONL, metrics, `aq-health-spider` checks (mode vs Nix value, shadow expired = RED, unknown class traffic, SSRF off-switch, audit growth), attention alerts, minimal `aq-agent-auth` (`explain`, `list`, `mode` tighten, `revoke class`) | S2 | sonnet | independent | revert |
| AUTH-S9 | Probe and classify the unverified services (5.4); aidb fail-closed on empty key (`ai-stack/mcp-servers/aidb/server.py:1341-1345`); dashboard Host/Origin enforce; llama.cpp socket-or-`--api-key` decision | S1 | sonnet | independent | per-service flags |
| AUTH-S10 (deferred) | Issuer unit + key + verifier + `sandbox` listener + `bound_peer` + aq-confine launcher/broker integration (sections 3.1-3.4). Scheduled together with aq-confine S2d, not before | S3, S5, aq-confine S2a-c | sonnet + independent security review; no-key-readable and replay tests are blocking | independent | issuer disabled; sandbox listener removed |

Slice DoD for every slice is the Rule 15 six-dimension attestation (integrated, turned ON, validated in the real system, observable, intervenable, PM-tracked in the plan's `tracker.json`). Shadow counts as "ON" only for S2 and S3; S5 is its own attested step.

Dependency with aq-confine: S2d (coordinator access from sandboxes) requires AUTH-S10, which requires AUTH-S3 and AUTH-S5 in enforce. The aq-confine S2a-c lite slices (llama-only forward) proceed independently. Until S10 the coordinator is not grantable to sandboxes (consistent with aq-confine v3 section 6A).

### 8.2 MVP cut (F11)

MVP = S0-S9 (everything except S10). It delivers: browser/DNS-rebinding closed on coordinator, switchboard and dashboard; UDS identity for all in-repo callers with no keys or tokens; per-family authorization enforced for non-owner and legacy classes; guided denies; pinned-IP SSRF; switchboard and API-key laundering paths closed; modes with an expiring shadow and a documented lockdown exit; audit, metrics, health-spider and alerts.

Cut from MVP (recorded, not scheduled): the audit-sidecar mirror (`/run/ai-audit-sidecar.sock`), the hints-engine "repeated denial" lesson feed, and a dedicated dashboard panel (the stats endpoint and the existing health-spider/aq-report surfaces are enough; a panel can read the same endpoint later). The guided deny body and its rendering by the MCP bridge as the tool-error text stay in MVP, because that is the owner's steering requirement and costs a mapping function, not a subsystem. Revocation granularity in MVP is class/unit level plus mode; per-jti/run revocation arrives with S10.

MVP E2E journey (the readiness test, real dependencies, no mocks): (1) Claude Code with `.mcp.json` over UDS calls `get_hints`, `store_memory`, `web_fetch` successfully; (2) a browser page with a rebound hostname receives 403 from coordinator, switchboard and dashboard; (3) a `legacy-loopback` TCP client attempting `research.fetch` after the window gets the guided deny; (4) a call through `:8085` cannot reach a scope the caller class lacks; (5) `mode lockdown` blocks writes and `sudo systemctl restart ai-hybrid-coordinator` restores the declared mode; (6) the benchmark gate passes.

### 8.3 Per-client migration checklist and enforce gating (N2, N3)

Rule: no client may lose `X-API-Key` access to a route before that client is migrated to its socket class. A family flips to enforce only when both hold: (1) the shadow log shows zero would-deny events attributable to that family from a client on its checklist, and (2) every client below that uses the family is marked migrated. Each item is verified in the live system (Rule 15), not by unit test alone.

| Client | Today | Migration | Done when |
|---|---|---|---|
| MCP bridge `scripts/ai/mcp-bridge-hybrid.py` | reads `HYBRID_API_KEY_FILE`, sends `X-API-Key` on every call (`:59-66`, `:153`, `:169`) | stdlib UDS client (`aq_http`), no key read; `.mcp.json` `HYBRID_URL=unix://...` with TCP fallback until `legacyTcpWritesUntil`; deny body rendered as tool error | all bridge tools (`get_hints`, `store_memory`, `web_fetch`, `qa_check`, workflow tools) pass in a real Claude Code session; shadow shows no `api-key` mode requests from the bridge |
| Timers and units (`ai-gap-auto-remediate` etc., `ai-stack.nix:2316-2320,2647,2694`) | `HYBRID_API_KEY_FILE` env | unit mapped in policy `units` by full cgroup path; env key removed; socket path via env | each timer run succeeds once via socket; unit appears as `service:<unit>` in audit |
| Dashboard backend (`command-center-dashboard.nix:347`) | key file | `service:dashboard` class over `agent.sock`, key env removed | dashboard pages that call the coordinator load; no `api-key` mode traffic |
| Switchboard (`switchboard.nix:563`, `switchboard.py:717-723`) | key read at import | S4 item (httpx UDS), key removed | `/hints` enrichment still works; the unit has no `HYBRID_API_KEY_FILE` |
| CLIs (`aq-hints`, `aq-qa`, `aq-resume`, aqd, `scripts/ai/aq-*`) | raw HTTP, some with key | `aq_http` helper; `curl --unix-socket` in docs | grep of `scripts/` shows no remaining key reads for coordinator calls (list generated by a script, tracked) |
| Qwen loop / agent_spawner (`agent_executor.py:1884`, `ai_coordination.py:34`) | loopback prefix trust, no key | `aq_http` | local-agent smoke test passes |
| Ralph, aider-wrapper, aidb callers into the coordinator | key via env (`mcp-servers.nix:1430,1484,1587`) | service users: their own uid classes (`unknown` on `agent.sock` unless mapped); decide per service in S9 | either mapped in policy or kept on `api-key` admin-only routes, documented |

Step K (key tightening), explicitly after S7: when the checklist is complete and the shadow log shows no owner-uid process reading the key (audit of `api-key` mode requests is zero for 14 days), rotate the coordinator API key (owner act via sops) and set the secret so only the service users that still need it can read it (not the `aiSvcMode` group pattern). Until step K the owner agent holds `admin` through the readable key; this is recorded as an open risk with a tracker date and shown in `aq-agent-auth explain` output.

## 9. Hostile test additions (to v1 section 9 matrix)

| Finding | Test | Expected |
|---|---|---|
| F1 | `systemd-run --user --unit=ai-gap-auto-remediate` (and a user-manager transient `.service` and `--scope`) connects to `agent.sock` and calls a `service:`-only scope | class `owner-agent` (cgroup under `/user.slice/`), scope denied, audit `reason=user_manager_unit` |
| F1 | System unit not in the table connects as owner uid | `owner-agent` with `reason=unlisted_unit`; as another uid: `unknown` |
| F2 | Force `getsockopt(77)` to fail (test hook) | class `unknown`, health only, alert; no fallback path exists |
| F2 | Connect, send, exit, recycle the pid before the cgroup read (loop of short-lived clients) | never inherits another process's class; liveness check fails to `unknown` |
| F2 | Owner-uid process ptrace-injects code into the switchboard (documented, not prevented) | recorded as a known non-boundary; test asserts the documentation line exists and that `service:switchboard` has no scope above `owner-agent` defaults |
| N1 | 10k short-lived `curl --unix-socket` clients in a burst; separately `aq-hints` in a loop | `unknown` rate under 0.1 percent; every `unknown` is `peer_gone` with a retry hint; no request ever receives more than health as `unknown` |
| N1 | S3 first test: `ai-hybrid` reads `/proc/<owner-pid>/cgroup` | succeeds; otherwise S3 is blocked until the unit hardening is fixed |
| N2 | Enforce a family while a listed client still sends the key | gate refuses the flip (checklist/shadow evidence missing) |
| N3 | Owner reads the key file and calls an `admin` route before step K | succeeds (documented open risk); after step K: `EACCES` on the file |
| N5 | Switchboard unit started without `HYBRID_API_KEY_FILE` | `/hints` enrichment works over the UDS transport; `memory.write` through the switchboard identity denied |
| F3 | Owner-uid process requests a profile equal to, or wider than, its own rights without approval | denied; approval ticket created; `no_delegate` scope request always denied |
| F3 | Policy lint with a `self_service` profile that is not a strict subset | tier0.d check fails |
| F3 | Owner uid reads `/run/secrets/aq-agent-auth-signing-key` | `EACCES`; the issuer refuses to start if the file is group/other-readable |
| F4 | Owner-uid process requests a token with a chosen `run_id` | ignored; issuer returns its own id; no way to obtain a token for another live run |
| F4 | Token copied and presented from a different process on the `sandbox` listener, then on `agent.sock` | `wrong_peer` deny + high alert, then `wrong_listener` deny |
| F5 | DNS stub answers public then `127.0.0.1`; redirect chain to private; `HTTP_PROXY` set; off-switch env false under enforce | all blocked / ignored (section 4.5) |
| F6 | Sandbox/legacy caller asks the switchboard tool loop to perform a `research.fetch` or `qa.run` equivalent | denied at the coordinator (switchboard class lacks the scope) |
| F6 | `X-API-Key` with a valid key calling `memory.write` / `orchestrate` under enforce | denied; only `admin` scopes pass |
| F7 | Set `AQ_AGENT_AUTH_SHADOW_UNTIL` in the past in shadow | spider RED, alert filed, metric 1, tracker signal; mode does not change |
| F8 | Enter lockdown from an owner-agent connection, run the recovery allow-set, then restart the unit | recovery calls succeed in lockdown; writes denied; after restart the declared mode is active and the mode file is gone |
| F9 | Step the system clock forward/back (VM or `faketime`) with a cached token | cache entry is dropped within 60 s; expired token never accepted |
| F10 | Run the in-process benchmark with and without the middleware | meets section 7 thresholds |

## 10. Owner decisions (revised)

Real owner decisions, kept:
1. **Issuer key provisioning** (SOPS act: add `aq-agent-auth-signing-key`, enable the issuer). Needed only when AUTH-S10 is scheduled; nothing before that depends on it.
2. **llama.cpp: unix socket versus `--api-key`** (AUTH-S9). It touches every inference consumer including switchboard, embeddings consumers and the aq-confine `llama` forward; the recommendation is a unix socket with group access, adopted only after the aq-confine S2c-lite forward lands so the sandbox path is not broken twice.
3. **`research.fetch` as a default grant for host `owner-agent`**, conditional on AUTH-S6 landing first (section 4.4). Recommendation: yes after S6; before S6 it stays shadow-only.

Decided by the architect (defaults; reversible by Nix change, not owner questions): compat window = `shadowUntil` + 90 days; `sandbox-readonly` as the sandbox exposure profile (read hints/status, `prsi.read`, `safety.tighten`) and everything else grant-only; lockdown exit by `sudo systemctl restart ai-hybrid-coordinator`; CLI name `aq-agent-auth`; MVP cut line at S9; separate key set for grants.

Recorded follow-up, not asked now: moving switchboard and the dashboard API to dedicated uids (the only way `service:*` becomes a boundary against a same-uid agent), and giving the egress broker its own uid (then `sandbox/` can live in a group the owner is not in).

## 11. Remaining unverified items

- `SO_PEERPIDFD` raw constant 77 behaviour on this kernel (first test of S3); `/proc/self/fdinfo` pid line format.
- Whether switching on the switchboard capability lease gate for TCP callers breaks current agent tool use (first task of S4).
- Whether `ai-hybrid` can read owner-uid `/proc/<pid>/cgroup` (first S3 test); whether session safety modes default safely after restart; broker pid namespace vs aq-confine v4.
- Ed25519 support in `capability_lease.attenuate`; the design does not depend on it (issuer-mediated narrowing).
- Approval receipt format for the `agent_scope_grant` executor.
- Which Nix units set `HYBRID_BLOCK_PRIVATE_EGRESS` and whether the curated-fetch workflow uses the same fetch function.
- Auth state of ralph, aider-wrapper, docs, llama.cpp and the dashboard routes (probe task dated 2026-10-21 in S9).
- How `browser_runner` isolates browser network access.
- v1 items not re-examined here keep their v1 status.
