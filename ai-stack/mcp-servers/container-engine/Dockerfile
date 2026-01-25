FROM python:3.13-slim

LABEL maintainer="NixOS Quick Deploy AI Stack"
LABEL description="Container Engine MCP Server - Docker/Podman management and best practices"

WORKDIR /app

# Install podman CLI tools
RUN apt-get update && apt-get install -y \
    podman \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY container-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries (for Podman API client)
COPY shared /app/shared

COPY container-engine/server.py .

EXPOSE 8095

CMD ["python", "server.py"]
