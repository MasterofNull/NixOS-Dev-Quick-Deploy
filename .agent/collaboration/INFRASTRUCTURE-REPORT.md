# INFRASTRUCTURE DIAGNOSTIC SUMMARY — 2026-05-26
## Status
The hybrid-coordinator services are functional for standard queries. The delegation functionality (`/control/ai-coordinator/delegate`) is integrated with a robust retry-with-backoff mechanism, but it continues to fail due to sustained downstream HTTP 429 (Rate Limit) and 503 (Service Unavailable) errors from the `switchboard` proxy.

## Root Cause Analysis
1.  **Shared Circuit Breaking:** The `switchboard` proxy bundles remote and local requests under the same circuit-breaker registry. When remote provider errors trip the circuit breaker, it blocks *all* requests, including local inference/tool execution.
2.  **Missing Local Agent Service:** The `local-agent` profile in `switchboard` does not correspond to an active service on the host, preventing the delegation framework from offloading tasks to local inference lanes.
3.  **Upstream Congestion:** The `switchboard` is consistently receiving `HTTP 429 (Too Many Requests)` from `https://openrouter.ai/api`.

## Infrastructure Actions Required (Remediation Plan)
- **Decouple Proxying (Priority):** Modify `ai-stack/switchboard/switchboard.py` to route local tool/inference calls directly to local endpoints (e.g., `http://127.0.0.1:8080`), bypassing the `switchboard` proxy and its shared circuit breaker.
- **Service Deployment:** Update NixOS configuration to explicitly define and activate the `local-agent` service, ensuring a dedicated inference endpoint is available for local delegation.
- **Provider Quota Management:** Investigate the OpenRouter API dashboard to verify current token usage and quota limits.
- **Proxy Observability:** Enhance `switchboard` logs to distinguish between internal proxy errors, provider-side rate limits, and service-level connectivity failures.
