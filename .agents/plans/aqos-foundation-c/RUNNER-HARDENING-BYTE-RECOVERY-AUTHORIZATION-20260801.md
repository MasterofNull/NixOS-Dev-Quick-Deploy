# Runner-Hardening Exact-Byte Recovery Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-foundation-c-runner-hardening-byte-recovery-20260801`  
Bound HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

This prepared authorization binds recovery design
`RUNNER-HARDENING-BYTE-RECOVERY-DESIGN-20260801.md` by its SHA at owner
activation, acceptance evidence
`45ca1b4bba0567fbdc73089b85e67c21f828bc5b01906466eaefff264e0a81d6`,
current runner design `2ab876ff3c04df249324fd5033fdb03a6bd4553cb0acd0a3fb1b0b6a46a7d8e7`,
and consumed original authorization
`e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059`.

After a fresh owner activation, only the four paths and exact predecessor →
accepted hashes table in the recovery design may be written. The implementer
must be distinct from the original implementer and from the independent
exact-byte reviewer. The owner act must name an exclusive lease covering sources,
worktree, empty index, the four paths, frozen switchboard anchor, and commit
owner boundary; it must forbid concurrent git/Tier-0/test writers for the
window. The activation is single-use and void on any drift or mismatch.

Required evidence is exact post-write hashes, unchanged switchboard anchor,
offline py_compile/diff-check, and an outside-managed-sandbox `56/56 passed`
runner test report with only two R6 systemd canaries deferred. No stage, commit,
deploy, restart, socket/cgroup canary, provider/network call, or live activation
is authorized. Any failure requires a new numbered recovery authorization.

`RECORD: PREPARED_ONLY recovery authorization; no candidate restoration until fresh owner activation.`
