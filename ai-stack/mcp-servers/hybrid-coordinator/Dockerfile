# syntax=docker/dockerfile:1.3
# Hybrid Coordinator MCP Server Dockerfile
# Multi-stage build for optimal image size

FROM docker.io/library/python:3.13-slim AS builder

# Set environment for non-interactive apt and faster downloads
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PARALLEL_BUILDS=4 \
    PIP_TIMEOUT=300 \
    HTTP_TIMEOUT=300

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for faster downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    pip config set global.timeout 300 && \
    pip config set global.retries 5 && \
    pip install --upgrade pip wheel setuptools

# Copy requirements and install Python dependencies
# Use --prefix to install to /build/.local instead of /root/.local
COPY hybrid-coordinator/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 --prefix=/build/.local -r requirements.txt

# ============================================================================
# Final Stage
# ============================================================================
FROM docker.io/library/python:3.13-slim

# Set environment for non-interactive apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directory
RUN useradd --create-home --home-dir /opt/coordinator --shell /bin/bash coordinator
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /build/.local /opt/coordinator/.local

# Copy application code
COPY hybrid-coordinator/server.py .
COPY hybrid-coordinator/coordinator.py .
COPY hybrid-coordinator/federation_sync.py .
COPY hybrid-coordinator/continuous_learning.py .
COPY hybrid-coordinator/continuous_learning_daemon.py .
COPY hybrid-coordinator/multi_turn_context.py .
COPY hybrid-coordinator/remote_llm_feedback.py .
COPY hybrid-coordinator/progressive_disclosure.py .
COPY hybrid-coordinator/context_compression.py .
COPY hybrid-coordinator/query_expansion.py .
COPY hybrid-coordinator/embedding_cache.py .
COPY hybrid-coordinator/start_with_learning.sh .
COPY shared/ /app/shared/
COPY config/config.yaml /app/config/config.yaml

# Create data directories and set permissions
RUN mkdir -p /data/telemetry /data/fine-tuning /data/collections && \
    chmod +x /app/start_with_learning.sh && \
    chown -R coordinator:coordinator /data /app /opt/coordinator

# Switch to app user
USER coordinator

# Add local Python packages to PATH
ENV HOME="/opt/coordinator" \
    PATH="/opt/coordinator/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose MCP server port
EXPOSE 8092

# Health check (removed - will be handled by Kubernetes probes)
# OCI format doesn't support HEALTHCHECK directive

# Start server with continuous learning daemon
CMD ["/app/start_with_learning.sh"]
