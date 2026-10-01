# Lightweight Python Embedding Service
# Uses sentence-transformers for embeddings
FROM docker.io/library/python:3.11-slim

WORKDIR /app

# Install system dependencies
# security updates at build time (owner floor-not-pin policy)
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Refresh packaging tooling before installing runtime dependencies so the
# image does not retain known vulnerable pip/wheel/setuptools artifacts.
RUN python -m pip install --no-cache-dir \
    "pip>=26.1" \
    "setuptools>=83.0.0" \
    "wheel>=0.46.3"

# Install dependencies
# Install PyTorch from CPU-only index
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# Install other packages from PyPI
RUN pip install --no-cache-dir flask sentence-transformers requests prometheus-client structlog pydantic pyyaml

# Copy server code and shared config helpers
COPY embeddings-service/server.py .
COPY shared/ /app/shared/
COPY config/config.yaml /app/config/config.yaml

# Expose port
EXPOSE 8081

# Run server
CMD ["python", "server.py"]
