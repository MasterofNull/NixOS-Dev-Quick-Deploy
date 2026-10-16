# FACTORY-TEMPLATE-DESIGN-v2 independent adversarial review (read-only)

Subject: FACTORY-TEMPLATE-DESIGN-v2.md
Subject sha256: e7add88595720af0b17e9eb5fa732bbd0a8ef7a82496d5ef9e948d32cf801530

## Overall verdict: PLAN_READY_WITH_FOLLOWUPS (K1, K2, K4 can proceed; K3 and the T17 claims are gated on H1-H4 below)

| Slice group | Verdict |
|---|---|
| K1 blockers | PLAN_READY_WITH_FOLLOWUPS (add H3: absolute path baked in hook router) |
| K2 kit tree, exporter, signed tag | NOT_READY until H1 (tag must point at an orphan kit commit) and H2 (signer root) are decided |
| K3 fetch/verify/init/doctor | NOT_READY as written; private-repo read access (H1b) is an unanswered blocker for any non-owner-machine use; fine for owner-local with ambient ssh/gh auth if stated |
| K4 kit CI, T1-T5 | PLAN_READY_WITH_FOLLOWUPS (M1) |
| K5 parity WARN | PLAN_READY_WITH_FOLLOWUPS; candidate to CUT from v0.1 (O1) |
| K6-K8 retrofit/update | PLAN_READY_WITH_FOLLOWUPS (H4, M2-M5); not MVP, fine |
| K9-K12 | PLAN_READY |

## F1-F9 resolution check
- F1 (completeness): RESOLVED. S2.3 table names each item with a decision.
- F2 (supply chain): PARTIAL. Signed tag + TOFU + tests T6-T9 exist, but trust root, rollback, and non-interactive TOFU are underspecified (H2).
- F3 (3-way): RESOLVED in design (merge-file, re-render base with lock params); gaps in M2.
- F4 (parity brittleness): RESOLVED (fast path, overrides w/ expiry, WARN cycle). Still overbuilt for v0.1 (O1).
- F5 (foreign hooks): RESOLVED for refusal; detection list incomplete (M3).
- F6 (secrets): RESOLVED (allowlist manifest, canary, zero-allowlist gitleaks), but only as good as H1.
- F7 (ruleset): RESOLVED (print only).
- F8 (citations): RESOLVED; verified below.
- F9 (history risk): NOT RESOLVED, only reasoned away. See H1.

## Findings

H1 (HIGH) F9 and private-repo access are not solved; "fetches only manifest paths" is a client-side promise, not a control.
 - `git fetch --depth=1 <source> tag kit/vX.Y.Z` (S1.2) transfers the full tree of the tagged commit, i.e. the whole repo at that commit: `.sops.yaml`, `nix/modules/core/secrets.nix`, `scripts/governance/tier0.d/check-sops-sync.sh`, `lib/l1-infra/secrets-sops.sh`, all plans/evidence (33 tracked secret/sops-named files today). The manifest filter runs after objects are already in the consumer's temp repo; `git show <tag>:<any path>` or a plain `git fetch` of any other ref obtains everything. Depth-1 limits history of that ref only; the same read credential also lists all 149 `refs/delegate-base/*` and all branches. So any consumer holding read access to the repo can read all private content and history. The design's "history never materialised" is false for the credential holder and only true for the tool's default behaviour.
 - Private-repo read access (S5.2 "Residual risk", Remaining decision 2) is deferred, yet K3 cannot fetch without it. For owner-only repos using ambient ssh/gh auth it works with no secret in the kit; for anything else it is a real blocker (a read token scoped to this repo grants the whole repo).
 - Fix (pick all): (a) the release tag MUST point at an orphan commit containing only the manifest tree (built by `aq-factory release`, pushed as `refs/tags/kit/vX.Y.Z` with no parents), so a tag fetch yields no private objects; the tag message still carries source commit sha for provenance. (b) State explicitly: this bounds what the TAG exposes, not what a read credential exposes; consumers must be only the owner's own repos until the kit is published in a public location (release asset or public mirror). (c) Add test T4b: fetch the tag into an empty repo, `git rev-list --all --objects` contains only manifest paths and zero parents; assert no `secrets.nix` blob. (d) Make "owner-local ambient auth only" the explicit MVP access model in K3.

H2 (HIGH) Signature trust root is soft; failure modes partly fail-open.
 - TOFU "confirm in prompt" has no out-of-band anchor. Fix: anchor on the owner's published keys (github.com/<owner>.keys fingerprint, or a fingerprint recorded in README of the kit) and display it; non-interactive path `--confirm <digest>` must bind the signer fingerprint into the confirmed digest (currently it binds only the file preview), else a swapped signer passes a scripted init.
 - `update --to <older tag>` is unconstrained: no monotonic version/rollback guard. Fix: refuse a downgrade unless `--allow-downgrade`; lock stores highest verified version.
 - `--rotate-signer` is only a prompt. A compromised old key can sign a "rotation". Fix: rotation tag must be signed by BOTH old and new keys (or by an owner-recorded offline root); document revocation = new allowed_signers + minimum_version.
 - Using the GitHub auth key as signing key couples signing to the daily-use key in an agent. Accept, but record; require `namespaces="git"` in allowed_signers line and `valid-before` expiry.
 - Moved-tag detection lives only in `doctor` and SKIPs offline; `update` and `init` must themselves compare tag commit to lock/last-seen and exit 3.
 - Fail-closed is asserted (exit 3, no writes) but not specified for: missing/old git (<2.34 ssh verify), missing ssh-keygen, empty allowed_signers file, `git verify-tag` exit 0 with "no principal matched" variants. Fix: tool generates its own temp allowed_signers from the lock, parses `git verify-tag --raw`/`ssh-keygen -Y` output, requires the exact fingerprint, treats any tool error as failure; add T6b for each.
 - `--insecure-allow-unsigned` blocked only when `CI` is set; env-var gating is bypassable (`env -u CI`). Fix: remove it from the shipped CLI; fixtures use a test-only signer key generated in the test.

H3 (HIGH) Hook router bakes an absolute path; T15 does not catch it.
 - `factory_gate_install.py:666-668` writes `repo_root=<shlex.quote(str(target))>` into the router hook, and the router also calls `.git/hooks/<name>` via that path. A retrofit with pre-existing `.githooks` scripts (Mendocino has `.githooks/pre-push`, per design) commits a hook containing `/home/<user>/...`: leaks username (violates the no-private-info decision), breaks every other clone/worktree (the hook cds to a path that does not exist, or worse runs the hooks of a different checkout). B6 only checks `core.hooksPath`; B17 only the receipt.
 - Fix: router must compute `repo_root="$(git rev-parse --show-toplevel)"`; add to K1; extend T15 and the export scan to hook files; `doctor` greps all `.githooks/*` for `/home/`.

H4 (HIGH) T17 as stated is not currently checkable, and its starting state is unverified here.
 - `mcp-repo-inspect/` does not exist under the repo or within depth 6 of `/` on this host, so the claims about the Mendocino clone (receipt contents, `.githooks/pre-push`, no `.github/`, HEAD 4eac7a2) could not be re-verified by me; they are `[UNVERIFIED]` for this review. If the inspect clone was in a deleted worktree, T17's "known state" must be re-captured into the evidence doc before K7.
 - Pass criterion (d) "npm run test count unchanged" has no baseline procedure; (e) grep for "no NixOS/Qwen strings" needs a fixed deny-list and must also cover AGENTS.md/LOCAL-AGENT.md tmpl text (LOCAL-AGENT.md itself implies Qwen: define whether the local-model layer is off for Mendocino).
 - (b) "git diff --stat shows only kit paths" conflicts with retrofit modifying `.githooks/pre-push` (consumer's own file). Define it as: consumer files changed only by the documented hook composition, listed explicitly.
 - Fix: K7 begins with a recorded baseline step (fresh clone, SHA, test count, build result) in the evidence doc.

M1 (MED) T-tests missing for the MVP's main risks: no test for H1 (tag content), no test that `init` produces a hook set free of absolute paths, no test that `doctor` is truly read-only (assert clean `git status` + no file mtime change), no T for non-interactive `--confirm` with signer binding. T8 "moved tag" is only a `doctor` test; add an `init`/`update` variant.

M2 (MED) 3-way merge holes.
 - Base re-render requires the old tag's template AND renderer. Which renderer runs, the new tool's or the old tag's? If the tool changed render semantics, base != what the consumer got. Fix: store per-file `sha256_rendered` (done) and verify the re-rendered base hashes to it before merging; if not equal, treat file as modified-unknown -> `.kit-proposed`, never merge. Also fail closed if the old tag is not fetchable (deleted/lost access): fall back to `.kit-proposed`.
 - `git merge-file` exit code = conflict count (capped 127), >127 is error; design says "exit 1". Fix: map explicitly; write result to temp and move, never in place.
 - Committed conflict markers: after a conflicted `update`, nothing prevents committing markers. Fix: kit tier0/gate check refuses `<<<<<<<` in managed files; `doctor` FAIL.
 - Mode bits (0755) and CRLF/`.gitattributes` changes not handled in merge; `.kit-proposed` files themselves need ignoring/ cleanup rules and a `doctor` WARN when stale.
 - Consumer-owned slot markers inside agent files: if the consumer deletes or edits a marker, the merge can overwrite their facts. Fix: no markers -> treat file as fully consumer-modified (proposed only).
 - "Never half-applies ... restore from backup" lacks an atomicity claim for the multi-file move (a crash mid-move). Fix: write a journal in the backup dir first; `doctor` detects an incomplete journal and refuses until `update --rollback`.

M3 (MED) Hook-manager detection incomplete and bypass-prone: missing `.lefthook.yml`/`lefthook.yaml`/`.config/lefthook*`, `.pre-commit-config.yml`, overcommit, `simple-git-hooks`/`lint-staged` keys in package.json, `core.hooksPath` set in global/system git config or per-worktree (`git config --worktree`), `.git/hooks` located via `git rev-parse --git-common-dir` (not `.git/hooks`). Use `git config --show-origin --get-all core.hooksPath`. The docstring at `factory_gate_install.py:6-8` says existing hook configurations are "refused" while v2 composes plain `.githooks` scripts; reconcile (also the router executes `.git/hooks/<name>` first, undocumented foreign-hook execution).

M4 (MED) Lock integrity: `.factory/kit.lock` is committed and holds `allowed_signers_line`; a PR that edits the lock changes the trust root silently. Fix: CODEOWNERS entry for `.factory/kit.lock` and a gate check that signer fields change only with `--rotate-signer` provenance (or require review-disposition note).

M5 (MED) Fast-forward rule `sha256(current)==lock.sha256_rendered -> replace` and "theirs == base -> keep current" are right, but a gate/checks.d file replaced while a commit is in flight can alter the gate that judges the update itself. Fix: update is its own commit; gate for that commit runs from the pre-update HEAD copy (note only).

L1 (LOW) `git init` temp dir outside consumer repo + `git fetch` from a user-provided `--source` can be a local path or hostile remote: set `protocol.file.allow`, `-c transfer.fsckObjects=true`, `-c core.hooksPath=/dev/null`, no submodules, no `uploadpack` options, size cap. Add to S1.2.
L2 (LOW) `kit.source` in `~/.config` contradicts "never prompts, stdlib only" ergonomics; fine, but the lock should record the source URL only as a hash or redacted (may contain tokens).
L3 (LOW) Tag naming `kit/vX.Y.Z` in this repo: confirm tag-ruleset on this repo protects `kit/*` from deletion/move (server-side), since "immutable by convention" is the only guard. Printed `gh api` block should cover this repo too.

## Signature verification checklist
Trust root: partial (H2). TOFU: present, no out-of-band anchor. Rotation: weak. Rollback: absent. Fail-closed: stated for the main paths, not for tool/environment errors; `--insecure-allow-unsigned` is env-gated only. Verdict: needs H2 changes before K3.

## Acceptance tests T1-T17
Checkable as commands: T1, T2, T3, T5, T6, T7, T9 (replace with test-only signer), T10, T11, T12, T13, T14, T15 (extend to hooks). Weak: T4 (planted file detection depends on manifest never including it; add a negative where a manifest entry points at it), T8 (doctor only), T10 ("call trace" mechanism unspecified; use no-network sandbox or a fake `gh` shim that fails on write verbs), T16 (v0.2). T17: see H4. Missing: tag-content test (H1), hook absolute-path test (H3).

## MVP slice set K1-K5
Shippable and safe on its own only after H1 and H3. Safety properties that hold: init writes only inside the repo, leaves changes staged, prints (never applies) ruleset, refuses unsigned. K5 is not needed for a consumer MVP (O1). K4's CI is fine. Order: K1->K2->K3 and K4 parallel after K2 is sound; K1 and K2/K3 both touch the installer/MANIFEST, correctly sequenced.

## Overbuild vs minimal-code ladder
O1 Cut `check-kit-parity` (K5) and `derived_from`/override machinery from v0.1. It guards the owner's dogfood drift, not any consumer, and needs render caching, expiry, and a p95 budget not yet measured. Replace in v0.1 with a one-line CI check: `aq-factory release --dry-run` output digest equals committed `KIT-MANIFEST.json` digests (kit tree is the source, not derived). Revisit K5 after one cycle.
O2 Cut `--insecure-allow-unsigned` (H2) and `init` support for `kit.toml [layers]` switches until a second layer exists; v0.1 ships Core only.
O3 `doctor` ruleset check via `gh api` and moved-tag checks can be SKIP-only stubs in v0.1; the printed block is enough.
O4 Pillars 5-8 content at v0.1 (parity engine, lessons) is already deferred; good. Keep `ci-merge-parity` out.
O5 Keep: manifest allowlist, signed tag + digest, init, doctor, K1 blockers. Do not cut.

## Citation spot-check (8 of v2's citations, against HEAD)
1. `factory_gate_install.py:1118-1121` op list: actual `choices=(...)` at 1120-1121 (list spans 1120+). VERIFIED (off by two lines at start).
2. `factory_gate_install.py:666` router_script: VERIFIED (def at 666).
3. `factory_gate_install.py:36` HARD_CHECK_PREFIXES: VERIFIED (design says "receipt/HARD_CHECK_PREFIXES"; only the latter is at :36; wording slightly misleading).
4. `factory_gate_install.py:52` HOOKS_PATH = ".githooks": VERIFIED.
5. `factory_gate_install.py:6-8` metadata-only: VERIFIED (docstring lines 5-8; also says existing hook configs are refused: contradiction with composition, see M3).
6. `.mcp.json:21` `/run/current-system/sw/bin/semgrep`: VERIFIED.
7. `templates/factory-gate-bundle/MANIFEST.json` `bundle_version 1.0.0-ft1` (line 2): VERIFIED.
8. Mendocino clone claims (`.factory/gate-install.json` target path, CONFIGURATION_BLOCKED, HEAD 4eac7a2, `.githooks/pre-push`, no `.github/`): UNVERIFIABLE, `mcp-repo-inspect/` absent on this host.
Additional: `.githooks/commit-msg` main|master case at lines 6-9: VERIFIED. New unlisted finding: `factory_gate_install.py:668` (absolute repo_root), see H3.

## Required changes before freeze
1. H1: orphan-commit kit tag + explicit access model + tag-content test.
2. H2: out-of-band signer anchor, signer bound into `--confirm`, rollback guard, two-key rotation, remove env-gated unsigned flag, explicit fail-closed list.
3. H3: router uses `git rev-parse --show-toplevel`; extend T15/doctor to hooks.
4. H4: re-capture Mendocino baseline; fix T17 (b),(d),(e) wording.
5. Cut K5 from v0.1 (O1); apply M2-M4 to K6/K8 design text.

---
# v2.1 re-review (bounded, confirmatory)

New subject sha256 (v2.1): d9e63248ab69297f64510c1dac327a92febd4ea9b9f5a12c97c18feb1a979443

Mendocino inspect clone re-verified at `mcp-repo-inspect/` (HEAD 4eac7a2): `.factory/gate-install.json` target is `/home/hyperd/Documents/Mendocino Coastal Plants` (line 36), state ACTIVATION_BLOCKED / CONFIGURATION_BLOCKED with gitleaks missing; no `.github/`; `.githooks/{commit-msg,pre-commit,pre-push}` each contain `/home/`; one test file with 5 `def test`; package.json test/lint/build scripts match. My v2 "unverifiable" note for H4 is withdrawn (path was wrong, not the design). Note v2.1 states the three hooks all exist, correcting v2's "pre-push only".

| Finding | Status | Evidence |
|---|---|---|
| H1 | RESOLVED | S1.1 orphan parentless kit commit, tag pushed alone; access model explicit (owner-local ambient auth, non-owner OUT of v0.1); S1.3 step 4 tag tree == manifest. Tag-content test: confirm T4b exists in S7 at freeze (not located by grep, minor). |
| H2 | RESOLVED | Own allowed_signers w/ namespaces+valid-before, fingerprint anchor via gh api/typed, confirm binds fingerprint, rollback guard + minimum_version, two-key rotation, no unsigned CLI, fail-closed list + T6b. |
| H3 | RESOLVED (design) | B17 extended, K1 router uses `git rev-parse --show-toplevel`, T15 greps `.githooks/*`; real-world confirmed by Mendocino hooks containing `/home/`. |
| H4 | RESOLVED | T17 step-0 baseline, (b) allowlist, (d) counts (5), (e) deny-list with local-model layer off; matches clone. |
| M1 | RESOLVED | T6b, T9 rewrite, T12b read-only, confirm-binding test. |
| M2 | RESOLVED | rendered-base hash check, unfetchable -> proposed, exit mapping, journal/atomicity. Committed-marker gate check not found in grep: PARTIAL minor, add to K8. |
| M3 | RESOLVED | expanded detector list, `--show-origin`, git-common-dir. |
| M4 | RESOLVED | S1.4 line 63: CODEOWNERS entry + gate check on signer-field changes with rotation provenance note. |
| O1-O3 | RESOLVED | parity moved to K11/1.0 with derived_from; no [layers]; doctor stubs SKIP-only. |

New HIGH introduced by v2.1: none. Watch item (MED): T15 exempts "consumer-authored hook bodies" containing `/home/`, and Mendocino's are all such; retrofit must report them but they stay machine-specific, so (e)/(f) hooks may misfire on other clones; acceptable if listed in the retrofit report.

Verdicts: K1 PLAN_READY; K2 PLAN_READY; K3 PLAN_READY; K4 PLAN_READY; K5 removed from v0.1. K6-K8 PLAN_READY_WITH_FOLLOWUPS (marker gate check). v0.1 (K1-K4) is PLAN_READY (freezable now); only follow-up is confirming T4b tag-content test text.
