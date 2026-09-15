# Local FT-2 prep contribution

Task: `local-20260915-102237-47afub`, direct architect draft, bounded 512 tokens.
Output remains in its delegation log. It supplies proposal evidence only;
no tools were executed and no stack-command compatibility was verified.

Useful proposal to fold: unavailable optional tools must be reported explicitly,
not silently passed. Language markers include pyproject.toml, package.json,
Cargo.toml, go.mod and flake.nix. Concrete commands must be resolved from trusted
project configuration and verified per fixture.

Do NOT automatically adopt the draft's taskfile-first priority, install commands
(`pip install .`), or arbitrary root scripts as defaults. Stack detection must
only inspect bounded metadata, never execute target code. A polyglot repository
should report multiple stacks rather than accidentally select one by filename
order. Gitleaks/other scanner output must redact secrets and be validated against
the actual installed version.

The answer was truncated before completing all six requested stacks at the
token bound. Record this as a partial contribution—not a finished FT-2 inventory
or a PASS. Remote fixture-driven implementation supplies the missing coverage.

FT-7 follow-up: local git hooks provide cooperative lane-independent enforcement,
not an unbypassable same-user security boundary. Reviewer names/emails and
editorial acceptance need trusted evidence before being treated as attestation.
