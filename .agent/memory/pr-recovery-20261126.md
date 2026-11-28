# PR877/878 recovery — 2026-11-26

Root cause: three required hosted contract tests were missing from the focused local validation registry. PR877 needed explicit ownership of its new tier0 gate. PR878 needed the standard usage hook and durable-plan classification. Existing tests catch these defects; reuse them locally.

PR877: local mutation suite 37/37; repaired hosted manifest job passed; all completed hosted checks pass, including closure scan; Build & Package skipped. PR878: ca92895 repairs both files; real usage and plan suites pass, independent Gemini run gemini-20261126-114137-issz2s has persisted PASS output and verified receipt; tier0 71/0; pushed; hosted code/security/manifest checks pass; closure scan is pending. Review disposition correctly rejected a receipt bound to d8ff255 instead of committed repair ca92895. Committed-head review gemini-20261126-121334-j8vuor passed and receipt pr878-ca92895b42df.json was published on review-receipts. The PR body still needs to bind that receipt instead of its old reviewed-head field; prior output alone cannot authenticate a changed commit.

Shared learning verified: MemoryBroker recall returned memory 5d8cae59-47a0-49a4-8f3a-d2588a7aea06 for PR-RECOVERY-20261126-877-878. Existing RAG embedding/upsert helper seeded one deterministic lesson per collection with wait=true, then retrieved each ID and verified lesson_id:
- error-solutions: d7e9cb81-9639-5c78-b9c0-ea02a25d73b2
- best-practices: 7d71733b-ed6b-5261-a190-1d5244e1dbcf
- skills-patterns: f5b46d54-6044-5caf-bd0c-26473299fe57

Prevention slice: real producer regressions, hosted manifest ownership and staged Python checks pass; full tier0 passed 73/0. Independent Gemini gemini-20261126-122124-x6j0gj passed the frozen staged code, including clean and poisoned Git-environment regressions. Activation is pending landing; no rebuild is needed for these repository validation registrations. Separate review-output producer patch has focused passing tests but full-gate blockers. See issues-backlog.md and WORKAROUND-REGISTER.md; no manufactured gate or review success.
