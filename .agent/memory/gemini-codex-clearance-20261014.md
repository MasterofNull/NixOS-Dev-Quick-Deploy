# Gemini/Codex clearance — 2026-10-14

Baseline origin/main: 29d5fcd2d8acbbcf10bebe3da7bd834ccd8b8e2b. Original checkout is dirty on DP3; preserved. Audit in isolated /tmp/gemini-codex-clearance-20261014.

Prior Codex Oct11 audit already cleared scoped governance, reaper/PRM and the N2 packaging repair through PR485/487; do not manufacture a new review of those changes. N2 live activation remains deferred.

DP2: reproduced duplicate external mutation after ambiguous callback failure (2 callbacks for one idempotency key). Bounded repair claims states legally and blocks unresolved or concurrent replay; independent review pending. Live spawn integration and authoritative recovery of abandoned EXECUTING intents remain unimplemented.

DP1 cursor repair 8c070b6 is not merged: break on throttled entry preserves the global cursor; throughput may block later sources. Independent review and integration pending.

DP3 PR506 head 7f9ef0f4fdcf9d9425e08975a975bbd3ee7391a8: independent reviewer /root/review_dp3 REQUEST_REVISION. Proof-string PASS and PR_STAGED/RESOLVED have no real reviewer/PR; isolation falls back to plain directory; incident shell runs unconfined; concurrency and dedup absent; async route runs blocking Git; heartbeat is fabricated from state. No acceptance or deployment.

DP4: guidance only persists a spool with no consumer but reports injected, even on write failure. Bounded truthful-status repair underway in separate worktree. Live steering is deferred pending consumer acknowledgment contract.

Focused baseline checks: durable 7/7; Pi UI 5/5 (leaked aiohttp session warning); training pipeline 3/3; RSI OSI trigger 5/5. Tests are not proof of activation or complete independent review.

Branch clearance uses raw subprocess records and return codes. Compressed output previously yielded wrong counts; corrected inventory is being recorded. Preserve unique commits/stashes and original dirty checkout. No branch deletion yet.
