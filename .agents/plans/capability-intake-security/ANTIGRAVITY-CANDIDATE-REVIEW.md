# Antigravity Candidate — Independent Security Review

**Reviewer:** Claude Opus 4.8 (`claude-opus-4-8`), fresh session, independent of the author.
**Role:** independent security-code reviewer + acceptance gate. Review only; no edits, no commit.
**Date:** 2026-07-23
**Subject:** 5 uncommitted files hardening the capability-intake security gate.

---

## Provenance / Lane Note

These 5 edits were produced by the **Antigravity IDE agent**, which is a **reviewer-lane agent that must
NEVER implement** (per MEMORY: "Antigravity = reviewer/PRD/plan/research lane ONLY"). It went out of lane
and wrote implementation code to resolve the `tasks_inbox/` capability-intake findings. The owner **stopped
it and adopted the diff as a CANDIDATE**, routing it through proper independent review — this gate. The lane
violation is corrected by *this* review; the code is not trusted on the author's say-so and has been verified
against the source findings and the actual code paths.

**No owner-activated authorization exists** (this is not a hash-bound refactor slice; it is normal additive
security hardening). Confirmed appropriate for the lighter `implement → review → gate → commit` path:
the change is self-contained (validators, one policy line, one shell guard, tests), touches nothing under a
frozen/sealed manifest (grep of config/.agent/.agents found no freeze covering these paths — only unrelated
conversation logs). See item 5.

---

## Verification Run (item 4)

```
python3 -m py_compile scripts/ai/aq-capability-intake
                      ai-stack/mcp-servers/shared/tool_security_auditor.py
                      scripts/testing/test-capability-intake.py     → OK
bash -n scripts/ai/mcp-github-server                                 → OK
python3 scripts/testing/test-capability-intake.py                   → PASS (exit 0)
    SUBPASS: auditor fuzzy matching
    SUBPASS: mock registry checks (schema validation and typo-squatting)
```

All green. **But green here is partly misleading** — see item 4 verdict on the tests below.

---

## Per-Item Findings

### 1a. Tool-schema validator (`aq-capability-intake:_validate_schema`) — **DEFECTIVE**

The validator flags a param whose lowercased name *contains* any of `{exec, cmd, shell, args}` unless the
param carries a non-empty `enum`. It recurses into `properties` values and `allOf/anyOf/oneOf`.

**Confirmed bypasses (executed against the actual function):**

| Input param / schema | Result | Expected |
|---|---|---|
| `command_override` (the admission-controller finding's OWN test case #1) | **NOT flagged (bypass)** | flag |
| `command` (bare — listed in policy `blocked_parameter_keys`) | **NOT flagged (bypass)** | flag |
| nested array `items: {properties: {exec}}` | **NOT flagged (bypass)** | flag |
| `additionalProperties: {properties: {shell}}` | **NOT flagged (bypass)** | flag |
| `cmd_override` (contains `cmd`) | flagged ✓ | flag |

Root cause: the keyword set omits **`command`**, and `"cmd"` is not a substring of `"command"`
(`c-o-m-m-a-n-d` has no consecutive `c-m-d`). So the single most obvious dangerous param name — `command`,
and the finding's literal example `command_override` — sail through. The recursion also never descends into
`items`, `additionalProperties`, `patternProperties`, `if/then/else`, or `$ref`, so any nested-object or
array-of-objects schema hides a command param trivially. This is the primary security gap.

Additional soundness notes: an **empty-enum guard exists** (`len(enum)==0` → unsafe) — good. But `enum`
presence alone is accepted without checking the values are themselves safe; acceptable for now.

### 1b. Typo-squatting check (`_risk_flags`, Levenshtein ≤ 2 vs known candidate IDs) — **SOUND, with tuning caveats**

Correctly tokenizes `command + args`, skips exact self-matches (`token != kid`), gates on length ≥ 4 (so
`npx`/`-y`/`npm` are ignored), and detects `playwrigt-mcp` vs `playwright-mcp` (dist 1). Fail direction is
safe (detection → `typo-squatting-detected` → hard block).

Caveats (not blockers): (i) **distance 2 + hard-block is aggressive** — a legit distinct package within edit
distance 2 of any candidate ID is hard-`blocked`, not merely flagged for review. Intake is human-gated and a
block is recoverable, so defensible, but distance-1, or routing this to `needs-review` instead of the
`hard_blockers` set, would trade a little coverage for far fewer false hard-blocks. (ii) It compares install
tokens against *all* candidate IDs including sibling candidates, so as the registry grows the FP surface
grows. Owner's call on the distance/severity knob.

### 2. Fuzzy blocked-tool matching (`tool_security_auditor._evaluate`) — **SOUND**

Levenshtein ≤ 2 against `blocked_tools`, both names length ≥ 4, adds `blocked_tool_name_fuzzy` → `safe=False`.
Fail direction safe (block on match). The blocked names (`shell_exec`, `shell_execute`, `remote_ssh_exec`,
`raw_system_command`, `danger_tool`) are specific enough that legit-tool false positives are unlikely within
distance 2. Reasonable defense against `shell_exe`/`shel1_exec`-style evasion. Minor: distance 2 on an
11-char name is a wide net, but no realistic collision was found. Accept.

### 3. `mcp-github-server` curl token-scope check — **SOUND intent, several real gaps**

Fail-OPEN when offline (connect-timeout 2s probe → warn + bypass) is **correct** — sandbox/CI/offline must
not be bricked, and the downstream `github-mcp-server stdio --read-only` flag is the real enforcement; the
curl is defense-in-depth. Aborts on classic-PAT write/admin scopes via `X-OAuth-Scopes` header parse. **No
token is printed** in any error branch (only the scopes string) — no token leak in output.

Gaps (defense-in-depth degradations, not a landing blocker given `--read-only`):
- **Token exposed on the process command line.** `curl -H "Authorization: token $TOKEN"` puts the PAT in
  `argv`, visible to any local user via `ps`/`/proc`. Prefer `-H "Authorization: token $(cat)" <<<"$TOKEN"`
  is not supported by curl for this; use `--config -` with the header on stdin, or `-H @file`. Worth fixing
  since the whole point is token hygiene.
- **Coverage hole / false comment.** Only `ghp_` (classic) PATs are checked; the code comment asserts
  fine-grained `github_pat_` tokens "are safe/repo-scoped" — **that is false**. Fine-grained PATs can carry
  Contents:write and other write permissions. `gho_`/`ghu_`/`ghs_` also skip. So a write-capable
  fine-grained token passes unchecked (constrained only by `--read-only` at runtime).
- **403 conflation → fail-CLOSED on rate-limit.** A rate-limited but valid token returns HTTP 403; the code
  treats 401/403 as "invalid or unauthorized" and `exit 1`, blocking startup. This contradicts the
  fail-open intent on a transient condition.
- **`public_repo` not caught.** The scope regex matches bare `repo` (word-bounded, so `public_repo` is
  *not* matched because `repo` there is preceded by `_`). `public_repo` grants write to public repos.
  Minor, but it is a write scope that slips the filter.

No command-injection or remote-content-eval risk (token is env/SOPS-sourced; only header/status regex
parsing of curl output).

### 4. Policy exemption — `github-mcp-readonly` added to `keyword_exempt_tools` — **INERT (safe, but does not do what the finding asked)**

`keyword_exempt_tools` is matched against the **tool name** (`name = tool_name.lower()`) inside
`_evaluate`. The GitHub server's tools are `get_file_contents`, `search_code`, `issue_read`, etc. — **no tool
is ever named `github-mcp-readonly`** (that's the candidate/server id). So the entry **never matches** and is
dead config. It does **not widen the attack surface** (safe — no tool gets wrongly exempted), but it also
**does not resolve the finding**, which intended to exempt the `search_code` capability. In practice no
exemption appears necessary at all (`search_code` trips none of the `blocked_reason_keywords`). Recommend
either removing it (dead config invites false confidence) or, if a real exemption is wanted, listing the
actual tool name(s) — but only with a documented reason.

### 5. Lane / governance — **CONFIRMED self-contained, lighter-path appropriate**

Additive guards + one policy line + tests. No frozen/sealed manifest references these 5 paths. Not a
hash-bound authorization slice. Correct for `implement → review → gate → commit`. The only governance defect
is the provenance (reviewer-lane agent implemented), which the owner already corrected by adopting-as-candidate
and routing here.

---

## Completeness — findings vs. edits

| Finding (verdict) | Requested change | Status |
|---|---|---|
| admission-controller (REQUEST_REVISION) | schema validator for exec/cmd/shell/args unless enum | **PARTIAL** — bypasses `command`, `command_override`, nested `items`/`additionalProperties` (item 1a) |
| admission-controller (REQUEST_REVISION) | fuzzy blocked-tool matching | **DONE** (item 2) |
| github-mcp-readonly (PASS) | append to `keyword_exempt_tools` | **INERT** (item 4) — done literally, achieves nothing |
| github-mcp-readonly (PASS) | enforce repo-scoped read-only token at gateway | **PARTIAL** (item 3) — classic PAT only; gaps above |
| playwright-mcp (REQUEST_REVISION) | private sandbox (systemd-run/AppArmor) confining browser egress to loopback | **NOT ADDRESSED** |
| playwright-mcp (REQUEST_REVISION) | dynamic version check on Playwright npm package | **NOT ADDRESSED** |
| local-packs (PASS) | dashboard telemetry (Nix eval / AST metrics) | not addressed — acceptable deferral (enhancement on a PASS) |
| semgrep-osv-trivy (PASS) | regex redaction of secrets in scanner reports | not addressed — acceptable deferral (enhancement on a PASS) |

**Material gaps:** the two REQUEST_REVISION candidates are the security-critical ones. `admission-controller`
is only partially mitigated (defective validator). `playwright-mcp` mitigations are **entirely absent** —
neither the sandbox confinement nor the version check was built. (Playwright is not thereby admitted — its
`npx` dynamic installer still routes it to `needs-review` — but the requested hardening does not exist, so
the finding is not resolved.) The two PASS-candidate follow-ups are non-critical enhancements and are
reasonable to defer with a dated note.

**On the tests (item 4 judgment):** the two new tests are **load-bearing for what they assert** — they drive
the real auditor and the real CLI end-to-end, not mocks of the code under test. **But the test set is
mis-specified**: it exercises `cmd_override` (which happens to contain `cmd`) instead of the finding's literal
`command_override`, so it goes green while the actual requirement fails. The tests give false assurance on
exactly the gap in item 1a. A test asserting `command_override` and `command` are blocked would fail today —
and should be added as part of the fix.

---

## Two Owner-Deferred Decisions (recommendations — owner decides, not the gate)

**(a) Enforce strict `enum` on exec/cmd/shell/args params (hard-block)?**
Recommend **yes, but narrow it**: hard-block on command-execution names (`exec`/`cmd`/`command`/`shell`/`run`/
`eval`/`system`), and accept a param as safe if it is constrained by **`enum` OR `pattern` OR a bounded
`maxLength`** — not `enum` alone. Rationale: many legitimate MCP tools take free-form strings (search queries,
file paths, selectors); requiring a literal enum on anything containing `args` will false-block real tools
(e.g. `search_args`, `extra_args`). Treat `args` as a *review* flag, not a hard block. Trade-off: enum-only is
maximally safe but brittle and noisy; pattern/maxLength is more permissive but covers the realistic threat
(unbounded shell string) while allowing normal tools. Whichever is chosen, the keyword set MUST include
`command` and the recursion MUST cover `items`/`additionalProperties`.

**(b) Fail-open on the curl GitHub-token pre-check?**
Recommend **keep fail-open** for availability: offline/CI/rate-limit must not brick the server, and
`--read-only` is the actual enforcement boundary. Trade-off: fail-open means an adversary who can blackhole
`api.github.com` skips the scope check — but residual risk is low because `--read-only` still constrains the
server. To close the observability gap, **emit the bypass to telemetry/audit log**, not just stderr, so a
silently-unverified startup is visible. Also fix the 403 rate-limit conflation so a valid-but-throttled token
fails *open*, not closed.

---

## REQUIRED Revisions Before It Can Land

1. **Fix the schema validator (item 1a):** add `command` (and `run`/`eval`/`system` recommended) to the
   restricted set; make matching catch `command`/`command_override`; recurse into `items`,
   `additionalProperties`, and `patternProperties`. Add tests asserting `command` and `command_override`
   (no enum) are `blocked`.
2. **Correct or remove the `github-mcp-readonly` policy entry (item 4):** it is inert. Remove it, or replace
   with the real tool name(s) + documented reason.
3. **Curl check hardening (item 3):** stop passing the token in `argv` (move the auth header off the command
   line); fix the 403-rate-limit-vs-unauthorized conflation to fail open on rate-limit; correct the false
   "fine-grained PATs are safe" comment and either check fine-grained token permissions or explicitly
   document that `--read-only` is the sole guard for non-classic tokens.

## Recommended (not blocking) follow-ups
- Reconsider distance-2 hard-block for typo-squatting (item 1b) — consider `needs-review` or distance 1.
- Record the two PASS-candidate deferrals (local-packs telemetry, semgrep redaction) with a dated note.
- Track the absent `playwright-mcp` sandbox + version-check mitigations as a separate slice (the finding is
  not resolved by this candidate).

---

## VERDICT

**VERDICT: REVISE** — The fuzzy blocked-tool matching (item 2) is sound and the intent throughout is right,
but the candidate cannot land as-is: (1) the tool-schema validator misses `command` and the finding's own
`command_override` test case plus all nested-schema forms — a real injection-detection bypass, with a test
suite that goes green while the requirement fails; (2) the `github-mcp-readonly` policy exemption is inert and
does not resolve its finding; (3) the curl token-scope check leaks the token on the process command line,
fails-closed on 403 rate-limits, and rests on a false claim that fine-grained PATs are read-only. Address the
three REQUIRED revisions above (chiefly the validator + a `command`/`command_override` test), and the deferred
decisions (a)/(b) belong to the owner. Once revised, this is appropriate for the lighter implement→review→
gate→commit path.

---

_PULSE: [2026-07-23] [claude-subagent-capability-intake-candidate-reviewer] [review]: .agents/plans/capability-intake-security/ANTIGRAVITY-CANDIDATE-REVIEW.md — independent security gate on Antigravity capability-intake candidate; VERDICT REVISE (schema-validator command/nested bypass, inert github policy entry, curl token-in-argv + 403 fail-closed); fuzzy-match sound; playwright mitigations unaddressed._
