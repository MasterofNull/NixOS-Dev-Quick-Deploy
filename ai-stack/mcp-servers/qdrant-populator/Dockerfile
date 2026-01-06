FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    sentence-transformers==3.3.1 \
    qdrant-client==1.12.1

# Copy population script
COPY populate.py /app/populate.py

CMD ["python", "populate.py"]
