# FT-3 implementation boundary

FT-3 adds a greenfield-only installer through `aqd workflows project-init`.
It preserves a pristine byte-for-byte copy of the FT-1 bundle at
`.factory/gate-bundle`, renders only the manifest destinations outside that
copy into the target, activates executable `.githooks` through the target's
`core.hooksPath`, and records `.factory/gate-install.json`. It also seeds the
installed PM standard at `.agents/plans/factory-gate/tracker.json` so the
installed PM checker has an actual discoverable target tracker.

The installer performs metadata-only FT-2 stack resolution. Any unavailable
required command remains `CONFIGURATION_BLOCKED`; it is not rendered as a
successful no-op. The receipt therefore distinguishes installed/active hook
path from check readiness and records `ACTIVATION_BLOCKED` when configuration
is incomplete. `aqd workflows factory-gate-status --target <dir>` emits that
read-only JSON state without running target commands.

Safety boundary: existing effective `core.hooksPath`, manifest destination,
ancestor file/symlink, or receipt/bundle collision is refused before bootstrap
writes; `--force` is not a bypass. A redirected `.git`, `.git/config`, or
`.git/hooks`, or active default `pre-commit`/`commit-msg` hook is also refused:
any executable non-`.sample` default hook is preserved because changing
`core.hooksPath` would disable it. Composing or replacing those guards is
reserved for FT-4. A `.git/commondir` shared-worktree pointer is similarly
refused rather than writing shared metadata. Existing repositories are reserved
for FT-4.
The installer never invokes project build/test/lint commands or installs
dependencies. The focused fixture uses only disposable target repositories to
prove the installed hook blocks a bad commit and the installed PM checker finds
a real tracker; it is execution evidence, not a claim that same-user hooks are
tamper resistant.
