"""Reproduce the A2 drift-threshold table (DESIGN section 4) against the live embedding server.

Run: LLAMA_EMBED_URL=<base url> python3 calibrate.py
Synthetic queries only. Selects the best threshold on the calibration topics and reports it on
separate holdout topics.
"""

from __future__ import annotations

import json
import math
import os
import random
import urllib.request

CALIBRATION = {
    "nix": [
        "how do I add a systemd service in the NixOS module",
        "where is the flake output for the ai-dev profile defined",
        "nixos-rebuild fails with infinite recursion in options",
        "add a tmpfiles rule for the state directory",
        "which nix option sets the coordinator port",
        "systemd activationScripts deps users example",
        "override a package version in the overlay",
        "NixOS firewall open port declaratively",
        "how to enable zram in the module",
        "flake lock update only nixpkgs input",
    ],
    "rag": [
        "qdrant collection returns no semantic results",
        "how is hybrid search reranked",
        "embedding dimension mismatch in vector store",
        "seed error-solutions collection with a new fix",
        "keyword scroll pool is too slow for retrieval",
        "what score threshold filters semantic hits",
        "AIDB document import trust level",
        "semantic cache hit rate is low",
        "chunking strategy for codebase context",
        "how are duplicate retrieval results merged",
    ],
    "gpu": [
        "llama.cpp runs out of VRAM on the APU",
        "what n-gpu-layers value is safe on Renoir",
        "KV cache quantization q8_0 flash attention",
        "prompt processing tokens per second is slow",
        "model swap to a smaller quant file",
        "thermal throttling during inference",
        "speculative decoding draft model settings",
        "context size versus memory usage for the model",
        "vulkan backend crashes on load",
        "how many parallel slots should the server run",
    ],
}
HOLDOUT = {
    "sec": [
        "apparmor profile denies sqlite lock",
        "rotate the sops secret for the api key",
        "systemd NoNewPrivileges blocks transition",
        "audit the repo for hardcoded tokens",
        "prompt injection scanner missed a pattern",
        "restrict the service user capabilities",
        "firejail sandbox for the agent shell",
        "verify the signature on the release artifact",
        "what does the zero trust module check",
        "harden ssh daemon settings",
    ],
    "git": [
        "rebase the branch onto origin main",
        "pull request checks are stuck pending",
        "how to create a new worktree for a slice",
        "resolve a merge conflict in the manifest",
        "the commit hook rejected my message format",
        "force push was blocked by branch protection",
        "list open pull requests with their status",
        "squash merge changed the commit sha",
        "bisect to find the regression commit",
        "revert a merged pull request safely",
    ],
    "dash": [
        "dashboard chart shows blank values",
        "add a new route to the dashboard backend",
        "websocket updates stop after reconnect",
        "css theme colors for the status cards",
        "frontend table pagination is broken",
        "prometheus metric not appearing in the panel",
        "the health tile shows stale data",
        "how to cache the aggregated API response",
        "keyboard accessibility for the approval button",
        "mobile layout overflows horizontally",
    ],
}
LAMBDA = 0.85
COOLDOWN = 8
PIVOT = 10
SESSIONS = 80

Vector = list[float]


def normalize(vector: Vector) -> Vector:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def embed(base_url: str, text: str) -> Vector:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/embeddings",
        data=json.dumps({"input": text}).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return normalize(json.load(response)["data"][0]["embedding"])


def velocities(sequence: list[Vector]) -> list[float | None]:
    """Per-turn velocity against the EWMA centroid; None before the cooldown has passed."""
    centroid: Vector | None = None
    out: list[float | None] = []
    for turn, vector in enumerate(sequence):
        if centroid is None:
            out.append(None)
            centroid = vector
            continue
        velocity = 1 - sum(a * b for a, b in zip(centroid, vector, strict=True))
        out.append(velocity if turn >= COOLDOWN else None)
        centroid = normalize([LAMBDA * a + (1 - LAMBDA) * b for a, b in zip(centroid, vector, strict=True)])
    return out


def first_over(series: list[float | None], threshold: float) -> int | None:
    return next((i for i, v in enumerate(series) if v is not None and v > threshold), None)


def sessions(topics: dict[str, list[Vector]], seed: int) -> tuple[list[list[float | None]], list[list[float | None]]]:
    rng = random.Random(seed)
    names = list(topics)
    single, pivoted = [], []
    for _ in range(SESSIONS):
        a, b = rng.sample(names, 2)
        single.append(velocities(rng.sample(topics[a], PIVOT) + rng.sample(topics[a], 5)))
        pivoted.append(velocities(rng.sample(topics[a], PIVOT) + rng.sample(topics[b], 5)))
    return single, pivoted


def rates(single: list[list[float | None]], pivoted: list[list[float | None]], threshold: float) -> tuple[float, float]:
    false_rate = sum(first_over(s, threshold) is not None for s in single) / len(single)
    firsts = [first_over(s, threshold) for s in pivoted]
    detect = sum(i is not None and i >= PIVOT for i in firsts) / len(pivoted)
    return false_rate, detect


def main() -> int:
    base_url = os.environ.get("LLAMA_EMBED_URL")
    if not base_url:
        raise SystemExit("set LLAMA_EMBED_URL to the embedding server base URL")
    embedded = [
        {name: [embed(base_url, q) for q in queries] for name, queries in topics.items()}
        for topics in (CALIBRATION, HOLDOUT)
    ]
    cal = sessions(embedded[0], 1)
    hold = sessions(embedded[1], 2)
    best = max((x / 100 for x in range(10, 56)), key=lambda t: rates(*cal, t)[1] - rates(*cal, t)[0])
    print(f"best threshold on calibration: {best:.2f} (false, detect) = {rates(*cal, best)}")
    for threshold in sorted({0.28, best - 0.02, best, best + 0.02}):
        false_rate, detect = rates(*hold, threshold)
        print(f"holdout threshold={threshold:.2f} single-topic nudge={false_rate:.4f} post-pivot nudge={detect:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
