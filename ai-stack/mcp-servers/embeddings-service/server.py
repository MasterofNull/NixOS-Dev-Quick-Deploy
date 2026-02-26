#!/usr/bin/env python3
"""
Resilient Embedding Service using sentence-transformers
Provides OpenAI-compatible and TEI-compatible APIs with production-grade error handling.
Migration: Flask → FastAPI (v2.0.0)

Features:
- Async model loading with retry logic
- Request timeout and size validation
- Graceful error handling
- Health checks that accurately reflect readiness
- Thread-safe model access via EmbeddingBatcher daemon thread
- asyncio.to_thread for non-blocking future.result() in async endpoints
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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sentence_transformers import SentenceTransformer
import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars, clear_contextvars

from shared.stack_settings import EmbeddingsSettings

SERVICE_NAME = "embeddings-service"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "2.0.0")


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
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", SETTINGS.max_input_length))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", SETTINGS.max_batch_size))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", SETTINGS.request_timeout))
MODEL_LOAD_RETRIES = int(os.getenv("MODEL_LOAD_RETRIES", SETTINGS.model_load_retries))
MODEL_LOAD_RETRY_DELAY = int(os.getenv("MODEL_LOAD_RETRY_DELAY", SETTINGS.model_load_retry_delay))
BATCH_MAX_SIZE = int(os.getenv("BATCH_MAX_SIZE", SETTINGS.batch_max_size))
BATCH_MAX_LATENCY_MS = int(os.getenv("BATCH_MAX_LATENCY_MS", SETTINGS.batch_max_latency_ms))
BATCH_QUEUE_MAX = int(os.getenv("BATCH_QUEUE_MAX", SETTINGS.batch_queue_max))

# API key
API_KEY_FILE = os.getenv("EMBEDDINGS_API_KEY_FILE") or (SETTINGS.api_key_file or "")


def read_secret(path: str) -> Optional[str]:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return None


API_KEY = read_secret(API_KEY_FILE)


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


# ============================================================================
# Global model state
# ============================================================================

model_instance: Optional[SentenceTransformer] = None
model_lock = threading.Lock()
model_loading = False
model_load_error: Optional[str] = None
model_load_start_time: Optional[float] = None


# ============================================================================
# Batching (thread-based; encode is CPU-bound, runs in daemon thread)
# ============================================================================

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
        except Exception as exc:
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
                slices: List[tuple] = []
                for request_item in batch:
                    start = len(merged)
                    merged.extend(request_item.texts)
                    slices.append((request_item, start, len(merged)))

                # CPU-bound: encode runs in this dedicated daemon thread, never on event loop
                embeddings = model.encode(merged)
                if hasattr(embeddings, "tolist"):
                    embeddings = embeddings.tolist()

                for request_item, start, end in slices:
                    wait_time = time.monotonic() - request_item.enqueued_at
                    BATCH_WAIT_SECONDS.observe(wait_time)
                    request_item.future.set_result(
                        [list(map(float, vector)) for vector in embeddings[start:end]]
                    )
            except Exception as exc:
                for request_item in batch:
                    request_item.future.set_exception(exc)


batcher = EmbeddingBatcher(BATCH_MAX_SIZE, BATCH_MAX_LATENCY_MS, BATCH_QUEUE_MAX)


# ============================================================================
# Prometheus metrics
# ============================================================================

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


# ============================================================================
# Model loading
# ============================================================================

class ValidationError(Exception):
    pass


def timeout_decorator(seconds: int):
    """Threading-based timeout for synchronous model loading."""
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
    global model_instance, model_loading, model_load_error, model_load_start_time

    model_loading = True
    model_load_start_time = time.time()
    model_load_error = None

    for attempt in range(1, MODEL_LOAD_RETRIES + 1):
        try:
            logger.info("Loading model '%s' (attempt %d/%d)...", MODEL_NAME, attempt, MODEL_LOAD_RETRIES)

            @timeout_decorator(120)
            def load():
                cache_dir = os.getenv("TRANSFORMERS_CACHE") or os.getenv("HF_HOME")
                return SentenceTransformer(
                    MODEL_NAME,
                    device="cpu",
                    trust_remote_code=True,
                    cache_folder=cache_dir,
                    local_files_only=True,
                )

            model = load()

            test_embedding = model.encode("test")
            if test_embedding is None or len(test_embedding) == 0:
                raise RuntimeError("Model loaded but failed test encoding")

            load_time = time.time() - model_load_start_time
            logger.info(
                "Model loaded. dimensions=%d max_seq=%d load_time=%.2fs",
                model.get_sentence_embedding_dimension(),
                model.max_seq_length,
                load_time,
            )
            if model_load_start_time is not None:
                MODEL_LOAD_SECONDS.set(load_time)

            model_instance = model
            model_loading = False
            return model

        except TimeoutError as e:
            model_load_error = f"Model loading timed out on attempt {attempt}: {e}"
            logger.error(model_load_error)
        except OSError as e:
            model_load_error = f"OS error during model loading (attempt {attempt}): {e}"
            logger.error(model_load_error)
        except Exception as e:
            model_load_error = f"Unexpected error during model loading (attempt {attempt}): {e}"
            logger.exception(model_load_error)

        if attempt < MODEL_LOAD_RETRIES:
            delay = MODEL_LOAD_RETRY_DELAY * (2 ** (attempt - 1))
            logger.info("Retrying in %d seconds...", delay)
            time.sleep(delay)

    model_loading = False
    final_error = f"Failed to load model after {MODEL_LOAD_RETRIES} attempts: {model_load_error}"
    logger.error(final_error)
    raise RuntimeError(final_error)


def get_model() -> SentenceTransformer:
    global model_instance
    if model_instance is not None:
        return model_instance
    if model_loading:
        max_wait = 180
        start = time.time()
        while model_loading and (time.time() - start) < max_wait:
            time.sleep(0.5)
        if model_instance is not None:
            return model_instance
        raise RuntimeError(f"Model loading timed out or failed: {model_load_error}")
    with model_lock:
        if model_instance is not None:
            return model_instance
        return load_model_with_retry()


def validate_input(inputs: Union[str, List[str]]) -> List[str]:
    if isinstance(inputs, str):
        texts = [inputs]
    elif isinstance(inputs, list):
        texts = inputs
    else:
        raise ValidationError("Input must be string or list of strings")
    if not texts:
        raise ValidationError("Input list cannot be empty")
    if len(texts) > MAX_BATCH_SIZE:
        raise ValidationError(f"Batch size {len(texts)} exceeds maximum {MAX_BATCH_SIZE}")
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


# ============================================================================
# FastAPI app
# ============================================================================

app = FastAPI(
    title="Embeddings Service",
    description="Resilient embedding service using sentence-transformers",
    version="2.0.0",
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforce API key on all paths except /health and /metrics."""
    if request.url.path not in ("/health", "/metrics") and API_KEY:
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
        if token != API_KEY:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    """Assign request ID, measure latency, and update Prometheus counters."""
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    start = time.time()
    bind_contextvars(request_id=request_id)
    response = await call_next(request)
    duration = time.time() - start
    REQUEST_LATENCY.labels(request.url.path, request.method).observe(duration)
    REQUEST_COUNT.labels(request.url.path, str(response.status_code)).inc()
    if response.status_code >= 400:
        REQUEST_ERRORS.labels(request.url.path, request.method).inc()
    response.headers["X-Request-ID"] = request_id
    clear_contextvars()
    return response


@app.on_event("startup")
async def _startup():
    logger.info("Starting Embeddings Service model=%s port=%d", MODEL_NAME, PORT)
    thread = threading.Thread(target=load_model_with_retry, daemon=True)
    thread.start()
    batcher.start()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/metrics")
async def metrics_endpoint():
    PROCESS_MEMORY_BYTES.set(_get_process_memory_bytes())
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    if model_instance is not None:
        return {"status": "ok", "model": MODEL_NAME, "ready": True}
    if model_loading:
        elapsed = time.time() - model_load_start_time if model_load_start_time else 0
        return JSONResponse(
            {"status": "loading", "model": MODEL_NAME, "ready": False,
             "loading_time_seconds": round(elapsed, 2)},
            status_code=503,
        )
    return JSONResponse(
        {"status": "error", "model": MODEL_NAME, "ready": False,
         "error": model_load_error or "Model not loaded"},
        status_code=503,
    )


@app.get("/info")
async def info():
    try:
        model = get_model()
        return {
            "model": MODEL_NAME,
            "dimensions": model.get_sentence_embedding_dimension(),
            "max_sequence_length": model.max_seq_length,
            "status": "ready",
        }
    except RuntimeError as e:
        return JSONResponse(error_payload("model_not_ready", e), status_code=503)


class EmbedRequest(BaseModel):
    inputs: Union[str, List[str]]


@app.post("/embed")
async def embed(body: EmbedRequest):
    """TEI-compatible embedding endpoint."""
    try:
        texts = validate_input(body.inputs)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        future = batcher.submit(texts)
        # future.result() blocks; run in thread pool to avoid blocking the event loop
        embeddings = await asyncio.to_thread(future.result, REQUEST_TIMEOUT)
        return embeddings
    except FutureTimeout:
        logger.error("Embedding generation timed out after %ds", REQUEST_TIMEOUT)
        raise HTTPException(status_code=504, detail="Request timed out")
    except RuntimeError as e:
        if str(e) == "batch_queue_full":
            raise HTTPException(status_code=503, detail="Service overloaded")
        return JSONResponse(error_payload("service_not_ready", e), status_code=503)
    except Exception as e:
        return JSONResponse(error_payload("internal_error", e), status_code=500)


class OpenAIEmbedRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None


@app.post("/v1/embeddings")
async def openai_embeddings(body: OpenAIEmbedRequest):
    """OpenAI-compatible embedding endpoint."""
    try:
        texts = validate_input(body.input)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "type": "invalid_request_error"},
        )
    try:
        future = batcher.submit(texts)
        embeddings = await asyncio.to_thread(future.result, REQUEST_TIMEOUT)
        return {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": emb, "index": idx}
                for idx, emb in enumerate(embeddings)
            ],
            "model": MODEL_NAME,
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in texts),
                "total_tokens": sum(len(t.split()) for t in texts),
            },
        }
    except FutureTimeout:
        logger.error("Embedding generation timed out after %ds", REQUEST_TIMEOUT)
        raise HTTPException(
            status_code=504,
            detail={"message": "Request timed out", "type": "timeout"},
        )
    except RuntimeError as e:
        if str(e) == "batch_queue_full":
            raise HTTPException(
                status_code=503,
                detail={"message": "Service overloaded", "type": "overloaded"},
            )
        payload = error_payload("service_not_ready", e)
        return JSONResponse(
            {"error": {"message": "Service not ready", "type": "service_unavailable", **payload}},
            status_code=503,
        )
    except Exception as e:
        payload = error_payload("internal_error", e)
        return JSONResponse(
            {"error": {"message": "Internal server error", "type": "internal_error", **payload}},
            status_code=500,
        )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Embeddings Service port=%d model=%s", PORT, MODEL_NAME)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
