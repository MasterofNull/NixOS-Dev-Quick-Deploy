# Frontier adoption 2026-11-18: goals, metrics and follow-up verification

Owner directive, 2026-11-18: "follow all the recommendations and schedule a follow-up after we start getting real data and system impacts, so we can verify that they are meeting, completing and/or exceeding the intended goals."

Rule: each item is reviewed **14 days after it is ON** (Rule 15: integrated, ON, validated), and no earlier than once it has real data. The review records MET, EXCEEDED, NOT MET or INCONCLUSIVE with the measured number. NOT MET triggers a root-cause slice or a rollback decision put to the owner. The global checkpoint is **2026-12-02** (`aq-frontier` + this file), and later checkpoints come every 14 days until every item has a verdict.

Baselines were measured on 2026-11-18, from .agents/delegation/outputs.

| # | Item (frontier id) | Goal | Metric (source) | Baseline 2026-11-18 | Target |
|---|---|---|---|---|---|
| 1 | Constrained decoding (fe-2ab16cb00ee3) | Machine-read local outputs are always well formed | local runs with format failure, TRUNCATED or a parse error, as a share of machine-read local runs (registry.jsonl status + output parse) | format-failure rate 0/27 (0.0%): of 33 machine-read local runs (role=reviewer or verdict/JSON-demanding prompt) in registry.jsonl whose output file survives, 27 finished and all carried a valid Review-Disposition line; 0 of 154 surviving local outputs contain TRUNCATED. The other 6 of 33 (18.2% any-failure) were timeouts, context-limit refusals or agent-loop exits, none a format failure. Caveat: 253 of 286 machine-read runs have no surviving output, so the sample is small (method: evidence file 2026-11-18-constrained-decoding.md) | at most 1% format failures; no new TRUNCATED on schema runs |
| 1a | grammar + ignore_eos guard (llama.cpp b12489) | No caller sends grammar/json_schema together with ignore_eos | regression test + rg over payload builders | 0 `ignore_eos` occurrences in source before this slice (rg, 2026-11-18); the helper and build_llama_payload now strip it next to a schema | 0 occurrences; test in CI |
| 2 | Owned-path merge gate (lanes-owned-scope-gate) | No cross-lane overlap ever merges | aq-land refusals logged; merged PRs with files outside the brief's owned paths | manual coordination only | 0 out-of-scope merges; at most 1 false refusal per 20 lands |
| 3 | Checks command in the brief (yt-checks-over-plans-goal) | "Done" is test-proven; fewer review rounds | share of briefs with a checks field; aq-land review rounds per branch | rounds mean 1.83 / median 1 (n=63) | 100% of briefs; mean rounds at most 1.5 |
| 4 | Token caps + stop condition (lanes-token-caps-in-brief) | Same throughput for fewer tokens | codex headless tokens per landed PR (budget logs); local prompt chars per task | Codex hit 1.5M/24h on 2026-11-14/15 for about 9 PRs | at least 20% fewer tokens per landed PR, with no rise in rounds |
| 5 | Skill eval + prune (yt-skill-eval-prune) | Load only skills that help | skill count; session-start context tokens; eval with vs without | 65 skills | at least 30% fewer with no eval regression |
| 6 | LLM01 boundary audit (fe-a2a4a2caa18a) | Every LLM-output to shell/Nix/disk boundary is validated | audited boundary list; open findings | p2a only | 100% enumerated; 0 open findings |
| 7 | systemd egress limits (FE-8) | Untrusted units are pinned to the network they need | units with IPAddressDeny/RestrictAddressFamilies; journal denials; unit health | 0 units | all MCP/untrusted units restricted; 0 unexpected denials; 0 health regressions |
| 8 | Functional eval metric (FE-2a) | A non-saturated, reproducible quality metric exists before any prompt optimizer | metric score spread; repeat-run variance | the earlier baseline was ceilinged | baseline below 90%, variance at most 3 points; it gates the FE-2b start |
| 9 | Hook smoke test (Claude Code 2.1.326 hook semantics) | Our PreToolUse hooks still block and rewrite correctly | the smoke test result | not run | PASS recorded |
| 10 | llama.cpp b12498 slot fix | Pin includes it if our arch needs it | flake.lock rev vs b12498; slot errors in the llama journal | not checked | decided at the next scheduled rebuild |
| 11 | arXiv memory/verifier papers (local slice) | One-line takeaways inform P3/F3 | takeaways file | none | written; at most 1 adopted follow-up |
| 12 | lean-ctx shell_security (owner one-liner + Nix) | Agent harness tools are never blocked | BLOCKED lines in hook output and agent logs | blocked: aq-pin-watch, aq-update --dry-run, systemctl status, nixos-version, bash scripts | 0 harness-tool blocks |
| 13 | Activation of developed features (activation-audit-20261118.md) | Every merged feature is ON or carries a dated deferral | the audit table's ON column | measured in the audit | 100% ON or deferred |

Closed items (no work; re-check trigger): FE-4 (dense-model switch), FE-5 (native 30B+ ternary), FE-9 (in llama.cpp), FE-3 (A2A v1.x), FE-10 (external trace viewer; Claude Code OTel events noted), FE-1 (folded into F3), lanes-as-dependency, yt-claudemd-index (satisfied).
