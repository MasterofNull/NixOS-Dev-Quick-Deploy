# syntax=docker/dockerfile:1.3
FROM docker.io/library/python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    PIP_ONLY_BINARY=:all: \
    TORCH_CUDA_ARCH_LIST="" \
    PIP_PARALLEL_BUILDS=4 \
    HTTP_TIMEOUT=300 \
    PIP_TIMEOUT=300

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        aria2 \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for faster downloads with parallel connections
RUN --mount=type=cache,target=/root/.cache/pip \
    pip config set global.timeout 300 && \
    pip config set global.retries 3 && \
    pip install --upgrade pip wheel setuptools

COPY aidb/requirements.txt /app/requirements.txt

# CRITICAL: Install PyTorch CPU-only FIRST using --index-url (not --extra-index-url)
# This prevents sentence-transformers from pulling in CUDA dependencies
# Cache mount persists pip downloads across rebuilds
# See: https://github.com/pytorch/pytorch/issues/146786
#      https://github.com/UKPLab/sentence-transformers/issues/2637
#      https://pythonspeed.com/articles/docker-cache-pip-downloads/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    --timeout 300 \
    --retries 5 \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1

# Then install remaining dependencies (will use already-installed PyTorch CPU)
# Cache mount reuses previously downloaded packages
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout 300 \
    --retries 5 \
    -r /app/requirements.txt

COPY aidb/ /app/
COPY shared/ /app/shared/
COPY config/config.yaml /app/config/config.yaml

RUN mkdir -p /data /app/.mcp_cache

# Make startup script executable
RUN chmod +x /app/start_with_discovery.sh

EXPOSE 8091

# Use startup script that launches both server and tool discovery daemon
CMD ["/app/start_with_discovery.sh"]
