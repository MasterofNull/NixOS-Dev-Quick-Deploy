# AQ-OS Installer Experience — Independent PRD (Codex)

Status: independent draft for consolidation
Author: Codex
Date: 2026-08-30
Scope: product and engineering contract only; no installer implementation changes

## 1. Decision summary

AQ-OS should add a guided experience, but it should not begin by building a graphical installer or by asking an agent to write arbitrary Nix. The first product boundary must be a versioned, closed-schema **install plan** that every supported input path resolves into before any system mutation.

The required flow is:

```text
guided answers ─┐
AI proposal ────┼─> adapter -> validate -> normalize/default -> resolved plan
manual flags ───┘                                      |
                                                       +-> Nix projections
                                                       +-> deploy argv/env
                                                       +-> preview + receipts
                                                                  |
                                                       existing deploy executor
```

The smallest honest P1 is a guided, non-destructive quick-deploy flow for a machine already running NixOS. It supports the three profiles that exist today, hardware discovery, build/boot/switch choice, Home Manager, validation, and health checks. It defaults to `build`, never enables disko, and does not promise pre-install local AI.

Bare-metal disk installation is a later, separately gated product slice. The current repository has declarative disko layouts, but it does not contain an end-to-end `nixos-install` workflow and its destructive gate is only `DISKO_CONFIRM=YES`. That is not sufficient for a beginner-safe disk installer.

## 2. Source-backed current-state findings

### 2.1 The canonical executor is currently ambiguous

The existing architecture is not exactly what the Claude draft assumes:

- `nixos-quick-deploy.sh` is the working executor, but its header marks it deprecated and points to `./deploy system`.
- `./deploy system` is not implemented; it prints a migration notice and redirects back to `nixos-quick-deploy.sh`.
- `nixos-quick-deploy.sh` contains its active workflow as shell functions in one file. Its `main` calls model selection, preflight, guardrails, optional destructive steps, build/boot/switch, validation, and post-flight functions directly.
- The script does not source or execute `phases/phase-*.sh`. `--list-phases` only lists filenames.
- Most phase files are explicit deprecation stubs. Only phase 02, 04, and 06 still contain substantial legacy logic, and they are not part of the active quick-deploy call graph.

Therefore P1 must wrap `nixos-quick-deploy.sh` as the active compatibility executor while declaring one future executor boundary. It must not couple a new UI to the deprecated phase filenames.

### 2.2 The actual declarative layers are useful

The Nix side already provides a strong base:

1. `facts.nix` is intended to hold discovered machine facts.
2. reusable policy lives under `nix/modules/{core,profiles,roles,services,...}`;
3. host-specific configuration lives under `nix/hosts/<host>/`;
4. `deploy-options.nix` and `home-deploy-options.nix` supply deploy policy;
5. gitignored `deploy-options.local.nix` supplies local secret-related policy;
6. `flake.nix` constructs `nixosConfigurations` and `homeConfigurations` from those layers.

The existing profile enum is exactly `ai-dev | gaming | minimal`. There is no current `everyday`, `creative`, or `server` profile. A guided UI may label the existing choices in plain language, but P1 must not pretend missing presets exist.

The script also already has valuable primitives: hardware discovery, target validation, root-filesystem and bootloader checks, account/password guards, mandatory system and Home Manager dry-builds by default, generation snapshots, build/boot/switch modes, health checks, stateful downgrade guards, and post-flight verification.

### 2.3 The input surface is not yet a contract

The active script parses roughly 41 flags and references roughly 72 environment/default variables. Values are resolved incrementally into mutable shell globals. Hardware discovery accepts another set of `*_OVERRIDE` variables and writes `facts.nix`; model selection later edits the same generated file.

This causes four contract problems:

- precedence among config, flags, environment, discovery, prompts, and existing files is implicit;
- there is no versioned machine-readable record of the fully resolved intent;
- `facts.nix` is described as discovered facts only, but user policy such as profile and model selection is also written there;
- two front ends can invoke the same script while silently resolving different defaults.

A guided wrapper that merely assembles flags would reuse the executable, but it would not prove one configuration engine.

### 2.4 Disk provisioning is not beginner-safe today

Current disko execution checks only that:

- `--phase0-disko` was passed;
- `DISKO_CONFIRM=YES` is present;
- evaluated `mySystem.disk.layout` is not `none`.

The configured device defaults to `/dev/disk/by-id/CHANGE-ME`, but the runner does not bind confirmation to the disk's stable ID, serial, model, size, or a plan digest. It does not prove that the disk is not backing `/`, `/nix`, the repository, or the live installation media. The same reusable `YES` value can authorize a changed plan.

More importantly, the repository has no active `nixos-install` or target-root installation flow. Running disko is not itself a complete bare-metal installation. After a disk has been wiped, NixOS generations on that disk are gone; `nixos-rebuild switch --rollback` cannot reverse the wipe.

## 3. Corrections and gaps in the Claude draft

The draft has the right product direction but misses these engineering constraints:

1. **It names the wrong engine shape.** The phase directory is legacy inventory, not the active engine. The monolithic quick-deploy script is active, while its proposed replacement is incomplete.
2. **It treats “same inputs” as enough.** Flags and environment variables with implicit defaults do not provide a parity proof. Both paths need the same normalized plan and compiler.
3. **It overstates byte identity.** Source files may contain formatting, generated metadata, absolute paths, or timestamps. The correct proof is byte-identical canonical plan plus projection hashes and equal evaluated Nix derivations under the same locked flake.
4. **It assumes local AI is available during installation.** A wiped or fresh machine does not yet have the AQ-OS services or models. An AI-enabled live image would add model size, hardware, latency, and update constraints. AI cannot be on P1's critical path.
5. **It lets AI draft “actual Nix.”** For the beginner path, arbitrary model-produced Nix is too broad and defeats schema parity. AI should propose closed-schema intent; a deterministic trusted compiler should render Nix.
6. **It calls disk actions reversible.** Disk erasure is not reversible through NixOS generations. Backups and recovery media reduce loss; they do not create rollback.
7. **It does not distinguish upgrade recovery from first-install recovery.** Existing generations help an upgrade. They do not exist after a first-install wipe.
8. **It proposes personas that do not map to current profiles.** New presets require separate product and module work.
9. **It puts aesthetics in P0/P1 without an executable definition.** Theme work is valuable, but the first release gate is safe deterministic deployment. Aesthetic acceptance needs its own later asset and accessibility criteria.
10. **It lacks a resumable mutation journal.** A polished progress display is not enough; a power loss between partitioning and bootloader installation needs durable state and explicit recovery behavior.
11. **It lacks an expert-extension boundary.** Direct Nix edits must remain supported, but they cannot be silently conflated with schema-controlled installer choices.
12. **It does not address secrets.** Secrets, disk passphrases, and authorization phrases must never be serialized into the plan, logs, telemetry, or AI prompt.

## 4. Product goals and non-goals

### Goals

- Give a new Linux user one recommended path with plain-language explanations.
- Preserve all current expert flags and direct Nix workflows during migration.
- Make guided, AI, and manifest-mode manual inputs converge on one normalized contract.
- Make validation and the exact planned mutations visible before authorization.
- Fail closed on unknown fields, conflicting inputs, unsafe devices, stale plans, and drift.
- Produce durable, machine-readable progress and recovery receipts.

### Non-goals for P1

- no disk repartitioning, formatting, or bare-metal installation;
- no generated arbitrary Nix from AI;
- no dependence on a running model, coordinator, network, or external account;
- no new profile names, desktop environment, theme gallery, or ISO;
- no removal of legacy flags or direct host Nix customization;
- no automatic rollback of stateful data or destructive storage operations.

## 5. Canonical configuration contract

### 5.1 Source of truth

The planned SSOT is a pair, not JSON Schema alone:

- `config/schemas/aqos-install-plan-v1.schema.json`: structural contract, Draft 2020-12, with `additionalProperties: false` at every object boundary;
- a single resolver/compiler command: validates input, applies defaults, checks cross-field invariants, emits canonical JSON, and produces executor/Nix projections.

The schema defines valid shapes. The resolver defines precedence and semantics. Front ends must not independently implement defaults or map choices directly to shell variables.

Three artifacts are distinct:

- **request plan**: user-supplied values; may omit defaultable fields;
- **resolved plan lock**: all defaults explicit, canonicalized, immutable, secret-free;
- **execution authorization receipt**: short-lived approval bound to the resolved-plan hash and current hardware identity. It is never part of reusable desired configuration.

### 5.2 Proposed v1 resolved-plan shape

```json
{
  "schema_version": "aqos.install/v1",
  "target": {
    "host_name": "workstation",
    "primary_user": "alex",
    "profile": "ai-dev",
    "nixos_target": "workstation-ai-dev",
    "home_target": "alex-workstation",
    "flake_ref": "path:."
  },
  "operation": {
    "kind": "build",
    "apply_system": true,
    "apply_home": true,
    "update_flake_lock": false
  },
  "hardware": {
    "discovery": "refresh",
    "overrides": {}
  },
  "storage": {
    "action": "preserve",
    "layout": "none",
    "device": null,
    "luks": false
  },
  "features": {
    "model_selection": "retain",
    "ai_secrets": "retain",
    "flatpak_sync": true,
    "health_check": true
  },
  "validation": {
    "readiness": true,
    "roadmap": true,
    "system_dry_build": true,
    "home_dry_build": true,
    "max_preflight_passes": 3,
    "auto_remediation": false
  },
  "safety": {
    "allow_gui_switch": false,
    "previous_fsck_failure": "deny",
    "generated_file_policy": "persist",
    "stateful_downgrade_policy": "strict"
  },
  "extensions": {
    "nix_modules": []
  }
}
```

This is the normalized representation, so all fields are present. Request plans may omit values for which the resolver has documented defaults.

### 5.3 Field rules

| Path | Contract |
|---|---|
| `schema_version` | Exact enum in v1; no silent forward compatibility. |
| `target.host_name` | Lowercase RFC 1123-style hostname; reject shell/Nix metacharacters. |
| `target.primary_user` | Valid local username; reject `root` for the beginner flow. |
| `target.profile` | `ai-dev`, `gaming`, or `minimal` only in v1. |
| `target.*_target` | Derived unless explicitly supplied in expert manifest mode; explicit values must exist in flake outputs. |
| `target.flake_ref` | Defaults to the current repository. Remote refs require expert mode and a locked revision. |
| `operation.kind` | `analyze`, `build`, `boot`, or `switch` in P1. `install` is reserved and rejected until the bare-metal gate ships. |
| `hardware.discovery` | `refresh` or `reuse`; override keys are an allowlisted typed object, not arbitrary environment names. |
| `storage.action` | P1 requires `preserve`. Later: `repartition` requires the stronger disk contract below. |
| `features.model_selection` | P1: `retain` or a typed catalog selection; no free-form model path from guided/AI input. |
| `features.ai_secrets` | `retain`, `prompt`, `enable`, or `disable`; secret material is never embedded. |
| `validation.*` | Safety checks default on. Disabling a safety check requires expert mode and is visible in the preview. |
| `extensions.nix_modules` | Expert-only repo-relative module references with content hashes. Guided and AI adapters must emit an empty list. |

For future destructive installs, `storage.device` must be an object with `by_id`, `expected_serial`, `expected_model`, `expected_size_bytes`, and the discovery snapshot hash. `/dev/sdX` and `/dev/nvmeXnY` are display data, never authority.

### 5.4 Precedence

Precedence is resolved once and conflicts are reported, not silently won:

1. explicit request-plan value;
2. selected preset value;
3. schema default;
4. hardware discovery only for fields declared discoverable.

Existing environment variables and legacy flags are accepted by a compatibility adapter. If the same semantic field is supplied twice with unequal values, normalization fails and names both sources. Ambient environment values not on an allowlist are ignored.

### 5.5 Existing-engine projection

The compiler emits a secret-free execution manifest with an argv array and allowlisted environment map. Example mappings for P1:

| Resolved plan | Existing executor input |
|---|---|
| `target.host_name` | `--host` |
| `target.primary_user` | `--user` |
| `target.profile` | `--profile` |
| `operation.kind=build` | `--build-only` |
| `operation.kind=boot` | `--boot` |
| `operation.apply_system=false` | `--skip-system-switch` |
| `operation.apply_home=false` | `--skip-home-switch` |
| `hardware.discovery=reuse` | `--skip-discovery` |
| `features.model_selection=retain` | `--skip-model-selection` |
| `features.flatpak_sync=false` | `--skip-flatpak-sync` |
| `features.health_check=false` | `--skip-health-check` |
| `validation.readiness=false` | `--skip-readiness-check` |
| `validation.auto_remediation=true` | `--enable-preflight-auto-remediation` |
| `validation.max_preflight_passes` | `--preflight-loop-max-passes` |
| `safety.generated_file_policy` | `--restore-generated-files` or `--persist-generated-files` |

The first compatibility implementation may invoke `nixos-quick-deploy.sh` with this projection. The long-term executor should consume the resolved plan directly. No UI may call internal shell functions or legacy phase files.

### 5.6 Nix projection ownership

Projection must respect the repository's intended layers:

- discovery writes hardware facts;
- chosen policy writes deploy options or a generated installer-policy module;
- secret references write only to the existing local secret-policy surface;
- Home Manager choices write the Home Manager deploy surface;
- direct expert modules remain explicit hashed extensions.

The resolver should stop writing model/policy choices into the “facts only” namespace over time. That migration is separate from P1 compatibility and must preserve current behavior until tested.

### 5.7 AI contract

AI is an untrusted proposal adapter:

1. it receives a redacted hardware capability summary and the schema-supported choice catalog;
2. it returns strict JSON only, constrained to the request-plan schema;
3. unknown fields, safety overrides, raw Nix, shell, paths, secrets, and disk authorization are rejected;
4. the trusted resolver applies defaults and policy;
5. the UI shows a semantic diff between the current and proposed resolved plan;
6. the user approves the trusted plan, not the model response.

AI may explain choices, but explanation text has no execution authority. It can never authorize disk erasure, bypass validation, or supply a secret.

## 6. Parity guarantee and test design

“One engine” needs evidence at four layers.

### 6.1 Adapter parity

For every golden scenario, guided answers, AI JSON, manual manifest, and equivalent legacy flags must produce byte-identical canonical resolved-plan JSON. Canonicalization uses UTF-8, sorted object keys, normalized arrays where order is semantically irrelevant, explicit defaults, and no timestamps, random IDs, source labels, or UI text.

Provenance is stored in a sidecar receipt so it cannot change semantic hashes.

### 6.2 Projection parity

The same resolved-plan digest must produce byte-identical:

- generated Nix projections;
- argv array and environment map;
- selected flake targets;
- planned mutation list;
- validation checklist.

Each artifact is hashed and recorded in the preview receipt.

### 6.3 Nix evaluation parity

Against the same repository commit and `flake.lock`, tests evaluate both paths and compare:

- `config.mySystem` projected to JSON for installer-owned fields;
- NixOS system `drvPath`;
- Home Manager activation package `drvPath`;
- disko configuration JSON when the later storage path is enabled.

Direct expert Nix modules are included only when their path and content hash match in both inputs. Hand editing arbitrary Nix remains supported, but it is outside input-adapter parity; its correctness is evaluated by Nix.

### 6.4 Execution parity

A fake executor records argv, environment, ordered phase events, and attempted mutations. Guided and manual runs must produce the same trace from the normalized-plan boundary onward. Real NixOS VM tests then cover build, boot, switch, Home Manager failure, health-check failure, and reboot behavior.

### 6.5 Required suites

- **Golden matrix:** all three current profiles × build/boot/switch × discovery refresh/reuse × system/home toggles.
- **Default tests:** omitted request fields normalize identically in all adapters.
- **Conflict tests:** flag/config/env disagreement fails with no executor call.
- **Closed-schema tests:** unknown or mistyped fields fail; no permissive extra keys.
- **Round-trip tests:** resolved plan -> projections -> evaluated installer-owned values equals the resolved plan.
- **Coverage test:** every supported legacy flag and allowlisted environment variable maps to exactly one schema field or is explicitly classified runtime-only/deprecated.
- **Determinism test:** key order, locale, terminal type, current directory, and harmless ambient environment do not change the semantic digest.
- **Drift test:** repository commit, `flake.lock`, projected file, target hardware, or disk identity change invalidates prior preview/authorization.
- **Adversarial test:** shell/Nix interpolation strings remain inert data or are rejected.
- **Backward-compatibility test:** representative existing manual invocations retain behavior through the adapter.

The acceptance statement should be: “equivalent inputs produce identical canonical plan and projections, and equal evaluated derivations under the same locked source.” It should not claim every generated source file is universally byte-identical.

## 7. Failure, rollback, and disk safety

### 7.1 Separate reversible and irreversible operations

The preview must classify every action:

- read-only: discovery, evaluation, analyze;
- build-only: creates store paths but does not activate;
- activation: boot or switch, recoverable through generations in normal cases;
- secret mutation: separately confirmed and redacted;
- destructive storage: irreversible and governed by a separate authorization protocol.

P1 contains only the first three classes.

### 7.2 Upgrade/switch failure

For existing systems:

- default guided action is `build`;
- offer `boot` as the recommended application path when desktop/session risk exists;
- snapshot current NixOS and Home Manager generations before activation;
- write the plan digest, old/new generation IDs, and exact recovery commands to a receipt;
- if validation fails after switch, stop further post-flight mutations and offer an explicit rollback action;
- do not automatically roll back stateful services or databases;
- keep the previous generation bootable and show the boot-menu recovery path.

Current code prints rollback guidance, but the product must turn that into a tested recovery state with a durable receipt.

### 7.3 Preconditions for future destructive storage support

No bare-metal release may enable `storage.action=repartition` until all are true:

1. The workflow runs from a supported live environment, not the target's running root.
2. It proves the target disk is not an ancestor of `/`, `/nix`, the repository, swap, or installation media.
3. Authority uses `/dev/disk/by-id` plus serial/model/size; kernel names are display-only.
4. The identity tuple is captured during preview and rechecked immediately before mutation.
5. The target NixOS closure and boot configuration pass evaluation/build before wipe, or are available from a verified offline/cache source.
6. The user declares either a verified backup destination or that the disk contains no needed data. The UI must not call the wipe reversible.
7. Confirmation requires a plan-specific phrase containing the disk model and serial suffix, then a second final action. A stored `YES` is invalid.
8. Authorization is single-use, expires quickly, and binds plan digest, source revision, hardware snapshot, disk identity, and operation.
9. Encryption passphrases use an interactive secret channel; they never enter argv, environment, plan, logs, telemetry, or AI context.
10. Power and resource checks pass; laptop installs require AC power or an explicit expert override.
11. A durable journal exists outside the target disk, and recovery instructions can be exported before wipe.

### 7.4 Post-wipe state machine

The later installer needs explicit states:

```text
PLANNED -> VALIDATED -> AUTHORIZED -> WIPE_STARTED -> PARTITIONED
        -> SYSTEM_INSTALLED -> BOOTLOADER_INSTALLED -> VERIFIED -> COMPLETE
```

Once `WIPE_STARTED` is recorded, resume must never invoke disko again automatically. A failure after partitioning should preserve mounts and offer “retry installation into existing layout,” log export, diagnostics, or a shell. A failure after bootloader installation should offer `nixos-enter`/bootloader repair from the live environment. First-install recovery must never promise an old generation that no longer exists.

## 8. P1: smallest genuinely shippable guided flow

### Supported environment

- already-running NixOS machine with this repository available;
- interactive terminal;
- existing `nixos-quick-deploy.sh` compatibility executor;
- storage preservation only;
- network optional except where the selected flake/build inputs require it.

### Six guided decisions

1. Confirm detected host and primary user.
2. Choose one current profile with plain-language labels and `minimal` as the conservative fallback.
3. Choose discovery refresh or reuse.
4. Retain current model selection in the default path; advanced users may choose from the existing typed catalog.
5. Preview the exact config diff, build impact, validation gates, and planned mutations.
6. Run `build` by default; after success, separately offer `boot` or expert `switch`.

The wizard must provide Back, Cancel, Save Plan, and Explain on every decision. Cancellation before execution makes no config mutation. It must work without AI.

### P1 acceptance criteria

- all three input adapters normalize through one resolver;
- guided and manual golden cases meet the parity suites in section 6;
- default guided execution cannot pass `--phase0-disko`, enroll Secure Boot keys, update `flake.lock`, disable dry-build gates, or use arbitrary modules;
- unknown fields and conflicts fail before invoking the executor;
- preview and execution receipts contain semantic/projection hashes and no secrets;
- build failure returns to an editable plan without partial activation;
- boot/switch failure shows tested recovery actions;
- progress is emitted as timestamped structured events and visible in the installer; post-install status has a dashboard/QA integration when a new service is introduced;
- existing expert CLI regression tests remain green.

## 9. Realistic phase ordering

### P0 — contract and factual alignment

- designate `nixos-quick-deploy.sh` as compatibility executor until `deploy system` is real;
- mark legacy phase files as inventory, not executable architecture;
- inventory every flag/environment input and its precedence;
- freeze v1 schema, canonicalization rules, security invariants, and golden vectors;
- define event and receipt schemas.

### P1A — resolver and manual manifest mode

- implement schema validation, normalization, semantic hashing, projection, and dry-run preview;
- add `--config`/manifest-mode compatibility without changing current flag behavior;
- establish adapter, projection, and Nix-evaluation parity tests.

### P1B — guided non-destructive UI

- implement the six-decision flow;
- default to build, then explicit boot/switch;
- add timestamped progress events, cancellation, saved plan, and recovery receipt;
- dogfood on existing NixOS and test in VMs.

### P2 — executor stabilization

- make `deploy system` the real stable entrypoint or remove its false migration claim;
- move input normalization out of mutable shell globals;
- expose machine-readable events and resumable execution;
- reconcile policy values currently written into `facts.nix` with the documented layer ownership.

### P3 — bare-metal/live-media installer

- implement target-root `nixos-install`, bootloader verification, external journal, and the disk gates in section 7;
- test induced failures at every state transition on disposable virtual disks and representative hardware;
- only then enable `storage.action=repartition` and build an installer ISO.

### P4 — AI proposal adapter

- choose and document the bootstrap runtime: model on ISO, explicitly opted-in remote service, or post-install-only assistance;
- constrain output to the request-plan schema;
- add redaction, semantic diff, strict validation, and adversarial prompt tests;
- keep AI out of authorization and secret handling.

### P5 — first-run and curated experience

- welcome/tour, update and rollback teaching, living manual, accessibility;
- add new persona presets only with corresponding Nix modules and parity fixtures;
- theme gallery and visual polish with measurable accessibility and recovery acceptance.

## 10. Operational telemetry

Every run should emit a stable run ID in a non-semantic sidecar and timestamped events for plan validation, projection, preflight, build, activation, health, and recovery. Each event records the plan digest, phase, status, duration, and redacted error category. Secrets and raw AI prompts are excluded.

Required measures include success/failure by phase, retry count, time to first actionable error, build/boot/switch duration, recovery action selected, and parity-suite status. A new persistent installer service is incomplete without an `aq-qa` integration check and dashboard state; a command-only P1 can publish its latest receipt through an existing status surface rather than adding a daemon.

## 11. Success metrics

- 100% of guided and manifest-mode manual golden cases produce the same canonical plan and projections.
- 100% of supported legacy flags are mapped or explicitly classified; none disappear silently.
- Zero destructive operations are reachable from P1 guided mode.
- A novice usability test completes plan creation and a build without terminal vocabulary beyond explanations shown by the UI.
- Every failure state presents one tested next action and an exportable receipt.
- Direct Nix and legacy CLI workflows remain available to experts.
- Before bare-metal release, all destructive state-transition fault-injection tests pass and no authorization survives plan or disk drift.

## 12. Consolidation decisions required

1. Accept that P1 is existing-NixOS, non-destructive guided deploy rather than a bare-metal installer.
2. Name the compatibility and future canonical executors so documentation stops contradicting runtime reality.
3. Approve the resolved-plan contract as the semantic SSOT and keep authorization receipts separate.
4. Decide where installer-owned policy should live while preserving `facts.nix` as discovered facts.
5. Choose the P3 live-media/target-root architecture before any beginner disk UI is designed.
6. Choose the P4 AI bootstrap strategy and its offline guarantees.

The key product promise should be modest and testable: AQ-OS turns human intent into a validated, inspectable declarative plan, and every interface applies that same plan through one trusted compiler and executor. Beauty and AI become differentiators only after this safety and parity boundary is real.
