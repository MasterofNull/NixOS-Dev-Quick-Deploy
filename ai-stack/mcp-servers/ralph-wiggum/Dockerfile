# syntax=docker/dockerfile:1.3
# Ralph Wiggum Loop - Continuous Autonomous Agent Orchestrator
# Dockerfile for MCP Server
# Version: 1.0.0 (December 2025)

FROM python:3.12-slim

LABEL maintainer="NixOS Quick Deploy AI Stack"
LABEL description="Ralph Wiggum Loop - Continuous self-referential AI orchestration"
LABEL version="1.0.0"

# Set environment for non-interactive apt and faster downloads
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PARALLEL_BUILDS=4 \
    PIP_TIMEOUT=300 \
    HTTP_TIMEOUT=300

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Configure pip for faster downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    pip config set global.timeout 300 && \
    pip config set global.retries 5 && \
    pip install --upgrade pip wheel setuptools

# Copy requirements first for better caching
COPY ralph-wiggum/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r requirements.txt

# Copy shared libraries (for authentication middleware)
COPY shared /app/shared

# Copy application code
COPY ralph-wiggum/server.py .
COPY ralph-wiggum/orchestrator.py .
COPY ralph-wiggum/loop_engine.py .
COPY ralph-wiggum/state_manager.py .
COPY ralph-wiggum/hooks.py .
COPY ralph-wiggum/config/ ./config/

# Create data directories
RUN mkdir -p /data/telemetry /data/state /workspace

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RALPH_MCP_SERVER_PORT=8098
ENV RALPH_LOOP_ENABLED=true

# Health check (removed - OCI format doesn't support HEALTHCHECK directive)
# Use podman-compose.yml healthcheck configuration instead:
# test: ["CMD", "curl", "-f", "http://localhost:8098/health"]

# Expose port
EXPOSE 8098

# Run the server
CMD ["python", "server.py"]
