# Security Validation Reliability — Design Packet

Status: **PREPARED_ONLY / DESIGN_ONLY / REVIEW REVISION 2**
Prepared: 2026-07-16
Activation: **Not authorized by this packet**
Scope boundary: No runtime, test, governance, workflow, dashboard, Nix, or existing-plan file is changed by this packet.

## 1. Objective

Restore a single, enforceable, redaction-safe secret-validation path across local development, staged commits, Tier-0/Phase-0 validation, and CI. Correct the stale security-library references and directory scanner coverage defect without creating a second security-library tree, enabling a dormant dashboard route, cutting over live traffic, or adding a lifecycle store.

This work is justified by observed validation failures, not by speculative hardening:

- `gitleaks` is not available in the current shell.
- The security integration test references a nonexistent `lib/security/` tree and fails before exercising the scanner.
- The canonical scanner's `find` predicate is ungrouped, so most intended file extensions do not reach `-print0`.
- Markdown is absent from the canonical scanner's extension set.
- Gitleaks CI workflows disagree on whether findings are blocking.
- `.gitleaks.toml` excludes agent and archive trees wholesale, including Markdown-rich planning and prompt surfaces.
- A dormant dashboard security route uses the stale library path and interpolates an identifier into `bash -c`.

## 2. Exact Evidence Snapshot

All observations below were collected on 2026-07-16 from the working tree. Hashes identify the inspected versions; point-in-time counts are evidence, not acceptance thresholds.

### E1 — Required scanner is absent

```text
$ command -v gitleaks
<no output>
$ gitleaks version
zsh: command not found: gitleaks
```

`flake.nix` does not currently include gitleaks in the default, security, or full development shells. A sandbox restriction prevented evaluating the nixpkgs package during this design-only investigation; package availability must therefore be proven during implementation rather than assumed.

### E2 — Canonical security library and stale test disagree

- Canonical scanner: `lib/cross-cutting/security/scanner.sh`
  - SHA-256: `55554098cf6d7b3ffb6e2c58043d5d42c7fc0e2c748879f2dd5797c9c2a4b996`
  - Size observed: 30,258 bytes
- Integration test: `scripts/testing/test-security-workflow-integration.py`
  - SHA-256: `8bea8ecf6ebcbdecba9c3daf8551d99ddbbfb52c93bebe4d947d28886dc44e60`
  - Adds `lib/security` to `sys.path`.
  - References `lib/security/scanner.sh` and `lib/security/compliance-checker.sh`.
  - Imports `audit_logger`, while the canonical file is `audit-logger.py`.

Direct execution fails before scanner coverage is tested:

```text
ModuleNotFoundError: No module named 'audit_logger'
```

Repository search found documentation references to this integration test, but no current Tier-0, Phase-0, or CI invocation.

### E3 — Directory traversal does not implement its apparent extension contract

In `detect_secrets()` within the canonical scanner, the directory branch has an unparenthesized expression of the form:

```sh
find "$path" -type f -name "*.sh" -o -name "*.py" ... -o -name "*.conf" -print0
```

Because `-print0` is attached only to the last OR branch, the expression does not emit all matching extensions. Against the current repository snapshot:

- Existing expression emitted 34 files.
- Equivalent expression with grouped name predicates emitted 6,443 files.
- The tree contained 2,312 Markdown files matching the proposed Markdown predicates.

Markdown (`*.md`, `*.markdown`) is not present in the scanner's extension list at all.

### E4 — Gitleaks configuration hides high-value text surfaces

`.gitleaks.toml` SHA-256: `751ff9444a7f1c601b13d985a1a7496903890b0210343c89bcc51032dc66f42a`.

The configuration excludes entire trees including:

- `^.agent/.*$`
- `^.agents/.*$`
- `^docs/archive/.*$`
- broad archive patterns such as `^archive/.*$`

These exclusions prevent content-based validation of prompts, plans, handoffs, and historical Markdown. Directory-wide exclusions are not evidence-backed allowlists.

### E5 — CI enforcement is contradictory

- `.github/workflows/gitleaks.yml`
  - SHA-256: `7f1c8164a5c812584d35f60633dda97c5d1bae4c71b892cb1c4336f2c137d40f`
  - Installs gitleaks v8.24.3.
  - Runs a no-git scan with `--exit-code 0`, making findings nonblocking.
- `.github/workflows/security.yml`
  - SHA-256: `b435a566513baa0dcf5c925499acae41bb227a4b1cb1421379a549d3a1bc9160`
  - Installs gitleaks v8.24.3.
  - Uses `--exit-code 1`, making findings blocking.
- `.github/workflows/test.yml` scans only selected `*.sh`, `*.nix`, and `*.py` files using a separate nonblocking heuristic.
- `.githooks/pre-commit` uses another staged-file regex scanner. It is narrower than gitleaks, has path exclusions, and permits `SKIP_SECRET_SCAN=1`.
- Tier-0 has a SOPS synchronization check but no gitleaks-backed repository validation.

The same repository therefore produces different pass/fail decisions depending on entrypoint.

### E6 — Documentation and dormant dashboard compatibility defects

- `docs/operations/security-audit-compliance-integration.md`
  - SHA-256: `3b90a1e0e8384e0e6ee64dc3b5c00d6d31653d2a407dc0f6d159cae89b5b9c13`
  - Contains multiple `lib/security/...` examples for scanner, audit logger, compliance checker, and workflow validator.
- `dashboard/backend/api/routes/security.py`
  - SHA-256: `84ee7de85c387c92d02568976460eab56f2939c5650bcc15358e7f336ac17f41`
  - Defines `SECURITY_LIB_DIR` as `<repo>/lib/security`.
  - Builds a `bash -c` command by interpolating `deployment_id`.
- `dashboard/backend/api/main.py` does not import or mount this security router. The route is dormant and must not be represented as live dashboard coverage.

### E7 — Exact Phase-0 and Tier-0 ownership

- Phase-0 implementation owner: `scripts/testing/harness_qa/phases/phase0.py`
  - SHA-256: `97d43f92c7638a6be261ea1ba5934caa8a8e178370b58f48820c54dcde3dc5c4`
- Phase registry: `scripts/testing/harness_qa/phases/__init__.py`
  - SHA-256: `dcb0bab2863333d70005f27870ad6e194859bfce82564c3d82e67b4e03cdb405`
  - Phase `0` is already registered as `phase0.run`; no registry edit is required.
- Tier-0 owner: `scripts/governance/tier0-validation-gate.sh`
  - SHA-256: `da91d135fa2adf2caed221aa8e6a68f5212c287865dbd09c833b6195e631a553`
  - `gate_qa_phase0()` already executes `scripts/ai/aq-qa 0`; no Tier-0 owner edit or `tier0.d` duplicate is required.

Therefore `scripts/testing/harness_qa/phases/phase0.py` is the only additional coverage owner required by this design. The registry and Tier-0 gate are validation inputs, not edit inventory.

## 3. Proposed Architecture and Ownership

### 3.1 Single source of truth

`lib/cross-cutting/security/` remains the only canonical security-library tree. No `lib/security` directory, copy, symlink, import alias file, or compatibility shim is permitted. All consumers migrate to the canonical path.

A new executable `scripts/security/secret-scan.sh` becomes the transport-neutral validation facade and the **sole process allowed to invoke `gitleaks`**. The call graph is strictly one-way:

```text
pre-commit / CI / Phase-0 / scanner.sh:detect_secrets
                         |
                         v
             scripts/security/secret-scan.sh
                         |
                         v
             gitleaks executable from PATH
```

The facade never sources or invokes `scanner.sh`. `scanner.sh` retains its public functions; only its `detect_secrets` implementation invokes the facade and translates the facade result into the existing JSON shape. No other hook, workflow, Python test, or library function invokes gitleaks directly. This prevents recursion and makes gitleaks argument/config ownership unambiguous.

### 3.2 Modes and typed outcomes

The facade supports explicit bounded modes:

- `staged`: only candidate content in the Git index.
- `worktree`: repository files under the declared scope.
- `history`: an explicitly requested Git-history scan; never implied by a fast local gate.
- `self-test`: a synthetic temporary Git corpus used only by Phase-0 and integration tests.

Exit contract:

| Exit | Meaning |
|---:|---|
| 0 | Scan completed with no unapproved findings; during the authorized migration window, active baseline matches are reported as degraded but are not new findings. |
| 1 | Scan completed with a new, unapproved, expired-baseline, or otherwise blocking finding. |
| 2 | Validation could not establish a result: tool absent, invalid configuration, timeout, malformed input, or execution failure. |

Enforcement callers fail closed on exits 1 and 2. A temporary audit-only transition, if separately authorized, must be explicit, owner-bound, and expiry-bound; it cannot be the default CI mode.

### 3.3 Pinned resource bounds

Limits are contract defaults, not implementation suggestions. A limit breach is exit 2 (`incomplete_limit`) rather than a partial success. Overrides may only lower limits in hooks/CI; raising one requires an explicit CLI option, is recorded in machine output, and is forbidden in Phase-0.

| Mode | Max files/objects | Per-file bytes | Total input bytes | Wall time | Machine-output bytes |
|---|---:|---:|---:|---:|---:|
| `self-test` | 16 | 262,144 (256 KiB) | 4,194,304 (4 MiB) | 15 s | 65,536 (64 KiB) |
| `staged` | 500 | 2,097,152 (2 MiB) | 67,108,864 (64 MiB) | 30 s | 262,144 (256 KiB) |
| `worktree` | 10,000 | 2,097,152 (2 MiB) | 536,870,912 (512 MiB) | 120 s | 1,048,576 (1 MiB) |
| `history` | 50,000 | 2,097,152 (2 MiB) | 1,073,741,824 (1 GiB) | 300 s | 2,097,152 (2 MiB) |

Output is counted after redaction. Exceeding the output bound truncates detail, preserves aggregate counts, marks `output_truncated=true`, and exits 2 because the full evidence contract was not delivered.

### 3.4 Content and traversal contract

- Include Markdown extensions `*.md` and `*.markdown`, including `.agent/` and `.agents/`.
- Group all `find` name predicates and attach the action to the complete expression.
- Traverse deterministically and handle spaces and line breaks in names using NUL-delimited paths.
- Reject traversal outside the repository root and do not follow untrusted symlinks.
- Apply the pinned size, count, duration, and output limits above with a typed exit-2 result when completeness cannot be established.
- Detect and skip binary data through a documented, tested policy.
- Never print matched secret values. Reports contain redacted findings and stable rule/fingerprint identifiers only.

### 3.5 Baseline and allowlist migration contract

Remove whole-tree exclusions for agent, documentation, and archive content. A retained exception must be scoped to an exact reviewed fixture or stable fingerprint plus rule identifier, include a rationale, and have an owner/review date. Generated reports and test fixtures must use synthetic canaries, never real credentials.

Legacy findings are distinct from new findings through `config/secret-scan-baseline.json`, a redacted, versioned ledger. Each entry contains only `rule_id`, repository-relative path, the SHA-256 of the upstream non-secret finding fingerprint, owner, rationale, `first_seen_commit`, and an expiry no later than 30 days after admission. It must not contain the matched value, source line, or surrounding content.

Migration sequence:

1. After declarative tool availability is deployed, run bounded `worktree` and `history` audits with the hook still unchanged.
2. Rotate/remove every real credential immediately. Convert intentional synthetic fixtures to exact rule-plus-fingerprint allowlist entries.
3. Admit an unresolved legacy finding to the baseline only through review, with owner and expiry. Blanket paths/globs remain prohibited.
4. The facade partitions results into `new_findings`, `baseline_findings`, and `stale_baseline_entries`. New or expired findings exit 1. Active baseline matches produce exit 0 only in the explicitly declared transition window and set `degraded_baseline=true`; CI/Tier-0 surface the count.
5. A baseline entry not observed in a complete scan is stale and fails validation until removed, preventing the ledger from becoming an accumulating suppression list.
6. Activate the fail-closed pre-commit hook only after the baseline review is committed and the host tool-availability gate passes.

### 3.6 Declarative launcher and activation sequence

The facade resolves exactly `command -v gitleaks` and refuses aliases, shell functions, repo-local downloaded binaries, or runtime installation. It never calls `nix shell`, `nix develop`, `curl`, package managers, or the network.

Availability is established before hook activation in a separate precursor:

- Add `pkgs.gitleaks` to `nix/modules/roles/ai-stack.nix` `environment.systemPackages`, making it available to ordinary host shells outside `nix develop` after the normal NixOS deployment.
- Add `pkgs.gitleaks` to the default, security, and full development shells in `flake.nix` for supported non-deployed development entrypoints.
- Evaluate/build from the pinned `flake.lock`, deploy the role package, then prove in a fresh ordinary login shell that `command -v gitleaks` resolves to `/nix/store/.../bin/gitleaks` and `gitleaks version` succeeds without network access.
- Do not modify `.githooks/pre-commit` until that proof passes. On a supported host that has not completed the precursor, the old hook remains active. On another machine, entering/building the declared dev shell is a bootstrap prerequisite before the fail-closed hook is activated; hook-time fetching is never a fallback.

Once activated, missing gitleaks is exit 2 and blocks the commit with a deterministic remediation message naming the declarative precursor. `SKIP_SECRET_SCAN` is removed as an ordinary bypass; any emergency bypass requires the existing approval-gated governance path and leaves auditable evidence.

### 3.7 Compatibility contract

- Preserve current exported shell function names and JSON result shapes in `scanner.sh` unless a versioned contract migration is separately authorized.
- Load canonical `audit-logger.py` by an explicit file loader or execute it through its supported CLI; do not create `audit_logger.py` as a duplicate.
- Both gitleaks workflows invoke the same facade, configuration, version policy, and blocking semantics.
- The staged hook invokes the same facade. An absent tool is a typed failure, not a silent skip.
- Gitleaks availability and hook activation follow Section 3.6; neither the facade nor hook downloads tools.
- If retained, the dormant dashboard trigger passes values as positional arguments, for example `bash -c 'source "$1"; scan_deployment "$2"' -- "$scanner_script" "$deployment_id"`, or calls an executable facade directly. User-controlled data is never interpolated into shell program text.
- Do not mount the dormant security router or activate a new endpoint in this slice.

## 4. Closed Implementation Inventory and Activation Order

Each slice has a closed inventory. Expansion requires a fresh review and authorization.

### SVR-0 — Declarative tooling precursor

1. `nix/modules/roles/ai-stack.nix` — install `pkgs.gitleaks` into the deployed harness role so ordinary login shells have it without a dev shell.
2. `flake.nix` — include the same package in default, security, and full development shells.

Acceptance: pinned-flake evaluation/build succeeds; after deployment, a fresh ordinary shell resolves the Nix-store binary and a no-network version probe succeeds. The pre-commit hook is unchanged in this slice.

### SVR-1A — Core contract, baseline, coverage, and CI parity

1. `scripts/security/secret-scan.sh` — new canonical facade and typed machine output.
2. `lib/cross-cutting/security/scanner.sh` — grouped traversal, Markdown support, facade integration while preserving public results.
3. `scripts/testing/test-security-workflow-integration.py` — canonical paths, explicit loading of the hyphenated logger, and meaningful assertions.
4. `scripts/testing/harness_qa/phases/phase0.py` — add the bounded `self-test` integration check; this is the exact registered Phase-0 owner already consumed by Tier-0.
5. `.gitleaks.toml` — replace blanket tree exclusions with exact reviewed exceptions.
6. `config/secret-scan-baseline.json` — new redacted, expiring, per-finding legacy ledger.
7. `.github/workflows/gitleaks.yml` — call the canonical blocking facade.
8. `.github/workflows/security.yml` — call the same facade and remove behavioral drift.

The existing `scripts/testing/harness_qa/phases/__init__.py` and `scripts/governance/tier0-validation-gate.sh` require no edits: Phase 0 is registered and Tier-0 already invokes it.

### SVR-1B — Local hook activation

1. `.githooks/pre-commit` — replace the heuristic scanner with bounded staged-facade execution and honor typed outcomes.

SVR-1B is authorized only after SVR-0 deployment evidence and SVR-1A baseline review pass. It is not combined with SVR-0 in one commit.

### SVR-2 — Dormant compatibility and documentation

1. `dashboard/backend/api/routes/security.py` — canonical library path and non-interpolated argument handling; router remains unmounted.
2. `docs/operations/security-audit-compliance-integration.md` — canonical paths and validation contract.

No additional library alias, lifecycle store, service, dashboard mount, registry edit, Tier-0 gate edit, or traffic cutover belongs in these slices.

## 5. Acceptance and Regression Tests

### Contract and path tests

- Canonical security files exist under `lib/cross-cutting/security/`.
- No `lib/security` directory, symlink, or compatibility copy exists.
- No active code or documentation references `lib/security/`, except a deliberate negative regression fixture.
- `bash -n` passes for every changed shell script.
- The integration test loads `audit-logger.py` and exercises actual scanner functions.

### Corpus and traversal tests

- A temporary corpus covers every supported extension, including `.md` and `.markdown`, nested paths, spaces, line breaks, binary data, oversized files, and symlinks.
- Every eligible extension is scanned exactly once; a regression proves the grouped `find` predicate.
- Synthetic canaries in `.agent/` and `.agents/` Markdown are detected.
- Finding output is redacted; the canary value never appears in JSON, SARIF, console output, or logs.
- Exact fixture/fingerprint exceptions pass while adjacent unapproved content still fails.
- Baseline entries partition legacy from new findings, expire within 30 days, reveal no matched content, and become errors when stale.
- Traversal is deterministic and cannot escape the repository root.

### Entry-point parity tests

- `staged`, `worktree`, and explicitly requested `history` modes select the documented scope.
- Staged mode evaluates indexed additions rather than unrelated worktree content.
- Clean, finding, missing-tool, malformed-config, timeout, and execution-failure cases produce exits 0, 1, or 2 exactly as specified.
- In enforcement mode, missing gitleaks produces exit 2.
- `.gitleaks.toml` contains no blanket agent/docs/archive exclusion.
- Both CI workflows call the canonical facade and block exits 1 and 2.
- The pre-commit hook calls the staged facade and cannot silently convert tool absence to success.
- The facade is the sole direct gitleaks invoker; a static call-graph test rejects direct workflow/hook/library invocations and facade-to-scanner recursion.
- Every mode enforces its exact count, byte, time, and output defaults at the boundary.
- Nix evaluation proves gitleaks availability in the system role and required development shells.
- After SVR-0 deployment, a clean ordinary login shell outside `nix develop` resolves the store binary with network disabled.
- Before that proof, SVR-1B is absent; after activation, missing-tool behavior blocks with exit 2 and performs no download.

### Compatibility and system regressions

- Static dashboard-route test proves the canonical path and absence of identifier interpolation.
- `dashboard/backend/api/main.py` still does not mount the dormant security router.
- Existing security audit/compliance smoke tests pass.
- Dashboard security automation regressions pass without claiming repo-secret-scan coverage.
- Tier-0 pre-commit gate, Phase-0 checks, documentation-link validation, and changed-file security checks pass.

## 6. Phase-0 and Governance Coverage

The owner is closed: add the live bounded check to `scripts/testing/harness_qa/phases/phase0.py`. Its `run()` is already registered as phase `0` by `scripts/testing/harness_qa/phases/__init__.py`; `gate_qa_phase0()` in `scripts/governance/tier0-validation-gate.sh` already executes it. Neither registry nor gate is edited.

Phase-0 invokes `secret-scan.sh --mode self-test --machine` against a synthetic temporary Git corpus and asserts the clean and detected-canary paths within the 15-second/4-MiB contract. Missing tool or incomplete evidence is a failed `CheckResult`, not a skip. `scripts/testing/test-security-workflow-integration.py` deterministically simulates all three exit classes, including missing-tool exit 2. This supplies live integration coverage without making every Phase-0 run scan the whole repository.

The validation output must be machine-readable and bounded. Required fields are:

- schema version and mode;
- tool availability/version status;
- files considered, scanned, and skipped;
- Markdown considered and scanned;
- redacted finding count;
- duration;
- result and reason class.

File paths, matched values, prompt content, and credentials must not become metric labels or unprotected logs.

## 7. Telemetry and Dashboard Coverage Decision

**Decision: machine evidence is required; a new dashboard panel is not required for SVR-1 or SVR-2.**

Reasoning:

- This change repairs repository validation invoked by hooks, CI, and gates; it does not introduce a live service or background daemon.
- CI step summaries and Tier-0/Phase-0 machine output are the correct operational surface for this slice.
- The existing dashboard security route is dormant. Correcting its path and command construction is compatibility repair, not proof of live coverage.

The facade must emit the bounded fields in Section 6 so failures are observable without exposing secret material. If a later slice schedules the scanner, mounts the dashboard route, or introduces a service, the Service Coverage Contract applies in that activation slice: integration-path `aq-qa` coverage, a live dashboard card/badge, and the service code must ship together.

## 8. Threats and Controls

| Threat | Required control |
|---|---|
| Secret present in Markdown or agent prompt | Scan `.md`/`.markdown`; remove blanket agent-tree exclusions. |
| False green when tool is absent | Exit 2 and fail closed in enforcement callers. |
| Different results by entrypoint | One facade, one config, one version policy, parity vectors. |
| Secret leaked by scanner output | Redaction at source; synthetic-canary no-leak tests. |
| Shell injection in dormant route | Positional arguments or direct executable invocation. |
| Path traversal/symlink escape | Repository-root containment and no untrusted symlink following. |
| Scanner denial of service | Pinned file-count, per-file, total-byte, duration, and output bounds with typed incomplete result. |
| Permanent suppression of legacy findings | Redacted exact-fingerprint baseline, named owner, 30-day maximum expiry, and stale-entry failure. |
| Hook bricks ordinary host commits | Deploy system-package precursor first; activate hook only after an offline fresh-shell proof. |
| Hook downloads executable code | Facade accepts only an existing PATH binary and never invokes network/package tooling. |
| Recursive or drifting scanner ownership | One-way call graph; facade is sole gitleaks process owner. |
| Duplicate security implementation | Canonical cross-cutting tree; prohibit alias/symlink/copy. |
| Dashboard gives false assurance | Do not mount or label dormant compatibility code as live coverage. |

## 9. Rollback

Implement each slice as an atomic commit. Roll back in reverse order: SVR-2, SVR-1B, SVR-1A, then SVR-0.

- Revert the implementation commit; do not create a `lib/security` alias or symlink during rollback.
- If Nix evaluation, deployment, or the offline fresh-shell probe fails, leave the existing hook unchanged and roll back SVR-0. Do not proceed to SVR-1B or silently skip an unavailable scanner.
- If newly exposed legacy findings block adoption, retain traversal/path/redaction fixes and request a time-limited audit-only transition with named owner, expiry, and typed degraded evidence. Never restore blanket Markdown/agent exclusions or `--exit-code 0` as the permanent resolution.
- The dashboard router remains unmounted throughout, so its compatibility edit can be reverted without live traffic impact.
- Generated evidence must remain redacted. If an implementation defect writes secret content to an artifact, quarantine access immediately and use the approval-gated repository procedure for removal and credential rotation.

## 10. Authorization Gate

This packet is ready for review but authorizes no implementation. A fresh authorization should name either:

- **SVR-0 only** (required next): declarative system/dev-shell tool availability and offline proof, with no hook change.
- **SVR-1A after SVR-0 evidence**: facade, scanner repair, baseline, exact Phase-0 coverage, config, tests, and CI parity.
- **SVR-1B after SVR-1A review**: activate the local fail-closed hook.
- **SVR-2 independently after SVR-1A**: dormant compatibility/documentation cleanup.

Before execution, record full SHA-256 hashes for every existing file in the selected closed inventory and confirm working-tree overlap is safe. The Phase-0/Tier-0 ownership question is resolved by Section 6; no owner discovery or implicit inventory expansion remains.
