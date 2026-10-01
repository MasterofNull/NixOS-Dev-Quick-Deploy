# syntax=docker/dockerfile:1.3

FROM docker.io/library/python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    PIP_PARALLEL_BUILDS=4 \
    PIP_TIMEOUT=300 \
    HTTP_TIMEOUT=300

# Install system dependencies
# security updates at build time (owner floor-not-pin policy)
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
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
    pip install "pip>=26.1" "wheel>=0.46.3" "setuptools>=83.0.0"

# CRITICAL: Install PyTorch CPU-only FIRST to prevent CUDA dependencies
# sentence-transformers requires PyTorch, so we install CPU version before requirements.txt
# Use floors (>=) to allow newer CPU-compatible versions (exact pins only in requirements.lock)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    --timeout 300 \
    --retries 5 \
    "torch>=2.11.0" "torchvision>=0.26.0"

# Copy requirements and install Python dependencies.
COPY nixos-docs/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r /app/requirements.txt

# FINAL: Verify floor versions after all dependency installs to catch downgrades
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade "pip>=26.1" "wheel>=0.46.3" "setuptools>=83.0.0" && \
    python -c "import setuptools,sys; v=tuple(int(x) for x in setuptools.__version__.split('.')[:2]); sys.exit(0 if v>=(83,0) else 1)"

# Copy shared libraries (for authentication middleware)
COPY shared /app/shared

# Copy application code
COPY nixos-docs/ /app/

# Create data directories
RUN mkdir -p /data/cache /data/repos /data/embeddings /app/.nixos_cache

# Make startup script executable
RUN chmod +x /app/start_server.sh

EXPOSE 8094

# Health check (removed - OCI format doesn't support HEALTHCHECK directive)
# Use Kubernetes probe configuration instead:
# healthcheck:
#   test: ["CMD", "curl", "-f", "http://localhost:8094/health"]
#   interval: 30s
#   timeout: 10s
#   retries: 5
#   start_period: 60s

# Start the server
CMD ["/app/start_server.sh"]
