# Project payload manifest — foundation handoff

Status: WIP foundation only; no producer has been migrated. The revision closes the
inventory and source-safety review findings; it remains unreviewed for integration.

The versioned manifest is `templates/agentic-workflow/project-payload-manifest.json`.
`scripts/ai/lib/project_payload_manifest.py` only validates and deterministically resolves
the required greenfield/brownfield inventory. It neither reads a consumer checkout nor writes
one, so it cannot clobber configured checks or collaboration state.

Fresh collaboration targets are named as fresh seeds. Shared skills/tools are thin references;
no host skills, credentials, runtime histories, ports, or service state are vendored.

The inventory names every file in the installed gate-bundle reference subtree, rather than
using directory targets. It also explicitly includes the project task entry point and both
factory PM-tracker references (`tracker.schema.json` and `sample-tracker.json`). The capability
record is required to declare the complete typed shared-engine interface set.

The inventory is checked against every file-output target declared by the gate-bundle manifest,
including the PM-tracker gate check. This prevents a later bundle file from silently being absent
from a project payload declaration.

Manifest validation rejects secret, credential, token, log, queue, and history source artifacts,
including suffixed runtime files. The sole explicit exception is the versioned factory
`hard-20-secret-scan.sh` check: it is code that detects secrets, not a secret artifact. Source
resolution follows links and rejects any resolved path outside the supplied repository root. The
exception applies only to its exact factory path; a secret or runtime ancestor cannot use that
filename to bypass validation.

Next producer-integration owners/files:

- `scripts/ai/aqd`: make project-init preview/install consume the manifest.
- `scripts/ai/lib/factory_gate_install.py`: make retrofit preview/install consume the manifest
  with the existing managed-state, backup, and lossless-upgrade contract.
- Factory gate template/config integration: render only validated concrete values, preserving
  configured checks rather than reintroducing unresolved command placeholders.

Validation after the revision:

```bash
python3 -m py_compile scripts/ai/lib/project_payload_manifest.py \
  scripts/testing/test-project-payload-manifest.py
python3 scripts/testing/test-project-payload-manifest.py
git diff --check
```

The focused test passes with 90 required targets and includes negative coverage for
`config/secrets.json`, `.agent/history.json`, `PULSE.log.bak`, token artifacts, incomplete
capability interfaces, nested source-path evasions, and an escaping symlink source.
