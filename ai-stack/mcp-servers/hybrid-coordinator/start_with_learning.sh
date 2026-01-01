#!/usr/bin/env bash
# Start Hybrid Coordinator with Continuous Learning
# Runs both the main server and the learning pipeline daemon

set -e

# Redirect all output to console (unbuffered)
exec 1>&1 2>&2

# Configuration from environment
export CONTINUOUS_LEARNING_ENABLED="${CONTINUOUS_LEARNING_ENABLED:-true}"
export LEARNING_PROCESSING_INTERVAL="${LEARNING_PROCESSING_INTERVAL:-3600}"
export LEARNING_DATASET_THRESHOLD="${LEARNING_DATASET_THRESHOLD:-1000}"

echo "Starting Hybrid Coordinator with Continuous Learning..." >&2
echo "Learning enabled: $CONTINUOUS_LEARNING_ENABLED" >&2
echo "Processing interval: ${LEARNING_PROCESSING_INTERVAL}s" >&2

# Start main server in background with unbuffered output
python3 -u /app/server.py "$@" 2>&1 &
SERVER_PID=$!
echo "Server started with PID: $SERVER_PID" >&2

# Start continuous learning daemon if enabled
if [ "$CONTINUOUS_LEARNING_ENABLED" = "true" ]; then
    python3 -u /app/continuous_learning_daemon.py 2>&1 &
    LEARNING_PID=$!
    echo "Learning daemon started with PID: $LEARNING_PID" >&2

    # Wait for either process to exit
    wait -n $SERVER_PID $LEARNING_PID
    EXIT_CODE=$?

    # Kill both processes on exit
    kill $SERVER_PID $LEARNING_PID 2>/dev/null || true
else
    echo "Continuous learning disabled, running server only" >&2
    wait $SERVER_PID
    EXIT_CODE=$?
fi

exit $EXIT_CODE
