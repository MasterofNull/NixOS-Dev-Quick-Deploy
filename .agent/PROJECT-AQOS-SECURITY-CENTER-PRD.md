# AQ-OS Security Center PRD

Status: DRAFT — implementation authorized; privileged mutation remains fail-closed until its security gates pass
Owner: AQ-OS orchestrator
Parent: `.agent/PROJECT-AQOS-PRD.md`
Date: 2026-09-08

## 1. Outcome

AQ-OS users can understand and manage passwords, SOPS secrets, access keys, and
security posture from a beginner-friendly graphical Security Center. They do not
need an AI coding agent, shell command, or installer rerun for ordinary credential
lifecycle work.

The interface supports:

- a complete metadata-only inventory of current and future credentials;
- plain-language readiness, ownership, dependency, and rotation status;
- guided add, replace, revoke, and coordinated rotation workflows;
- a separate PAM-backed flow for the signed-in user's system password;
- emergency breach response that rotates an explicitly reviewed credential set;
- validation, dependent-service health checks, audit receipts, and rollback;
- recovery guidance for credentials that cannot safely be revealed or rolled back.

The browser, dashboard service, agents, prompts, telemetry, Git repository, Nix
store, and audit ledger never receive plaintext secrets.

## 2. Current Baseline and Gaps

Live inventory on 2026-09-08 found:

- 13 entries in the host's encrypted SOPS bundle;
- 9 entries in `manage-secrets.py`'s catalog, of which 8 are present;
- 4 stored signing/lease keys absent from that catalog;
- one mutable primary-user login password managed by PAM/`/etc/shadow`;
- GNOME Keyring and `pass` enabled, but no safe inventory/status projection;
- no graphical credential rotation or breach-response workflow;
- no single lifecycle catalog connecting a credential to its consumers,
  validation, restart order, rotation method, rollback semantics, and risk class;
- the present dashboard process is not a safe privileged authority boundary.

A redacted Gitleaks 8.30.1 baseline found 192 candidate detections across 36
historical paths and 28 commits; the current checkout has 13 candidates concentrated
in test fixtures and public/config examples. These are triage candidates, not proof
that 192 live credentials leaked. Historical Kubernetes Secret manifests and a
localhost private-key path are high-priority review targets. Rotation decisions must
be based on unique credential identity and present validity, never raw finding count.
An in-memory comparison found no equality between any current SOPS value and any of
the 192 detected historical candidates (including the decoded retired Kubernetes
values). This is useful evidence of prior rotation, but upstream revocation and
PAM/vault scope still require separate confirmation.

This mismatch is itself a defect: an uncataloged credential cannot be managed,
measured, or rotated reliably.

## 3. Users and Jobs

### Beginner operator

- “Tell me whether my system is protected and what needs attention.”
- “Help me change a database or service password safely.”
- “I think a key leaked; help me rotate everything affected.”
- “Explain what will restart, what could break, and how I recover.”

### Experienced administrator

- Inspect credential metadata, dependencies, rotation age, and audit receipts.
- Prepare and approve typed changes without granting arbitrary root or shell access.
- Export an encrypted recovery bundle and verify restoration procedures.

## 4. Non-Goals and Hard Boundaries

- No generic secret-reveal endpoint. Service credentials and private signing keys
  are non-revealable.
- No arbitrary Nix editor, shell, path, SOPS-decrypt, systemctl, sudo, or root D-Bus
  API.
- No plaintext values in URLs, JSON responses, browser storage, clipboard by
  default, logs, metrics, traces, crash reports, Git, or Nix expressions.
- No use of `X-Dashboard-Internal`, loopback source address, or caller-controlled
  headers as authorization.
- No direct write authority in the existing dashboard process.
- No shared-password shortcut across services. Independent credentials are the
  default and breach containment is mandatory.

## 5. Architecture

```text
Security Center UI (unprivileged, dedicated local origin)
  -> metadata-only dashboard projection
  -> authenticated typed request
AQ Settings Broker (dedicated identity, Unix socket, SO_PEERCRED)
  -> fresh PAM + WebAuthn/polkit step-up
  -> versioned allowlisted action schema
  -> one-shot privileged helper
       -> PAM password change OR SOPS candidate update OR declarative Nix staging
       -> validation and dependency-scoped activation
       -> health verification and rollback
  -> redacted append-only audit receipt
```

The broker has its own system user, private state directory, AppArmor profile,
systemd sandbox, resource limits, and no membership in the broad `ai-stack` group.
The one-shot helper receives values over a protected file descriptor or sealed
memory channel, never command arguments or environment variables.

## 6. Credential Lifecycle Catalog

Create one versioned catalog as the authority for both CLI and GUI. Every entry
must declare:

- stable ID, beginner label, purpose, class, and scope;
- storage backend (`sops`, `pam`, `gnome-keyring`, `password-store`, `hardware`,
  or external provider);
- owning identity and consuming services;
- whether it is addable, replaceable, rotatable, revocable, recoverable, or
  non-revealable;
- value policy (type, minimum strength, maximum size) without storing a value;
- prepare, validate, apply, health-check, and rollback action IDs;
- restart/rebuild impact and safe ordering;
- rotation interval/advisory and last-rotation evidence source;
- risk class and required authentication ceremony;
- external-provider instructions where AQ-OS cannot rotate the upstream value.

Unknown SOPS keys fail visibly as **Uncataloged credential**. A newly declared
SOPS secret fails CI unless the same change adds its catalog entry, QA check, and
Security Center projection.

## 7. Risk Classes

| Class | Examples | Required control |
|---|---|---|
| R0 metadata | readiness, consumer, last rotation | authenticated local session |
| R1 self-service | own login password, own vault health | fresh PAM authentication |
| R2 service credential | Postgres, Redis, internal API keys | PAM + WebAuthn/polkit, preview |
| R3 external/revocation | GitHub/provider keys, SSH access | R2 plus provider/revocation confirmation |
| R4 signing/recovery | lease/grant private keys, age recovery | local console, two-step ceremony, tested recovery |

## 8. User Experience

### Home

Show four simple states: **Protected**, **Needs attention**, **Rotation due**, and
**Setup incomplete**. Never show a blank `--` for available data.

Each credential card answers:

1. What is this for?
2. Is it configured and healthy?
3. What will be affected if I change it?
4. What is the safest next action?

Advanced identifiers and technical details remain behind progressive disclosure.

### Guided change

1. Choose a named credential/action.
2. Enter or securely generate a replacement; values are masked and never persisted
   by the browser.
3. Validate strength/format locally and again in the broker.
4. Review a redacted impact preview: affected services, restart/rebuild, checks,
   rollback availability, and external revocation step.
5. Complete fresh authentication and physical WebAuthn/polkit approval.
6. Apply once; replay and duplicate submission fail closed.
7. Watch dependency-scoped health verification.
8. Receive a redacted receipt and explicit old-credential revocation reminder.

### Emergency breach mode

“I may have leaked credentials” opens a breach wizard that:

- runs a redacted working-tree and full-Git-history scan;
- maps findings to catalog entries without displaying detected values;
- proposes a bounded rotation wave ordered by dependencies;
- distinguishes locally generated secrets from upstream provider credentials;
- rotates high-confidence affected credentials first, then validates consumers;
- requires explicit approval for each R3/R4 group;
- records old-key revocation as incomplete until independently confirmed;
- preserves only encrypted prior bundles and Nix generation rollback references.

“Rotate all” means all eligible catalog entries—not PAM passwords, vault entries,
hardware keys, or private signing roots without their required recovery ceremony.

## 9. Broker API (Version 1)

- `GET /v1/status` — broker readiness and policy metadata.
- `GET /v1/catalog` — metadata-only catalog and allowed actions.
- `POST /v1/changes/prepare` — typed candidate; returns opaque change ID and
  redacted preview.
- `POST /v1/changes/{id}/challenge` — fresh step-up challenge.
- `POST /v1/changes/{id}/apply` — consumes one single-use approval.
- `POST /v1/changes/{id}/rollback` — only the broker-recorded preceding state.
- `GET /v1/audit` — redacted, paginated receipts.
- `POST /v1/password/self/change` — PAM-backed caller-only password change.
- `POST /v1/incidents/prepare-rotation` — evidence-bound emergency rotation plan.

There are no generic execution, filesystem, decrypt, reveal, restart, or Nix APIs.

## 10. Security Controls

- Local-only by default. Remote administration is a separate HTTPS/mTLS mode.
- Dedicated origin, locally packaged assets, nonce/hash CSP, no third-party JS,
  exact CORS, CSRF and Origin enforcement, `frame-ancestors 'none'`, no-store.
- HttpOnly, Secure, SameSite=Strict server-side sessions with short idle/absolute
  expiry and rotation after login/elevation.
- Exact polkit action IDs; no wildcard or passwordless general helper.
- Schema validation, normalized identifiers, bounded sizes, symlink/race defenses,
  atomic candidate replacement, and no user-controlled command/path/unit names.
- Secret buffers are short-lived and excluded from diagnostics/core dumps.
- Dashboard, agent, and model identities cannot read broker state or `/run/secrets`.
- Every mutation is deny-by-default if authentication, audit, validation, health,
  or rollback prerequisites are unavailable.

## 11. Delivery Slices

### SC-0 — Inventory authority and PRD

- Reconcile SOPS declarations, encrypted bundle metadata, PAM, and vault backends.
- Define the lifecycle catalog schema and uncataloged-secret CI failure.
- Record the current history-scan baseline without detected values.

### SC-1 — Read-only Security Center

- Add a metadata-only status adapter and allowlisted response schema.
- Add the Secrets & Access card with beginner copy and all degraded states.
- Add Phase-0 integration coverage and dashboard contract tests.
- No new mutation authority.

### SC-2 — Broker foundation

- Dedicated Unix-socket broker, identity, AppArmor/systemd confinement, typed
  prepare/status APIs, redacted ledger, and negative security suite.
- Dashboard remains an unprivileged client.

### SC-3 — Own-password flow

- PAM-backed self password change with fresh auth and tested failure recovery.
- GNOME Keyring re-unlock/rekey guidance; never put the login password in SOPS.

### SC-4 — Service-secret replacement

- SOPS add/replace/generate, encrypted candidate, preview, one-shot apply,
  dependency health verification, and rollback.

### SC-5 — Coordinated rotation and breach response

- Dependency graph, rotation waves, provider-revocation checklist, historical scan
  mapping, and “rotate eligible set” workflow.

### SC-6 — Signing roots and recovery

- Separate R4 ceremony, public-key rollover, dual-verification window where safe,
  recovery export, restore drill, and revocation confirmation.

### SC-7 — Vault integration

- Metadata-only GNOME Keyring/`pass` health first; item mutation only through each
  backend's native trusted UI or separately reviewed adapter.

## 12. Acceptance Criteria

- Inventory count reconciles declared, stored, required, active, and uncataloged
  credentials without exposing values, hashes, prefixes, or lengths.
- No dashboard/agent identity can read SOPS plaintext, age keys, `/etc/shadow`,
  signing keys, broker state, or privileged helper inputs.
- Forged internal headers, loopback requests, CSRF, cross-origin requests, expired
  approvals, replay, concurrent rotation, path traversal, shell metacharacters,
  malformed Unicode, oversized input, symlink swaps, and interrupted applies fail.
- Every change produces a redacted impact preview, explicit approval, audit receipt,
  dependency-scoped verification, and truthful rollback/recovery state.
- Network/DOM/storage/log/telemetry captures contain no submitted secret bytes or
  derived identifying material.
- The active and previous encrypted bundles remain recoverable; plaintext backups do
  not exist.
- API, QA integration, and dashboard visibility ship together for every slice.
- Mutation controls do not activate until an independent security review passes.

## 13. Operational Measures

- inventory coverage: cataloged / discovered credentials (target 100%);
- rotation completion and failed/recovered changes;
- median time from suspected breach to verified rotation;
- credentials overdue for rotation and provider revocations still open;
- broker authorization failures/replays (redacted);
- dependent-service health after rotation;
- recovery drill age and success;
- dashboard data freshness and degraded-state accuracy.

## 14. Immediate Decision

Proceed with SC-0 and SC-1. SC-1 is intentionally read-only and provides immediate
visibility. Build SC-2 next; do not expose write controls as disabled theater in the
UI until the broker and authorization path are real. Password, service-secret,
emergency rotation, signing-root, and vault flows then land as separately reviewed,
measurable slices so implementation momentum continues without weakening the trust
boundary.

## 15. SC-0 / SC-1 Candidate Status

The corrected candidate now catalogs 17 security items: 14 possible SOPS entries
(13 declared and active on the current host, one optional/not enabled), the primary
PAM login password, GNOME Keyring, and `pass`. Each entry carries the lifecycle
fields in section 6. The publisher reconciles the catalog with Nix-evaluated declared
names and regular runtime entries, reports uncataloged entries without revealing
their names, and marks PAM/vault backends as managed separately rather than missing.

SC-1 publishes through a descriptor-anchored root-owned `/run/aqos-security`
directory, rejects symlink swaps, and gives the dashboard a fresh, owner-validated,
internally consistent metadata snapshot only. The publisher is an immutable Nix
store program with a reduced capability set and an enforcing AppArmor profile that
denies secret-file reads. Write and reveal operations remain absent.
