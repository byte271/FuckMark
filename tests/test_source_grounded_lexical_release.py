import pytest

from corpus_helpers import model_identity
from fuckmark.transforms.fidelity_evidence import (
    BlindReviewJudgment,
    FidelityLabel,
    FidelityReviewSample,
    GrammarFixture,
    GrammarFixtureDisposition,
    create_blind_human_fidelity_audit,
)
from fuckmark.transforms.fidelity_verification import (
    FidelityEvidenceVerificationError,
    LexicalPromotionEvidence,
    source_verified_historical_visible_edit_transform_registry,
    source_verified_release_transform_registry,
    verify_lexical_promotion_evidence,
)
from fuckmark.transforms.lexical_rules import development_lexical_rules
from fuckmark.transforms.lexical_tokenization import capture_lexical_retokenization_fixture
from fuckmark.transforms.schema import CandidateRejectionReason


POSITIVE = (
    ("For example, use a cache.", "For instance, use a cache."),
    ("for example, use a cache.", "for instance, use a cache."),
    ("This works. For example, use a cache.", "This works. For instance, use a cache."),
    ("Does this work? For example, retry once.", "Does this work? For instance, retry once."),
    ("Stop!\nFor example, inspect the log.", "Stop!\nFor instance, inspect the log."),
)

NEGATIVE = (
    "Use, for example, a cache.",
    "Use this—for example, a cache.",
    "Note: For example, retry once.",
    "- For example, retry once.",
    "(For example, retry once.)",
)


def _tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def _grammar(rule_hash: str) -> tuple[GrammarFixture, ...]:
    positives = tuple(
        GrammarFixture.candidate(rule_hash, f"positive-{index}", source, expected)
        for index, (source, expected) in enumerate(POSITIVE)
    )
    negatives = tuple(
        GrammarFixture.rejection(
            rule_hash,
            f"negative-{index}",
            source,
            CandidateRejectionReason.PRECONDITION_FAILED,
        )
        for index, source in enumerate(NEGATIVE)
    )
    return (*positives, *negatives)


def _human_audit(rule_hash: str, duplicate_pairs: bool = False, wrong_output_index: int | None = None):
    samples = []
    judgments = []
    for index in range(50):
        value = 0 if duplicate_pairs else index
        source = f"For example, use cache item {value} now."
        transformed = f"For instance, use cache item {value} now."
        if wrong_output_index == index:
            transformed = f"For illustration, use cache item {value} now."
        sample = FidelityReviewSample.create(rule_hash, f"human-{index:03d}", source, transformed)
        samples.append(sample)
        judgments.extend(
            (
                BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
                BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.EQUIVALENT_OR_MINOR),
            )
        )
    return create_blind_human_fidelity_audit(rule_hash, tuple(samples), tuple(judgments))


def _promotion(human_audit=None):
    rule = development_lexical_rules()[0]
    identity = model_identity()
    token_fixture = capture_lexical_retokenization_fixture(
        "source-grounded-tokenizer",
        rule,
        identity,
        POSITIVE[0][0],
        _tokenizer,
    )
    return LexicalPromotionEvidence.create(
        rule,
        _grammar(rule.rule_hash),
        (token_fixture,),
        identity,
        human_audit or _human_audit(rule.rule_hash),
    )


def test_source_grounded_release_rejects_visible_lexical_promotion() -> None:
    promotion = _promotion()
    summary = verify_lexical_promotion_evidence(promotion, _tokenizer)
    assert summary.evidence_summary_complete
    with pytest.raises(FidelityEvidenceVerificationError, match="user-visible text"):
        source_verified_release_transform_registry(
            (promotion,),
            {promotion.model_tokenizer_identity.identity_hash: _tokenizer},
        )


def test_source_grounded_historical_visible_edit_registry_still_enables_lexical_replay() -> None:
    promotion = _promotion()
    registry = source_verified_historical_visible_edit_transform_registry(
        (promotion,),
        {promotion.model_tokenizer_identity.identity_hash: _tokenizer},
    )
    enumeration = registry.enumerate("Do not wait. For example, use a cache.")
    assert tuple(candidate.rule_id for candidate in enumeration.candidates) == (
        "contract-do-not",
        "lexical-for-example-for-instance",
    )


def test_source_grounded_release_rejects_valid_but_wrong_grammar_expectation() -> None:
    promotion = _promotion()
    grammar = list(promotion.grammar_fixtures)
    index = next(
        position
        for position, fixture in enumerate(grammar)
        if fixture.disposition is GrammarFixtureDisposition.CANDIDATE
    )
    first = grammar[index]
    grammar[index] = GrammarFixture.candidate(
        first.rule_hash,
        first.fixture_id,
        first.source_text,
        "For illustration, use a cache.",
    )
    forged = LexicalPromotionEvidence.create(
        promotion.rule,
        tuple(grammar),
        promotion.retokenization_fixtures,
        promotion.model_tokenizer_identity,
        promotion.human_audit,
    )
    with pytest.raises(FidelityEvidenceVerificationError, match="output does not replay exactly"):
        verify_lexical_promotion_evidence(forged, _tokenizer)


def test_source_grounded_release_rejects_duplicate_human_text_pairs() -> None:
    rule = development_lexical_rules()[0]
    promotion = _promotion(_human_audit(rule.rule_hash, duplicate_pairs=True))
    with pytest.raises(FidelityEvidenceVerificationError, match="duplicate reviewed text pairs"):
        verify_lexical_promotion_evidence(promotion, _tokenizer)


def test_source_grounded_release_rejects_human_sample_whose_transform_does_not_replay() -> None:
    rule = development_lexical_rules()[0]
    promotion = _promotion(_human_audit(rule.rule_hash, wrong_output_index=7))
    with pytest.raises(FidelityEvidenceVerificationError, match="transformed text does not replay exactly"):
        verify_lexical_promotion_evidence(promotion, _tokenizer)


def test_source_grounded_release_requires_tokenizer_for_exact_identity() -> None:
    promotion = _promotion()
    with pytest.raises(FidelityEvidenceVerificationError, match="missing tokenizer callable"):
        source_verified_release_transform_registry((promotion,), {})
