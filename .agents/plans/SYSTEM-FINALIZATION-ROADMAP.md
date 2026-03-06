# System Finalization Roadmap

**Generated:** 2026-03-05
**Version:** 1.0.0
**Target:** Production-Ready AI Stack Harness

---

## Overview

This roadmap completes the production finalization of NixOS-Dev-Quick-Deploy following PRSI (Pessimistic Recursive Self-Improvement) methodology. Each phase is gated by success criteria that must be validated before proceeding.

## Execution Protocol

```
For each Phase:
  For each Task:
    1. Set task status → in_progress
    2. Execute with suggested tooling
    3. Validate → Fix → Validate (loop until success)
    4. Capture evidence
    5. Set task status → completed
    6. Commit if significant
  End
  Run phase gate validation
  If gate fails: Fix → Validate → Commit → Re-check gate
End
```

---

## Phase 1: Infrastructure Hardening (Gate: Security Audit Clean)

**Objective:** Ensure all MCP server endpoints are production-secure.

### Task 1.1: Input Validation Audit
**Status:** pending
**Tooling:** `Grep` for pattern analysis, `Read` for code review
**Action:**
- Audit all FastAPI/aiohttp route handlers for input validation
- Verify Pydantic models enforce constraints
- Check for SQL injection, command injection patterns
**Success Criteria:**
- [ ] All endpoints use Pydantic request models
- [ ] No raw string interpolation in SQL/shell commands
- [ ] Query parameters have type/length constraints
**Evidence:** `scripts/testing/test-prompt-injection-resilience.sh` passes

### Task 1.2: Rate Limiting Implementation
**Status:** pending
**Tooling:** `Edit` for code changes, `Bash` for testing
**Action:**
- Add slowapi/ratelimit middleware to hybrid-coordinator
- Configure per-endpoint limits in config
- Add 429 response handling
**Success Criteria:**
- [ ] Rate limiter middleware active on /search, /hints, /workflow/* endpoints
- [ ] Configurable via environment variables
- [ ] Returns proper 429 + Retry-After header
**Evidence:** `curl` test showing 429 after threshold

### Task 1.3: SSRF Protection Verification
**Status:** pending
**Tooling:** `Read` existing implementation, `Bash` for testing
**Action:**
- Verify `shared/ssrf_protection.py` is used on all external fetch paths
- Test private IP blocking
- Test DNS rebinding protection
**Success Criteria:**
- [ ] All httpx clients use `create_ssrf_safe_http_client`
- [ ] Private ranges blocked by default
- [ ] DNS resolution failures block request
**Evidence:** Unit test or manual verification log

### Task 1.4: Secrets Management Verification
**Status:** pending
**Tooling:** `Grep` for hardcoded secrets, `Read` sops config
**Action:**
- Scan codebase for hardcoded credentials
- Verify sops-nix integration works
- Test secret rotation procedure
**Success Criteria:**
- [ ] No hardcoded API keys, passwords, tokens
- [ ] `sops-nix` secrets load at runtime
- [ ] Rotation documented in runbook
**Evidence:** `grep -r "password\|api_key\|token" --include="*.py" | grep -v "test"` clean

### Task 1.5: Circuit Breaker Metrics Dashboard
**Status:** pending
**Tooling:** `Read` existing circuit breakers, `Edit` for metrics
**Action:**
- Add Prometheus metrics to circuit breakers
- Track open/half-open/closed state transitions
- Add recovery success rate metric
**Success Criteria:**
- [ ] `/metrics` endpoint exposes circuit breaker state
- [ ] Grafana dashboard (or equivalent) can visualize
**Evidence:** `curl localhost:8003/metrics | grep circuit` output

---

## Phase 2: Harness Optimization (Gate: Eval Score ≥ 0.7)

**Objective:** Tune PRSI loops and hint engine for optimal performance.

### Task 2.1: Hint Bandit Calibration
**Status:** pending
**Tooling:** `Read` hints_engine.py, `Edit` for tuning, `Bash` for eval
**Action:**
- Review current exploration/exploitation balance
- Adjust UCB exploration weight based on feedback data
- Tune confidence floor for cold-start scenarios
**Success Criteria:**
- [ ] Hint adoption rate ≥ 70%
- [ ] Bandit converges within 10 interactions for common tasks
**Evidence:** `scripts/ai/aq-report --since=7d` shows adoption ≥ 70%

### Task 2.2: Eval Timeout Threshold Tuning
**Status:** pending
**Tooling:** `Read` harness_eval.py, `Edit` config, `Bash` for benchmarks
**Action:**
- Profile actual eval latencies on target hardware
- Set timeout_hard_cap_s based on 99th percentile
- Ensure timeout doesn't exceed 20s absolute cap
**Success Criteria:**
- [ ] 95% of evals complete under timeout
- [ ] No timeout-triggered failures in normal operation
**Evidence:** Eval run showing < 5% timeout rate

### Task 2.3: Semantic Cache Warming
**Status:** pending
**Tooling:** `Read` semantic_cache.py, `Edit` for warm-up script
**Action:**
- Implement on-startup cache population from common queries
- Use Qdrant nearest-neighbor seeding
- Add cache hit rate metric
**Success Criteria:**
- [ ] Cache pre-populated on service start
- [ ] Cache hit rate ≥ 30% for first 100 queries
**Evidence:** `/metrics` shows cache_hit_rate

### Task 2.4: Progressive Disclosure Response Time
**Status:** pending
**Tooling:** `Read` progressive_disclosure.py, profile with `time`
**Action:**
- Profile discovery endpoint response times
- Optimize collection info fetching (parallel queries)
- Add response time metric
**Success Criteria:**
- [ ] `overview` level < 100ms
- [ ] `detailed` level < 300ms
- [ ] `comprehensive` level < 800ms
**Evidence:** `curl -w "%{time_total}"` measurements

### Task 2.5: Context Compression Validation
**Status:** pending
**Tooling:** `Read` context_compression.py, `Bash` for testing
**Action:**
- Verify compression ratio meets target
- Test decompression accuracy
- Ensure episodic memory retention
**Success Criteria:**
- [ ] Compression ratio ≥ 3:1
- [ ] No information loss in critical fields
**Evidence:** Test script output

---

## Phase 3: COSMIC Desktop Polish (Gate: Boot-to-Usable < 15s)

**Objective:** Finalize COSMIC DE configuration for production use.

### Task 3.1: cosmic-greeter Theming Verification
**Status:** pending
**Tooling:** `Read` desktop.nix, visual inspection
**Action:**
- Verify cosmic-greeter starts correctly
- Check theme consistency across monitor configurations
- Test multi-monitor login scenario
**Success Criteria:**
- [ ] Greeter displays on all monitors
- [ ] Theme matches COSMIC default/custom theme
**Evidence:** Screenshot or manual verification

### Task 3.2: XDG Portal File Picker Testing
**Status:** pending
**Tooling:** Flatpak app testing, `Bash` for xdg-desktop-portal status
**Action:**
- Test file picker in a Flatpak app (Firefox, etc.)
- Verify portal backend chain: COSMIC → Hyprland → GNOME
- Check screenshot/screencast portals
**Success Criteria:**
- [ ] File picker opens native COSMIC dialog
- [ ] Screenshot portal functional
**Evidence:** Manual test log

### Task 3.3: PipeWire/wireplumber Stability
**Status:** pending
**Tooling:** `Read` desktop.nix, `systemctl status` checks
**Action:**
- Verify libcamera monitor disabled
- Test USB webcam via V4L2 path
- Check PipeWire service stability over 24h
**Success Criteria:**
- [ ] No wireplumber crashes in journal
- [ ] USB webcam works in apps
**Evidence:** `journalctl -u wireplumber --since="24 hours ago" | grep -i error` clean

### Task 3.4: Suspend/Resume with llama-server
**Status:** pending
**Tooling:** `Bash` for suspend test, service status checks
**Action:**
- Test system suspend/resume cycle
- Verify llama-server recovers or restarts cleanly
- Check GPU re-initialization
**Success Criteria:**
- [ ] System resumes without hang
- [ ] llama-server healthy after resume
**Evidence:** Test cycle log

### Task 3.5: Flatpak Duplicate Prevention
**Status:** pending
**Tooling:** `Read` desktop.nix, check launcher
**Action:**
- Verify user-scope-only Flatpak installation
- Check COSMIC launcher for duplicates
- Validate XDG_DATA_DIRS handling
**Success Criteria:**
- [ ] No duplicate app entries in launcher
- [ ] Flatpak apps appear once
**Evidence:** Screenshot of launcher

---

## Phase 4: Documentation & Packaging (Gate: Runbook Complete)

**Objective:** Prepare system for external deployment and operator handoff.

### Task 4.1: OpenAPI Spec Generation
**Status:** pending
**Tooling:** FastAPI automatic docs, `Write` for spec file
**Action:**
- Enable FastAPI `/openapi.json` on hybrid-coordinator
- Generate spec for aidb server
- Validate specs with swagger-cli
**Success Criteria:**
- [ ] `/openapi.json` returns valid schema
- [ ] All endpoints documented
**Evidence:** Saved openapi.json files

### Task 4.2: Architecture Diagrams
**Status:** pending
**Tooling:** Mermaid/D2 in markdown, `Write` for diagram files
**Action:**
- Create service topology diagram
- Create data flow diagram for PRSI loops
- Create memory architecture diagram
**Success Criteria:**
- [ ] 3 diagrams in docs/architecture/
- [ ] Diagrams render correctly in GitHub
**Evidence:** Files committed

### Task 4.3: Operator Runbook
**Status:** pending
**Tooling:** `Write` for markdown, consolidate from existing docs
**Action:**
- Document common failure modes and recovery
- Include escalation procedures
- Add monitoring setup guide
**Success Criteria:**
- [ ] Runbook covers: service restart, secret rotation, backup/restore
- [ ] TOC with quick navigation
**Evidence:** `docs/operations/OPERATOR-RUNBOOK.md` exists

### Task 4.4: Skill Bundle Packaging
**Status:** pending
**Tooling:** `Read` existing skills, `Bash` for packaging test
**Action:**
- Package slash commands as distributable bundle
- Create installation script
- Document customization points
**Success Criteria:**
- [ ] Bundle installable via single command
- [ ] Skills functional after install
**Evidence:** Fresh install test passes

### Task 4.5: Final Validation Suite
**Status:** pending
**Tooling:** `Bash` for test runner
**Action:**
- Run full validation suite
- Generate coverage report
- Document any known limitations
**Success Criteria:**
- [ ] All quality gates pass
- [ ] Coverage report generated
**Evidence:** Test output log

---

## Quality Gates Summary

| Phase | Gate | Validation Command |
|-------|------|-------------------|
| Phase 1 | Security audit clean | `scripts/testing/check-api-auth-hardening.sh && scripts/testing/test-prompt-injection-resilience.sh` |
| Phase 2 | Eval score ≥ 0.7 | `scripts/ai/aq-report --since=7d --format=text \| grep "mean_score"` |
| Phase 3 | Boot-to-usable < 15s | Manual timing from power-on to desktop |
| Phase 4 | Runbook complete | File existence + TOC validation |

---

## Commit Protocol

After each significant task completion:

```bash
# Stage specific files
git add <modified-files>

# Commit with task reference
git commit -m "$(cat <<'EOF'
<phase>.<task>: <brief description>

- <change 1>
- <change 2>

Evidence: <validation output or reference>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Execution Start

Begin with Phase 1, Task 1.1. Mark task in_progress and proceed.
