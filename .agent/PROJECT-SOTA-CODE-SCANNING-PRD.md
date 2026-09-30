# PROJECT: SOTA Code-Scanning & Vulnerability Prevention

Status: DRAFT — framing by Claude (Opus); pending cohort review (Codex + local + Antigravity)
Owner: AI Stack Maintainers
Last Updated: 2026-09-26

## 1. Problem / attribution (evidence-based, 2026-09-26)

"Who is creating the new code-scanning errors?" — grounded from `gh api .../code-scanning/alerts` + the CI workflows:
- **34/34 open code-scanning alerts are Trivy** = CVEs in pinned THIRD-PARTY base images (postgres/redis/qdrant/nginx/grafana/prometheus/jaeger). **Upstream vendor CVEs surfacing as pins age — not agent-authored vulnerabilities.**
- **gitleaks findings** = test fixtures (`scripts/testing/test-aq-evidence-collector.py`, `test-a2a-guard.py`) + `.sops.yaml` public age recipients → **false-positives, not leaks.**
- **CI red (failed jobs)** was **config drift** from high-velocity parallel-agent commits (archived smoke-script refs, missing test deps, unpinned installer) — fixed by #348/#349; `main` is green.

Root classes (NOT "agents writing vulns"): (A) base-image CVE aging, (B) secret-scan fixture noise, (C) CI-config drift from fast multi-agent commits.

## 2. Prevention going forward (per class)

- **A — base-image CVE aging:** automate digest bumps (Renovate/Dependabot for container images), pin by digest, auto-PR on new upstream releases; a CVE-triage policy (bump, or waive-with-dated-expiry via `.trivyignore` — never silent-ignore). Fail the image job on a build error (don't scan an empty ref — a Codex #348 fix).
- **B — secret-scan fixture noise:** `.gitleaks.toml` fingerprint-allowlist the known fixtures + `.sops.yaml` public recipients (narrow, per-finding — never blanket), so a REAL leak isn't masked; enable **GitHub secret-scanning push protection** (blocks real secrets pre-merge). Add transient dirs (`.claude/worktrees`, `.codex/worktrees`, `__pycache__`, `.understand-anything/tmp`) to gitignore + gitleaks path-allowlist (they inflate/slow scans — the local scan hit 2.85 GB / 14 min).
- **C — CI-config drift from agents:** keep the merge gate on green CI-on-every-PR (now in place); the workflow-path-existence lint (Codex added) catches archived-script refs; extend the pre-commit/pre-push gates so an agent commit that would fail CI is caught locally (shift-left). Pin all GitHub Actions by commit SHA (already largely done — verified `@<sha>` pins in security.yml).

## 3. Current scanning baseline (solid) + SOTA gaps

**Have:** Trivy (container CVE, SARIF→code-scanning), gitleaks (secrets), semgrep (via MCP), hadolint (Dockerfile), custom governance/security-audit + tier0/focused-CI gates, SHA-pinned actions, per-PR CI.

**Missing for SOTA (agentic + software-dev):**
1. **CodeQL** — GitHub SAST on our Python/JS/shell (we have NO source-SAST in CI; Trivy=containers-only, gitleaks=secrets-only, semgrep=MCP-not-CI). Highest-value add.
2. **Dependency review** (PR-time `dependency-review-action`) + Dependabot/Renovate for code deps AND container images.
3. **SBOM + SLSA provenance** (per release/flake closure) — supply-chain (sota-supply-chain-sbom-slsa backlog item).
4. **Secret-scanning push protection** (native GitHub) — blocks secrets at push, complements gitleaks.
5. **OSSF Scorecard** — repo security-posture score, gated.
6. **Property-based / fuzz tests on security primitives** (lease/epoch/gate invariants) — sota-property-based backlog item.
7. **Signed commits/tags** (sota-signed-commits backlog item) — provenance.

## 4. Delivery (multi-lane, coordinated — NOT solo, NOT colliding)

- The peer (Codex) is actively on CI + `security.yml` (uncommitted) — **coordinate**: the security.yml-touching items (CodeQL job, dependency-review, image auto-bump) QUEUE behind the peer's landing to avoid collision (log in AGENT-CATCHUP-QUEUE).
- Non-colliding, do-now: `.gitleaks.toml` allowlist hygiene (new file surface), gitignore for transient dirs, a NEW `codeql.yml` workflow (new file), this PRD.
- Route the build via `aq-collab-round` (architect+security baseline across Claude/Codex/local); each item is a bounded slice; activation of any new *blocking* gate follows the commit-non-perfect / gate-activation-on-consensus rule.
- Fold into the existing 7 `sota-*` backlog items (issues-backlog.md) — this PRD is their SSOT for the scanning subset.

## 5. Success criteria
Green CI-on-every-PR (done); CodeQL + dependency-review + push-protection live; base-image CVEs auto-bumped or dated-waived (no silent ignores); gitleaks noise-free (fixtures fingerprinted, real leaks block); SBOM+provenance on releases; documented CVE-triage + agent-commit-hygiene policy so the three root classes can't silently regress.

## 6. Upstream findings — local fix + notify maintainers + propose fix (responsible contribution)

When our agents/tools find an issue in an UPSTREAM package / base image / dependency (not our own code) — security, correctness, performance, or efficiency:

1. **LOCAL FIX (immediate, tracked — never silent):**
   - Patched upstream release exists → bump the pin/digest (Renovate/PR).
   - No patched release → declarative local mitigation: a **Nix overlay/patch** (committed, so it survives rebuilds — Rule 13), or a config/usage workaround, or a **dated `.trivyignore`/waiver that references the upstream tracking item** (expiry, not silent — Rule 19 / anti-gaming). The local patch is explicitly TEMPORARY and linked to the upstream item so it retires when upstream lands.
2. **NOTIFY UPSTREAM:**
   - Non-security (bug/perf/efficiency): file an issue on the maintainer's tracker with a minimal reproducer + our analysis.
   - **Security vulnerability: RESPONSIBLE DISCLOSURE** — private channel first (maintainer security contact / GitHub private security advisory / CVE coordination), **never a public weaponized PoC** — describe the vulnerability class + our mitigation, not a step-by-step exploit (harness security policy). Coordinate an embargo/disclosure timeline.
3. **PROPOSE THE FIX (contribute back) — owner-authored, propose-not-push (HARD):** open an upstream PR/patch with our proposed fix + a regression test, referencing our local mitigation. **NEVER push directly to upstream** — submit PROPOSED changes via fork+PR (or patch) for the maintainers to review + accept (we propose, they decide). **STRIP all AI/agent attribution** — no `Co-Authored-By: Claude`, no `Generated with Claude Code`, no session links, no model tags; author = the owner's own identity (`git -c user.name/email=<owner>`), because many maintainers distrust/reject AI-generated code and the proposal must read as the owner's human work. **Validate the fix on THIS live running machine first** (real reproduction + verification, not asserted). Security vulns → responsible disclosure. When it merges/releases, drop our local patch and bump the pin. (Our OWN repo keeps its internal attribution convention; this owner-authored/no-AI-marks rule is for upstream only.)
4. **TRACK (ledger):** an `upstream-contributions` registry (section in issues-backlog.md, or `.agent/collaboration/UPSTREAM-CONTRIBUTIONS.md`) mapping each: finding → severity → local-mitigation(+file) → upstream issue/PR URL → status (filed / PR-open / merged / released) → local-patch-retire-condition. Reviewed every cycle; local patches retire on upstream landing (prevents perpetual local forks).
5. **AUTOMATION / agentic loop:** the scan gate emits findings → a triage step classifies our-code vs upstream → an upstream finding auto-opens a ledger entry (and optionally drafts the upstream issue) → the local mitigation + the upstream PR are bounded slices routed multi-lane (cheapest-eligible, cohort-reviewed) → activation of any gating change follows commit-non-perfect / gate-activation-on-consensus. This closes the loop: find → mitigate locally → notify + propose upstream → retire on merge.

Applies to the current 34 Trivy base-image CVEs: bump the patched images (Renovate), dated-waive the un-patched ones with the upstream CVE link, and for any CVE traced to a genuine upstream bug we can fix, open the upstream PR. Owner-directed 2026-09-26.
