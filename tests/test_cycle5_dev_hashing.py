from fuckmark.hashing import sha256_json
from tools.cycle5_dev_paired_run import corpus_content_payload, scored_result_payload


def test_corpus_content_hash_excludes_recording_time_and_legacy_hash() -> None:
    first = {
        "algorithm_version": "freeze-v1",
        "recorded_at_utc": "2026-08-24T00:00:00Z",
        "samples": ({"index": 0, "text": "same"},),
        "corpus_hash": "a" * 64,
    }
    second = {
        **first,
        "recorded_at_utc": "2026-08-25T00:00:00Z",
        "corpus_hash": "b" * 64,
    }
    assert sha256_json(corpus_content_payload(first)) == sha256_json(
        corpus_content_payload(second)
    )


def test_scored_result_hash_excludes_recording_and_container_hashes() -> None:
    first = {
        "algorithm_version": "scored-v1",
        "recorded_at_utc": "2026-08-24T00:00:00Z",
        "rows": ({"index": 0, "score": 0.5},),
        "artifact_hash": "a" * 64,
    }
    second = {
        **first,
        "recorded_at_utc": "2026-08-25T00:00:00Z",
        "artifact_hash": "b" * 64,
    }
    assert sha256_json(scored_result_payload(first)) == sha256_json(
        scored_result_payload(second)
    )
