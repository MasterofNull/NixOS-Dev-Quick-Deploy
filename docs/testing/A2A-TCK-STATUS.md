# A2A TCK Status

Current upstream signal from the live hybrid coordinator using:

```bash
bash scripts/testing/run-a2a-tck.sh mandatory
```

Current result:

- mandatory TCK is effectively green on coordinator behavior
- latest run finished `75 passed / 1 failed / 40 skipped`
- latest local evidence is captured in `/tmp/a2a-tck-mandatory.log`

Primary gap buckets observed:

- Remaining failure is currently in the upstream TCK helper layer, not the
  hybrid coordinator surface.
- `test_push_notification_not_supported_error_32003_enhanced` currently fails
  with a Python `TypeError` because the TCK helper
  `transport_create_task_push_notification_config(...)` is called with the wrong
  signature before the coordinator can return its protocol error.
- The coordinator is already returning the expected push-notification rejection
  path (`-32003` / unsupported boundary) for the reachable push-notification
  flows.

Current interpretation:

- The system now has a functioning A2A architecture and live interoperability
  surface for discovery, task RPC, task replay, and streaming.
- The previously missing protocol pieces were implemented: JSON-RPC aliasing,
  root endpoint compatibility, stricter JSON-RPC error handling, task-list
  pagination/filtering/history behavior, and timestamp ordering precision.
- The remaining mandatory red signal is best treated as an upstream TCK defect
  to track rather than a coordinator runtime defect to patch around locally.

Related repo-native entrypoints:

- `scripts/testing/run-a2a-tck.sh`
- `docs/testing/A2A-TCK-RUNBOOK.md`
- `scripts/testing/smoke-a2a-compat.sh`
