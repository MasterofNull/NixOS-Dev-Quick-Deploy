#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${EMBEDDING_MODEL:-BAAI/bge-small-en-v1.5}"
CACHE_DIR="${EMBEDDINGS_CACHE_DIR:-${HOME}/.local/share/nixos-ai-stack/embeddings-cache}"
HUB_DIR="${CACHE_DIR}/hub"
export HF_HUB_ENABLE_HF_TRANSFER=0

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is required" >&2
  exit 1
fi

mkdir -p "$HUB_DIR"

python3 - <<'PY'
import os
import sys

model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
cache_root = os.environ.get("EMBEDDINGS_CACHE_DIR", os.path.expanduser("~/.local/share/nixos-ai-stack/embeddings-cache"))
cache_dir = os.path.join(cache_root, "hub")
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

try:
    from huggingface_hub import snapshot_download
except Exception:
    import subprocess
    print("[INFO] Installing huggingface_hub...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "huggingface_hub"])
    from huggingface_hub import snapshot_download

print(f"[INFO] Downloading {model} to cache: {cache_dir}")
allow = [
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "model.safetensors",
    "1_Pooling/config.json",
]
path = snapshot_download(
    repo_id=model,
    cache_dir=cache_dir,
    allow_patterns=allow,
    local_dir_use_symlinks=False,
)
print(f"[OK] Cached at: {path}")
PY

echo "[DONE] Embedding model cached in ${CACHE_DIR}"
