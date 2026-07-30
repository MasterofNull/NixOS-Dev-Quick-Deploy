# Collaborative Round — c4-review

Opened: 2026-07-30T16:03:22Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C slice C4 (network profiles / connected
zero trust). Read-only. DESIGN review. ENFORCEMENT-TIER (build needs owner activation). Highest bar.
Substitute for codex (down to Aug-4; confirmatory on return). VERIFY against real code/system.
READ: .agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md; the C3b runner it extends
(ai-stack/switchboard/execution_cell_runner.py — bwrap --unshare-net); DESIGN-PACKET.md §5; ports in
nix/modules/core/options.nix. GROUND: confirm slirp4netns/pasta absent + nft present + runner has
empty caps (the §2 constraint the whole design rests on).
JUDGE (§9): 1. the cell truly has ZERO ambient net (--unshare-net retained); the egress-broker UDS is
the SOLE egress; NO fail-open. Is the broker-over-UDS mechanism sound given no slirp4netns, or is
there a hole? 2. threat pass soundness — is the closed 6-profile set {local-inference:8080,
embed:8081, coordinator:8003, AIDB:8002+Qdrant:6333, switchboard-remote-OAuth:443, MCP-github:443}
correct? Are the COLLAPSES right (A2A-inbox=file/no-net, telemetry=local/no-net) and the DEFER right
(playwright broad egress != closed profile)? Is any wildcard/broad egress representable (must not be)?
3. NO API key handled/forwarded; NO silent alternate-provider (OpenRouter) reroute; switchboard-remote
allows ONLY the intended provider host; OAuth/gh use their OWN sessions (broker gates host:port+TLS
only, never injects a credential). 4. signed-profile authoritative; config/network-profiles.json
compare-only DENY (never grant); subset attenuation. 5. broker hardening (empty caps,
RestrictAddressFamilies, egress-logging) + runner/switchboard byte-parity + flag default-OFF. 6.
deny-closed on policy/key-unavailable; egress audit low-cardinality/secret-free. Weigh Q-C4-1..4.
Any NEW fail-open, ambient-net leak, key leak, or reroute?
OUTPUT: `VERDICT: PASS`/`FAIL`/`REQUEST_REVISION` line 1, then findings by severity + §ref + fix, +
Q-C4-1..4 verdicts. No outcome authorizes build or activation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c4-review.md` and writes `antigravity.md`. No API keys.
