# Backlog reconciliation — 2026-11-15

## Scope

Preserve only the owner-listed durable historical plans, prompts, operator manual,
and append-only operational records from the manifest-backed main-checkout snapshot.
This is a preservation slice, not plan activation or feature work.

## Method

1. Compare tracked records against the reconciliation branch and retain only
   historical source deltas.
2. Import the listed untracked durable records byte-for-byte.
3. Add only exact host-runtime paths to `.gitignore`; durable plans remain
   trackable.
4. Exclude `flake.lock`, bulk research, archives, and live runtime state from
   this change. Root handles local-only archive/research excludes.

## Validation

Review the resulting path inventory, JSON syntax for imported JSON, and the
text diffs. The parent agent owns tier0, commit, and landing.
