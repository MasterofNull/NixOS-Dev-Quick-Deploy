1. **Factual spot-check (8 claims checked on `origin/main`):**
   - **Confirmed (5):** [main.rs](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/crates/contract-validator/src/main.rs#L71-L74) (653 lines; `all`/`writable-state`/`memory-surface`/`scope-gate`) and [check-owned-scope.sh](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/governance/tier0.d/check-owned-scope.sh#L11-L14) (exits 0 if `OWNED_PATHS` unset); [system-state-authorities.yaml](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/system-state-authorities.yaml#L186) has 10 `SPLIT_BRAIN` rows (all deadline `2026-10-09`) and 3 unowned/unknown recovery rows (`:186, :232, :501`); `scripts/upstream/{dev,track}` are tracked bash files; [pi-agent.nix](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/pkgs/pi-agent.nix#L24-L29) has `lib.fakeHash`, [ai-stack.nix](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/roles/ai-stack.nix#L1010) asserts `>= 12` GB, and [ai-dev.nix](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/profiles/ai-dev.nix#L54-L71) sets 4 security daemons `= true` without `mkDefault`; `flake.lock` pins nixpkgs `8c3cede7` (`2026-06-08`) and repo has `LICENSE` (AGPL-3.0+), `COMMERCIAL-LICENSE`, `NOTICE`.
   - **Wrong / imprecise (3):**
     - `delta.md:37` says `state-authorities` is referenced "only" by `test-state-authorities.py` in `config/ci-checks.json:2125,2237` — **wrong**: it is also wired in `config/validation-check-registry.json:1044`, `scripts/ai/_aq-qa-bash:1676`, and `scripts/testing/harness_qa/phases/phase0.py:3057` (still true that tier0 and GitHub CI do not gate on it).
     - `delta.md:14` states `config/schemas/` has 59 files — `origin/main` has **64** tracked files (`*.schema.json` repo-wide = 71 is accurate).
     - `upstream-candidates.md:13` marks `.upstream/` gitignore status unchecked — `.gitignore:167` already ignores `.upstream/`.

2. **Overlap 9 / Orphan 3 credibility & missing decision types:**
   - **Overlap 9** is a credible **floor**, not a complete current count (`census-refresh.md:55` leaves rows 6–8 unverified since 11-23, while `#882` `work_ledger.py` and `aq-land-queue` added writers). **Orphan 3** is **not credible as a complete count**: it only greps `UNOWNED`/`UNKNOWN` recovery fields from the 10-row authorities YAML, which does not map 1:1 to the 9 census decisions.
   - **Missing decision types:** (a) capability-lease / execution-cell / revocation-epoch authority, (b) secrets & SOPS provisioning, (c) upstream patch/extraction & pin-bump lifecycle (`REGISTER.json`), (d) intent-lock / session continuity & operator approval state (in the YAML, missing from the 9-row census), (e) CI/tier0 gate & exception/waiver governance (`.grype.yaml`, `npm-exceptions.yaml`, `WORKAROUND-REGISTER.md`).

3. **Ownership registry vs. `contract-validator` reconciliation (`delta.md` §2):**
   - Keeping `config/system-state-authorities.yaml` as the sole ownership/import-boundary registry with a `contract:` field per row is sound, **but** registering schemas separately in Python `CONFIG_SCHEMA_REGISTRY` ([contracts/config/__init__.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/contracts/config/__init__.py#L16)) creates a **second registry** unless the validator derives its check list directly from `system-state-authorities.yaml` (or enforces 1:1 parity in tier0). Also note `contracts/config/` validates Pydantic config models, whereas cross-context contracts are JSON schemas/envelopes.

4. **Owner decisions:**
   - **D-R5-1:** `AGREE-WITH-CHANGES: require an explicit local-only flag + recorded owner waiver file/trailer, and forbid automatic fallback to local review during remote outages on protected repos.`
     Satisfies C1 for local-only/offline installs without letting a Codex/Gemini outage silently weaken trust-critical review gates.
   - **D-R5-2:** `AGREE-WITH-CHANGES: also enforce LLAMA_BUILD_UI=OFF in core/lite profiles, gate/replace runtime npx wrappers (Playwright/MCP), and retire nix/pkgs/{pi-agent,continue-cli}.nix.`
     Dropping `nodejs` from `profile-system-packages.nix` alone still leaves build-time `npmDeps` and offline-breaking `npx` downloads in the tree.
   - **D-R5-3:** `AGREE-WITH-CHANGES: in S1, drive schema/contract checks from system-state-authorities.yaml (no parallel list) and fail-closed on missing contract paths; port to Rust at S9 only if Python violates tier0 latency or trust-gate needs.`
     Unblocks immediate enforcement in S1 without creating a second registry or premature Rust churn.
   - **D-R5-4:** `AGREE-WITH-CHANGES: fold aq-land-queue in as S1b MVP only after S2's candidate/receipt verifier lands (preserve S2 -> S1b order) and remove seqland*.sh in the same PR.`
     Reuses working serial-queue code while keeping rev4's trust-gate-first order and "no second runner" invariant.
   - **D-R5-5:** `AGREE`
     `scripts/upstream/track` is a tracked executable file; `scripts/upstream/REGISTER.json` avoids breaking callers and pairs cleanly with a `contracts/` schema.
   - **D-R5-6:** `AGREE-WITH-CHANGES: change ai-dev.nix's hard `= true` daemon flags to `mkDefault`, lower/tier the 12 GB RAM assertion for `lite` (e.g. 8 GB for 4B Q4), and explicitly disable Postgres/Qdrant/GitHub-merge-queue in `lite`.`
     Makes `lite` genuinely usable on modest offline makerspace/student machines (8–16 GB) instead of inheriting heavy `ai-dev` services.

5. **What rev5 still misses from the brief:**
   - **Offline C4 install/runbook:** notes Hugging Face GGUF fetches and Nix binary cache needs, but defines no offline pre-seed/air-gapped validation path.
   - **Upstream AI-attribution guard:** flags the Rule 3 `Co-Authored-By` conflict (`delta.md:28`) and leaves `ai_policy` TODO, but proposes no hook/check preventing AI trailers from leaking into `.forks/*` commits.
   - **C5 dual-licence rule:** leaves EUPL-1.2 vs `COMMERCIAL-LICENSE` unverified (`candidates.md:25,58`) and lacks a formal binary-invocation vs linking/vendoring policy for the C5 gate.
   - **Baseline merge disposition:** `origin/feat/control-plane-consolidation-prd` is unmerged (`delta.md:3`), yet rev5 never states whether it amends that branch or supersedes it on `main`.

Top risk I see: merging rev5 as a second unimplemented design layer (with a split YAML + `CONFIG_SCHEMA_REGISTRY` contract list and unmerged rev4 S1) while new writers (`aq-land-queue`, `work_ledger.py`, `oncalld`) continue landing unguarded on `main`.
