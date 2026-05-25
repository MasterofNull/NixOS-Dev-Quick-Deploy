from learning_lifecycle import (
    LearningLifecycleStatus,
    filter_runtime_active_records,
    is_default_runtime_active,
    validate_learning_record,
)
from lesson_effectiveness_tracker import (
    clear_lesson_tracking,
    get_lesson_effectiveness_stats,
    get_lesson_recommendation,
    track_lesson_usage,
)


def _record(status: str) -> dict:
    return {
        "source_event_id": "evt-1",
        "evidence": {"aq_qa": "passed"},
        "scope": {"surface": "hints"},
        "confidence": 0.91,
        "last_validated_at": "2026-05-15T00:00:00Z",
        "promotion_status": status,
        "supersedes": [],
        "expires_at": None,
    }


def test_learning_record_contract_requires_promotion_metadata():
    validation = validate_learning_record({"promotion_status": "promoted"})

    assert validation.valid is False
    assert "source_event_id" in validation.missing_fields
    assert validation.promotion_status == LearningLifecycleStatus.PROMOTED
    assert validation.runtime_active is True


def test_runtime_active_filter_excludes_candidate_and_retired_records():
    records = [
        _record("candidate"),
        _record("validated"),
        _record("promoted"),
        _record("crystallized"),
        _record("superseded"),
        _record("archived"),
    ]

    active = filter_runtime_active_records(records)

    assert [item["promotion_status"] for item in active] == ["promoted", "crystallized"]
    assert is_default_runtime_active("candidate") is False


def test_lesson_recommendations_require_promoted_runtime_status():
    clear_lesson_tracking()

    for _ in range(4):
        track_lesson_usage(
            "candidate-lesson",
            context="hints",
            success=True,
            metadata={"promotion_status": "candidate"},
        )
        track_lesson_usage(
            "promoted-lesson",
            context="hints",
            success=True,
            metadata={"promotion_status": "promoted"},
        )

    stats = get_lesson_effectiveness_stats()
    by_key = {item["lesson_key"]: item for item in stats["top_lessons"]}

    assert by_key["candidate-lesson"]["runtime_active"] is False
    assert by_key["promoted-lesson"]["runtime_active"] is True
    assert get_lesson_recommendation("hints") == ["promoted-lesson"]
