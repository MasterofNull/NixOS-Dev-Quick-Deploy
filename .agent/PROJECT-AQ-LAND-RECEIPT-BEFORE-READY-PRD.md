# Publish the review receipt before marking a pull request ready

PR #864 exposed a publication ordering gap. GitHub allocates the pull request
number during creation and the receipt binds to that number. A ready pull
request could therefore become visible to reviewers before the binding receipt
was available.

The landing command will allocate new pull requests as drafts. After publishing
the receipt, it must verify the remote receipt with revocation checking before
marking the draft ready. It rechecks the open state, head, and review body
immediately before promotion. A stopped landing resumes the same draft and
reuses its existing review only when the current head already qualifies under
the existing subject rules. A missing or revoked receipt keeps the PR in draft.
Existing ready PRs keep the merge-time verification gate.

The required disposition workflow will evaluate ready-for-review events from
the base branch. Draft evaluations may fail while receipt publication is
pending. A successful evaluation still requires valid evidence. New drafts
carry a publication notice that is removed after publishing the binding. This
body edit runs the check during rollout while the base workflow still listens
only for the existing events.

Acceptance covers new draft creation, publication and remote verification
before promotion, interrupted promotion, a changed live head, and the existing
merge-time and body-edit gates. Rollback leaves any interrupted PR as a draft
for inspection. GitHub does not offer a head compare-and-swap on ready
transitions, so the required CI check and head-matched merge still enforce the
final decision.
