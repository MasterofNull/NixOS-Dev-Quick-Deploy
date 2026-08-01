# Foundation C — Runner Deployment-Hardening Slice (deferred from R5-shadow)

status: OPEN — deferred 2026-07-31 after R5-shadow rollback
tier: enforcement (touches R3 runner socket-setup code + its Nix unit)
owner-activation: REQUIRED before build (enforcement-tier; fresh single-use grant)
review: codex confirmatory on Aug-4 return (queued) + independent reviewer at freeze
predecessor state: R5 adapter (6d17f9e6) + runner (ccbc0718) BUILT + reviewed, now DORMANT

## Why this slice exists

The R5-shadow activation (turning the C3b confinement runner ON in SHADOW to dogfood
mint→sign→UDS→bwrap-cell→validator on real effects, deny-closed, never touching the real
result) exposed that the R3 runner service had **never been deployment-exercised** — it ships
`enable=false` and was only unit-tested. Activating it surfaced FIVE distinct deployment-config
defects. Four were one-line unit fixes and are already committed. The fifth is an architecture
mismatch that needs a real code change + re-test, so the whole shadow was rolled back to the
safe, validated **C2 (enforcing) + C5 (observing)** baseline rather than hot-patched one rebuild
at a time.

## The five deployment bugs (surfaced 2026-07-30..31)

| # | Defect | Root cause | Fix | Commit |
|---|--------|-----------|-----|--------|
| 1 | Grant signing key rejected | adapter/runner expected RAW 32-byte key; SOPS stores UTF-8 text (raw Ed25519 seed isn't valid UTF-8) | decode HEX both sides (match runner env-hex convention); tests 43→49 | (R5 build) |
| 2 | Runner crash-loop `ModuleNotFoundError: execution_grant` | runner runs bare Nix-store copy; its 9 transitive local-module deps not on sys.path | self-contained `runnerBundle` derivation co-locating the closure | b41c81e3 |
| 3 | Socket unreachable (dir) | control socket inside RuntimeDirectory 0750 runner:runner; clients can't traverse | RuntimeDirectoryMode 0750→0755 (state is in separate 0700 StateDirectory) | d950f0fe |
| 4 | `RestrictNamespaces` ignored | value `"CLONE_NEWUSER CLONE_NEWNS"` — systemd wants type names, not CLONE_* flags; silently ignored; also incompatible with bwrap `--unshare-all` (needs all 7 types) | `RestrictNamespaces = false` | d950f0fe |
| 5 | **Socket unreachable (group) — THE BLOCKER** | runner **self-binds** its UDS (`execution_cell_runner.py:988-998`): unlinks the systemd socket unit's `SocketGroup=aq-execution-cell-clients` socket and re-binds its own, which comes out `aq-execution-cell-runner:aq-execution-cell-runner` 0660 → clients can never connect | **this slice** | — |

Symptom of #5: the FIRST connect after boot succeeds (hits the socket unit's clients-group socket,
fires socket-activation) and every connect after fails `PermissionError [Errno 13]` (runner has
replaced the socket with a runner-group one). Adapter reports it as deny-closed `runner-unreachable`.

## The real fix (bug #5)

The Nix unit is built for **systemd socket-activation** (`systemd.sockets` with `Accept=false`,
`SocketGroup=aq-execution-cell-clients`, `SocketMode=0660`, `RemoveOnStop=true`), but the runner
ignores it and self-binds. Reconcile them — preferred: make the runner **socket-activation aware**.

- On start, if `LISTEN_FDS` / `LISTEN_PID == getpid()` are set, adopt the passed listening fd
  (`socket.socket(fileno=SD_LISTEN_FDS_START=3, family=AF_UNIX, type=SOCK_STREAM)`) instead of
  `unlink`+`bind`+`chmod`+`listen`. systemd already bound + `listen()`ed it with the unit's
  group/mode, so the clients-group + 0660 survive.
- Keep the current self-bind path as a **fallback** for non-systemd/dev runs (tests), so
  `test-execution-cell-*.py` still exercise the runner standalone.
- Do NOT paper over it by adding the switchboard to the runner's own group or by chowning the
  socket to clients (the runner is unprivileged and not a clients member; conflating the two
  groups defeats the design's client/runner separation). Fix the producer.

## REV2 (2026-08-01, codex binding depth-review REQUEST_REVISION)
Codex (`codex-20260801-090026`) confirmed the fd-3 fix is correct and cannot bypass SO_PEERCRED /
Ed25519 (Q1/Q2), all 3 committed fixes are sound (Q3), and endorsed Q-H-1 strict-fd-3 + Q-H-2
keep-fallback. But it found **deployment bug #6**, a hard pre-activation blocker that bug #5 masked,
and it forces the ceiling to grow beyond the original two files — hence this revision (freeze lifted;
re-review + re-freeze required before owner activation).

**Bug #6 — the runner authorizes NO client identity.** `peer_authorized()`
(`execution_cell_runner.py:513`) authenticates a peer by SO_PEERCRED, matching the peer's *effective*
uid==`client_uid` OR gid==`client_gid`. But the Nix unit never sets
`AQ_EXECUTION_CELL_RUNNER_CLIENT_UID`/`CLIENT_GID`, so `build_config_from_env()` (`:1084-1085`)
yields both `None` → `peer_authorized()` returns False for every peer → `_handle_connection()`
(`:945`) drops every connection before reading a request. Once bug #5 (socket group) is fixed and the
switchboard can finally *reach* the socket, this rejects it at authentication. **The naive fix is
wrong:** SO_PEERCRED returns the peer's *effective* GID, but the switchboard only joins
`aq-execution-cell-clients` *supplementarily* (`execution-cell-runner.nix:155/160`), so
`CLIENT_GID=that-group` never matches. The correct mechanism is an explicit expected switchboard
**effective UID**. Both env names are also absent from `config/env-contract.yaml`.

## Ceiling (REV2 — expanded; re-freeze at this scope)
- EDIT `ai-stack/switchboard/execution_cell_runner.py` — (a) socket-activation adoption (fd 3) with
  self-bind fallback (bug #5), meeting ALL the "Socket-activation robustness" requirements below
  (fail-closed malformed parsing, single-validated-fd-3, close inherited fds, clear activation env,
  safe self-bind only when path provably unowned); no change to grant verify / SO_PEERCRED semantics /
  cell construction / validator / cgroup reap.
- EDIT `nix/modules/services/execution-cell-runner.nix` — set
  `AQ_EXECUTION_CELL_RUNNER_CLIENT_USER=${primaryUser}` in `runnerEnvironment` (the **username**, which
  IS statically known at eval). Do **NOT** derive the uid at eval via
  `config.users.users.${primaryUser}.uid` — a dynamically-allocated `isNormalUser` (hyperd has no
  explicit `uid=` declared; runtime uid 1000 is NixOS auto-allocation) can be **null at eval**, which
  would re-introduce bug #6. Do NOT set `CLIENT_GID` to the supplementary clients group (ineffective —
  SO_PEERCRED returns the *effective* gid, and the switchboard joins that group only supplementarily).
  UID-match is the authenticator. (bug #6)
- EDIT `ai-stack/switchboard/execution_cell_runner.py` `build_config_from_env()` (`:1084-1085`) — when
  `AQ_EXECUTION_CELL_RUNNER_CLIENT_UID` is absent but `...CLIENT_USER` is set, resolve
  `client_uid = pwd.getpwnam(user).pw_uid` at startup (authoritative at runtime, portable across hosts
  where `primaryUser` differs e.g. `pi`). A direct `CLIENT_UID` int still wins if given (tests). Deny-
  closed: if neither resolves, `client_uid=None` (current behaviour — rejects all, never opens up).
- EDIT `config/env-contract.yaml` — declare `AQ_EXECUTION_CELL_RUNNER_CLIENT_USER` (primary),
  `AQ_EXECUTION_CELL_RUNNER_CLIENT_UID` (optional override), AND `AQ_EXECUTION_CELL_RUNNER_CLIENT_GID`
  (the runner still *reads* it at `execution_cell_runner.py:1085`, so it must be contract-declared even
  though it is deliberately NOT provisioned in Nix — declare ≠ provision). (rev2 re-review item b)
- EDIT `scripts/testing/test-execution-cell-runner.py` (or adjacent) — the test list below.
- A REAL deploy-exercise gate (not unit-only): after owner activation + rebuild, verify the socket
  keeps `SocketGroup=aq-execution-cell-clients` after the runner starts, the switchboard connects AND
  passes SO_PEERCRED (effective-uid match), and a full mint→sign→UDS→bwrap-cell→validator→typed-receipt
  round-trips GREEN.
- MUST NOT alter C2 admission, R1/R2/R5 frozen semantics, the switchboard byte-parity anchor, or the
  `peer_authorized`/Ed25519 *logic* (only provision the identity the logic already expects).
- b41c81e3 caveat (codex): the runner bundle is not the full telemetry closure —
  `span_taxonomy→trace→event_log→contracts.events` is unbundled; harmless today (telemetry-path
  exceptions swallowed) but must be exercised if runner-side C5 spans are ever enabled.
- Deployment-only surfaces to probe in the live gate (#7+, none disproven statically): unprivileged
  cgroup create/write/remove + `cgroup.kill` (`execution_cell_runner.py:383-464`), bwrap
  `--unshare-all` preflight under `NoNewPrivileges=true` (`:320-347`), out-of-cell validator access
  (`:757-772`).

## Fix implementation sketch (bug #5 — grounds the ceiling)

`serve_forever` (`execution_cell_runner.py:983-1017`) *always* unlinks + self-binds, despite its
own docstring claiming "systemd owns socket creation/mode/ownership in production." Replace the
unconditional self-bind with an activation-first acquisition:

```python
SD_LISTEN_FDS_START = 3  # systemd passes activated fds starting here

def _acquire_listen_socket(config):
    # Socket-activation: adopt the fd systemd already bound + listen()ed with the
    # unit's SocketGroup=aq-execution-cell-clients + SocketMode=0660. NEVER unlink
    # or re-bind it — that is exactly what destroyed the group (bug #5).
    if os.environ.get("LISTEN_PID") == str(os.getpid()) \
       and int(os.environ.get("LISTEN_FDS", "0")) >= 1:
        s = socket.socket(fileno=SD_LISTEN_FDS_START)  # family/type inherited from the fd
        return s, False  # owns_path=False -> do NOT unlink on exit (systemd owns it)
    # Offline / dev / test fallback: self-bind (unchanged behaviour, tests rely on it).
    if os.path.exists(config.socket_path):
        try: os.unlink(config.socket_path)
        except OSError: pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(config.socket_path); os.chmod(config.socket_path, 0o660); s.listen(16)
    return s, True
```

`serve_forever` calls it, keeps `settimeout(0.5)` + the accept loop unchanged, and only unlinks the
path in `finally` when `owns_path` is True. The adopted fd is already listening, so re-`listen()` is
skipped (or is a harmless no-op). Net diff: ~15 lines, one seam, zero change to `_handle_connection`,
grant verify, SO_PEERCRED, cell construction, the validator, or the cgroup reap.

## Review obligations (freeze §)
1. Activation path adopts fd 3 ONLY when `LISTEN_PID==getpid()` and `LISTEN_FDS>=1`; never unlinks
   or chmods the activated socket (that regression is the whole bug).
2. Fallback self-bind path is byte-unchanged so `test-execution-cell-runner.py` standalone still runs.
3. No widening: SO_PEERCRED still authenticates every peer; the socket group is authorization
   transport only; grant Ed25519 verify unchanged; deny-closed posture intact.
4. The deploy-exercise gate is REAL (post-rebuild live round-trip), not a unit-only assertion —
   R0 §8 "a /health probe does not count" applies.
5. Watch-list (#6+ candidates) explicitly probed once the socket connects: cgroup.kill write as the
   unprivileged runner, bwrap `--unshare-all` under `NoNewPrivileges=true`, out-of-cell validator read.

## Acceptance bar
- After owner activation + rebuild: `ls -l` on the socket shows `SocketGroup=aq-execution-cell-clients`
  **after the runner has started** (proves adoption, not clobber); a clients-group member connects
  first-try and repeatedly (not just the activation-triggering first connect).
- A real `write_file` cell-effect round-trips mint→sign→UDS→bwrap-cell→validator→typed GREEN receipt.
- Fallback: running the runner standalone (no `LISTEN_FDS`) still self-binds + serves (tests pass).
- Flag-OFF byte-parity preserved for the switchboard; C2 admission + C5 spans unchanged; no regression.

## Open questions for review
- Q-H-1: adopt strictly fd 3, or scan `LISTEN_FDS` range / honour `LISTEN_FDNAMES`? Recommend strict
  fd 3 — the unit declares exactly one `ListenStream`, so a single activated fd is invariant.
- Q-H-2: keep the self-bind fallback in the production module, or split it to a test-only shim?
  Recommend keep (guarded by the env check) — it is inert in production (systemd always sets
  `LISTEN_FDS`) and keeps the offline tests self-contained, lowering total surface vs a second file.

## REV3 (2026-08-01) — folds BOTH codex reviews of runner-hardening
Two complementary codex reviews, both REQUEST_REVISION, now folded:
- **Autonomous batch review** (`RUNNER-DEPLOYMENT-HARDENING-CODEX-DEPTH-REVIEW-20260801.md` + the
  consolidated `CODEX-DEPTH-REVISION-BRIEF-20260801.md`): socket-activation *robustness*.
- **rev2 re-review** (`codex-20260801-092906`): bug-#6 fix mechanism. Confirmed **NSS/getpwnam PASS**
  — `ProtectHome`/`ProtectSystem=strict`/`NoNewPrivileges` do NOT block `/etc/passwd` resolution;
  codex verified `hyperd`→uid 1000 resolves via `passwd: files systemd` in the unit. REQUEST_REVISION
  only on: (a) tests must exercise the resolution mechanism; (b) `CLIENT_GID` must also be declared in
  env-contract (the runner still reads it at `execution_cell_runner.py:1085`; declare ≠ provision).

### Socket-activation robustness (codex brief — added to the Ceiling)
- Safely parse `LISTEN_PID`/`LISTEN_FDS` and **fail closed** on malformed values (no leaked
  `ValueError`; a bad value falls back or refuses, never adopts a wrong fd).
- Require **exactly one** validated `AF_UNIX` listening socket at fd 3 bound to the configured path;
  **close unexpected inherited descriptors** and **clear the activation environment** after adoption.
- **Never** unlink/chmod a systemd-owned socket on fallback, manual start, restart, activation
  mismatch, or error. Self-bind ONLY when the path is provably unowned + exclusively created by this
  process.
- **Pin** both runner + test baselines and the runner/switchboard Nix no-edit anchors.

## Required tests (REV3 — union of both codex reviews)
Socket-activation (brief):
- matching `LISTEN_PID` + one fd → adopts fd 3; activated socket inode + path/group/mode unchanged.
- mismatched `LISTEN_PID` → does NOT adopt fd 3 (falls back).
- zero/absent `LISTEN_FDS` → self-binds and cleans up its path on exit.
- **malformed** `LISTEN_FDS` → deterministic fail-closed, no leaked `ValueError`.
- **multiple** descriptors / **wrong fd type or path** → refused (not silently adopted).
- **manual restart** / systemd-owned socket → never unlink/chmod'd.
Peer-auth / bug #6 (rev2 re-review):
- valid `CLIENT_USER` → resolves via `pwd.getpwnam(...).pw_uid`, matching effective-uid peer authorized.
- direct `CLIENT_UID` int **wins over** `CLIENT_USER`.
- unknown/unresolvable `CLIENT_USER` → `client_uid=None` → REJECT (deny-closed).
- neither variable set → REJECT.
- supplementary client-group membership with a **different effective GID** → NOT authorized
  (proves the SO_PEERCRED effective-gid pitfall is closed).

## Ceremony (REV2 — freeze was lifted by the codex REQUEST_REVISION)
design **rev2** (this doc, bug #6 folded) → **codex re-review** of the revised design (binding; it
raised the finding, it confirms the resolution) → **re-freeze** at the expanded 4-file subject →
**single-use owner activation** (hash-bound to the rev2 subject) → build → independent review → commit
→ fresh owner R5-shadow re-activation (enable+flagOn+CAPABILITY_CELL_ADAPTER, one rebuild) → the full
deploy-exercise gate above (which now also asserts SO_PEERCRED passes for the switchboard).

## Current safe state (post-rollback)
- C2 lease enforcement: LIVE (enforcing — admits first-party tools, denies unknown).
- C5 span-truth: LIVE (observing).
- R5 adapter + R3 runner: BUILT + reviewed, DORMANT (flags OFF, runner enable=false).
- No regression to real tool-calling. The confinement spine is paused pending this slice, not lost.
