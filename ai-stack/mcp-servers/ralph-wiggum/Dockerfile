# Ralph Wiggum Loop - Continuous Autonomous Agent Orchestrator
# Dockerfile for MCP Server
# Version: 1.0.0 (December 2025)

FROM python:3.12-slim

LABEL maintainer="NixOS Quick Deploy AI Stack"
LABEL description="Ralph Wiggum Loop - Continuous self-referential AI orchestration"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY ralph-wiggum/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8098/health || exit 1

# Expose port
EXPOSE 8098

# Run the server
CMD ["python", "server.py"]
