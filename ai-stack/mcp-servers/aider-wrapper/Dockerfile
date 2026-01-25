FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for git and Aider
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python dependencies
COPY aider-wrapper/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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
