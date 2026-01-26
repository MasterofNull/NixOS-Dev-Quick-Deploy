#!/usr/bin/env python3
"""
Simple Embedding Service using sentence-transformers
Provides OpenAI-compatible and TEI-compatible APIs
"""

import logging
import os
from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embeddings-service")

app = Flask(__name__)

# Load model on startup
model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
logger.info(f"Loading embedding model: {model_name}")
model = SentenceTransformer(model_name)
logger.info(f"Model loaded successfully. Dimensions: {model.get_sentence_embedding_dimension()}")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "model": model_name})


@app.route("/info", methods=["GET"])
def info():
    """Model information"""
    return jsonify({
        "model": model_name,
        "dimensions": model.get_sentence_embedding_dimension(),
        "max_sequence_length": model.max_seq_length
    })


@app.route("/embed", methods=["POST"])
def embed():
    """
    TEI-compatible embedding endpoint

    Request: {"inputs": "text to embed"} or {"inputs": ["text1", "text2"]}
    Response: [[embedding1], [embedding2]] or [[embedding]]
    """
    try:
        data = request.get_json()
        inputs = data.get("inputs")

        if not inputs:
            return jsonify({"error": "Missing 'inputs' in request"}), 400

        # Handle single string or list
        if isinstance(inputs, str):
            embeddings = [model.encode(inputs).tolist()]
        elif isinstance(inputs, list):
            embeddings = [model.encode(text).tolist() for text in inputs]
        else:
            return jsonify({"error": "inputs must be string or list of strings"}), 400

        return jsonify(embeddings)

    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/embeddings", methods=["POST"])
def openai_embeddings():
    """
    OpenAI-compatible embedding endpoint

    Request: {"input": "text"} or {"input": ["text1", "text2"]}
    Response: {"data": [{"embedding": [...], "index": 0}], "model": "...", ...}
    """
    try:
        data = request.get_json()
        text_input = data.get("input")

        if not text_input:
            return jsonify({"error": "Missing 'input' in request"}), 400

        # Handle single string or list
        if isinstance(text_input, str):
            texts = [text_input]
        elif isinstance(text_input, list):
            texts = text_input
        else:
            return jsonify({"error": "input must be string or list of strings"}), 400

        # Generate embeddings
        embeddings = [model.encode(text).tolist() for text in texts]

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
            "model": model_name,
            "usage": {
                "prompt_tokens": sum(len(text.split()) for text in texts),
                "total_tokens": sum(len(text.split()) for text in texts)
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8081))
    logger.info(f"Starting embedding service on port {port}")
    app.run(host="0.0.0.0", port=port)
