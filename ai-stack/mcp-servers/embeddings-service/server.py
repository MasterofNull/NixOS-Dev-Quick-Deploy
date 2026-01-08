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
from uuid import uuid4
from typing import Dict, List, Optional, Union
from functools import wraps
from concurrent.futures import Future, TimeoutError as FutureTimeout
from queue import Queue, Empty

from flask import Flask, jsonify, request, g, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sentence_transformers import SentenceTransformer
import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars, clear_contextvars

from shared.stack_settings import EmbeddingsSettings

SERVICE_NAME = "embeddings-service"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")


def configure_logging() -> None:
    bind_contextvars(service=SERVICE_NAME, version=SERVICE_VERSION)
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    pre_chain = [
        merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=pre_chain,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers.clear()
    if root.handlers:
        werkzeug_logger.addHandler(root.handlers[0])
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.propagate = False

    structlog.configure(
        processors=pre_chain + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


configure_logging()
logger = logging.getLogger(SERVICE_NAME)

# Configuration
SETTINGS = EmbeddingsSettings.load()
MODEL_NAME = os.getenv("EMBEDDING_MODEL", SETTINGS.model)
PORT = int(os.getenv("PORT", SETTINGS.port))
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", SETTINGS.max_input_length))  # Max characters per input
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", SETTINGS.max_batch_size))  # Max inputs per request
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", SETTINGS.request_timeout))  # Seconds
MODEL_LOAD_RETRIES = int(os.getenv("MODEL_LOAD_RETRIES", SETTINGS.model_load_retries))
MODEL_LOAD_RETRY_DELAY = int(os.getenv("MODEL_LOAD_RETRY_DELAY", SETTINGS.model_load_retry_delay))  # Seconds
BATCH_MAX_SIZE = int(os.getenv("BATCH_MAX_SIZE", SETTINGS.batch_max_size))
BATCH_MAX_LATENCY_MS = int(os.getenv("BATCH_MAX_LATENCY_MS", SETTINGS.batch_max_latency_ms))
BATCH_QUEUE_MAX = int(os.getenv("BATCH_QUEUE_MAX", SETTINGS.batch_queue_max))

app = Flask(__name__)

# API key handling
API_KEY_FILE = os.getenv("EMBEDDINGS_API_KEY_FILE") or (SETTINGS.api_key_file or "")


def read_secret(path: str) -> Optional[str]:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return None


API_KEY = os.getenv("EMBEDDINGS_API_KEY") or read_secret(API_KEY_FILE)


def error_payload(message: str, exc: Exception) -> Dict[str, str]:
    error_id = uuid4().hex[:12]
    logger.exception("%s error_id=%s", message, error_id)
    return {"error": message, "error_id": error_id}


def _get_process_memory_bytes() -> int:
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            rss_pages = int(handle.read().split()[1])
        return rss_pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return 0

# Global state
model_instance: Optional[SentenceTransformer] = None
model_lock = threading.Lock()
model_loading = False
model_load_error: Optional[str] = None
model_load_start_time: Optional[float] = None

# Batching
class BatchRequest:
    def __init__(self, texts: List[str]):
        self.texts = texts
        self.future: Future = Future()
        self.enqueued_at = time.monotonic()


class EmbeddingBatcher:
    def __init__(self, max_batch_size: int, max_latency_ms: int, max_queue_size: int):
        self._max_batch_size = max_batch_size
        self._max_latency = max_latency_ms / 1000.0
        self._queue: Queue[BatchRequest] = Queue(maxsize=max_queue_size)
        self._running = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._thread.start()

    def submit(self, texts: List[str]) -> Future:
        if not self._running.is_set():
            raise RuntimeError("batcher_not_running")
        request_item = BatchRequest(texts)
        try:
            self._queue.put(request_item, timeout=0.1)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("batch_queue_full") from exc
        BATCH_QUEUE_DEPTH.set(self._queue.qsize())
        return request_item.future

    def _worker(self) -> None:
        pending: Optional[BatchRequest] = None
        while self._running.is_set():
            try:
                if pending is not None:
                    item = pending
                    pending = None
                else:
                    item = self._queue.get(timeout=0.1)
            except Empty:
                continue

            batch = [item]
            total = len(item.texts)
            deadline = time.monotonic() + self._max_latency

            while total < self._max_batch_size:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                try:
                    next_item = self._queue.get(timeout=timeout)
                except Empty:
                    break

                if total + len(next_item.texts) > self._max_batch_size:
                    pending = next_item
                    break

                batch.append(next_item)
                total += len(next_item.texts)

            BATCH_QUEUE_DEPTH.set(self._queue.qsize())
            BATCH_SIZE.observe(total)

            try:
                model = get_model()
                merged: List[str] = []
                slices: List[tuple[BatchRequest, int, int]] = []
                for request_item in batch:
                    start = len(merged)
                    merged.extend(request_item.texts)
                    slices.append((request_item, start, len(merged)))

                embeddings = model.encode(merged)
                if hasattr(embeddings, "tolist"):
                    embeddings = embeddings.tolist()

                for request_item, start, end in slices:
                    wait_time = time.monotonic() - request_item.enqueued_at
                    BATCH_WAIT_SECONDS.observe(wait_time)
                    request_item.future.set_result(
                        [list(map(float, vector)) for vector in embeddings[start:end]]
                    )
            except Exception as exc:  # noqa: BLE001
                for request_item in batch:
                    request_item.future.set_exception(exc)


batcher = EmbeddingBatcher(BATCH_MAX_SIZE, BATCH_MAX_LATENCY_MS, BATCH_QUEUE_MAX)

# Metrics
REQUEST_COUNT = Counter(
    "embeddings_requests_total",
    "Total embedding service requests",
    ["endpoint", "status"],
)
REQUEST_ERRORS = Counter(
    "embeddings_request_errors_total",
    "Total embedding service request errors",
    ["endpoint", "method"],
)
REQUEST_LATENCY = Histogram(
    "embeddings_request_latency_seconds",
    "Embedding service HTTP request latency in seconds",
    ["endpoint", "method"],
)
MODEL_LOAD_SECONDS = Gauge(
    "embeddings_model_load_seconds",
    "Embedding model load duration in seconds",
)
PROCESS_MEMORY_BYTES = Gauge(
    "embeddings_process_memory_bytes",
    "Embedding service process resident memory in bytes",
)
BATCH_SIZE = Histogram(
    "embeddings_batch_size",
    "Embedding batch size",
)
BATCH_QUEUE_DEPTH = Gauge(
    "embeddings_batch_queue_depth",
    "Embedding batch queue depth",
)
BATCH_WAIT_SECONDS = Histogram(
    "embeddings_batch_wait_seconds",
    "Time requests spend waiting for batch execution",
)


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
            if model_load_start_time is not None:
                MODEL_LOAD_SECONDS.set(time.time() - model_load_start_time)

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


@app.before_request
def enforce_api_key():
    if request.path in ("/health", "/metrics"):
        return None
    if not API_KEY:
        return None
    token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    if token != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.before_request
def assign_request_id():
    g.request_id = request.headers.get("X-Request-ID") or uuid4().hex
    g.request_start = time.time()
    bind_contextvars(request_id=g.request_id)


@app.after_request
def add_request_id_header(response):
    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id
    duration = time.time() - getattr(g, "request_start", time.time())
    REQUEST_LATENCY.labels(request.path, request.method).observe(duration)
    REQUEST_COUNT.labels(request.path, str(response.status_code)).inc()
    if response.status_code >= 400:
        REQUEST_ERRORS.labels(request.path, request.method).inc()
    clear_contextvars()
    return response


@app.route("/metrics", methods=["GET"])
def metrics():
    PROCESS_MEMORY_BYTES.set(_get_process_memory_bytes())
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


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
        return jsonify(error_payload("model_not_ready", e)), 503


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

        future = batcher.submit(texts)
        embeddings = future.result(timeout=REQUEST_TIMEOUT)

        return jsonify(embeddings), 200

    except FutureTimeout:
        logger.error(f"Embedding generation timed out after {REQUEST_TIMEOUT}s")
        return jsonify({"error": "Request timed out"}), 504
    except RuntimeError as e:
        if str(e) == "batch_queue_full":
            return jsonify({"error": "Service overloaded"}), 503
        return jsonify(error_payload("service_not_ready", e)), 503

    except RuntimeError as e:
        return jsonify(error_payload("service_not_ready", e)), 503

    except Exception as e:
        return jsonify(error_payload("internal_error", e)), 500


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

        future = batcher.submit(texts)
        embeddings = future.result(timeout=REQUEST_TIMEOUT)

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

    except FutureTimeout:
        logger.error(f"Embedding generation timed out after {REQUEST_TIMEOUT}s")
        return jsonify({"error": {"message": "Request timed out", "type": "timeout"}}), 504

    except RuntimeError as e:
        if str(e) == "batch_queue_full":
            return jsonify({"error": {"message": "Service overloaded", "type": "overloaded"}}), 503
        payload = error_payload("service_not_ready", e)
        return jsonify({"error": {"message": "Service not ready", "type": "service_unavailable", **payload}}), 503

    except Exception as e:
        payload = error_payload("internal_error", e)
        return jsonify({"error": {"message": "Internal server error", "type": "internal_error", **payload}}), 500


def startup_model_loading():
    """
    Start model loading in background thread during Flask startup

    This allows the Flask server to start and respond to health checks
    while the model loads in the background.
    """
    logger.info("Starting background model loading...")
    thread = threading.Thread(target=load_model_with_retry, daemon=True)
    thread.start()
    batcher.start()


if __name__ == "__main__":
    logger.info(f"Starting Embeddings Service")
    logger.info(f"Model: {MODEL_NAME}")
    logger.info(f"Port: {PORT}")
    logger.info(f"Max input length: {MAX_INPUT_LENGTH} characters")
    logger.info(f"Max batch size: {MAX_BATCH_SIZE}")
    logger.info(f"Request timeout: {REQUEST_TIMEOUT}s")
    logger.info(f"Batch max size: {BATCH_MAX_SIZE}")
    logger.info(f"Batch max latency: {BATCH_MAX_LATENCY_MS}ms")
    logger.info(f"Batch queue max: {BATCH_QUEUE_MAX}")

    # Start model loading in background
    startup_model_loading()

    # Start Flask server
    # Note: Flask development server is single-threaded
    # For production, use gunicorn: gunicorn -w 4 -b 0.0.0.0:8081 server:app
    app.run(host="0.0.0.0", port=PORT, threaded=True)
