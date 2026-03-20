# Hybrid Coordinator SDKs

Publishable SDK surfaces for workflow orchestration, branch/session management, reviewer gates, and harness evaluation.

## A2A compatibility surface

The hybrid coordinator now exposes a lightweight A2A-compatible facade over the
existing workflow runtime. This is an interoperability layer, not a second
orchestrator.

Public discovery:
- `GET /.well-known/agent.json`
- `GET /.well-known/agent-card.json`

JSON-RPC endpoint:
- `POST /a2a`

Task stream:
- `GET /a2a/tasks/{id}/events`

Implemented A2A-style methods:
- `agent/getCard`
- `message/send`
- `tasks/get`
- `tasks/list`
- `tasks/cancel`

Runtime mapping:
- A2A task IDs map directly to persisted workflow run `session_id` values.
- A2A task state is derived from workflow run `status`.
- Task event streaming is replayed from workflow `trajectory`.
- Safety mode, reviewer gate state, and replay URLs remain the underlying source of truth.

Live smoke:

```bash
bash scripts/testing/smoke-a2a-compat.sh
```

## Python SDK

Path:
- `ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py`

Package metadata:
- `ai-stack/mcp-servers/hybrid-coordinator/pyproject.toml`
- package name: `nixos-ai-harness-sdk`

Install from source:

```bash
pip install ./ai-stack/mcp-servers/hybrid-coordinator
```

Basic usage:

```python
from harness_sdk import HarnessClient

client = HarnessClient(base_url="http://127.0.0.1:8003")
plan = client.plan("debug continue local profile hangs")
session = client.start_session("stabilize switchboard profile routing")
tree = client.workflow_tree()
```

## TypeScript / JavaScript SDK

Source:
- `ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.ts`

Publish artifacts:
- `ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.js`
- `ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.d.ts`
- `ai-stack/mcp-servers/hybrid-coordinator/package.json`
- package name: `@nixos-ai/harness-sdk`

Pack dry run:

```bash
cd ai-stack/mcp-servers/hybrid-coordinator
npm run pack:dry
```

Basic usage:

```ts
import { HarnessClient } from "@nixos-ai/harness-sdk";

const client = new HarnessClient({ baseUrl: "http://127.0.0.1:8003" });
const plan = await client.plan("smoke test all workflow profiles");
const manifest = await client.toolingManifest("debug MCP tool chatter", "typescript");
const session = await client.startSession("run branch-aware workflow checks");
const tree = await client.workflowTree();
```

## API surface

Both SDKs cover:
- `POST /workflow/plan`
- `POST /workflow/tooling-manifest`
- `POST /workflow/session/start`
- `GET /workflow/sessions`
- `GET /workflow/tree`
- `GET /workflow/session/{id}`
- `GET /workflow/session/{id}?lineage=true`
- `POST /workflow/session/{id}/fork`
- `POST /workflow/session/{id}/advance`
- `POST /review/acceptance`
- `POST /harness/eval`
- `POST /workflow/run/start`
- `GET /workflow/run/{id}`
- `POST /workflow/run/{id}/mode`
- `GET /workflow/run/{id}/isolation`
- `POST /workflow/run/{id}/isolation`
- `POST /workflow/run/{id}/event`
- `GET /workflow/run/{id}/replay`
- `GET /workflow/blueprints`
- `POST /control/runtimes/register`
- `GET /control/runtimes`
- `GET /control/runtimes/{id}`
- `POST /control/runtimes/{id}/status`
- `POST /control/runtimes/{id}/deployments`
- `POST /control/runtimes/{id}/rollback`
- `GET /control/runtimes/schedule/policy`
- `POST /control/runtimes/schedule/select`
- `GET /parity/scorecard`

Generated API reference:
- `docs/generated/HARNESS-SDK-API.md`
- refresh/check via `scripts/data/generate-harness-sdk-api-docs.sh --write|--check`

## Release automation

Workflow:
- `.github/workflows/harness-sdk-release.yml`

Behavior:
- Pull requests touching SDK files run validation/build only (no publish).
- Tags matching `harness-sdk-v*` run validation and publish jobs.
- Manual dispatch supports optional publish via workflow input.

Safety gates:
- `scripts/testing/check-harness-sdk-version-parity.sh` enforces Python/npm version lockstep.
- `scripts/testing/smoke-harness-sdk-packaging.sh` enforces docs + packaging parity.
