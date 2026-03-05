#!/bin/bash
# Simple continuous learning test
TELEMETRY_FILE="$HOME/.local/share/ai-test-telemetry/test-events.jsonl"

echo '{"timestamp":"2025-12-22T13:40:00","event_type":"query_routed","source":"hybrid_coordinator","metadata":{"query":"How to enable Docker in NixOS?","decision":"local","tokens_saved":500}}' >> "$TELEMETRY_FILE"
echo '{"timestamp":"2025-12-22T13:40:05","event_type":"query_routed","source":"hybrid_coordinator","metadata":{"query":"Design microservices architecture","decision":"remote","tokens_saved":0}}' >> "$TELEMETRY_FILE"
echo '{"timestamp":"2025-12-22T13:40:10","event_type":"query_routed","source":"hybrid_coordinator","metadata":{"query":"Fix GNOME keyring error","decision":"local","tokens_saved":450}}' >> "$TELEMETRY_FILE"
echo '{"timestamp":"2025-12-22T13:40:15","event_type":"query_routed","source":"hybrid_coordinator","metadata":{"query":"Configure Bluetooth","decision":"local","tokens_saved":480}}' >> "$TELEMETRY_FILE"
echo '{"timestamp":"2025-12-22T13:40:20","event_type":"query_routed","source":"hybrid_coordinator","metadata":{"query":"List running services","decision":"local","tokens_saved":300}}' >> "$TELEMETRY_FILE"

echo "✅ Created 5 test telemetry events"
echo ""
echo "📊 Analysis:"
LOCAL=$(grep -c '"decision":"local"' "$TELEMETRY_FILE")
REMOTE=$(grep -c '"decision":"remote"' "$TELEMETRY_FILE")
TOTAL=$((LOCAL + REMOTE))
LOCAL_PCT=$(awk "BEGIN {printf \"%.0f\", ($LOCAL / $TOTAL) * 100}")
TOKENS=$(grep '"tokens_saved"' "$TELEMETRY_FILE" | grep -o '"tokens_saved":[0-9]*' | cut -d: -f2 | awk '{s+=$1} END {print s}')

echo "  Total queries: $TOTAL"
echo "  Local queries: $LOCAL ($LOCAL_PCT%)"
echo "  Remote queries: $REMOTE"
echo "  Tokens saved: $TOKENS"
echo ""
echo "💰 Cost Savings:"
COST=$(awk "BEGIN {printf \"%.2f\", ($TOKENS / 1000) * 0.015}")
MONTHLY=$(awk "BEGIN {printf \"%.2f\", $COST * 30}")
echo "  Money saved: \$$COST"
echo "  Projected monthly: \$$MONTHLY"
echo ""
cat "$TELEMETRY_FILE"
