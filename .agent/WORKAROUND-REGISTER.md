# Workaround / Debt Register (SSOT)

Every workaround, band-aid, or ad-hoc fix that is NOT yet fixed at its producer lives here —
never silently in the code. Governed by `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md` (proposed
Rule 19). Swept like the agent catch-up queue; items aging past their window escalate.

Entry fields: id · symptom · band-aid in place? · root cause · producer to fix · fix-path ·
class (T1 tooling / T2 validation-gap / T3 diagnosability / T4 gate-coupling / T5
producer-governance-fracture) · severity · status · opened.

Status legend: OPEN (band-aid live, unfixed) · FIXED (producer fixed, band-aid removed) ·
ACCEPTED (documented deliberate tradeoff, no band-aid) · MAINT-DUE (time/env expiry, tracked).

---

## WR-1 — nested-quoting mangles cell-adapter submits — FIXED
- symptom: `sg -c "… python3 -c \"…\""` (triple quote layers) garbled newlines/special chars.
- root cause (T1): no reusable CLI; inline python nested in two shell layers.
- fix: `scripts/testing/cell-submit.py` — argparse CLI, single `sg -c` layer, plain args.
- status: FIXED 2026-08-06 (validated: clean GREEN round-trip, exit 0).

## WR-2 — inline commit messages die on `${}` / `->` — FIXED
- symptom: `git commit -m` with `${pkgs.git}` (zsh bad-substitution) and `->` (control-char hook).
- root cause (T1): shell metachar/expansion in inline messages.
- fix: use `git commit -F <file>`; author multi-line docs via Write + `cat >>`, never inline heredocs with `${}`.
- status: FIXED 2026-08-06 (habit + documented in the PRD).

## WR-3 — runner deploy bugs only discoverable live, one per rebuild — OPEN
- symptom: #10 (durable_reservation.py missing from runnerBundle), #11 (systemd strips JSON quotes), #13 (git not on PATH) each passed offline acceptance, failed live, needed a rebuild to find the next.
- root cause (T2): no deploy-context preflight (bundle-import resolution, env round-trip through systemd, bare-binary PATH deps).
- producer to fix: execution-cell-runner activation path.
- fix-path: a preflight (simulate_nix_change-adjacent) asserting bundle imports resolve, `TRUSTED_REPO_MIRRORS` JSON survives systemd, and every bare-`git` dep is on the service PATH. Normal PRD→build→review slice.
- class T2 · severity MED · status OPEN · opened 2026-08-06.

## WR-4 — cell-create failures hide their cause — OPEN
- symptom: every cell-create failure surfaced only a catch-all code (`quarantined`); the real "why" (git-not-found, isolation-violation, path-escape) required reverse-engineering source+repo.
- root cause (T3): runner Decision keeps only `cell_result.code`, discards `TypedFailure.detail`.
- producer to fix: `execution_cell_runner.py` cell-create failure branch (line ~641).
- fix-path: log `cell_result.detail` low-cardinality class to journald alongside `_log_unproven_tree`. Normal slice.
- class T3 · severity MED · status OPEN · opened 2026-08-06.

## WR-5 — tier0 0.10.5 model-profile freshness hard-blocks all commits — MAINT-DUE
- symptom: `reviewed_at`/`probed_at` (2026-06-21) aged ~1 day past the 45-day window → tier0 `--pre-commit` fails → ALL commits blocked. Tempts hand-bumping the timestamp (gaming) or bypassing tier0.
- root cause (T4 + T5): a time-based freshness check wired as a HARD pre-commit blocker (T4); AND the producer `model_probe.py` writes measurement fields but NOT the `_meta`/freshness governance fields it's checked against, so a real re-probe clobbers governance and hand-editing becomes the "easy" path (T5).
- profile verified accurate: active.gguf/Qwen3-35B, TPS 3.0, ctx 262144 all match reality — content is NOT drifted; only the timestamps lapsed.
- fix-path: (a) gate hygiene — freshness-class checks WARN in `--pre-commit`, HARD only in scheduled `--maintenance` that opens a register item (needs owner ratification, changes tier0 behavior); (b) producer patch — `model_probe.py` maintains `_meta.reviewed_at`/`freshness_max_age_days` so a re-probe is a complete, honest refresh.
- class T4+T5 · severity HIGH (currently blocking) · status MAINT-DUE · opened 2026-08-06 · owner decision required.

## WR-6 — sudo unavailable in agent shell → repeated fallback attempts — ACCEPTED
- symptom: `sudo -n` needs a password here; I attempted it (cgroup/watcher reads) before falling back to /proc or asking for a `!`-run.
- root cause: no setuid in the agent shell (environment constraint, known).
- resolution: ACCEPTED tradeoff — do NOT attempt sudo; go straight to non-sudo paths (/proc, world-readable files) or a user `!`-run. No producer fix (environment is intentional).
- class — · severity LOW · status ACCEPTED · opened 2026-08-06.
