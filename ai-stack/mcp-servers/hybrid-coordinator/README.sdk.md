# Hybrid Coordinator SDKs

Publishable SDK surfaces for workflow orchestration, branch/session management, reviewer gates, and harness evaluation.

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
const session = await client.startSession("run branch-aware workflow checks");
const tree = await client.workflowTree();
```

## API surface

Both SDKs cover:
- `POST /workflow/plan`
- `POST /workflow/session/start`
- `GET /workflow/sessions`
- `GET /workflow/tree`
- `GET /workflow/session/{id}`
- `GET /workflow/session/{id}?lineage=true`
- `POST /workflow/session/{id}/fork`
- `POST /workflow/session/{id}/advance`
- `POST /review/acceptance`
- `POST /harness/eval`
