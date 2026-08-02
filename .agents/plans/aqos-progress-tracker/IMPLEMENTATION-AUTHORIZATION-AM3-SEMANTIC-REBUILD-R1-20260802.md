# AQ-OS Tracker AM3 Semantic Rebuild R1 — Prepared Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-aqos-tracker-am3-semantic-rebuild-r1-20260802`  
Bound HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

This authorization binds
`DESIGN-PACKET-AM3-SEMANTIC-REBUILD-R1-20260802.md` by its exact SHA at owner
activation. Original AM3 authorization `9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
is consumed/non-replayable. Exact-byte recovery authorization
`91121deccc5168deb7fe2302899cdef0683d95dd039b1356affe841506cdba90`
stopped before first write and is non-replayable because its mandatory bytes do
not exist.

## Self-contained source and write bindings

Required sources are: Unified Program Plan `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e`;
Owner Decision Sheet `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1`;
`config/system-state-authorities.yaml` `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`;
Foundation-A adjudication `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a`;
and issues backlog `814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8`.

The exact five EDIT paths and predecessors are:

1. `config/refactor-milestones.json` — `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe`;
2. `assets/aqos-progress-tracker.html` — `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa`;
3. `scripts/testing/test-dashboard-program-progress.py` — `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7`;
4. `scripts/testing/harness_qa/phases/phase0.py` — `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`;
5. `scripts/ai/lib/refactor_status.py` — `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b`.

The candidate must project `PROJECTED_CURRENT_STATE`, 19 tracks, active B1 /
Foundation C / AAF / LEC / Track S, blocked Track V, zero pending owner
decisions, 10 authority rows, Critical+High issue count with malformed/unknown
separate, truthful C2/C5 deployed distinction, dormant-never-LIVE C3b, disputed
C0.3 settlement, PREPARED_ONLY Foundation C revisions, active LEC, and no stale
closed findings. Phase-0 may alter only `0.10.40`; AST-extracted function source
with terminal LF must retain hashes `d44744f31b590072185edc70cf9018e1345865810853da8c1c779c5d8767bf84`
for 0.10.41, `322e69c0a4b78e3492d80e1c38909d8cc3fe1c1068a61848d2ea3fe33381405f`
for 0.10.42, `a04c2cc318a47b214c232e50bd90c53b2d030c295fffa1c7c25300ddc0fe3453`
for 0.10.43, and `0eddf5b47a0a99c7a2d1ddcd8c773590ce6fa7e3f3ffa99580a66bca586863ec`
for 0.10.44.

After independent review and fresh owner activation, the named preparer may
prepare only these five files in `/tmp`; new hashes are expected. A distinct
reviewer must approve the full temp manifest and evidence before repository
write. The repository implementer may apply only those reviewed bytes.

## No-touch accepted candidates

Runner manifest `0d1f9acfbd349a88fcc21084c04be1ba0d6ed7d86ba297bfb2ed3499577544e3`
binds: runner `0370037e8822394fd7d8d8ace64c52d2fcf22f3797f0314c725790a43e1bfac6`;
test `0c290c36d4c4c6e07a7233a03650d617a7fb77929d8d827b38db6637179b7504`;
Nix `3ad51487deefa9a604471ad407c496033d32efcc406ec6400fc9f89b7c2e3f72`;
env `7bf49e7d3b64fb8eeb8b7902893a96230a414325da137233586ccda2d0c8f96e`.

L3-P0 manifest `2f0e7cb4e82c7a1cf7b925deb5749048977dc13bf8c66a6b041037d6654bdb87`
binds, in canonical explicit-path order: producer set
`7a4a02e126592c6eb837e1895dd440f6b07a2f5a310012cc0a4346de6f787b7c`;
resolved plan `f1e1dc9cad8cbd810fb57f9b0af2e1d4237414d617b5e3c869c2efdf62d50f4e`;
observation metadata `0ba645a795f3be0b115190a2f903c6a1479bfe685d6b16027940f9e36cfa4666`;
observation `a705a6d0127306ff6df13c1232e2113fa98c104c3e74fb6937ebe0668145e888`;
request projection `079fdbfabd733d5b67bac50ace8c1b41168d8b8454b6181815458dfe4805ad59`;
fact envelope `4d0d2e0ebfd1d397d8171856df26e2747647993fb09c3a52df9a88ee50b285d4`;
unavailable `96ec244410f835bc4f92074ece7d3ef8824b956bb71ec05a05ec79654b530e7c`;
module `c90275d7dc14b960bf9d4347d4869009f3c14d0292e04fe61744f15b8f202c04`;
fixture `56864a3829acbd382a7a4f093c7ed4514cb0058e8c9f8727a8b2ef9ef50a7f78`;
and test `711b06ffa0e744436f8a7d186d613268d6a1a4ffb5c5c696e6de9186f6454978`.

Activation must name the temp preparer, repository implementer, independent
reviewer, and an observable exclusive lease lasting no more than 45 minutes
after first repository write. The lease covers all five sources, five candidate
paths, runner/L3 no-touch state, repository index/HEAD/commit boundary, and the
focused/Tier-0 writer slot; forbids every concurrent agent, test, formatter,
issue writer, reset, checkout, stage, commit, and deployment; and requires empty
index/no-overlap/hash checks before preparation, before application, and after
validation.

Run exactly:

```text
python3 -m json.tool config/refactor-milestones.json
python3 scripts/testing/test-refactor-status.py
python3 scripts/testing/test-dashboard-program-progress.py --static-only
PYTHONPYCACHEPREFIX=/tmp/tracker-semantic-rebuild-pyc python3 -m py_compile scripts/ai/lib/refactor_status.py scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check -- config/refactor-milestones.json assets/aqos-progress-tracker.html scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py scripts/ai/lib/refactor_status.py
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
```

Recheck empty index, all five sources, five final candidate hashes, four Phase-0
function hashes, runner manifest, L3-P0 manifest, and HEAD before and after temp
review, application, and validation. Any source/HEAD/hash/
inventory/lease drift, failed test, sixth path, or inability to prove truth is a
stop and consumes an activated grant. The implementer cannot self-review, stage,
or commit. No deployment, runtime/provider/network, live traffic/HTTP, service,
Nix, reset, or checkout authority is granted.

`RECORD: PREPARED_ONLY semantic rebuild authorization; exact review and owner activation required.`
