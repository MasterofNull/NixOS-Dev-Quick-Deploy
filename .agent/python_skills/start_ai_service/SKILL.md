# Skill Name: start_ai_service

## Description
Starts a specific service in the local Podman AI stack.

## Function Signature
`start_ai_service(service_name: str)`

## Parameters
- `service_name` (string): Container name or substring (e.g., `qdrant`, `open-webui`).

## Returns
A dictionary describing the outcome.

**Example Return Value:**
```json
{"status": "success", "message": "Container qdrant started."}
```

## When to Use
Use this when a service is stopped/exited and needs to be started.
