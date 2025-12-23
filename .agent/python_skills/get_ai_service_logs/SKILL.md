# Skill Name: get_ai_service_logs

## Description
Fetches recent logs for a specific AI stack service.

## Function Signature
`get_ai_service_logs(service_name: str, tail: int = 100)`

## Parameters
- `service_name` (string): Container name or substring.
- `tail` (int, optional): Number of log lines to return (default 100).

## Returns
A string containing the recent logs.

## When to Use
Use this for diagnosing startup failures or runtime errors.
