# Project agent payload contract

## Finding

The factory currently has two partially overlapping payload producers:

- `aqd workflows project-init` renders the `templates/agentic-workflow` command,
  intent, plan, settings, and workflow surfaces.
- gate install/retrofit renders the gate bundle's lane/rule templates, fresh
  collaboration seeds, checks, hooks, tracker, and shared-engine capability record.

The gate manifest itself contains only lane/rule scaffolding plus the capability
record. A brownfield retrofit therefore does not prove parity with the fuller
greenfield project payload. Conversely, copying the host `.agent/skills`, runtime
receipts, secrets, histories, ports, or service state into a consumer would violate
least privilege and shared-engine ownership.

## Required product contract

Each initialized or retrofitted project receives one versioned, previewable project
payload with the same functional surfaces:

1. Project-local instruction and role contracts for every supported lane.
2. Workflow commands, intent contract, project PRD/plan scaffolding, and factory-start
   entrypoint.
3. Fresh collaboration state: PULSE, RESUME, HANDOFF, PENDING/intent lock, issues
   backlog, recovery surface, and archive roots. Never copy host contents.
4. Gate/check/hook/PM-tracker bundle and protected review contract.
5. A capability record declaring shared coordinator, memory, model, tool, skill,
   telemetry, and secret interfaces as available, unavailable, or unauthorized.
6. Thin project references/allowlists for shared skills and tools. Skills remain in
   the versioned shared factory unless a project-specific skill is explicitly vendored.
7. Client settings generated from declared capabilities, without embedded secrets,
   host-absolute paths, fixed ports, or assumed authentication.
8. Payload version, source digest, per-file ownership/disposition, upgrade plan,
   backups, and drift/status reporting.

## Explicit exclusions

Do not replicate host prompts wholesale, provider credentials, `/run/secrets`
contents, model weights, ports, hardware configuration, agent histories, queues,
logs, dashboards, vector data, or mutable service state. Projects connect to these
through scoped shared-engine capabilities and leases.

## Acceptance

- Greenfield and brownfield previews resolve the same required payload inventory.
- Existing project-local files are preserved or require an explicit reviewed adoption;
  upgrades use the lossless managed-state/backup contract.
- A disposable project can invoke each installed workflow command and reach every
  declared available shared capability; unavailable/unauthorized capabilities fail
  with typed state before assignment.
- Every installed file has a functional owner, source/version, and upgrade disposition.
- QA and dashboard show payload version, drift, missing required surfaces, shared
  capability reachability, and last validated time.
- No consumer name is embedded in factory module, API, branch, or test identifiers.

## Implementation order

1. Inventory/diff both payload producers into one declarative payload manifest.
2. Make project-init and retrofit consume that manifest in preview and install modes.
3. Add lossless upgrade/migration fixtures for legacy greenfield and brownfield payloads.
4. Add shared skill/tool projection and client parity checks.
5. Add QA/dashboard visibility and real disposable consumer acceptance.

This contract follows the Run-3 lossless-upgrade correction and must not bypass its
data-loss guard. It complements, rather than duplicates, the shared-toolchain ST-1/ST-4
work: the project payload declares/reaches shared tooling; it does not copy the host.
