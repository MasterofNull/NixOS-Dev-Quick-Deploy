#!/usr/bin/env python3
"""Hermetic guard against unsafe local-model promotion."""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bench", ROOT / "scripts/testing/bench-local-agent.py")
bench = importlib.util.module_from_spec(spec); spec.loader.exec_module(bench)
criteria = json.loads((ROOT / "config/bench-promotion-criteria.json").read_text())


def gates():
    return {
        "tier0_protocol_runtime": {
            key: value for key, value in criteria["eligibility_gates"]["tier0_protocol_runtime"].items()
            if not key.startswith("_")
        },
        "tier2_lifecycle": {
            **{
                key: value for key, value in criteria["eligibility_gates"]["tier2_lifecycle"].items()
                if not key.startswith("_") and key != "license_class_allowed"
            },
            "license_class_allowed": "Apache-2.0",
        },
        "tier3_governance": {
            key: value for key, value in criteria["eligibility_gates"]["tier3_governance"].items()
            if not key.startswith("_")
        },
    }


def scores(dimensions=None):
    dimensions = dimensions or criteria["dimensions"].keys()
    return {
        "dims": {
            name: {
                "pct": 1.0,
                "max": criteria["dimensions"][name]["max_score"],
                "sample_ids": list(criteria["dimensions"][name]["tests"]),
            }
            for name in dimensions
        },
        "overall_pct": 1.0,
    }


def write_evidence(path: Path, artifact: Path, *, model="test-model", ragas=0.9, subject=None):
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    path.write_text(json.dumps({
        "model": model,
        "subject_sha256": subject or digest,
        "model_artifact_sha256": digest,
        "gates": gates(),
        "ragas_faithfulness": ragas,
    }))


with tempfile.TemporaryDirectory() as td:
    directory = Path(td)
    artifact = directory / "model.gguf"
    artifact.write_bytes(b"explicit test model artifact")
    evidence_path = directory / "eligibility.json"
    write_evidence(evidence_path, artifact)
    evidence = bench._load_eligibility_evidence(evidence_path, "test-model", artifact)
    assert evidence and evidence["artifact_verified"] is True

    tool_only = bench._check_promotion(scores(["tool_use"]), criteria, evidence, 1.0)
    assert not tool_only["promote"] and not tool_only["qualifying_run"] and not tool_only["complete_dimensions"]
    no_evidence = bench._check_promotion(scores(), criteria, None, 1.0)
    assert not no_evidence["qualifying_run"] and not no_evidence["eligibility_gates_pass"]
    complete = bench._check_promotion(scores(), criteria, evidence, 1.0)
    assert complete["promote"] and complete["qualifying_run"] and complete["latency_p95_pass"] and complete["ragas_faithfulness_pass"]

    undersampled = scores()
    undersampled["dims"]["reasoning"]["sample_ids"] = ["A1"]
    assert not bench._check_promotion(undersampled, criteria, evidence, 1.0)["qualifying_run"]
    assert not bench._check_promotion(scores(), criteria, evidence, criteria["promotion"]["latency_p95_s_max"] + 1)["qualifying_run"]

    write_evidence(evidence_path, artifact, ragas=criteria["promotion"]["ragas_faithfulness_min"] - 0.01)
    low_ragas = bench._load_eligibility_evidence(evidence_path, "test-model", artifact)
    assert not bench._check_promotion(scores(), criteria, low_ragas, 1.0)["qualifying_run"]
    write_evidence(evidence_path, artifact, subject="f" * 64)
    assert bench._load_eligibility_evidence(evidence_path, "test-model", artifact) is None
    write_evidence(evidence_path, artifact)
    evidence = bench._load_eligibility_evidence(evidence_path, "test-model", artifact)

    digest = evidence["subject_sha256"]
    for name, model, subject, verdict in (
        ("run-1.json", "test-model", digest, complete),
        ("run-2.json", "other-model", digest, complete),
        ("run-3.json", "test-model", digest, complete),
    ):
        (directory / name).write_text(json.dumps({
            "model": model, "subject_sha256": subject, "model_artifact_sha256": subject, "verdict": verdict,
        }))
    assert bench._count_consecutive_passing(directory, 2, "test-model", digest) == 1
    (directory / "run-2.json").write_text(json.dumps({
        "model": "test-model", "subject_sha256": "e" * 64, "model_artifact_sha256": "e" * 64, "verdict": complete,
    }))
    assert bench._count_consecutive_passing(directory, 2, "test-model", digest) == 1
    (directory / "run-2.json").write_text(json.dumps({
        "model": "test-model", "subject_sha256": digest, "model_artifact_sha256": digest, "verdict": complete,
    }))
    assert bench._count_consecutive_passing(directory, 2, "test-model", digest) == 2

    record = {
        "started_at": "20260821T000000Z", "run_id": "run-test", "model": "test-model",
        "subject_sha256": digest, "model_artifact_sha256": digest, "latency_p95_s": 1.0,
        "scores": scores(), "verdict": complete,
    }
    bench._write_promoted_file(directory, record)
    sentinel = json.loads((directory / "PROMOTED").read_text())
    assert sentinel["qualifying_run"] is True
    assert sentinel["subject_sha256"] == digest and sentinel["ragas_faithfulness"] == 0.9

print("local-model-promotion-contract: PASS")
