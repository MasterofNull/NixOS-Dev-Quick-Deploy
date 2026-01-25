# Lightweight Python Embedding Service
# Uses sentence-transformers for embeddings
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
# Install PyTorch from CPU-only index
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# Install other packages from PyPI
RUN pip install --no-cache-dir flask sentence-transformers requests

# Copy server code
COPY embeddings-service/server.py .

# Expose port
EXPOSE 8081

# Run server
CMD ["python", "server.py"]
