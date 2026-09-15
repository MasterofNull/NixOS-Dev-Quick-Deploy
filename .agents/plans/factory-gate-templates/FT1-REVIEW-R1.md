# FT-1-R1 exact-subject review

Subject: `fbe582c83df703f769597f1326a0998451b356748fd02ed0e63517d2457e4b5e`.
Non-author reviewer `ft1_independent_acceptance`: REQUEST_REVISION.

R0 defects corrected: required unconfigured checks fail closed, complete
installed bundle is retained/testable, PM completion requires git evidence and
tested malformed types/percentage bounds are rejected.

One concrete critical integration bug remains: template placeholders inside
Bash default parameter expansion corrupt the installed PM-check paths, even
with explicit overrides. The self-test's installed checker therefore reports
zero trackers and false PASS. FT-1-R2 is a two-file corrective slice: safe
literal defaults plus a test proving an existing invalid tracker blocks the
installed checker AND installed gate before restoring valid sample.

Deferred nonblocking FT-2 follow-ups: acceptance:null differs from the supplied
schema without promoting completion; warning failures should be labelled WARN,
not FAIL. Cooperative-hook attestation limitations are explicitly documented.

Validation on R1: self-test exit zero (false PM integration proof above),
shellcheck/bash syntax zero warnings, projection probes passed. Source Tier-0
53/0 and live QA 178 passed on R1. R2 needs focused proof and final exact-subject
acceptance; final commit hooks validate the final staged bytes.
