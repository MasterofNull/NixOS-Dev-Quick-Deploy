# A2A task for antigravity — build the Cycle 0 package freeze tool (F1 disposition)

Dropped: 2026-07-10T16:56:00Z
Requested by: fable-5 orchestrator (owner-directed critical path)

This is the LAST blocker before fresh APPROVE reviews and implementation authorization can proceed.
The owner ratification (OWNER-POLICY-RATIFICATION.md) prohibits hand-stamped package roots; the
amended STATE-CONTRACT.md specifies the freeze operation. Nobody has built the tool yet.

## Build exactly two files

### 1. `scripts/governance/aq-package-freeze` (python3, stdlib only, executable)

Implements the STATE-CONTRACT freeze contract ("Package freezing is one bounded operation: hash
declared subjects, write and fsync the descriptor, atomically replace it, write the digest sidecar,
then verify every subject"):

- `freeze <path/to/PACKAGE-ROOT.json>`:
  1. Load the descriptor; refuse (exit 3, listing paths) if any declared subject file is missing.
  2. Recompute sha256 of every subject's exact raw bytes; update the `subjects[].sha256` fields.
  3. Write the updated descriptor to a temp file in the same directory, `fsync`, atomic
     `os.replace` over PACKAGE-ROOT.json, then `fsync` the parent directory.
  4. Compute sha256 of the final descriptor bytes and write `PACKAGE-ROOT.sha256` beside it
     (same temp+fsync+replace pattern), format: `<hex>  PACKAGE-ROOT.json`.
  5. Immediately re-verify everything (step below); exit 0 only if verification passes.
  6. Print the new root hash on success.
- `verify <path/to/PACKAGE-ROOT.json>`:
  - Exit 0 if the .sha256 sidecar matches the descriptor bytes AND every subject's recorded sha256
    matches its current raw bytes.
  - Exit 2 with a per-subject mismatch/missing report on stderr otherwise.
- No other subcommands, no third-party imports, no network. Paths in the descriptor are
  repo-relative; resolve them from the repository root (walk up from the descriptor to the `.git`
  directory).

### 2. `scripts/testing/test-package-freeze.py`

Self-contained (tempfile dirs, no production files touched):
- clean freeze → verify exit 0;
- subject drift after freeze → verify exit 2 naming the drifted subject;
- missing subject → freeze refuses exit 3;
- sidecar/descriptor mismatch → verify exit 2;
- freeze is idempotent (second freeze with no changes yields the identical root hash).

## Validate

- `python3 -m py_compile` both files.
- Run the test file; all cases pass.
- Run `python3 scripts/governance/aq-package-freeze freeze .agents/plans/aqos-refoundation-cycle0/PACKAGE-ROOT.json`
  as the FINAL step, then `verify` (expect exit 0). Print the new root hash — this becomes the final
  root that the fresh APPROVE reviews will pin.

## Constraints

- Do NOT edit any file in `.agents/plans/aqos-refoundation-cycle0/` other than via the freeze
  operation itself (PACKAGE-ROOT.json + PACKAGE-ROOT.sha256).
- Do NOT commit — the orchestrator validates and commits (implementer/reviewer separation).
- Respond by writing `.agents/plans/aqos-refoundation-cycle0/freeze-tool-report.md` with: files
  created, test output summary, the new root hash, and any deviation from this spec.
