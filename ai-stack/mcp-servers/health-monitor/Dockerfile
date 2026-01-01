# Health Monitor Self-Healing Service Dockerfile
# Lightweight monitoring daemon for automatic container healing

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        podman \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY health-monitor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY health-monitor/self_healing.py /app/
COPY health-monitor/self_healing_daemon.py /app/

# Create log directory
RUN mkdir -p /data/logs

# No exposed ports - this is a monitoring daemon that manages other containers

# Health check (verify daemon is running)
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f self_healing_daemon.py || exit 1

# Start self-healing daemon
CMD ["python", "self_healing_daemon.py"]
