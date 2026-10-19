# Evidence — prompt registry eval refresh (2026-10-14 scores) — 2026-10-19

The prompt-eval job rewrote `mean_score` / `last_evaluated` in `ai-stack/prompts/registry.yaml` on 2026-10-14 directly in the primary checkout, which blocked owner deploys (deploy guard: uncommitted build-affecting tracked change; backlog DEPLOY-SOURCE-DRIFT). The change was set aside in stash `b112889f` and is landed here via PR so it deploys from main.

## Change
- 8 lines: `last_evaluated` 2026-09-30 -> 2026-10-14 on evaluated prompts; `gap_detection_score` mean_score 1.000 -> 0.667. No prompt text or template changed.

## Validation
- YAML parses; only `mean_score` / `last_evaluated` lines differ (independent reviewer check).

## Review
Author-lane claude (packaging the eval job's output). Independent review: gemini agent CLI (antigravity lane) PASS.

## Follow-up
Root cause (runtime job writing a tracked file in the primary checkout) is tracked in `.agent/memory/issues-backlog.md` DEPLOY-SOURCE-DRIFT; the fix is to move eval scores to a runtime state path or land them via PR automatically.
