# C0.2 telemetry symlink incident evidence

`telemetry-symlink.metadata.json` is inert evidence for the unauthorized link recovered on
2026-07-11. The live link object was removed after `lstat` and `readlink` capture. It targeted
`/var/lib/ai-stack/hybrid/telemetry` and had replaced the tracked `.agents/telemetry/` directory.

The owner explicitly authorized recovery. The pre-archive scanner was run first but returned exit 2
because it dereferenced the link and classified the deployed target as outside the repository. No
deployed telemetry bytes were moved or modified. No live link remains in the archive. The tracked directory and
`training-loop-progress.json` were restored from commit `42eb76f8`/its parent state.
4cd135fcefdc324c4d422a3506d4afc551fb1cc19e42bce2d9f3e647fba80475  rejected-implementation.patch (read-only reference evidence per C0.2-PRESERVED-DIFF-DISPOSITION; also archived: the two untracked focused tests)
