FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY aidb/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY aidb/ /app/
COPY config/config.yaml /app/config/config.yaml

RUN mkdir -p /data /app/.mcp_cache

# Make startup script executable
RUN chmod +x /app/start_with_discovery.sh

EXPOSE 8091

# Use startup script that launches both server and tool discovery daemon
CMD ["/app/start_with_discovery.sh"]
