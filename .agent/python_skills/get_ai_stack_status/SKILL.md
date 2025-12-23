# Skill Name: get_ai_stack_status

## Description
Gets the status of all services in the local Podman AI stack.

## Function Signature
`get_ai_stack_status()`

## Parameters
None.

## Returns
A list of dictionaries where each entry includes `name` and `status`.

**Example Return Value:**
```json
[
  {"name": "local-ai-postgres", "status": "running"},
  {"name": "local-ai-qdrant", "status": "exited"}
]
```

## When to Use
Use this to get a snapshot of all services before troubleshooting or taking action.
