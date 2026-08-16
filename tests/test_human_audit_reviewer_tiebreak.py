import pytest

from fuckmark.transforms import (
    BlindReviewJudgment,
    FidelityLabel,
    FidelityReviewSample,
    create_blind_human_fidelity_audit,
)


def test_existing_blind_review_requires_third_reviewer_on_disagreement() -> None:
    sample = FidelityReviewSample.create(
        "a" * 64,
        "human-audit-review",
        "Original sentence.",
        "Changed sentence.",
    )
    judgments = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.MATERIAL_CHANGE),
    )
    with pytest.raises(ValueError, match="third tiebreak"):
        create_blind_human_fidelity_audit(
            sample.rule_hash,
            (sample,),
            judgments,
        )


def test_existing_blind_review_accepts_third_reviewer_tiebreak() -> None:
    sample = FidelityReviewSample.create(
        "a" * 64,
        "human-audit-review",
        "Original sentence.",
        "Changed sentence.",
    )
    judgments = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.MATERIAL_CHANGE),
        BlindReviewJudgment.create(sample, "reviewer-c", FidelityLabel.EQUIVALENT_OR_MINOR),
    )
    audit = create_blind_human_fidelity_audit(
        sample.rule_hash,
        (sample,),
        judgments,
    )
    assert audit.adjudications[0].label is FidelityLabel.EQUIVALENT_OR_MINOR
