# Local dogfood exact-target scaffold

## Objective

Give the first dogfood validation task a small, machine-validated read target so
the local agent receives an honest, bounded pre-edit instruction.

## Scope

- Add optional `target_symbol` and `target_read_range` task metadata.
- Reject malformed target metadata before `delegate-to-local` is invoked.
- Render one exact pre-edit `read_file` instruction only when both fields are
  valid; otherwise retain a truthful generic context instruction.
- Add focused stdlib-only regression coverage.

## Constraints

- The runner retains its declared-single-file scope, no-commit instruction,
  executor guards, terminal waiting, capture, and revert behavior.
- `target_symbol` is display-only and restricted to a short safe token.
- `target_read_range` is exactly two positive integer line numbers with
  `start <= end` and a bounded span.

## Acceptance criteria

1. Valid metadata renders the exact file, line range, and symbol in the prompt.
2. Missing metadata does not claim an unspecified exact frontload.
3. Malformed ranges fail before dispatch.
4. The built-in `dogfood-01` task targets `_matches_exclude`, lines 270–279.
