# Runner-Hardening Exact-Byte Recovery Design

Status: `PREPARED_ONLY — NO RESTORATION OR ACTIVATION AUTHORIZED`  
Base HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Purpose and immutable evidence

The shared-worktree reset restored the four runner-hardening candidate paths to
their accepted predecessors. This recovery is not a redesign: it may reproduce
only the accepted bytes recorded by independent acceptance
`45ca1b4bba0567fbdc73089b85e67c21f828bc5b01906466eaefff264e0a81d6`.
The original implementation authorization
`e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059` is
consumed and non-replayable.

| Path | Required pre-write SHA-256 | Required recovered SHA-256 |
|---|---|---|
| `ai-stack/switchboard/execution_cell_runner.py` | `34837d4dc6718afccc2f663e590024f7d18723712a0a42c7cefd1969273e60fb` | `0370037e8822394fd7d8d8ace64c52d2fcf22f3797f0314c725790a43e1bfac6` |
| `scripts/testing/test-execution-cell-runner.py` | `4f8094bcc11cb29d8ce9ec8348bb4356d51df862bab4ee1124fcd87b13ea93ef` | `0c290c36d4c4c6e07a7233a03650d617a7fb77929d8d827b38db6637179b7504` |
| `nix/modules/services/execution-cell-runner.nix` | `d2f12a1cdcf4c33aae17239fbdbf92877a5b8940cd52e1946f60eab2cb6e1d12` | `3ad51487deefa9a604471ad407c496033d32efcc406ec6400fc9f89b7c2e3f72` |
| `config/env-contract.yaml` | `62450e1f6e84f9c473b2bf838e1121d6db3e40227480c1845d5b24c54686be4f` | `7bf49e7d3b64fb8eeb8b7902893a96230a414325da137233586ccda2d0c8f96e` |

No semantic change, substitution, fifth path, new file, cleanup, or mutation of
the frozen no-edit `nix/modules/services/switchboard.nix`
(`10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a`) is
permitted. Current runner design and authorization anchors are respectively
`2ab876ff3c04df249324fd5033fdb03a6bd4553cb0acd0a3fb1b0b6a46a7d8e7` and
`e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059`.

## Recovery controls

A new owner activation must name this design and a recovery authorization by
exact SHA, a distinct recovery implementer, and a distinct independent exact-byte
reviewer. It must establish one exclusive source/worktree/commit-owner lease
covering HEAD, index, all four paths, the no-edit anchor, and commit boundary.
The staged index must be empty; no concurrent git mutation, Tier-0 writer, test
writer, formatter, or release process may run. Any drift, overlap, nonempty
index, missing lease, or mismatch stops recovery and voids the activation.

Validation after exact reproduction is offline only: all four post-write hashes;
`python3 -m py_compile` for runner/test; `git diff --check`; and the accepted
outside-managed-sandbox standalone runner result `56/56 passed`, with only the
two documented R6 systemd canaries deferred. Managed-sandbox AF_UNIX/bwrap
`EPERM` is not substitute evidence. No staging, commit, deployment, restart,
socket activation, provider, network, or live traffic is included.

`RECORD: PREPARED_ONLY exact-byte recovery design; fresh owner activation required.`
