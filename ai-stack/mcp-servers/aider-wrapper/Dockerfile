FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY aider-wrapper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY aider-wrapper/server.py .

# Environment variables
ENV AIDER_WRAPPER_PORT=8099
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8099

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8099/health')" || exit 1

# Run server
CMD ["python", "server.py"]
