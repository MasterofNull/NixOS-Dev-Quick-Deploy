CONCERNS

Reviewer: `Simurg@claude/claude-sonnet-5-5#claude-20261113-184611-57y8dl` (independent review seat; author lane = gemini)

Q1 is approved with one change. Q2 and Q3 need tightening before the design freezes.

**Q1 (2,500-token ceiling plus <=400-token exemplar): yes, with one change.**
- Make the 400-token exemplar budget part of the 2,500 total, not an addition to it. Otherwise the effective ceiling quietly becomes 2,900.
- Log every degradation from full symbol bodies to signatures as a measured event. Otherwise nobody can tell whether the ceiling is starving the model of context.
- Define how "closest" is measured. If it is embedding similarity, the exemplar choice depends on a neural step, which conflicts with the CPU-only System 1 principle. Use deterministic path/AST-symbol/lexical overlap instead.

**Q2 (CPU routers, gated neural tasks): yes, with two fixes.**
- A `0.70 * cpu_count` 1-minute loadavg threshold is unstable on a 27GB laptop; a single indexing burst will flap the gate. Use a 5-minute load average (`loadavg[1]`) with hysteresis (enter pause at `0.70`, exit at `0.55`).
- Don't call CPU routers "unconditional" without a hard ceiling on their own cost (`<= 20ms` timeout and skip above `90°C`).
- Battery `>= 50%` is fine. Say explicitly what happens to queued neural tasks while gated: background jobs defer, and active slice tasks route to a healthy Tier-2 subscription lane—never drop silently.

**Q3 (redact and normalize before staging): yes, with a fail-closed post-redaction gate.**
- `redact_secrets` is pattern-based and can miss novel secret shapes. Add a fail-closed post-redaction scan (high-entropy / credential-assignment check) across `context_packet`, `rejected_attempts`, `verified_diff`, and `review_receipt`. Any hit quarantines the tuple instead of writing to `trajectories.jsonl` or `upstream-reciprocity/`.
- Keep the owner-asks-in-CLI step before external publication as a hard gate that nothing can bypass.
