# Logging Standards
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


## Structured Logging Requirements

- Emit JSON logs for service runtime events.
- Include at minimum:
  - `timestamp`
  - `level`
  - `service`
  - `event` (or `message`)
  - request/session correlation IDs when available

## Log Levels

- `error`: failure requiring intervention
- `warning`: degraded behavior or recoverable issue
- `info`: normal lifecycle events and checkpoints
- `debug`: diagnostic details for troubleshooting

## Parsing Utilities

Use:
```bash
scripts/observability/parse-structured-logs.py <jsonl-file>
```

This outputs:
- total rows
- invalid JSON rows
- level distribution
- top event/message counts

## Operational Guidance

- Prefer concise, machine-parseable event names.
- Avoid secret/token values in logs.
- For retries/circuit-breaker transitions, log state changes and retry attempt counts.
