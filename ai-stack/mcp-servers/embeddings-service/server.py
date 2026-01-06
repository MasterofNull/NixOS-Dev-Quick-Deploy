#!/usr/bin/env python3
"""
Resilient Embedding Service using sentence-transformers
Provides OpenAI-compatible and TEI-compatible APIs with production-grade error handling

Features:
- Async model loading with retry logic
- Request timeout and size validation
- Graceful error handling
- Health checks that accurately reflect readiness
- Thread-safe model access
"""

import asyncio
import logging
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Union
from functools import wraps

from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("embeddings-service")

# Configuration
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
PORT = int(os.getenv("PORT", 8081))
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", 10000))  # Max characters per input
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", 32))  # Max inputs per request
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))  # Seconds
MODEL_LOAD_RETRIES = int(os.getenv("MODEL_LOAD_RETRIES", 3))
MODEL_LOAD_RETRY_DELAY = int(os.getenv("MODEL_LOAD_RETRY_DELAY", 5))  # Seconds

app = Flask(__name__)

# Global state
model_instance: Optional[SentenceTransformer] = None
model_lock = threading.Lock()
model_loading = False
model_load_error: Optional[str] = None
model_load_start_time: Optional[float] = None


class ValidationError(Exception):
    """Input validation error"""
    pass


def timeout_decorator(seconds: int):
    """Decorator to add timeout to functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")

            if exception[0]:
                raise exception[0]

            return result[0]
        return wrapper
    return decorator


def load_model_with_retry() -> SentenceTransformer:
    """
    Load sentence-transformers model with retry logic

    Handles:
    - Network failures during model download
    - Disk space issues
    - Model corruption
    - Hugging Face rate limiting
    """
    global model_instance, model_loading, model_load_error, model_load_start_time

    model_loading = True
    model_load_start_time = time.time()
    model_load_error = None

    for attempt in range(1, MODEL_LOAD_RETRIES + 1):
        try:
            logger.info(f"Loading model '{MODEL_NAME}' (attempt {attempt}/{MODEL_LOAD_RETRIES})...")

            # Load model with timeout (prevent hanging on network issues)
            @timeout_decorator(120)  # 2 minute timeout for model download
            def load():
                return SentenceTransformer(MODEL_NAME, device="cpu")

            model = load()

            # Verify model loaded correctly
            test_embedding = model.encode("test")
            if test_embedding is None or len(test_embedding) == 0:
                raise RuntimeError("Model loaded but failed test encoding")

            logger.info(
                f"Model loaded successfully. "
                f"Dimensions: {model.get_sentence_embedding_dimension()}, "
                f"Max sequence length: {model.max_seq_length}, "
                f"Load time: {time.time() - model_load_start_time:.2f}s"
            )

            model_instance = model
            model_loading = False
            return model

        except TimeoutError as e:
            error_msg = f"Model loading timed out on attempt {attempt}: {e}"
            logger.error(error_msg)
            model_load_error = error_msg

        except OSError as e:
            # Disk full, network issues, etc.
            error_msg = f"OS error during model loading (attempt {attempt}): {e}"
            logger.error(error_msg)
            model_load_error = error_msg

        except Exception as e:
            error_msg = f"Unexpected error during model loading (attempt {attempt}): {e}"
            logger.exception(error_msg)
            model_load_error = error_msg

        # Wait before retry (exponential backoff)
        if attempt < MODEL_LOAD_RETRIES:
            delay = MODEL_LOAD_RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    # All retries failed
    model_loading = False
    final_error = f"Failed to load model after {MODEL_LOAD_RETRIES} attempts: {model_load_error}"
    logger.error(final_error)
    raise RuntimeError(final_error)


def get_model() -> SentenceTransformer:
    """
    Get model instance with thread-safe lazy loading

    Returns:
        SentenceTransformer instance

    Raises:
        RuntimeError: If model failed to load
    """
    global model_instance

    # Fast path: model already loaded
    if model_instance is not None:
        return model_instance

    # Model is being loaded by another thread
    if model_loading:
        # Wait for loading to complete
        max_wait = 180  # 3 minutes
        start = time.time()
        while model_loading and (time.time() - start) < max_wait:
            time.sleep(0.5)

        if model_instance is not None:
            return model_instance

        raise RuntimeError(f"Model loading timed out or failed: {model_load_error}")

    # Need to load model
    with model_lock:
        # Double-check after acquiring lock
        if model_instance is not None:
            return model_instance

        return load_model_with_retry()


def validate_input(inputs: Union[str, List[str]]) -> List[str]:
    """
    Validate and normalize input

    Args:
        inputs: Single string or list of strings

    Returns:
        List of validated strings

    Raises:
        ValidationError: If input invalid
    """
    # Normalize to list
    if isinstance(inputs, str):
        texts = [inputs]
    elif isinstance(inputs, list):
        texts = inputs
    else:
        raise ValidationError("Input must be string or list of strings")

    # Validate not empty
    if not texts:
        raise ValidationError("Input list cannot be empty")

    # Validate batch size
    if len(texts) > MAX_BATCH_SIZE:
        raise ValidationError(
            f"Batch size {len(texts)} exceeds maximum {MAX_BATCH_SIZE}"
        )

    # Validate each text
    validated = []
    for i, text in enumerate(texts):
        if not isinstance(text, str):
            raise ValidationError(f"Input at index {i} must be string, got {type(text)}")

        if not text.strip():
            raise ValidationError(f"Input at index {i} cannot be empty")

        if len(text) > MAX_INPUT_LENGTH:
            raise ValidationError(
                f"Input at index {i} length {len(text)} exceeds maximum {MAX_INPUT_LENGTH}"
            )

        validated.append(text)

    return validated


@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint with accurate readiness reporting

    Returns:
        200 OK if model loaded and ready
        503 Service Unavailable if model still loading or failed
    """
    if model_instance is not None:
        return jsonify({
            "status": "ok",
            "model": MODEL_NAME,
            "ready": True
        }), 200

    if model_loading:
        elapsed = time.time() - model_load_start_time if model_load_start_time else 0
        return jsonify({
            "status": "loading",
            "model": MODEL_NAME,
            "ready": False,
            "loading_time_seconds": round(elapsed, 2)
        }), 503

    return jsonify({
        "status": "error",
        "model": MODEL_NAME,
        "ready": False,
        "error": model_load_error or "Model not loaded"
    }), 503


@app.route("/info", methods=["GET"])
def info():
    """Model information endpoint"""
    try:
        model = get_model()
        return jsonify({
            "model": MODEL_NAME,
            "dimensions": model.get_sentence_embedding_dimension(),
            "max_sequence_length": model.max_seq_length,
            "status": "ready"
        }), 200
    except RuntimeError as e:
        return jsonify({
            "error": "Model not ready",
            "details": str(e)
        }), 503


@app.route("/embed", methods=["POST"])
def embed():
    """
    TEI-compatible embedding endpoint

    Request: {"inputs": "text"} or {"inputs": ["text1", "text2"]}
    Response: [[embedding1], [embedding2]] or [[embedding]]
    """
    try:
        # Get request data
        data = request.get_json()
        if data is None:
            return jsonify({"error": "Request body must be JSON"}), 400

        inputs = data.get("inputs")
        if inputs is None:
            return jsonify({"error": "Missing 'inputs' in request"}), 400

        # Validate input
        try:
            texts = validate_input(inputs)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        # Get model (may raise if not loaded)
        model = get_model()

        # Generate embeddings with timeout
        @timeout_decorator(REQUEST_TIMEOUT)
        def generate():
            return [model.encode(text).tolist() for text in texts]

        embeddings = generate()

        return jsonify(embeddings), 200

    except TimeoutError:
        logger.error(f"Embedding generation timed out after {REQUEST_TIMEOUT}s")
        return jsonify({"error": "Request timed out"}), 504

    except RuntimeError as e:
        logger.error(f"Model not ready: {e}")
        return jsonify({"error": "Service not ready", "details": str(e)}), 503

    except Exception as e:
        logger.exception("Unexpected error during embedding generation")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/v1/embeddings", methods=["POST"])
def openai_embeddings():
    """
    OpenAI-compatible embedding endpoint

    Request: {"input": "text"} or {"input": ["text1", "text2"]}
    Response: {"data": [{"embedding": [...], "index": 0}], "model": "...", ...}
    """
    try:
        # Get request data
        data = request.get_json()
        if data is None:
            return jsonify({"error": {"message": "Request body must be JSON", "type": "invalid_request_error"}}), 400

        text_input = data.get("input")
        if text_input is None:
            return jsonify({"error": {"message": "Missing 'input' in request", "type": "invalid_request_error"}}), 400

        # Validate input
        try:
            texts = validate_input(text_input)
        except ValidationError as e:
            return jsonify({"error": {"message": str(e), "type": "invalid_request_error"}}), 400

        # Get model (may raise if not loaded)
        model = get_model()

        # Generate embeddings with timeout
        @timeout_decorator(REQUEST_TIMEOUT)
        def generate():
            return [model.encode(text).tolist() for text in texts]

        embeddings = generate()

        # Format as OpenAI API response
        response = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": emb,
                    "index": idx
                }
                for idx, emb in enumerate(embeddings)
            ],
            "model": MODEL_NAME,
            "usage": {
                "prompt_tokens": sum(len(text.split()) for text in texts),
                "total_tokens": sum(len(text.split()) for text in texts)
            }
        }

        return jsonify(response), 200

    except TimeoutError:
        logger.error(f"Embedding generation timed out after {REQUEST_TIMEOUT}s")
        return jsonify({"error": {"message": "Request timed out", "type": "timeout"}}), 504

    except RuntimeError as e:
        logger.error(f"Model not ready: {e}")
        return jsonify({"error": {"message": "Service not ready", "type": "service_unavailable"}}), 503

    except Exception as e:
        logger.exception("Unexpected error during embedding generation")
        return jsonify({"error": {"message": "Internal server error", "type": "internal_error"}}), 500


def startup_model_loading():
    """
    Start model loading in background thread during Flask startup

    This allows the Flask server to start and respond to health checks
    while the model loads in the background.
    """
    logger.info("Starting background model loading...")
    thread = threading.Thread(target=load_model_with_retry, daemon=True)
    thread.start()


if __name__ == "__main__":
    logger.info(f"Starting Embeddings Service")
    logger.info(f"Model: {MODEL_NAME}")
    logger.info(f"Port: {PORT}")
    logger.info(f"Max input length: {MAX_INPUT_LENGTH} characters")
    logger.info(f"Max batch size: {MAX_BATCH_SIZE}")
    logger.info(f"Request timeout: {REQUEST_TIMEOUT}s")

    # Start model loading in background
    startup_model_loading()

    # Start Flask server
    # Note: Flask development server is single-threaded
    # For production, use gunicorn: gunicorn -w 4 -b 0.0.0.0:8081 server:app
    app.run(host="0.0.0.0", port=PORT, threaded=True)
