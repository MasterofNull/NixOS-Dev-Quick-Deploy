# A2A TCK Status

Current upstream signal from the live hybrid coordinator using:

```bash
bash scripts/testing/run-a2a-tck.sh mandatory
```

Current result:

- mandatory TCK does not pass yet
- latest local evidence is captured in `/tmp/a2a-tck-mandatory.log`

Primary gap buckets observed:

- JSON-RPC error handling is not protocol-shaped enough yet.
  The TCK expects JSON-RPC error envelopes for malformed requests and unknown
  methods, while the coordinator still returns HTTP `404` in several paths.
- Method mapping is incomplete for upstream expectations.
  The TCK task-creation path hits `method not found`, which means our current
  facade still diverges from the v0.3.0 method surface it probes.
- `tasks/list` is still too shallow.
  Upstream coverage expects pagination, filtering, history-length handling, and
  artifact inclusion toggles that the current facade does not implement.
- Agent-card security metadata needs tightening.
  Current card contents and security scheme shape trigger upstream security and
  authentication consistency failures.
- Public agent-card content still exposes development-local details.
  The TCK flags `127.0.0.1` URLs in the live card as internal/development
  endpoints.

Current interpretation:

- The system now has a functioning A2A architecture and live interoperability
  surface for discovery, task RPC, task replay, and streaming.
- It is not yet upstream-mandatory compliant under the official TCK.
- The next engineering batch should focus on protocol-correct JSON-RPC errors,
  agent-card hardening, and `tasks/list` parity before optional features.

Related repo-native entrypoints:

- `scripts/testing/run-a2a-tck.sh`
- `docs/testing/A2A-TCK-RUNBOOK.md`
- `scripts/testing/smoke-a2a-compat.sh`
