# Skill Name: stop_ai_service

## Description
Stops a specific service in the local Podman AI stack.

## Function Signature
`stop_ai_service(service_name: str)`

## Parameters
- `service_name` (string): Container name or substring.

## Returns
A dictionary describing the outcome.

**Example Return Value:**
```json
{"status": "success", "message": "Container qdrant stopped."}
```

## When to Use
Use this to stop services for maintenance or to reset a container.
