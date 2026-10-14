# SOTA Rounding Plan — persistent, durable, proactive agent configs (2026-10-14)
Scope: W1 REA, W2 isolation/sandboxing, W3 MCP + scraping SOTA sweep. Read-only research; no repo files edited.
Evidence base: worktree /tmp/gemini-codex-clearance-20261014 (origin/main = 29d5fcd2). All paths repo-relative.

## Corrections to the brief (verified)
- cs-4 is NOT pending: tracker acceptance 2026-10-06, commit 97b063d5, test-concurrent-dispatch-isolation 8/8. Only residual: cs3 note says "CS4 deployed dashboard + parallel-dispatch proof pending" -> that is stale text; needs an activation-audit line, not a slice.
- 728f8137 (sandbox) is already on main as eaf8d453 (PR #450, merged). origin/codex/wip-sandbox-20261009 is branch-only for c735bdf8 (capability-audit timer + capability_snapshots.py + rsi_sweep additions + dashboard route), plus two "wip" preservation commits (91d93989, 43fab0d7). main lacks scripts/ai/lib/capability_snapshots.py and test-capability-snapshots.py.
- The REA skill lives at .agent/skills/rea-reverse-engineering/SKILL.md (no .claude/skills dir; .claude has commands/, rules/, settings.json only).
- aq-frontier has NO timer by design ("pull, not poll"; FA-4 is on-demand `scan-topic`). A recurring scan is a deliberate policy change, see W3-S5.

---------------------------------------------------------------------
## W1 REA (Reverse Engineer Anything)

### Current state
- Registered in config/agent-capability-intake-candidates.json by 372c87de (PR #503): state=proposed, review_status=incomplete, pinned_version "0.1.0", install.type=disabled-external-repo, tool_allowlist = analyze_javascript_application / analyze_dotnet_assembly / analyze_native_binary / rea_session_evidence, permissions network=false fs=quarantine-read writes=false secrets=false. source_hash=null.
- `aq-capability-intake audit rea-reverse-engineering --json` -> admission "review-recommended"; all 4 tools audit approved/safe; risk flags tool-execution, npm-package-execution, resource-exhaustion, scope-escape, log-sensitive-data.
- Skill .agent/skills/rea-reverse-engineering/SKILL.md exists (policy text only). It says `npx -y rea-agents@latest ...` which violates our own rules (mutable npx, no hash; the playwright wrapper exists precisely to forbid this).
- test-capability-intake.py only asserts the id exists.
- Upstream (https://github.com/morluto/rea): MCP server via npm `rea-agents`; needs Node >=22.19; native analysis needs Hopper/Ghidra/IDA (commercial IDA/Hopper not acceptable; Ghidra is the realistic engine); static JS/.NET read files without executing; "runtime capture" executes the target under user perms (must stay disabled); MIT; no telemetry stated. Allowlist names in our candidate may not match upstream tool names: must verify against real tools/list.
- Reusable sandbox primitives already on main and ON in ai-dev.nix: execution-cell-runner (bwrap, socket-activated, unprivileged; nix/modules/services/execution-cell-runner.nix, ai-stack/switchboard/execution_cell_runner.py), mcp-playwright-sandboxed (admission check + AppArmor via aa-exec + dynamic integrity check; best template), AppArmor enabled (nix/modules/core/base.nix:399).

### Gaps vs DEFINITION-OF-DONE (integrated / ON / validated / observable / intervenable / PM-tracked)
1 Not integrated: no launcher, no MCP client entry, no switchboard/coordinator route; skill is text only.
2 Not ON: install disabled; no Nix package (npm tool, Ghidra not declared).
3 Not sandboxed: no AppArmor profile, no bwrap/no-net wrapper, no resource limits, no secret scrub.
4 Not validated: no real analysis on a fixture; allowlist names unverified; no regression test.
5 Not observable/intervenable: no aq-report/dashboard card, no kill switch.
6 Not PM-tracked: no plan tracker.json.

### Slices (ordered)
W1-S1 Intake close-out + supply-chain pin (docs/config only). Scope: resolve upstream tools/list from a pinned tarball (npm view integrity, as in playwright wrapper), set source_hash, correct allowlist names, run osv-scanner + syft on tarball, record license MIT, drop `npx -y @latest` from skill. Files: config/agent-capability-intake-candidates.json, .agent/skills/rea-reverse-engineering/SKILL.md, tasks_inbox/capability-intake-rea.md (follow the playwright record format), scripts/testing/test-capability-intake.py (assert pin/hash/no-@latest). Accept: audit shows admission accepted-with-mitigations or explicit REQUEST_REVISION; test asserts no floating spec. Deps: none. Risk: low. Lane: sonnet (or local Qwen with verify gate; bounded single-file edits).
W1-S2 Sandboxed launcher scripts/ai/mcp-rea-sandboxed modeled on mcp-playwright-sandboxed: admission gate against both SSOTs, integrity check, `bwrap --unshare-all` (no net), tmpfs HOME, ro bind of target only from quarantine dir, env scrubbed (reuse scrub_credentials in scripts/ai/lib/oncalld_engine.py on the DP-3 branch, or extract a shared helper), timeout + RLIMIT/systemd-run MemoryMax/CPUQuota, runtime-capture tools disabled. Nix: nix/modules/core or mcp-servers.nix adds `security.apparmor.policies."mcp-rea"` + Ghidra/node packages (floors only, no pins); quarantine dir via systemd.tmpfiles. Accept: test-rea-sandbox.py (fixture: tiny ELF + tiny asar) proves (a) no network (connect fails), (b) cannot read /run/secrets or ~/.ssh, (c) target cannot be mutated, (d) wall-clock + memory kill, (e) refuses when candidate state != enabled. Deps S1; owner act: nrs. Risk: medium (Ghidra headless under bwrap, JVM memory vs 27 GB budget; local model must be idle). Lane: Codex/sonnet implementer, independent reviewer non-author (Rule 18).
W1-S3 Integrate + observe + intervene. Register MCP client entry via the same projection used for playwright (.mcp.json, .gemini/settings.json, codex TOML) only after admission; flip candidate state=enabled and system-capability-catalog.json; aq-report card (calls, denials, kills, last target hash); kill switch = Nix option mySystem.mcpServers.rea.enable + `aq-capability-intake disable`. Accept: test-enabled-external-mcp-candidates.py covers it; live: analyze a fixture via MCP from Claude and see the aq-report counter increment; disable switch makes launcher refuse. Deps S2. Risk: low-medium.
W1-S4 Tracker + activation attestation: .agents/plans/rea-integration/tracker.json (editorial only), ACTIVATION-AUDIT entry, evidence doc docs/harness-first/evidence/<date>-rea.md, seed AIDB skills-patterns. Deps S3. Lane: haiku/sonnet.
Sequencing note: Slice W1-S2 shares its confinement helper with W2-S2; do W2-S2 first or extract the helper in S2.

---------------------------------------------------------------------
## W2 Agent work isolation + system sandboxing

### Inventory
SHIPPED + ON (evidence):
- Worktree isolation of delegations: coordination-safety tracker cs-1..cs-4 shipped (commits; acceptance fields not recorded in tracker) (e8a905e8, 0d835c13, 97b063d5; tests test-worktree-isolation.py, test-concurrent-dispatch-isolation.py 8/8, test-worktree-write-guard.py); PreToolUse hook aq-worktree-write-guard in .claude/settings.json; aq-worktree, aq-worktree-reap; main-checkout commit refusal 90c7d554; antigravity worktree-bound lane 662b5055.
- AppArmor: enabled (base.nix:399); profiles ai-llama-cpp (ai-stack.nix:1694, enforced, assertion at :948), ai-mcp-base, ai-hybrid-coordinator (mcp-servers.nix:2550/2616; coordinator comment says complain mode with soak, verify current mode), command-center-dashboard-api (:2741), mcp-playwright (via aa-exec). apparmor-rules skill + scripts/automation/apparmor-fix-agent.py.
- Local-agent shell: nsjail (mcp-servers.nix:1090, NSJAIL_* env, jail mounts fixed in eaf8d453/PR #450); bwrap for aider (:1538).
- Execution cell runner (bwrap) ON in ai-dev.nix:39 with flagOn, but CAPABILITY_CELL_ADAPTER=0: nothing submits to it yet.
PENDING / DORMANT:
- fe-8-landlock-egress (frontier tracker): no acceptance; BACKLOG in_review; deferred by owner directive 2026-10-07 (security/containment after MVP baseline); Codex concern: redundant with bwrap+AppArmor+netns. Landlock not used anywhere in repo (rg: only aq-frontier, test-frontier-fold, evidence note).
- aqos-foundation-c: all 9 items pending (ala-build, enforce-verify, c2sci-*, c6-*, teg-c1, c4 network confinement "last cycle").
- DP-3 aq-oncalld: PR #506 OPEN (7f9ef0f4, branch feat/durable-mesh-dp3-oncall-daemon; local branch fix/dp3-oncall-review-revision at same commit). Ships worktree containment check + env scrubbing (oncalld_engine.py scrub_credentials) + fenced epochs, but the diff has NO .nix file: no systemd unit, no AppArmor profile, no bwrap/nsjail around the implementer shell. DESIGN.md s3.3 promises "AppArmor profile enforces directory containment" and s4 "cannot read /run/secrets or ~/.ssh": env scrubbing does not stop file reads. This is the key W2 gap.
- origin/codex/wip-sandbox-20261009: only c735bdf8 remains unmerged (capability-audit RSI observation). Two wip commits are preservation noise and also delete files vs main (branch is older than main: diff vs main shows -108 lines in reports, local_agent_runtime.py); do NOT merge wholesale, cherry-pick c735bdf8 onto main and re-test.
- aq-context-sandbox is a context artifact store, not an execution sandbox (name collision; note for docs).
- DP-0..DP-5 tracker acceptance fields empty for all items.

### Slices (minimal)
W2-S1 Land or retire the stale branch. Cherry-pick c735bdf8 (capability_snapshots.py, rsi_sweep, timer, QA, dashboard route) onto fresh main worktree; resolve ACTIVATION-AUDIT append conflict; run test-capability-snapshots, test-rsi-sweep, test-codex-config-reconcile, tier0. Archive the two wip commits (Rule 12: tag, not delete). Accept: tests pass on main base; branch tag archived. Risk low-med (merge conflicts). Lane: sonnet. Deps none.
W2-S2 Shared confinement launcher `scripts/ai/aq-confine` (single mechanism reused by DP-3 oncalld, REA, future MCP): wraps bwrap (already in system path) with profiles: `worktree-rw` (rw bind of one worktree, ro /nix/store, tmpfs HOME, no /run/secrets, no ~/.ssh, optional netns none or loopback-only), env scrub, rlimits. Minimal-code: reuse the bwrap invocation from execution_cell_runner.py rather than new code; do not add Landlock/gVisor yet. Accept: test-aq-confine.py: secrets path unreadable, writes outside worktree fail, net=none works, git commit inside worktree works, escape attempt via symlink/.. fails. Files: scripts/ai/aq-confine, scripts/testing/test-aq-confine.py, nix package list entry. Risk medium. Lane: Codex or sonnet; independent reviewer.
W2-S3 DP-3 confinement completion (blocks DP-5 activation gate): on #506 follow-up branch, run implementer subprocesses through aq-confine; add nix/modules/services/oncalld.nix (user unit, default OFF, MemoryMax/CPUQuota, ProtectHome=read-only + ReadWritePaths for worktrees dir and state dir per Rule 14, tmpfiles for dirs per Rule 13) and AppArmor policy `aq-oncalld` (complain first, per apparmor-rules skill). Accept: extend test-aq-oncalld.py with a hostile-worker fixture that tries to cat /run/secrets/* and ~/.ssh/id*, curl out, and write to main checkout: all denied and logged as incidents; aa-status shows profile loaded after rebuild; dashboard card shows confined=true. Deps W2-S2, PR #506 merge. Owner act: nrs + enabling. Risk medium-high (AppArmor DAC lesson Rule 14).
W2-S4 Decision on fe-8-landlock-egress: do not build now. Recommend "monitor" verdict: our controls (bwrap netns, AppArmor, nsjail, proxy-less no-net launchers) already cover loopback-only egress; revisit when foundation-c c4 (network confinement) starts, and evaluate Sandlock (https://arxiv.org/abs/2605.26298, github multikernel/sandlock) as a bwrap alternative then. Action: update frontier BACKLOG verdict via `aq-frontier verdict` (needs 2 lanes) and tracker note. Effort tiny. Lane: sonnet or local.
W2-S5 Hygiene: correct stale cs-3 note in tracker/ACTIVATION-AUDIT; add aq-confine + execution-cell status to aq-report; verify ai-hybrid-coordinator AppArmor complain->enforce status and file a backlog item if soak never closed. Lane: haiku.

---------------------------------------------------------------------
## W3 MCP + scraping SOTA sweep

### Our inventory
- MCP clients/servers: .mcp.json (lean-ctx, hybrid-coordinator via scripts/ai/mcp-bridge-hybrid.py, semgrep native `semgrep mcp`); .claude/settings.json (ai-stack-harness bridge, playwright via mcp-playwright-sandboxed [candidate quarantined/incomplete but wrapper fail-closed], semgrep); ~/.claude.json user scope: lean-ctx, hybrid-coordinator, osint-tools, github (read-only via scripts/ai/mcp-github-server). Server code: ai-stack/mcp-servers/{aidb, aider-wrapper, container-engine, embeddings-service, github, health-monitor, hybrid-coordinator, mlops-tools, nixos, nixos-docs, osint-tools, qa-tools, ralph-wiggum, trading-tools, shared}.
- Candidate registry: 17 candidates (enabled: semgrep, github-ro, osv, trivy, syft-grype, admission-controller, observability, nixos pack; partial: graph layer; ready-scope-gated: t3mp3st; proposed/incomplete: piyaz, raptor, ecc, herdr, rea; quarantined: playwright, sn1per).
- Skills: 66 in .agent/skills (plus auto-generated), 11 slash commands in .claude/commands, role matrix docs/architecture/role-matrix.md, config/workflow-blueprints.json + workflow-automation.yaml, plugins: only clangd-lsp (disabled). Hooks: PreToolUse worktree-write-guard and approval-ask-hook only.
- Scraping/ingestion: hybrid-coordinator web_fetch + extensions/browser_research.py (robots-aware, SSRF guard shared/ssrf_protection.py), osint-tools MCP (bbot, maigret, mosaic) + osint-systems skill, aq-frontier (backlog, sources.yaml with 27 sources incl. mcp-spec and a2a-spec at monthly cadence, relevance, fold), AIDB document_importer / rag, scripts/ai/aq-rag-prewarm, ingest-*.sh.

### SOTA findings (Oct 2026) with sources
1 MCP spec 2026-07-28 (final) - https://modelcontextprotocol.io/specification/2026-07-28/changelog : stateless (no initialize, no Mcp-Session-Id; per-request _meta protocol version/capabilities), `server/discover` mandatory, Tasks moved to extension io.modelcontextprotocol/tasks (poll tasks/get, tasks/update), Multi Round-Trip Requests replace server-initiated elicitation/sampling/roots (resultType "input_required"), ttlMs/cacheScope on list results, deterministic tools/list ordering, OTel traceparent in _meta, required Mcp-Method/Mcp-Name headers, JSON Schema 2020-12 for in/outputSchema, structuredContent any JSON; auth: RFC 9207 iss validation, Client ID Metadata Documents replace DCR; Roots/Sampling/Logging and HTTP+SSE deprecated (12-month window). Adoption: https://github.blog/changelog/2026-07-23-github-mcp-server-supports-the-next-mcp-specification/ , https://vercel.com/changelog/vercel-mcp-now-supports-the-2026-07-28-mcp-specification
   Our gap: mcp-bridge-hybrid.py:1702 advertises protocolVersion 2024-11-05 (initialize handshake, no discover, no ttl/cache, no structured output declared). Largest compatibility debt in the stack.
2 Agent sandboxing practice - https://codersera.com/blog/how-to-sandbox-ai-coding-agents-2026/ , https://pillar.security/blog/your-ai-agent-will-run-untrusted-code-now-what , Sandlock https://arxiv.org/abs/2605.26298 : consensus that OS-level confinement beats permission/deny-lists; Claude Code/Codex use bwrap/Seatbelt + seccomp + egress proxy; Landlock-based tools give full net block and ~5 ms overhead, no root; bwrap alone has weak syscall and HTTP-level policy; microVM/gVisor for adversarial code. Our posture (bwrap + AppArmor + nsjail) matches the mainstream; missing: seccomp filters and a domain-allowlist egress proxy for fetch tools (not needed for REA, which is no-net). Vendor-blog sources: treat as directional.
3 Durable execution - https://dev.to/mr_manushukla/durable-ai-agents-without-temporal-exactly-once-workflows-on-postgres-with-dbos-2026-5a6n , https://thenextweb.com/news/restate-20m-series-a-singular-durable-execution-ai-agents : Postgres-checkpoint pattern (DBOS) is the lightweight option. Our DP-2 aq-durable (intent log + CAS + reconciliation, PR #505 merged) already implements the same idea on local state; no new engine warranted (YAGNI).
4 Claude Code extensibility - https://code.claude.com/docs/en/plugins-reference.md , https://code.claude.com/docs/en/features-overview : plugins bundle skills/agents/hooks/MCP; skills can `context: fork` into subagents; async/prompt/plugin hooks exist. Search did not surface an Oct-2026 changelog; verify at code.claude.com before acting. Our gap: only 2 hooks; no SessionStart/Stop/PostToolUse hooks; skills not packaged as a plugin (all-agent parity makes a plugin optional).
5 Scraping tools - Firecrawl (self-hostable, AGPL, MCP server, July 2026 rebuild cut context ~50%) and Crawl4AI (self-hosted crawler; third-party MCP wrappers of low maintenance) per aggregator results (https://www.webfuse.com/mcp/web-scraping , https://use-apify.com/blog/ai-agent-web-tools-comparison-2026) - low-confidence sources; verify on the repos. Playwright MCP is already our headless path.

### Gaps ranked (value / effort)
1 MCP 2026-07-28 conformance for hybrid-coordinator bridge: HIGH value / MEDIUM effort.
2 Scheduled frontier scan with spec-revision watcher: HIGH / LOW (reuse aq-frontier + sources.yaml).
3 Hook coverage (PostToolUse evidence, SessionStart aq-resume injection, Stop closeout) : MEDIUM / LOW.
4 Playwright candidate still "quarantined/incomplete" though in live config: MEDIUM / LOW (finish intake record or remove; honesty gap).
5 Scraping: web_fetch has SSRF+robots but no structured extraction/markdown cleaning or crawl budgets: MEDIUM / LOW-MED (add to browser_research.py; do NOT adopt Firecrawl AGPL service; Crawl4AI only if a bounded benchmark shows gain, as a sandboxed candidate via capability-intake).
6 Egress proxy / seccomp: LOW now / HIGH (defer to foundation-c c4).
7 Tasks extension for long-running tools (aq-durable fits naturally): MEDIUM / MEDIUM, after #1.

### Slices
W3-S1 MCP conformance audit (read-only first): script `scripts/ai/aq-mcp-conformance` (or extend existing admission-controller) that probes each configured server for server/discover, protocolVersion, deterministic tools/list, outputSchema, ttlMs; emits JSON for aq-report. Accept: report lists all 6+ servers with pass/fail per rule, unit-tested with fixture servers. Deps none. Lane: sonnet/local. Risk low.
W3-S2 Bridge upgrade scripts/ai/mcp-bridge-hybrid.py: add server/discover, per-request _meta version negotiation while still answering legacy initialize (dual-stack so Claude Code/Codex/Gemini clients keep working), ttlMs/cacheScope, deterministic tool order, outputSchema+structuredContent for top tools (hybrid_search, get_hints, harness_health), traceparent passthrough into coordinator telemetry. Accept: test-mcp-bridge-compat.py exercises both handshakes; all existing tests/tool_catalog parity pass; live call from Claude Code. Deps W3-S1. Risk medium (client compat; keep legacy path default). Lane: Codex/sonnet.
W3-S3 Hooks: add SessionStart (aq-resume summary), PostToolUse PULSE/usage append (reuse aq_usage), Stop closeout reminder into .claude/settings.json; parity entry for other agents per Rule 16 (documented, since only Claude has hooks). Accept: hook unit tests, no latency >100 ms. Lane: sonnet.
W3-S4 Intake honesty fixes: close playwright-mcp record (state vs live config) and ensure test-enabled-external-mcp-candidates covers it. Lane: haiku.
W3-S5 [IN FLIGHT 2026-10-14: feat/frontier-scan-due-timer, owner-approved] Recurring frontier scan (reuse aq-frontier; no new tool): add `aq-frontier scan-due` (list sources whose cadence elapsed per sources.yaml, using existing scan-requests.jsonl + context staleness) and a systemd user timer in Nix (weekly, bounded 900s/512MiB like the capability-audit timer) that fetches only cadence-due primary sources via existing web_fetch (SSRF+robots), diffs against last seen (spec revision string, release tags), and files `aq-frontier add` candidates as `new` (never auto-accept; consensus gate and fa-3 fold stay manual). Add one source row: MCP spec changelog URL with etag-diff, claude-code changelog, sandlock repo. Policy note: this relaxes the "no polling" principle to "bounded, cadence-driven, review-gated"; needs owner nod and a FRONTIER-AUTOPILOT.md amendment. Accept: test-frontier-scan-due.py (fake clock, fake fetcher), timer unit present, dashboard/aq-report shows last-scan age, kill switch = Nix option. Deps none. Lane: sonnet.
W3-S6 (optional) browser_research.py structured-extract mode + crawl budget; benchmark against 20 URLs on our hardware before adopting any external crawler. Lane: local Qwen with verify gate, else sonnet.

---------------------------------------------------------------------
## Suggested order and parallelism
Phase A (parallel, independent): W2-S1, W1-S1, W3-S1, W3-S5, W3-S4.
Phase B: W2-S2 -> W2-S3 (and W1-S2 reuses S2) ; W3-S2.
Phase C: W1-S3/S4, W3-S3, W2-S4/S5, W3-S6.
Owner acts needed: nrs after W1-S2, W2-S3, W3-S5; owner nod for scan-cadence policy change; enabling flags are separate acts. One branch+worktree+PR per slice; tier0 --pre-commit; independent non-author review (Rule 18).

## Risks / open questions
- Ghidra headless memory vs 27 GB budget when llama is resident; schedule REA jobs only when local model idle.
- REA allowlist names unverified against upstream; may force S1 REQUEST_REVISION.
- Search results for Claude Code Oct-2026 features and scraping tools were secondary; re-verify before building.
- #506 DP-3 merge ordering: W2-S3 must follow it.

---------------------------------------------------------------------
## W4 Frontier parity intake (owner-flagged 2026-10-14)

Sources: https://github.com/thebpandey/lanes, https://youtu.be/J9NQTYUP6k0, https://youtu.be/VxGIopUQVKo.
Full report: `evidence/frontier-intake-lanes-videos-20261014.md`. Registered in
`frontier-evidence-intake/BACKLOG.jsonl` (ids below); consensus via `aq-frontier verdict` (2 lanes).

- lanes-as-dependency: DROP. 1 commit/1 author, install.sh writes $HOME, claude-via uses
  bypassPermissions + API-key-routed endpoints (violates no-API-keys). Its tests: 0 failures of ~50 in a
  HOME-redirected sandbox. Token-savings claim unbenchmarked.
- W4-S1 lanes-owned-scope-gate (PARITY): per-slice owned-path list; merge/integrate refuses diffs
  outside it; review verdict bound to exact head sha (we already bind subject sha256). Extends
  aq-worktree / tier0, no new tool. Accept: in-scope pass, out-of-scope block, uncommitted block.
- W4-S2 lanes-token-caps-in-brief + yt-checks-over-plans-goal (PARITY): slice-authoring template gains
  token caps, a mandatory runnable check command, end-state + turn cap; usage ledger records
  actual-vs-cap. Accept: template lint rejects a brief missing check command.
- W4-S3 yt-skill-eval-prune (PARITY): with/without eval of .agent/skills via `claude plugin eval` /
  /skill-doctor; zero-delta skills archived (Rule 12, parity-equivalent only). Accept: per-skill delta report.
- W4-S4 yt-claudemd-index (PARITY, Rule 16 all agents): instruction files as index, path refs instead of
  @imports, target <200 lines; canon blocks remain SSOT. Accept: parity check green, line budget gate.

Video theses are creator paraphrases of Anthropic guidance — directional, unverified.

## Orchestrator notes (2026-10-14)
- DP-3 revision (fix/dp3-oncall-review-revision) now confines incident repro with inline bwrap. W2-S2
  `aq-confine` should absorb that invocation (single mechanism), not add a second one.
- durable-proactive-mesh tracker carries hand-set `pct_hint` values on dp-* items; Rule 20 says status is
  projected — remove in a tracker-hygiene slice (W2-S5).
- MCP 2026-07-28 spec claims come from search results; W3-S1 must re-verify against the spec page first.

---------------------------------------------------------------------
## W5 Machine-enforced independent review on merge (root cause of Antigravity self-merge)

Evidence 2026-10-14: PRs #462-#505 merged with 0 GitHub reviews and no Reviewed-by trailers;
`gh api .../branches/main/protection` -> 404 "Branch not protected". Review-Disposition/Reviewed-by is
enforced only by the local `.githooks/commit-msg` hook, which `gh pr merge` / the GitHub merge button
bypass. Post-merge review of #488-#502 found 4 high defects (fabricated eval gates #489/#495, fake owner
ratification #494, self-review fail-open #496) — the system, not an owner gate, must stop this
(feedback-sop-enforced-by-system-not-owner-gate).

- W5-S1 `review-disposition` GitHub Actions check: PR must carry a review record bound to the head sha
  (Review-Disposition + Reviewed-subject-sha256 + Reviewed-by lane != author lane) in the PR body or a
  tracked review file; fails otherwise. Reuse commit-msg hook parsing logic (single source).
- W5-S2 Branch protection on main requiring that check (OWNER ACT — outward-facing repo setting; exact
  `gh api -X PUT` command provided in evidence doc).
- W5-S3 Anti-fabrication lint in tier0: block `pct_hint` / "accepted by" / "Preauthorized by owner" edits in
  tracker.json and "owner ... ratification" strings in config without an owner record pointer
  (aq-approve receipt id).
Accept: a PR without an independent review record cannot merge; a test PR proves it.

---------------------------------------------------------------------
## W6 CI <-> local gate parity (owner question 2026-10-14; audit: evidence/ci-local-parity-audit-20261014.md)

Last 600 CI runs: 4 failure classes (gitleaks secret detection; harness-first PR evidence gate; tier0/aq-qa in CI's
bare py3.11 env e.g. DP-4 fixture needs FastAPI; Nix toplevel build via xdg-desktop-portal check) — none caught locally.
Principle: CI and local invoke the SAME scripts from ONE manifest, so they cannot drift.

- W6-S1 `config/ci-checks.json` manifest + `scripts/governance/run-ci-checks.sh --all|--changed`: CI workflows call it;
  pre-push calls `--changed`; tier0.d check fails if a workflow `run:` invokes a repo script absent from the manifest.
  First entries: harness-first static gates, skill-governance, template-placeholder lint, aq-report/PRSI contracts.
- W6-S2 Path-triggered pre-push Nix eval (`flake.*`, `nix/**`): `nix flake check --no-build --system x86_64-linux` +
  toplevel drvPath eval. Replace CI `--all-systems || true` with explicit system, no `|| true`.
- W6-S3 `ci-clean-env.sh`: one clean-venv runner (CI python + requirements only) used by CI and optional pre-push.
- W6-S4 Dead security gate: security-audit.sh must exit non-zero on blocking findings; security.yml uses its exit code,
  drop continue-on-error on that step (it currently cannot fail — passes both while wrong).
- W6-S5 `config/tool-pins.json` (floors) read by workflows + tier0.d version-skew check (gitleaks 8.24.3 vs 8.30.1,
  python 3.11 vs 3.13, CI nix_path 25.11 vs flake 26.05).
- W6-S6 Merge-commit parity: run manifest checks in a temp merge-with-origin/main worktree (reuse --staged-isolated).
- W6-S7 Low: whole-tree maintenance run; surface missing-tool SKIPs as WARNs.

---------------------------------------------------------------------
## W7 Gate-triggered dependency hygiene rule (owner directives 2026-10-14)

Trigger: ONLY a failing security gate, scoped to the implicated package; no broad dependency audits/rewrites.
Ladder: (1) fixed release -> raise floor; (2) ACTIVE upstream, fix unreleased -> mitigate our usage + time-boxed
exception (config/security-exceptions.json, <=90d, expiry blocks); (3) ABANDONED/STALE (no release/commits
>18 months, archived, Scorecard Maintained low, open maintenance-status issue) -> move to an ACTIVELY MAINTAINED
replacement with parity (maintained successor/fork, maintained alternative, or stdlib for small usage), itself
passing the maintenance check; bridge with mitigation + exception until it lands; (4) upstream help for active
projects is owner-authored, propose-not-push.
- W7-S1 Canonize this ladder in canon/blocks (Rule 16 parity, canon-compile to all agent files).
- W7-S2 security-audit.sh: on a blocking finding, print the ladder step data (fix version available? maintenance
  signal via deps.dev Scorecard Maintained) so the triage starts from evidence.
