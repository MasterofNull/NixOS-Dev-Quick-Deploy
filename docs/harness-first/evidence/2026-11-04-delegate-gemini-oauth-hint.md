# Delegate-to-gemini failure hint points to OAuth (2026-11-04)

## Objective
When Gemini reports the sunset error, the `scripts/ai/delegate-to-gemini` failure branch (~L463) told the user to `export GEMINI_API_KEY`. That contradicts the OAuth-only policy (owner, 2026-10-17). The hint now says two things. To re-authenticate, run `gemini` and sign in with Google. On a quota or capacity error, retry later or pass a different `--model`.

## Workflow/Session IDs
- Branch: `fix/delegate-gemini-oauth-hint`, from `origin/main` (2055db6b).
- Backlog item closed: DELEGATE-GEMINI-API-KEY-HINT.
- Opened: DELEGATE-GEMINI-HELP-AUTH-NOTE-STALE. The usage-text AUTH NOTE (~L178-186) still describes API-key auth. It needs the live auth path verified before a rewrite, so it was kept out of this slice.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Haiku. This was a mechanical single-file edit with a checkable result (Rule 17).

## Commands Executed
- `bash -n scripts/ai/delegate-to-gemini`
- `python3 scripts/testing/test-delegate-wrapper-shell-safety.py`

## Validation Evidence
- `bash -n` passes.
- The shell-safety test passes (ALL PASS, 11 checks).
- The diff is 1 file, +2/-1, and only changes text in `info` lines. Stream and indentation are unchanged.

## Rollback Plan
Revert the commit. The change is text only.

## Residual Risk
None in behavior. The branch cannot tell an auth failure from a quota failure, so it prints both hints.

## Hint Feedback
No hints were consulted.
