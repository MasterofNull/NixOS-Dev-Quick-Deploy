# syntax=docker/dockerfile:1.3
# Health Monitor Self-Healing Service Dockerfile
# Lightweight monitoring daemon for automatic container healing

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    PIP_PARALLEL_BUILDS=4 \
    PIP_TIMEOUT=300 \
    HTTP_TIMEOUT=300

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        podman \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for faster downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    pip config set global.timeout 300 && \
    pip config set global.retries 5 && \
    pip install --upgrade pip wheel setuptools

# Copy requirements and install Python dependencies
COPY health-monitor/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r /app/requirements.txt

# Copy application code
COPY health-monitor/self_healing.py /app/
COPY health-monitor/self_healing_daemon.py /app/

# Create log directory
RUN mkdir -p /data/logs

# No exposed ports - this is a monitoring daemon that manages other containers

# Health check (removed - OCI format doesn't support HEALTHCHECK directive)
# Use podman-compose.yml healthcheck configuration instead:
# test: ["CMD", "pgrep", "-f", "self_healing_daemon.py"]

# Start self-healing daemon
CMD ["python", "self_healing_daemon.py"]
