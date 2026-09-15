# Stack adapters

`resolve.py REPOSITORY [--override STACK]` reads only root-level conventional metadata and writes one JSON document. It never executes repository code, package scripts, task files, installers, or network commands.

It reports every detected stack (`python`, `node`, `rust`, `go`, `nix`), so mixed repositories retain all applicable profiles. Unknown repositories safely receive `generic`. Each check is `READY` only when its conventional metadata is present and its executable is on `PATH`; otherwise it is explicitly `UNCONFIGURED`, never passed. Python module commands remain `UNCONFIGURED` with explicit `requires` because this detector does not import or execute project environments. Secret scanning uses `gitleaks detect --no-git --redact` when the executable is available. `READY` is configuration metadata, not proof that a command succeeds.

Profiles deliberately do not read task files, Makefiles, credentials, arbitrary root scripts, or auto-activate any output. A later installer may render only `READY` commands into the corresponding gate placeholders after its own review/confirmation flow.
