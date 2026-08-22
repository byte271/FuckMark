import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus import (
    MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE,
    MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION,
    CalibrationCollisionKind,
    CalibrationIndependenceV3Candidate,
    CalibrationIndependenceV3Error,
    CalibrationIndependenceV3InsufficientError,
    CalibrationIndependenceV3JsonError,
    build_calibration_independence_v3,
    parse_mid_dev_calibration_independence_v3_artifact_json,
    parse_mid_dev_calibration_independence_v3_exclusion_json,
    parse_mid_dev_calibration_independence_v3_manifest_json,
)
from fuckmark.corpus.mid_dev_calibration_shards import CalibrationRole
from fuckmark.hashing import sha256_json


def _hash(role: CalibrationRole, kind: str, value: object) -> str:
    return sha256_json((role.value, kind, value))


def _candidate(
    role: CalibrationRole,
    index: int,
    *,
    text: object | None = None,
    token: object | None = None,
    prompt_id: str | None = None,
    sample_id: str | None = None,
    record: object | None = None,
    seed: int | None = None,
    model: str = "a" * 64,
) -> CalibrationIndependenceV3Candidate:
    text_hash = sha256_json(("shared-text", text)) if text is not None else _hash(role, "text", index)
    token_hash = sha256_json(("shared-token", token)) if token is not None else _hash(role, "token", index)
    record_hash = sha256_json(("shared-record", record)) if record is not None else _hash(role, "record", index)
    return CalibrationIndependenceV3Candidate(
        role=role,
        prompt_id=prompt_id or f"{role.value}-prompt-{index}",
        sample_id=sample_id or f"{role.value}-sample-{index}",
        sample_record_hash=record_hash,
        text_sha256=text_hash,
        continuation_token_hash=token_hash,
        generation_seed=seed if seed is not None else (10_000 if role is CalibrationRole.SELECT else 20_000) + index,
        model_tokenizer_identity_hash=model,
        watermark_config_hash="b" * 64,
        watermark_condition_hash="c" * 64,
    )


def _pools(count: int = 4):
    return (
        tuple(_candidate(CalibrationRole.SELECT, index) for index in range(count)),
        tuple(_candidate(CalibrationRole.AUDIT, index) for index in range(count)),
    )


def _build(select, audit, required=2):
    return build_calibration_independence_v3(
        select,
        audit,
        select_plan_hash="d" * 64,
        audit_plan_hash="e" * 64,
        required_count_per_role=required,
    )


def test_v3_freezes_first_occurrence_order_and_replays_hashes() -> None:
    select, audit = _pools()
    result = _build(select, audit)
    replay = _build(select, audit)
    assert result.artifact.artifact_hash == replay.artifact.artifact_hash
    assert result.select_candidates == select[:2]
    assert result.audit_candidates == audit[:2]
    assert result.artifact.algorithm_version == MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION
    assert result.artifact.selection_rule == MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE
    assert result.artifact.cross_role_collision_count == 0


def test_v3_records_within_role_text_and_token_duplicates() -> None:
    select = (
        _candidate(CalibrationRole.SELECT, 0, text="same", token="first"),
        _candidate(CalibrationRole.SELECT, 1, text="same", token="second"),
        _candidate(CalibrationRole.SELECT, 2, text="third", token="first"),
        _candidate(CalibrationRole.SELECT, 3, text="fourth", token="fourth"),
    )
    audit = tuple(_candidate(CalibrationRole.AUDIT, index) for index in range(4))
    result = _build(select, audit, required=2)
    exclusions = tuple(item for item in result.exclusions if item.role is CalibrationRole.SELECT)
    assert result.select_manifest.independent_candidate_count == 2
    assert tuple(item.sample_id for item in result.select_candidates) == (
        "CAL-SELECT-sample-0",
        "CAL-SELECT-sample-3",
    )
    assert len(exclusions) == 2
    assert exclusions[0].reason == "WITHIN_ROLE_CONTENT_DUPLICATE"
    assert CalibrationCollisionKind.TEXT_SHA256 in exclusions[0].collision_kinds
    assert CalibrationCollisionKind.CONTINUATION_TOKEN_HASH in exclusions[1].collision_kinds


def test_v3_excludes_cross_role_text_collision_without_using_scores() -> None:
    select, audit = _pools()
    select = (_candidate(CalibrationRole.SELECT, 0, text=0),) + select[1:]
    audit = (
        _candidate(CalibrationRole.AUDIT, 0, text=0),
        audit[1],
        audit[2],
        audit[3],
    )
    result = _build(select, audit, required=3)
    cross = tuple(item for item in result.exclusions if item.reason == "CROSS_ROLE_CONTENT_COLLISION")
    assert len(cross) == 1
    assert cross[0].role is CalibrationRole.AUDIT
    assert cross[0].conflicting_role is CalibrationRole.SELECT
    assert cross[0].collision_kinds == (CalibrationCollisionKind.TEXT_SHA256,)
    assert result.artifact.cross_role_collision_count == 1
    assert result.audit_manifest.independent_candidate_count == 3


def test_v3_excludes_cross_role_token_collision_with_different_text() -> None:
    select, audit = _pools()
    select = (_candidate(CalibrationRole.SELECT, 0, token=0),) + select[1:]
    audit = (
        _candidate(CalibrationRole.AUDIT, 0, text="new", token=0),
        audit[1],
        audit[2],
        audit[3],
    )
    result = _build(select, audit, required=3)
    cross = tuple(item for item in result.exclusions if item.reason == "CROSS_ROLE_CONTENT_COLLISION")
    assert len(cross) == 1
    assert cross[0].collision_kinds == (CalibrationCollisionKind.CONTINUATION_TOKEN_HASH,)


def test_v3_cross_role_exclusion_ordinals_use_raw_pool_basis() -> None:
    select, audit = _pools()
    select = (
        _candidate(CalibrationRole.SELECT, 0, text="dup", token="dup-token"),
        _candidate(CalibrationRole.SELECT, 1, text="dup", token="other"),
        _candidate(CalibrationRole.SELECT, 2, text="shared", token="s-token"),
        _candidate(CalibrationRole.SELECT, 3, text="fourth", token="fourth"),
    )
    audit = (
        _candidate(CalibrationRole.AUDIT, 0, text="shared", token="a-token"),
        audit[1],
        audit[2],
        audit[3],
    )
    result = _build(select, audit, required=2)
    cross = next(item for item in result.exclusions if item.reason == "CROSS_ROLE_CONTENT_COLLISION")
    assert cross.conflicting_sample_id == "CAL-SELECT-sample-2"
    assert cross.conflicting_ordinal == 2


def test_v3_records_exact_text_token_pair_collisions() -> None:
    select, audit = _pools()
    select = (_candidate(CalibrationRole.SELECT, 0, text=0, token=0),) + select[1:]
    audit = (
        _candidate(CalibrationRole.AUDIT, 0, text=0, token=0),
        audit[1],
        audit[2],
        audit[3],
    )
    result = _build(select, audit, required=3)
    collision = next(item for item in result.exclusions if item.reason == "CROSS_ROLE_CONTENT_COLLISION")
    assert collision.collision_kinds == (
        CalibrationCollisionKind.CONTINUATION_TOKEN_HASH,
        CalibrationCollisionKind.EXACT_TEXT_TOKEN_PAIR,
        CalibrationCollisionKind.TEXT_SHA256,
    )


def test_v3_requires_overflow_when_cross_role_collisions_reduce_audit_count() -> None:
    select, audit = _pools()
    select = (_candidate(CalibrationRole.SELECT, 0, text=0),) + select[1:]
    audit = tuple(_candidate(CalibrationRole.AUDIT, index, text=index) for index in range(4))
    with pytest.raises(CalibrationIndependenceV3InsufficientError, match="CAL-AUDIT"):
        _build(select[:3], audit[:3], required=3)


@pytest.mark.parametrize("field", ("prompt_id", "sample_id", "sample_record_hash", "generation_seed"))
def test_v3_rejects_structural_identity_overlap(field: str) -> None:
    select, audit = _pools()
    value = getattr(select[0], field)
    if field == "sample_record_hash":
        audit = (_candidate(CalibrationRole.AUDIT, 0, record="shared"),) + audit[1:]
        select = (_candidate(CalibrationRole.SELECT, 0, record="shared"),) + select[1:]
    elif field in {"prompt_id", "sample_id"}:
        kwargs = {field: value}
        audit = (_candidate(CalibrationRole.AUDIT, 0, **kwargs),) + audit[1:]
    else:
        audit = (_candidate(CalibrationRole.AUDIT, 0, seed=value),) + audit[1:]
    with pytest.raises(CalibrationIndependenceV3Error, match=field):
        _build(select, audit)


def test_v3_rejects_duplicate_identity_within_role() -> None:
    select, audit = _pools()
    duplicate = _candidate(CalibrationRole.SELECT, 1, prompt_id=select[0].prompt_id)
    with pytest.raises(CalibrationIndependenceV3Error, match="duplicate prompt_id"):
        _build((select[0], duplicate, *select[2:]), audit)


def test_v3_rejects_mixed_model_identity() -> None:
    select, audit = _pools()
    audit = (_candidate(CalibrationRole.AUDIT, 0, model="f" * 64),) + audit[1:]
    with pytest.raises(CalibrationIndependenceV3Error, match="immutable"):
        _build(select, audit)


def test_v3_artifact_and_manifests_have_strict_canonical_replay() -> None:
    select, audit = _pools()
    result = _build(select, audit)
    artifact_text = canonical_json_text(result.artifact) + "\n"
    manifest_text = canonical_json_text(result.select_manifest) + "\n"
    exclusion = result.exclusions[0] if result.exclusions else None
    assert parse_mid_dev_calibration_independence_v3_artifact_json(artifact_text) == result.artifact
    assert parse_mid_dev_calibration_independence_v3_manifest_json(manifest_text) == result.select_manifest
    if exclusion is None:
        select = (_candidate(CalibrationRole.SELECT, 0, text=0),) + select[1:]
        audit = (_candidate(CalibrationRole.AUDIT, 0, text=0),) + audit[1:]
        result = _build(select, audit)
        exclusion = result.exclusions[0]
    exclusion_text = canonical_json_text(exclusion) + "\n"
    assert parse_mid_dev_calibration_independence_v3_exclusion_json(exclusion_text) == exclusion


def test_v3_json_parser_rejects_stale_version_and_noncanonical_text() -> None:
    select, audit = _pools()
    result = _build(select, audit)
    payload = result.artifact.payload() | {"artifact_hash": result.artifact.artifact_hash}
    payload["algorithm_version"] = "mid-dev-calibration-independence-v2"
    with pytest.raises(ValueError):
        parse_mid_dev_calibration_independence_v3_artifact_json(canonical_json_text(payload) + "\n")
    with pytest.raises(CalibrationIndependenceV3JsonError):
        parse_mid_dev_calibration_independence_v3_artifact_json(str(payload))
