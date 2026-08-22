import json
from pathlib import Path

from fuckmark.transforms import KEY_BLIND_HIGH_COVERAGE_PROFILE


def _contract() -> dict[str, object]:
    path = (
        Path(__file__).parents[1]
        / "specs"
        / "fuckmark-open-detector-effectiveness-v1.contract.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_open_detector_effectiveness_contract_binds_rewritten_profile() -> None:
    contract = _contract()
    assert contract["rewritten_profile_id"] == KEY_BLIND_HIGH_COVERAGE_PROFILE.profile_id
    assert contract["rewritten_profile_hash"] == KEY_BLIND_HIGH_COVERAGE_PROFILE.profile_hash
    assert contract["selection_access"] == {
        "detector": False,
        "watermark_key": False,
        "secret": False,
        "network_service": False,
        "public_tokenizer_geometry": True,
    }


def test_open_detector_effectiveness_contract_preserves_independent_denominators() -> None:
    holdouts = _contract()["locked_holdouts"]
    assert [(row["requested_budget"], row["independent_source_count"]) for row in holdouts] == [
        (10, 12),
        (16, 12),
    ]
    assert holdouts[0]["transformed_watermarked_detected"] == 8
    assert holdouts[1]["transformed_watermarked_detected"] == 6
    assert all(row["transformed_unwatermarked_detected"] == 0 for row in holdouts)
    assert holdouts[1]["realized_watermarked_edit_costs"] == [
        16,
        2,
        16,
        16,
        16,
        16,
        16,
        16,
        16,
        12,
        3,
        16,
    ]


def test_open_detector_effectiveness_contract_records_exact_b16_replay_boundary() -> None:
    replay = _contract()["archived_b16_replay"]
    assert replay["ruleset_hash"] == KEY_BLIND_HIGH_COVERAGE_PROFILE.ruleset_hash
    assert replay["sample_count"] == 24
    assert replay["exact_selection_and_transformed_text_match_count"] == 24
    assert replay["archived_trace_hash_reused"] is False


def test_open_detector_effectiveness_contract_does_not_authorize_broad_claims() -> None:
    boundary = _contract()["claim_boundary"]
    for name in (
        "watermark_removal_claim",
        "undetectability_claim",
        "unknown_key_claim",
        "proprietary_detector_claim",
        "normalization_durability_claim",
        "release_authorized",
    ):
        assert boundary[name] is False
    assert boundary["blind_human_semantic_audit"] == "NOT_PERFORMED"
    assert boundary["blind_human_style_audit"] == "NOT_PERFORMED"
