# AppArmor "already present" shortcut: real-profile-only parser (2026-10-29)

## Objective
Close Codex security finding 1 on #651 (review codex-20261029-122736-h8960s): `_apparmor_rules_already_present` in `scripts/ai/aq-approve` reported a rule as present when it appeared only in a Nix block comment holding a decoy `security.apparmor.policies."x"` block, or in an `extraConfig` string, so the executor was skipped and the alert archived as approved. The shortcut now returns True only for effective lines inside the real, non-commented `profile = ''...''` string of the single target header; every uncertain case returns False so the executor runs and validates.

## Workflow/Session IDs
- Codex review: codex-20261029-122736-h8960s
- Worktree/branch: `.agents/delegation/worktrees/apparmor-present-parser`, `fix/apparmor-present-parser` (base origin/main e8c4218d)

## Delegation Decision
Bounded single-file fix plus tests, implemented by Claude Sonnet (cheapest eligible Claude lane, Rule 17). Finding raised by Codex; Codex was over budget and could not implement. Not committed by the implementer.

## Commands Executed
- `python3 scripts/testing/test-apparmor-fix-agent-safety.py`
- `python3 scripts/testing/test-apparmor-fix-agent-generalization.py`
- Red run: same safety test against `git show HEAD:scripts/ai/aq-approve` copied to a scratch tree.
- Sanity run of the new parser against the real `nix/modules/services/mcp-servers.nix` (lexes cleanly; `ai-hybrid-coordinator` and `command-center-dashboard-api` report `deny /home/** wx,` present, a nonexistent rule absent).

## Validation Evidence
- Red on old code (3 failures): test_present_block_commented_decoy_profile_not_present, test_present_rule_only_in_extraconfig_not_present, test_present_duplicate_header_or_string_header_not_present.
- Green on fix: safety suite 13 tests OK; generalization suite 6 tests OK. Existing positive case (real rule in real profile is present) retained.
- Mechanism: a small Nix lexer separates code from `#` and `/* */` comments and from `""`/`''` strings (with `${}` nesting). The header must be real code, start its line, and occur exactly once; the body is the first top-level `''` string directly preceded by `profile =` before any other policies header. Malformed lexing returns False.

## Rollback Plan
Revert the commit; `aq-approve` returns to the line-based parser. The executor path is unchanged and still validates rules, so rollback only reopens the false-"present" shortcut.

## Residual Risk
- The shortcut now returns False in more situations (duplicate headers, unusual structure), costing an executor run; this is the intended fail-safe direction.
- The lexer is not a full Nix parser; exotic constructs (for example a `profile` attribute produced by a function call) yield False, not True.
- Prefix and double-quoted profile probes still invoke the executor (unchanged, safe).

## Hint Feedback
Facts only: implementer Claude Sonnet; finding by Codex; Codex was over budget so the fix was routed to Claude. The old extraConfig probe alone did not fail on the old code when extraConfig preceded the profile; the red case that does fail is a profile closed inline (`... wx, '';`) followed by extraConfig.
