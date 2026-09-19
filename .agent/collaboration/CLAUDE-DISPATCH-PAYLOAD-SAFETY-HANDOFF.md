# Claude dispatch payload safety

## Objective and scope

Replace interpolated background shell source with a fixed worker and positional
arguments. Prompt text, output paths, and audit metadata remain data, not shell
programs. Background stdin is explicitly closed. No provider, model, role,
authentication, budget, or local-dispatch policy changes are authorized here.

## Validation and disposition

The hermetic payload fixture exercises quotes, backticks, dollar expressions,
multiline text, closed stdin, model/role arguments, and successful/nonzero terminal
registry outcomes. Shell syntax and the existing model-routing fixture pass.
Independent review and canonical Tier0 remain required before acceptance.

This fixes a source-confirmed unsafe interpolation boundary. It does not establish
the cause of any historical empty output, nor assert that execution or leakage
occurred. Existing registry concurrency semantics are outside this bounded fix.

## Next gate

Freeze the exact staged subject, obtain independent PASS, run Tier0, and integrate
without overwriting concurrent field corrections. Real-provider activation is not
claimed by offline fixtures.
