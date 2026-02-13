#!/bin/bash
# Record Claude Code VSCode Extension Errors
# Date: 2026-01-08 22:28:10 - 22:28:40

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Recording Claude Code VSCode Extension errors..."

# Error 1: Connection error causing fallback to non-streaming mode
"${SCRIPT_DIR}/record-issue.py" \
  "Claude Code streaming connection failed" \
  "The Claude Code VSCode extension encountered a connection error and fell back to non-streaming mode. This happened at 2026-01-09T06:28:11.068Z during API communication. The error indicates intermittent connectivity issues with the Anthropic API." \
  --severity medium \
  --category reliability \
  --component claude-code-vscode \
  --error "Error streaming, falling back to non-streaming mode: Connection error" \
  --error-type "ConnectionError" \
  --context '{"timestamp": "2026-01-09T06:28:11.068Z", "operation": "API streaming", "fallback": "non-streaming mode"}' \
  --fix "Add retry logic with exponential backoff for streaming connections" \
  --fix "Implement connection health checks before attempting streaming" \
  --fix "Add network connectivity validation on startup" \
  --change "Implement graceful degradation from streaming to non-streaming" \
  --change "Add metrics for streaming vs non-streaming API usage" \
  --change "Configure streaming timeout and retry parameters" \
  --tag vscode --tag api --tag streaming --tag connection

# Error 2: Event logging export failure
"${SCRIPT_DIR}/record-issue.py" \
  "1P event logging export failed" \
  "The Claude Code extension failed to export 2 telemetry events to the 1Password analytics system. This occurred at 2026-01-09T06:28:30.486Z. The error suggests that event queuing and retry logic may need improvement." \
  --severity low \
  --category monitoring \
  --component claude-code-vscode \
  --error "1P event logging: 2 events failed to export" \
  --error-type "ExportError" \
  --stack-trace "Error: Error: 1P event logging: 2 events failed to export
    at \$i1.queueFailedEvents (file://$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js:262:2038)
    at async \$i1.doExport (file://$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js:262:1195)" \
  --context '{"timestamp": "2026-01-09T06:28:30.486Z", "failed_events": 2, "operation": "telemetry export"}' \
  --fix "Implement local event queue persistence for offline scenarios" \
  --fix "Add retry logic with exponential backoff for event exports" \
  --fix "Make telemetry export non-blocking and asynchronous" \
  --change "Add telemetry export health monitoring" \
  --change "Implement graceful degradation if telemetry fails" \
  --change "Configure telemetry batch size and timeout parameters" \
  --tag vscode --tag telemetry --tag 1password --tag analytics

# Error 3: Aggregate network error with TLS socket
"${SCRIPT_DIR}/record-issue.py" \
  "TLS socket connection aggregate error" \
  "The Claude Code extension encountered an AggregateError with the underlying TLS socket connection at 2026-01-09T06:28:40.496Z. This appears to be a network-level error affecting the HTTP client. The error propagated through multiple layers (ClientRequest → TLSSocket → socketErrorListener)." \
  --severity high \
  --category reliability \
  --component claude-code-vscode \
  --error "AggregateError in TLS socket connection" \
  --error-type "AggregateError" \
  --stack-trace "AggregateError: AggregateError
    at r5A.from (file://$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js:43:59581)
    at yU.<anonymous> (file://$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js:57:10021)
    at yU.emit (node:events:531:35)
    at yU.emit (node:domain:489:12)
    at ClientRequest.emit (node:events:531:35)
    at ClientRequest.emit (node:domain:489:12)
    at emitErrorEvent (node:_http_client:107:11)
    at TLSSocket.socketErrorListener (node:_http_client:574:5)
    at TLSSocket.emit (node:events:519:28)" \
  --context '{"timestamp": "2026-01-09T06:28:40.496Z", "layer": "TLS socket", "http_client": "ClientRequest", "event": "socketErrorListener"}' \
  --fix "Add TLS connection error handling with detailed error reporting" \
  --fix "Implement connection pool health checks" \
  --fix "Add circuit breaker pattern for repeated connection failures" \
  --fix "Validate TLS certificates and handle cert errors gracefully" \
  --change "Implement comprehensive network error recovery strategy" \
  --change "Add network diagnostics (DNS, TLS handshake, connectivity)" \
  --change "Configure HTTP client timeouts and retry parameters" \
  --change "Add monitoring for TLS connection failures" \
  --tag vscode --tag tls --tag network --tag connection --tag aggregate-error

echo ""
echo "✅ All errors recorded successfully!"
echo ""
echo "Next steps:"
echo "  1. List recorded issues: ./scripts/list-issues.py"
echo "  2. Analyze patterns: ./scripts/analyze-issues.py"
echo "  3. Review suggested fixes in the output above"
