# Lightweight Python Embedding Service
# Uses sentence-transformers for embeddings
FROM python:3.11-slim

WORKDIR /app

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD python -c "import requests; requests.get('http://localhost:8081/health').raise_for_status()"

# Run server
CMD ["python", "server.py"]
