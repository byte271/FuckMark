import pytest

from test_e20_bundle import _bundle_fixture
from test_e20_row_verification import _fixture
from fuckmark.alignment import align_tokens
from fuckmark.experiments import build_e20_outcome_row
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_gvalue_depth import (
    E20GValueDepthError,
    E20PerDepthGValueRecord,
    build_e20_gvalue_depth_bundle,
    build_e20_per_depth_gvalue_record,
    verify_e20_gvalue_depth_bundle,
    verify_e20_per_depth_gvalue_record,
)
from fuckmark.experiments.e20_row_verification import E20_ROW_REPLAY_ALGORITHM_VERSION
from fuckmark.hashing import sha256_json


def test_per_depth_gvalue_record_replays_from_observation_batches() -> None:
    artifacts = _fixture()
    row = build_e20_outcome_row(**artifacts)
    alignment = align_tokens(
        artifacts["original_batch"].token_ids,
        artifacts["transformed_batch"].token_ids,
    )
    record = build_e20_per_depth_gvalue_record(
        row,
        artifacts["original_batch"],
        artifacts["transformed_batch"],
        alignment,
    )
    assert len(record.per_depth_hamming_difference_count) == record.depth
    assert sum(record.per_depth_hamming_difference_count) == row.gvalues.hamming_difference_count
    assert record.matched_observation_count == row.gvalues.matched_observation_count
    verify_e20_per_depth_gvalue_record(
        record,
        row,
        artifacts["original_batch"],
        artifacts["transformed_batch"],
        alignment,
    )


def test_per_depth_gvalue_replay_rejects_self_consistent_but_wrong_vector() -> None:
    artifacts = _fixture()
    row = build_e20_outcome_row(**artifacts)
    alignment = align_tokens(
        artifacts["original_batch"].token_ids,
        artifacts["transformed_batch"].token_ids,
    )
    record = build_e20_per_depth_gvalue_record(
        row,
        artifacts["original_batch"],
        artifacts["transformed_batch"],
        alignment,
    )
    vector = list(record.per_depth_hamming_difference_count)
    if record.matched_observation_count == 0:
        pytest.skip("fixture has no matched observations")
    vector[0] = 0 if vector[0] else 1
    wrong_vector = tuple(vector)
    summary_hash = sha256_json(
        {
            "algorithm_version": E20_ROW_REPLAY_ALGORITHM_VERSION,
            "matched_observation_count": record.matched_observation_count,
            "per_depth_hamming_difference_count": wrong_vector,
        }
    )
    payload = {
        "algorithm_version": "e20-gvalue-depth-v1",
        "outcome_row_hash": row.row_hash,
        "depth": record.depth,
        "matched_observation_count": record.matched_observation_count,
        "per_depth_hamming_difference_count": wrong_vector,
        "per_depth_summary_hash": summary_hash,
    }
    forged = E20PerDepthGValueRecord(
        row.row_hash,
        record.depth,
        record.matched_observation_count,
        wrong_vector,
        summary_hash,
        sha256_json(payload),
    )
    with pytest.raises(E20GValueDepthError, match="does not replay exactly"):
        verify_e20_per_depth_gvalue_record(
            forged,
            row,
            artifacts["original_batch"],
            artifacts["transformed_batch"],
            alignment,
        )


def test_gvalue_depth_bundle_accepts_exact_empty_record_set_when_all_result_rows_failed() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    depth_bundle = build_e20_gvalue_depth_bundle(result_bundle, ())
    assert depth_bundle.records == ()
    verify_e20_gvalue_depth_bundle(depth_bundle, result_bundle)
