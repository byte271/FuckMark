import pytest

from fuckmark.transforms.fidelity_evidence import (
    BlindReviewJudgment,
    FidelityLabel,
    FidelityReviewSample,
    create_blind_human_fidelity_audit,
)
from fuckmark.transforms.lexical_rules import development_lexical_rules


def _sample(sample_id: str = "sample-001") -> FidelityReviewSample:
    rule = development_lexical_rules()[0]
    return FidelityReviewSample.create(
        rule.rule_hash,
        sample_id,
        "For example, use a cache.",
        "For instance, use a cache.",
    )


def test_two_agreeing_blind_reviewers_adjudicate_without_third_reviewer() -> None:
    sample = _sample()
    judgments = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.EQUIVALENT_OR_MINOR),
    )
    audit = create_blind_human_fidelity_audit(sample.rule_hash, (sample,), judgments)
    assert audit.sample_count == 1
    assert audit.equivalent_or_minor_count == 1
    assert len(audit.adjudications[0].judgment_hashes) == 2


def test_disagreement_requires_third_tiebreak_reviewer() -> None:
    sample = _sample()
    judgments = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.MATERIAL_CHANGE),
    )
    with pytest.raises(ValueError, match="third tiebreak"):
        create_blind_human_fidelity_audit(sample.rule_hash, (sample,), judgments)


def test_third_reviewer_resolves_disagreement_by_majority() -> None:
    sample = _sample()
    judgments = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.MATERIAL_CHANGE),
        BlindReviewJudgment.create(sample, "reviewer-c", FidelityLabel.EQUIVALENT_OR_MINOR),
    )
    audit = create_blind_human_fidelity_audit(sample.rule_hash, (sample,), judgments)
    assert audit.adjudications[0].label is FidelityLabel.EQUIVALENT_OR_MINOR


def test_unnecessary_or_three_way_third_review_is_rejected() -> None:
    sample = _sample()
    unanimous = tuple(
        BlindReviewJudgment.create(sample, reviewer, FidelityLabel.EQUIVALENT_OR_MINOR)
        for reviewer in ("reviewer-a", "reviewer-b", "reviewer-c")
    )
    with pytest.raises(ValueError, match="only to resolve disagreement"):
        create_blind_human_fidelity_audit(sample.rule_hash, (sample,), unanimous)
    three_way = (
        BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
        BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.MATERIAL_CHANGE),
        BlindReviewJudgment.create(sample, "reviewer-c", FidelityLabel.CANNOT_JUDGE),
    )
    with pytest.raises(ValueError, match="three-way"):
        create_blind_human_fidelity_audit(sample.rule_hash, (sample,), three_way)
