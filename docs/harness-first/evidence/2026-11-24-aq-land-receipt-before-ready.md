# aq-land review receipt publication before draft promotion

PR #864 exposed an ordering defect. A newly opened PR could trigger the required disposition check while the receipt binding its PR number and reviewed commit was still being published. The landing path now opens a draft, publishes the receipt, edits the body to rerun disposition, independently verifies the published receipt against the exact PR and head with revocation checking, and checks the live draft and subject before promotion.

## Validation

- Landing integration fixtures passed in eight shards (116 cases). Coverage includes initial draft creation, interrupted publication, resumed promotion, already-ready PRs, changed subjects, and an unchanged final body on retry.
- The pre-review gate passed 53 cases. The disposition check passed 4 cases. The receipt suite passed 39 cases with the test harness's volatile directory opt-in for this temporary checkout.
- GitHub's promotion and required workflow were exercised through mocks. Hosted verification remains pending the first authorized landing after merge.
- A failed remote lookup, subject mismatch, or revocation check leaves the new PR in draft. The existing exact-head merge gate still runs after promotion.
