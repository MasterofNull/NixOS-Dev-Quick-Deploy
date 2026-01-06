# syntax=docker/dockerfile:1.3

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    PIP_PARALLEL_BUILDS=4 \
    PIP_TIMEOUT=300 \
    HTTP_TIMEOUT=300

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for faster downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    pip config set global.timeout 300 && \
    pip config set global.retries 5 && \
    pip install --upgrade pip wheel setuptools

# CRITICAL: Install PyTorch CPU-only FIRST to prevent CUDA dependencies
# sentence-transformers requires PyTorch, so we install CPU version before requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    --timeout 300 \
    --retries 5 \
    torch==2.5.1 torchvision==0.20.1

# Copy requirements and install Python dependencies
COPY nixos-docs/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r /app/requirements.txt

# Copy application code
COPY nixos-docs/ /app/

# Create data directories
RUN mkdir -p /data/cache /data/repos /data/embeddings /app/.nixos_cache

# Make startup script executable
RUN chmod +x /app/start_server.sh

EXPOSE 8094

# Health check (removed - OCI format doesn't support HEALTHCHECK directive)
# Use docker-compose.yml healthcheck configuration instead:
# healthcheck:
#   test: ["CMD", "curl", "-f", "http://localhost:8094/health"]
#   interval: 30s
#   timeout: 10s
#   retries: 5
#   start_period: 60s

# Start the server
CMD ["/app/start_server.sh"]
