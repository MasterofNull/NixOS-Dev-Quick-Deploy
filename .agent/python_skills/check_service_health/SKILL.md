# Skill Name: check_service_health

## Description
Checks the HTTP health endpoint for a given AI stack service.

## Function Signature
`check_service_health(service_name: str)`

## Parameters
- `service_name` (string): Service name (e.g., `llama-cpp`, `aidb`, `hybrid-coordinator`).

## Returns
A dictionary describing the health status.

**Example Return Value:**
```json
{"status": "success", "message": "llama-cpp is healthy."}
```

## When to Use
Use this to confirm a service responds correctly after start/restart.
