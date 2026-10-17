# FACTORY-TEMPLATE-DESIGN v2 — in-repo signed kit, full-parity consumer repos that learn their project

> **v2.3 owner simplification 2026-10-16 (binding).** Git repo + auth are each local user's own sign-in/config supplied at system init and deployment; the kit must not contain or depend on the owner's account info. SUPERSEDED: sections 1.1-1.4 (signed tag, orphan kit commit, verification, signer fields in `kit.lock`), tests T4b/T6/T6b/T9, `aq-factory release`, and the "Owner key" open decision. K2 = `templates/factory-kit/` + clean-scan (`scripts/governance/check-factory-kit-clean.py`: owner identity, host paths, secret-like filenames, symlinks, gitleaks). K3 = `init`/`doctor` via the existing installer (`scripts/ai/lib/factory_gate_install.py`) from the user's own clone, no signature verification.

Status: DESIGN v2 (architect, 2026-10-15). Supersedes v1 (`FACTORY-TEMPLATE-DESIGN.md`, kept) for sections 0, 2, 3, 5, 6, 7 and the slice plan; v1 section 1 (asset inventory table) and section 4 (blockers B1-B16) remain valid and are amended in section 0.3 / section 8 here. Review input: `FACTORY-TEMPLATE-DESIGN-REVIEW.md` (findings F1-F9). Citations `file:line` verified in worktree dec-s1 (base 447c6d3e) or in the read-only inspect clone `mcp-repo-inspect/` of MasterofNull/Mendocino-Coastal-Plants (HEAD 4eac7a2). `[UNVERIFIED]` = not confirmed.

v2.2 (2026-10-15, owner clarification): repo is PUBLIC; anonymous HTTPS fetch; each user's own identity; non-owner-consumer decision and Mendocino decision resolved (S1.1, S3.1, S5.1-5.2, S7 T18, S8).
v2.1 changelog (2026-10-15): resolves v2 review H1-H4, M1-M4, O1-O3 (`FACTORY-TEMPLATE-DESIGN-v2-REVIEW.md`): orphan kit commit tags, out-of-band signer anchor + rollback guard, hook router fix (B17 extended), checkable T17, K5 parity moved to 1.0.

## 0. Headline, what changed, B1-B16 amendments

**Headline.** Ship a *kit* from THIS repo as a pinned, SSH-signed git tag. `aq-factory` (python stdlib, runs without NixOS) fetches only the manifest-listed paths at that tag, verifies signature and tree digest, then applies via the existing `scripts/ai/lib/factory_gate_install.py` ops (preview/install/retrofit-*/status; op list verified at `:1118-1121`). Consumers become full-parity, all-lane (Claude, Codex, Gemini/Antigravity, local Qwen) environments that learn their OWN project; nothing project-specific or secret travels in the kit. v0.1 = `init` + `doctor` only (review MVP); v1.0 adds `retrofit` + `update` after the Mendocino retrofit passes.

### 0.1 What changed from v1
| v1 | v2 |
|---|---|
| Separate exported kit repo | Kit lives in this repo; release = signed annotated tag `kit/vX.Y.Z` (owner decision 1) |
| Denylist-ish "strip D content" | Exporter is allowlist-by-MANIFEST; consumer fetches only manifest paths (S1, S5) |
| Tree sha256 in lock | Signed tag on an ORPHAN kit commit (ssh signature, owner's GitHub SSH key) + tree digest; `allowed_signers` pinned in lock at init, TOFU shown to owner |
| Own 3-way merge | `git merge-file -p` for text; whole-file rules for JSON/YAML/hooks (S4) |
| `init --apply-ruleset` | Tool only PRINTS the `gh api` block; owner runs it (S5) |
| 10 slices, tier0 core refactor inside | MVP slices first; tier0 core refactor is dogfood phase 2 and split (S8) |
| Windows unaddressed | WSL-only, `doctor` detects native Windows and refuses |
| secrets/SOPS "excluded" | No secrets, SOPS, or private info in the kit at all; deployment supplies them at runtime (env/files outside repo) |

### 0.2 Review findings resolved (F1-F9)
F1 -> S2.3 exclusion table. F2 -> S1.3 + S5.1. F3 -> S4.1. F4 -> S6. F5 -> S4.2/4.3. F6 -> S5.2 (history risk now moot for a separate repo but replaced by in-repo tag-subtree risk: manifest allowlist + gitleaks on exported tree + canary; the tag points at this repo's history, so the consumer MUST NOT clone history, only fetch manifest paths). F7 -> S5.3. F8 -> citation fix: receipt/HARD_CHECK_PREFIXES is `factory_gate_install.py:36`, `HOOKS_PATH` is `:52` (reviewer-verified; not re-verified by me) and `.mcp.json:21` semgrep `/run/current-system` added to B1. F9 -> overturned by owner decision 1; the risk (private content reachable by a fetch) is bounded by an orphan kit commit (S1.1, S5.2), not by client-side filtering.

### 0.3 Amendments to v1 blockers (B1-B16 still valid unless noted)
- B1: also `.mcp.json:21`; kit `.mcp.json.tmpl` uses `command -v`; export scan fails on `/home/` or `/run/current-system`.
- B2: `{{OWNER_HANDLE}}` comes from the local user's own git/gh config at init (S3.1), written to consumer-owned `kit.toml`, never a maintainer default; test renders CODEOWNERS and asserts handle (review F6).
- B3, B4, B5: unchanged, prerequisites for kit v0.2+ (not v0.1; v0.1 ships the existing bundle gate set).
- B6: `doctor` iterates `git worktree list`, flags absolute `core.hooksPath`.
- B7: class C, never exported; unchanged.
- B9: gitleaks `extend.path` support [UNVERIFIED]; fallback = kit core file + generated merged config at init (no chaining reliance).
- B10: scans run against `git archive HEAD` extract (ci-merge-parity pattern).
- B11: now S5.3 (printed command, doctor verifies).
- B12/B13: B13 landing automation NOT in kit until bug list closed [UNVERIFIED unchanged].
- B14: rename collision `aq-factory` -> keep `aq-factory skill` subcommand (v1 D3 default).
- B15: kit `core-rules` canon block + `project-facts` slot per agent file; consumer fills slot (S2.2 pillar 1).
- B16: replaced by `aq-factory export --check` in S6 (refresh = regenerate, not hand-edit).
- NEW B17 (extended, v2 review H3): absolute local paths leak into committed artifacts. (a) Receipt: Mendocino `.factory/gate-install.json` stores `"target": "/home/hyperd/Documents/Mendocino Coastal Plants"`; store `.`. (b) Hook router: `router_script` writes `repo_root=<shlex.quote(str(target))>` and runs `${repo_root}/.git/hooks/<name>` (`factory_gate_install.py:666-668`, verified); fix = `repo_root="$(git rev-parse --show-toplevel)"` at runtime and hooks dir via `git rev-parse --git-common-dir`. (c) Verified in the Mendocino clone: its committed `.githooks/{pre-commit,commit-msg,pre-push}` already contain `/home/`. The router script also executes pre-existing `.git/hooks/<name>` first (undocumented foreign execution): document it, and reconcile with the docstring at `:6-8` (says existing hook configs are refused). K1 scope; export scan and `doctor` grep all `.githooks/*` and `.factory/**/hooks` for `/home/`.
- NEW B18: `CONFIGURATION_BLOCKED` when `gitleaks` absent (verified in the same receipt: `required_unconfigured: secret_scan ... gitleaks`). `doctor` must report this as actionable with the exact install hint, `init` must not claim ACTIVE.

## 1. Distribution model

### 1.1 Release (orphan kit commit)
- Source of truth: `templates/factory-kit/` in this repo (evolves from `templates/factory-gate-bundle/`, `bundle_version 1.0.0-ft1`). `KIT-MANIFEST.json` lists every shipped path (exact paths, no globs), class (A/B), parameters, and in 1.0+ `derived_from`.
- `aq-factory release --version X.Y.Z` (owner-run) builds, with a temp `GIT_INDEX_FILE`, a tree containing ONLY manifest paths, commits it as a parentless ORPHAN commit, and creates annotated tag `kit/vX.Y.Z` on that commit signed with `git -c gpg.format=ssh -c user.signingkey=<owner key> tag -s`. Tag message: tree digest, `KIT-MANIFEST.json` sha256, source commit sha (provenance only). The tag is pushed alone (`refs/tags/kit/vX.Y.Z`); a `git fetch --depth=1 <source> tag kit/vX.Y.Z` therefore transfers no objects outside the kit. Agents never tag.
- Landing a kit change follows the PR flow. `kit/*` tags must be protected from deletion/move server-side by a tag ruleset (printed `gh api` block, S5.3; review L3); `doctor` and `init`/`update` compare tag commit with lock/last-seen and exit 3 on a moved tag.
- **Access model (owner-binding, repo is PUBLIC):** consumers fetch the kit anonymously over HTTPS; no key, token, or account is needed and none is stored in the kit or lock. The orphan commit is kept for a minimal fetch (only kit objects, nothing else to download or trust). Invariant instead of a privacy rationale: this repo's public history must never contain plaintext secrets, enforced by the existing gitleaks and SOPS gates (secrets only as SOPS ciphertext, never plaintext). Each local user's identity, signing key and auth are their own (S3.1); nothing is standardized to the maintainer's accounts.

### 1.2 Fetch (consumer side, no clone of history)
`aq-factory` resolves the kit source from `kit.source` in `~/.config` or `--source <git url or local path>` (never hardcoded; no URL in this document). Steps: `git init` a temp dir outside the consumer repo; `git fetch --depth=1 <source> tag kit/vX.Y.Z` with hardening `-c transfer.fsckObjects=true -c core.hooksPath=/dev/null -c protocol.file.allow=user`, no submodules, size cap (review L1); verify (S1.3); then stage manifest paths via `git archive`. Belt and braces: the tag tree listing must equal the manifest (S1.3 step 4). The lock records the source only as a hash/redacted form (L2). Temp dir is tool-owned and removed by the tool.

### 1.3 Verification before apply (fail closed; any failure = nonzero exit, zero writes)
Tool builds its OWN temp `allowed_signers` from the lock (entry has `namespaces="git"` and `valid-before`), runs `git verify-tag --raw` / `ssh-keygen -Y` itself, and requires the exact signer fingerprint; it never trusts exit code 0 alone.
1. Signature valid for the pinned fingerprint.
2. Anchor (first `init`): tool prints principal + key fingerprint, and compares it out-of-band against the owner's GitHub SSH signing keys via `gh api` (`/users/<owner>/ssh_signing_keys`) or a fingerprint typed by the owner (`--signer-fingerprint SHA256:...`). Non-interactive: `--confirm <digest>` binds BOTH the file preview and the signer fingerprint (`sha256(preview_digest || fingerprint)`), so a swapped signer invalidates a scripted init. Mismatch = exit 3.
3. Rollback guard: lock stores `highest_verified_version`; a tag version < that is refused unless `--allow-downgrade "<reason>"` (reason recorded in lock). `minimum_version` in a signed tag message may raise the floor (revocation).
4. Tree: tag tree listing == `KIT-MANIFEST.json` paths exactly; tree digest == tag message; each file sha256 == manifest; no symlinks; modes only 0644/0755; no `/home/` or `/run/current-system` strings.
5. Rotation: only a tag signed by BOTH old and new keys (two-key overlap window; `allowed_signers` carries both until the next tag verified with the new key alone, then old is dropped). Compromised old key alone cannot rotate. Prompt-only `--rotate-signer` is removed.
Fail-closed list (each has a test, T6b): git missing or < 2.34, `ssh-keygen` missing, empty/malformed `allowed_signers`, bad signature, unknown signer, digest mismatch, tree/manifest mismatch, moved tag, network/fetch error, oversized fetch, tool error parsing verify output. There is NO unsigned mode in the shipped CLI; fixtures use a test-only signer key generated inside the test (O2).

### 1.4 `.factory/kit.lock` (committed, JSON)
`{schema, kit_version, tag, tag_commit, tree_digest, signer:{principal,fingerprint,allowed_signers_line}, params:{...}, files:{path:{sha256_rendered, sha256_base_template, class, disposition}}, applied_at}`. `base` for merges is re-derived from the kit at the locked tag (not stored), per review F3. `.factory/kit.lock` signer fields are protected: CODEOWNERS entry plus a gate check that signer fields change only in a commit carrying a rotation-tag provenance note (review M4). Params (project name, owner handle, protected branches, stack, plan root) live in `.factory/kit.toml` (consumer-owned); the lock stores the values used for the last render.

### 1.5 Overrides of the Gemini draft
Gemini's rollout DESIGN (`.agents/plans/software-dev-factory-rollout/DESIGN.md`) invokes everything via `aqd workflows ...` only. v2.1 keeps those as thin wrappers but the canonical entry is standalone `aq-factory`, since consumers lack the harness. v2 supersedes its sections 3-4 (no version pin, no signature, no update path). Kept: its 8-pillar framing (used in S2) and the greenfield/brownfield fixture tests (S7).

## 2. Kit contents by pillar

### 2.1 Layers
Core only in v0.1 (no `[layers]` switch until a second layer exists, O2). Planned optional layers: `host-nixos` (never default), `local-model`, `mcp-plugins`, `sandbox-linux`. A consumer on any OS-supported host gets Core.

### 2.2 Manifest by pillar (v1 inventory classes: A as-is, B parameterised)
| Pillar | Ships | Version |
|---|---|---|
| 1 Agent scaffolding | `AGENTS.md`, `CLAUDE.md`, `.agent/{CODEX,GEMINI,LOCAL-AGENT,WORKFLOW-CANON}.md` from `agent-scaffolding/*.tmpl`; kit `core-rules` canon block (generalised rules 1-3,6-12,16,19,20); consumer-owned `project-facts` slot; Rule-16 parity check | v0.1 (static tmpl), canon compile v0.3 |
| 2 Trunk + hooks | `.githooks/{pre-commit,commit-msg,pre-push}`, relative `core.hooksPath`; `{{PROTECTED_BRANCHES}}` | v0.1 |
| 3 Gate runner | `gate-runner`, `checks.d/{hard-10,20,30,40,50,80,live-60,freshness-70}`, stack adapters (python/node/rust/go/nix/generic), repo-structure-lint | v0.1 |
| 4 Security | gitleaks core config + empty local allowlist, `ci-gitleaks` parity script, time-boxed `security-exceptions.json` (empty), SHA-pin audit | v0.1 gitleaks+pin audit; exceptions v0.2 |
| 5 CI/CD | `factory-gate.yml`, `factory-cd.yml`, `review-disposition.yml` + `check-review-disposition.py`, PR template, CODEOWNERS (rendered), `ci-checks.base.json` + `run-ci-checks.sh`/`ci-merge-parity.sh`/`ci-clean-env.sh` engine | gate/review-disp v0.1; parity engine v0.2 |
| 6 PM tracker | `projector.py`, schema, `check-pm-tracker.sh` | v0.1 |
| 7 Memory/RSI | `.agent/memory/issues-backlog.md`, `WORKAROUND-REGISTER.md`, `collaboration/{PULSE.log,RESUME.json}` seeds, HANDOFF.md skeleton with schema check, `LESSONS-CORE.md` (hooksPath relativity, CI/local scan parity, stale deploy source, volatile /tmp), file-based attention-queue schema `attention.schema.json` | v0.1 seeds; lessons/schema v0.2 |
| 8 Tooling/skills | generic skill subset (brownfield, commit, create-prd, execute, plan-feature, prime, minimal-code, reviewer-gate, role-contracts, slice-authoring, debug-workflow, testing-patterns, finding-freshness) [per-skill portability UNVERIFIED], `.mcp.json.tmpl` (lean-ctx + semgrep only), `.claude/settings.json` repo-relative permissions, worktree helper (param dir) | skills v0.3; worktree v0.3 |
| Tests | kit self-test (`self-test.sh`), installer/gate-runner/resolve/projector tests, per-stack test scaffold command strings | v0.1 self-test |

### 2.3 Explicit exclusions and optional layers (review F1)
| Item | Decision | Reason |
|---|---|---|
| Secrets, SOPS (`secrets.nix`, `sops`), `deploy-options.local.nix`, tokens, keys, `FUNDING.yml`, owner identity | EXCLUDED, no layer | Owner decision 2: deployment supplies at runtime; export canary asserts absence |
| MCP plugin trust / `capability-intake` policy | Optional layer `mcp-plugins`: ships the intake skill + deny-by-default template; consumer's trusted list starts empty | A consumer MCP set is project-specific; trust policy generic |
| Local-model layer | Optional `local-model`: contract only (`LOCAL-AGENT.md`, env var names for endpoint/model, `enable_thinking:false` note as param), no ports, no model files | Parity for local Qwen lane without hardcoding this host; endpoints come from env/deployment |
| aqd workflow definitions | EXCLUDED from v0.x; `aq-factory` verbs replace them; `aqd workflows project-init|retrofit` become wrappers in THIS repo | Consumers lack aqd/coordinator |
| HANDOFF.md / RESUME.json | INCLUDED: schemas + `doctor` validation (v0.2) | Compaction anchor, Rule 8b |
| Notification contract | Schema + file queue only (`.agent/attention/*.json`); implementation not shipped | Delivery needs the coordinator (class C) |
| `aq-confine`, grype ignores, Nix closure scanning, sops-sync, deploy scripts, AppArmor | Optional `host-nixos` / `sandbox-linux`, off by default, v0.4+ | Class C |
| `test.yml`, `nix-build.yml`, harness-specific workflows, `ai-stack/`, dashboard, domain plans/evidence | EXCLUDED | Class D |
| Landing automation (`check-mergeable.sh`) | EXCLUDED until bug list closed (B13) | UNVERIFIED stability |
| Project knowledge (RAG data, lessons from consumer's history, project-facts) | Never in kit; created in consumer by `learn` (S3, v0.3) | Owner decision 3 |

## 3. CLI verbs and contracts

Common: `aq-factory <verb> [--repo <path>=.] [--source <git>] [--version <tag>] [--json] [--dry-run]`. Python stdlib only. Exit codes: 0 ok, 1 findings/blocked, 2 usage, 3 verification failure, 4 dirty or unsupported environment. Never prompts when `--json` or non-tty unless confirmation is required (TOFU, retrofit digest), then exits 4 with the exact command to rerun with `--confirm <digest>`. Writes only inside `--repo`; no network except the one fetch (S1.2); never touches git remotes, GitHub, or `sudo`.

### 3.1 `init` (v0.1; greenfield or an empty/clean repo)
Preconditions: git repo, clean tree, no `.factory/kit.lock`, not native Windows, `git` >= 2.34 (ssh signature verification; per review). Flow: fetch+verify (S1.3) -> **identity step**: read the local user's own `git config user.name/user.email`, optional signing key (`user.signingkey`, `gpg.format`), and `gh auth status` (read-only; SKIP if gh absent); if user.name/email are unset, exit 4 with the exact `git config` commands (never a maintainer or default identity); derive `{{OWNER_HANDLE}}` from `gh` login or an explicit `--owner-handle`, else exit 4; signing key and auth are optional, only reported, never copied; values go to consumer-owned `kit.toml` only -> detect stack (existing `resolve.py`) -> `preview` (installer, shows paths + preview_digest) -> `--confirm <digest>` (binds signer, S1.3) -> installer `install` -> write `kit.lock`/`kit.toml` -> set relative `core.hooksPath` -> print owner block (ruleset `gh api` command, S5.3, plus install hints for missing tools like gitleaks, B18). Does not commit; it leaves a staged change set and prints the suggested commit. Idempotent: rerun on a locked repo is a no-op that exits 0 with `status`.

### 3.2 `doctor` (v0.1; read-only, always safe; asserted by test: clean `git status`, no mtime change)
Checks, each OK/WARN/FAIL/SKIP with a fix string (ruleset and moved-tag checks may be SKIP-only stubs in v0.1, O3): lock present and well-formed; tag/tree digests vs fetched or cached kit (SKIP offline); every managed file's sha256 vs lock (drift = WARN, listing `overrides`); hooks active (relative path in all `git worktree list` entries); required tools on PATH (gitleaks, python3, stack tools); foreign hook managers (S4.2); Windows native; review-disposition ruleset present via `gh api` (SKIP without token); receipt AND all hook files contain no `/home/` (B17); HANDOFF/RESUME schema (v0.2). Never modifies anything; exit 1 on FAIL.

### 3.3 `retrofit` (v1.0, existing repo)
Superset of init: refuses dirty tree; requires `--confirm <preview_digest>`; installer `retrofit-preview/-install` with lossless backups under `.factory/gate-backups/<digest>/` (already the installer's behavior, evidenced in the Mendocino receipt); existing non-factory files are never overwritten: collision -> side-by-side `*.kit-proposed` and a report. Foreign hook manager -> refuse (S4.2).

### 3.4 `update` (v1.0)
`update --to <tag>`: fetch+verify; per file three-way (S4.1); `--dry-run` prints the plan; conflicts leave conflict markers only in files the consumer already owned (text) and `.kit-proposed` for non-text, exit 1; never half-applies (staged into temp worktree copy, then moved in one pass; on any error restore from backup dir).

### 3.5 Later (not designed here)
`learn` (v0.3: generate project-facts, stack commands, seed memory files from consumer repo only), `export`/`release` (kit-maintainer, in this repo only), `skill` (existing behavior of old `aq-factory`).

## 4. Update, merging, foreign hooks, platforms

### 4.1 Three-way merge (F3)
- Text files, class B-parameterised or A: `git merge-file -p <current> <base> <theirs>` where `base` = file rendered from the lock's `tag` with the lock's `params`, `theirs` = new tag rendered with the (possibly changed) params from `kit.toml`. Re-rendering the base with the lock's params is mandatory, else every parameterised file looks modified. If `sha256(current)==lock.sha256_rendered` -> fast-forward replace (no merge). If `sha256(theirs)==sha256(base)` -> keep current.
- Never textually merged: any `*.json`, `*.yml`/`*.yaml` (workflows, `KIT-MANIFEST`, `ci-checks.base.json`), hooks, and `gate-runner`. Rule: if unmodified by consumer -> replace; if modified -> write `<path>.kit-proposed`, report, keep consumer file. Consumer-owned files (`kit.toml`, `project-facts` slot in agent files, `.gitleaks.local.toml`, `ci-checks.json`) are never touched; the project-facts slot is delimited by markers the merge treats as consumer territory.
- Consumer-declared divergence: `kit.toml [overrides]` list `{path, reason}`; update skips those and reports.
- Safety (review M2): before merging, re-render the base from the old tag and require its sha256 == `lock.sha256_rendered`; if not equal, or the old tag is unfetchable, treat as modified-unknown -> `.kit-proposed`, never merge. Map `git merge-file` exit explicitly (0 clean, 1..127 = conflict count, >127 error); write to temp then move, never in place. If the consumer deleted or edited a slot marker, treat the whole file as consumer-modified (proposed only). Gate/`doctor` FAIL on `<<<<<<<` in managed files and WARN on stale `*.kit-proposed`. Modes (0755) and `.gitattributes` changes are compared from the manifest, not merged.
- Atomicity: write a journal in the backup dir first, then move files; `doctor` refuses while a journal is incomplete until `update --rollback`. Update is its own commit; its gate runs from the pre-update HEAD copy (M5).
- Rollback: pre-update `.factory/gate-backups/<ts>/`; `update --rollback` restores.

### 4.2 Foreign hook managers (F5): v1 behavior = REFUSE
Detect in `init`/`retrofit`/`doctor` (review M3): husky (`.husky/`, `package.json` husky/`prepare`/`simple-git-hooks`/`lint-staged`), pre-commit.com (`.pre-commit-config.y{a,}ml`), lefthook (`lefthook.y{a,}ml`, `.lefthook.y{a,}ml`, `.config/lefthook*`), overcommit; `git config --show-origin --get-all core.hooksPath` (covers global/system/per-worktree) not equal to `.githooks`/unset; non-sample files in the hooks dir from `git rev-parse --git-common-dir`. Result: exit 4 with exact manual steps printed, e.g. "add `.githooks/commit-msg` and `.githooks/pre-commit` as steps in your tool's config; run `<tool> install`; then `aq-factory doctor`". Composition (installer's router_script, `factory_gate_install.py:666`, which routes pre-existing hooks before factory hooks) is used ONLY when the existing hooks live in `.githooks` and are plain scripts. Composing with foreign managers is a v1.x item after proven.
### 4.3 Windows: WSL-only
Native Windows (`sys.platform=="win32"`) -> `init/retrofit/update` exit 4 with "use WSL"; `doctor` runs the detection only. Reasons: bash hooks, symlinks, CRLF. Kit ships `.gitattributes` forcing `eol=lf` for hooks/scripts. macOS and Linux supported [macOS UNVERIFIED in tests].

## 5. Security

### 5.1 Supply chain (F2, H2)
Mechanics in S1.3. Tag signing is PROVENANCE ONLY: kit tags are signed by the kit maintainer; consumers verify with the maintainer's PUBLIC key shipped in `allowed_signers` (fingerprint anchored out-of-band, S1.3). No consumer credential is involved and nothing is shared: consumers never sign, never authenticate to the maintainer, and their own git identity/keys remain theirs. Maintainer signing key = existing GitHub SSH key (recorded: allowed_signers line uses `namespaces="git"` and `valid-before`); the private key never enters the repo or CI. Replaces v1's "CI rejects commits not signed by the exporter". Tests T6-T9, T6b.

### 5.2 Export hygiene (F6, decision 1 history risk)
- Exporter is allowlist-by-`KIT-MANIFEST.json` and builds an orphan commit (S1.1); no directory globs; a file in the tree but not in the manifest is simply not shipped. A manifest path that matches a deny-pattern (`secrets`, `sops`, `.env*`, `*.local.nix`, `id_*`, `*.pem`, `/home/`, `/run/current-system` content) fails the release.
- Release gates: gitleaks on the staged exported tree with the allowlist DISABLED (zero-allowlist config); path/content scan for owner identity strings; render CODEOWNERS test; canary test (S7 T4): plant `secrets.nix`, a SOPS-looking file, and `deploy-options.local.nix` in the source tree; assert none appear in the staged tree; plus a negative case where a manifest entry points at a planted file (release must fail).
- The tag fetch yields only kit objects (orphan, parentless): minimal download and trust surface. Public-history invariant: no plaintext secret ever lands in this repo's public history (gitleaks + SOPS gates, release gates above). Pre-existing public history is not rewritten by this design.
- Consumer receipt/lock contain no absolute paths or usernames (B17), asserted by `doctor`.

### 5.3 Branch protection / ruleset (F7): printed, never applied
`init` and `doctor` print a copy-paste block: a generated `ruleset.json` and a `gh api` command requiring the `review-disposition` and `factory-gate` checks, review count, no force-push on protected branches. The tool never calls GitHub write endpoints and never reads tokens. `doctor` verifies read-only with `gh api` when authenticated; otherwise SKIP with the instruction. The commit-msg hook remains cooperative; the server-side workflow is the enforcement.

### 5.4 Other
No network at hook time. Hooks and `gate-runner` never execute stack commands from consumer-controlled data without the installer's existing metadata-only detection (documented at `factory_gate_install.py:6-8` per v1). SHA-pin audit for workflows ships in v0.1 (`ci_policy.py`). Kit CI in this repo runs gitleaks and the export gates on every PR touching `templates/factory-kit/`.

## 6. Dogfood and kit-parity (F4; O1)

**v0.1:** the kit tree is the source and is not derived, so there is no `derived_from`/override machinery. The only parity guard is a one-line CI check in this repo: `aq-factory release --dry-run` output digests equal the committed `KIT-MANIFEST.json` digests.

**1.0 (K11):** this repo consumes its own kit (Core + host-nixos) and `check-kit-parity` (tier0.d) is added: reads `derived_from`; fast path exits 0 in constant time when no staged path intersects the union of sources or the kit tree; otherwise renders only affected files with a hash cache; divergence outside `kit.toml [overrides]` (`path`,`reason`,`expires`) fails with the refresh command; declared overrides are reported, expired ones fail. WARN-only for one cycle, HARD only after measuring p95 against a budget [UNVERIFIED, set after measurement]. Freshness/expiry signals are WARN in pre-commit and HARD in `--maintenance` (Rule 19 corollary). The tier0 core refactor (B4) is later, separate slices.
Absorbed from Gemini's draft: self-test and greenfield/brownfield fixtures (S7 T1-T3).

## 7. Acceptance tests

Each is a command + expected result, evidence pasted into `docs/harness-first/evidence/<date>-factory-kit.md`.
- T1 Self-test: kit `self-test.sh` exits 0 in a clean env (`ci-clean-env.sh`).
- T2 Greenfield fixture: temp git repo (python stack), `aq-factory init --source <local test remote> --confirm <digest>`; assert hooks active, direct commit to `main` without Review-Disposition is blocked by `commit-msg`, a compliant commit passes, `kit.lock` present.
- T3 Idempotency: second `init` and `doctor` after `init` produce zero diff and exit 0 (init) / 0 (doctor with only declared WARNs).
- T4b Tag content: fetch the tag into an empty repo; `git rev-list --all` shows exactly one commit with zero parents; tree listing == manifest; zero-allowlist gitleaks exits 0; canary blobs (`secrets.nix` etc.) absent; no `refs/delegate-base/*` objects.
- T4 Export canary: plant `secrets.nix`, a SOPS-style file, `deploy-options.local.nix`, `/home/x` string in source; release build excludes the files and fails when a planted string reaches a manifest path.
- T5 Gitleaks: zero-allowlist gitleaks on the exported tree exits 0; with an injected fake key in a manifest file, it exits non-zero.
- T6b Fail-closed matrix: for each item of the S1.3 list (stub missing `ssh-keygen`/old git via PATH shim, empty allowed_signers, wrong fingerprint, fetch failure), `init` exits nonzero and `git status` + file mtimes are unchanged. Also: scripted `init --confirm <digest>` with a swapped signer fails; downgrade without `--allow-downgrade` fails.
- T6 Tampered tag: modify tag object or sign with a different key -> `init` exit 3, no writes (`git status` unchanged).
- T7 Tampered tree: change one byte of a shipped file in the fetched staging -> exit 3.
- T8 Moved tag: lock commit != remote tag commit -> `doctor` FAIL and `init`/`update` exit 3.
- T9 Test fixtures sign with a test-only generated key; assert the shipped CLI has no unsigned/`--insecure` option.
- T10 Ruleset: `init` output contains the `gh api` block and makes no network write (assert via no GitHub token and call trace); `doctor` SKIPs without token. Method: fake `gh` shim on PATH that fails on any non-GET verb; assert it was never called with a write verb.
- T11 Windows/foreign managers: fixtures with `.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`, absolute hooksPath each exit 4 with the manual steps; sys.platform patched to win32 exits 4.
- T12 Dirty tree: `init/retrofit` on a dirty tree exit 4.
- T13 Update merge (v1.0): modify a text file locally, bump kit, `update` yields a clean `git merge-file` merge; with conflicting change leaves markers and exit 1; JSON/workflow modified locally -> `.kit-proposed`; parameterised file unmodified at old params + changed param renders cleanly (no false drift).
- T14 Kit-parity: edit a `derived_from` source without refreshing kit -> check fails; edit unrelated file -> check exits 0 without rendering (assert via counter); declared override reported; expired override fails.
- T15 Paths: `grep -rE '/home/|/Users/' ` over `.factory/` (lock, receipt, retrofit hooks) and every `.githooks/*` of the result is empty, EXCEPT consumer-authored hook files flagged in the retrofit report; clone the result to a second path and a commit there runs the hooks successfully (router uses `git rev-parse --show-toplevel`).
- T12b `doctor` read-only: `git status --porcelain` empty and `find -newer` shows no modified files after a run.
- T16 Attention queue: file written matching `attention.schema.json`; invalid file rejected (v0.2).
- T18 No maintainer identity: render a consumer repo with a test identity (`Test User <test@example.invalid>`, handle `testuser`); `grep -rEi` over the whole result for the maintainer handle, maintainer email/name, `hyperd`, `MasterofNull` is empty (CODEOWNERS shows `@testuser`); `init` with unset `user.email` exits 4 and writes nothing; no ssh key or token material appears in `.factory/` or `kit.toml`.
- **T17 Mendocino retrofit E2E (v1.0 acceptance; K7).** Subject: fresh clone of MasterofNull/Mendocino-Coastal-Plants in a worktree. Step 0 baseline (recorded in the evidence doc, re-captured, not assumed): commit SHA (inspect clone was HEAD 4eac7a2), `python3 -m unittest discover -s tests -p 'test_*.py' -v` result and test count (inspect clone: 1 test file, 5 `def test`), `npm run build` and `npm run lint` exit codes, `git ls-files` list, `git ls-files .githooks` (inspect clone: `commit-msg`, `pre-commit`, `pre-push`, all already containing `/home/`), `.factory/gate-install.json` state (inspect clone: ACTIVATION_BLOCKED / CONFIGURATION_BLOCKED: gitleaks, live-service, freshness), no `.github/`. Pass criteria, each a command:
 (a) `doctor` before retrofit prints each baseline blocker with a fix string, exit 1.
 (b) After `retrofit --confirm <digest>`: `git diff --name-status <baseline>` lists only paths in `KIT-MANIFEST.json` plus an explicit allowlist of consumer files changed by hook composition (expected: `.githooks/pre-commit`, `.githooks/commit-msg`, `.githooks/pre-push`); every other consumer-owned file (`src/`, `scripts/*.py`, `tests/`, `package*.json`, `data/`, `public/`) has an empty diff; backups exist under `.factory/gate-backups/<digest>/` and restore byte-identically (`update --rollback` then `git diff` empty).
 (c) With gitleaks installed, `doctor` has zero FAIL; SKIPs are only ruleset/token.
 (d) Post-retrofit `unittest` run: same exit code and same test count as baseline (5 in the inspect clone); `npm run build` and `npm run lint` exit codes equal baseline; gate-runner `--pre-commit` exits 0.
 (e) Leakage: `grep -rEi 'qwen|nixos|hyperd|aq-resume|aqd|llama|sops|/home/' ` over all newly added or modified files excluding consumer-authored hook bodies returns nothing; `local-model` layer is OFF for Mendocino, so `LOCAL-AGENT.md` ships only as the generic lane stub (asserted by file contents containing no endpoint/model strings). `project-facts` slots contain only Mendocino terms (stack, `npm run` commands) from `learn`/manual fill.
 (f) A staged fake secret and a commit lacking Review-Disposition to `main` are each blocked (nonzero hook exit).
 (g) Second `retrofit`/`update --to <same tag>` produces an empty diff.
 Nothing is pushed by the test.

## 8. Slice plan, MVP, owner decisions

Each slice: bounded, one concern, cheapest eligible implementer (Rule 17: Codex or local Qwen first when eligible, else `sonnet`; `haiku` only for mechanical single-file edits). Independent reviewer is a different lane (Rule 18). Orchestrator does not self-implement. S1-S3 and S4 touch the installer/MANIFEST, so they are sequenced, not parallel.

| Slice | Scope | Deps | Implementer | Release |
|---|---|---|---|---|
| K1 | Blockers: B1 (+`.mcp.json:21`), B2 param, B5 optional aq-* calls, B17 (receipt relative + hook router `git rev-parse --show-toplevel`, reconcile `:6-8` doc), B18 doctor hint; commit-msg behavior matrix test | none | sonnet (multi-file) | pre-0.1 |
| K2 | `templates/factory-kit/` + `KIT-MANIFEST.json` (allowlist), `release` building the ORPHAN commit, gitleaks/canary gates, T4/T4b, signed tag | K1 | sonnet; reviewer different lane | 0.1 |
| K3 | `aq-factory` standalone: hardened fetch, verify (S1.3), lock, `init`, `doctor` (read-only), T6/T6b/T7-T10/T12b/T15 | K2 | sonnet | 0.1 = MVP |
| K4 | Kit CI in this repo (T1-T5, release dry-run digest check), `review-disposition.yml`, gate workflow in kit, SHA-pin audit | K2 | haiku for mechanical copy, sonnet for CI wiring | 0.1 |
| K6 | `retrofit` (+ foreign-hook refusal, dirty-tree, Windows) | K3 | sonnet | 0.2 |
| K7 | Mendocino retrofit E2E T17 on worktree; fix findings (Rule 19) | K6 | sonnet, reviewer separate | 0.2 |
| K8 | `update` with `git merge-file`, rollback, T13 | K6, K7 | sonnet | 1.0 |
| K9 | Parity engine (B3 split), exceptions, LESSONS-CORE, HANDOFF/RESUME schemas, attention schema | K3 | sonnet | 0.3 |
| K10 | Canon compile for kit core-rules (B15), skills subset, worktree helper, `learn` | K9 | sonnet; Qwen for bounded doc slices | 0.3-0.4 |
| K11 | `check-kit-parity` (WARN one cycle, then measured HARD) + dogfood phase 2: tier0 core refactor split (B4) into separate PRs | K8 | sonnet | 1.0 |
| K12 | Optional layers (host-nixos, sandbox-linux, mcp-plugins, local-model) | K10 | sonnet | 0.4+ |

**MVP = v0.1 (K1-K4): init + doctor, signed, anonymous public fetch.** v1.0 only after K7 passes T17. Each slice carries the Rule 15 attestation (integrated/on/validated/observable/intervenable/PM-tracked) and a `tracker.json` entry.

### Remaining owner decisions
1. Owner key: confirm the existing GitHub SSH key signs kit tags and accept the out-of-band anchor flow (S1.3) before K2's first release.
2. RESOLVED (owner 2026-10-15): repo is public; anonymous fetch; no non-owner restriction.
3. RESOLVED (owner 2026-10-15): Mendocino-Coastal-Plants is the owner's own private project, retrofitted on the owner's machine with the owner's local auth as a dogfood; nothing from it enters the kit and it is never shared or shipped.
4. Tag ruleset for `kit/*` on this repo: owner runs the printed `gh api` block.
Defaults taken (change on request): D3 keep `aq-factory skill`; D4 python+node stacks first; Windows WSL-only.
