FROM docker.io/library/python:3.12-slim

WORKDIR /app

# Install system dependencies for git and Aider
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python server dependencies
COPY aider-wrapper/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install aider CLI separately from the API server dependencies.
# The Nix service injects AIDER_BIN from pkgs.aider-chat; this preserves the
# legacy container path without forcing the server lockfile to track a PyPI-only
# aider package version.
RUN pip install --no-cache-dir aider-chat==0.16.0

# Copy shared libraries (for authentication middleware)
COPY shared /app/shared

# Copy server code
COPY aider-wrapper/server.py .

# Set up git (required by Aider)
RUN git config --global user.name "Aider Bot" && \
    git config --global user.email "aider@ai-stack.local"

# Environment variables
ENV AIDER_WRAPPER_PORT=8099
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8099

# Run server
CMD ["python", "server.py"]
