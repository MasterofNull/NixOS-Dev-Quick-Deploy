# Hybrid Coordinator MCP Server Dockerfile
# Multi-stage build for optimal image size

FROM python:3.13-slim AS builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY hybrid-coordinator/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================================
# Final Stage
# ============================================================================
FROM python:3.13-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directory
RUN useradd --create-home --shell /bin/bash coordinator
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/coordinator/.local

# Copy application code
COPY hybrid-coordinator/server.py .
COPY hybrid-coordinator/coordinator.py .
COPY hybrid-coordinator/federation_sync.py .
COPY hybrid-coordinator/continuous_learning.py .
COPY hybrid-coordinator/continuous_learning_daemon.py .
COPY hybrid-coordinator/start_with_learning.sh .

# Create data directories and set permissions
RUN mkdir -p /data/telemetry /data/fine-tuning /data/collections && \
    chmod +x /app/start_with_learning.sh && \
    chown -R coordinator:coordinator /data /app

# Switch to app user
USER coordinator

# Add local Python packages to PATH
ENV PATH="/home/coordinator/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose MCP server port
EXPOSE 8092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8092/health || exit 1

# Start server with continuous learning daemon
CMD ["/app/start_with_learning.sh"]
