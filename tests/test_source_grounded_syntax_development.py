import pytest

from corpus_helpers import model_identity
from fuckmark.transforms.fidelity_evidence import (
    BlindReviewJudgment,
    FidelityLabel,
    FidelityReviewSample,
    GrammarFixture,
    create_blind_human_fidelity_audit,
)
from fuckmark.transforms.fidelity_verification import FidelityEvidenceVerificationError
from fuckmark.transforms.schema import CandidateRejectionReason
from fuckmark.transforms.syntax_fidelity_verification import (
    SyntaxDevelopmentEvidence,
    verify_syntax_development_evidence,
)
from fuckmark.transforms.syntax_rules import development_syntax_rules
from fuckmark.transforms.syntax_tokenization import capture_syntax_retokenization_fixture


POSITIVE = (
    ("The build passed; however, the deploy failed.", "The build passed. However, the deploy failed."),
    ("We checked the cache; however, the value was stale.", "We checked the cache. However, the value was stale."),
    ("The request completed; However, the result was empty.", "The request completed. However, the result was empty."),
    ("The worker stayed online; however, the queue remained blocked.", "The worker stayed online. However, the queue remained blocked."),
    ("The first attempt failed; however, the second attempt succeeded.", "The first attempt failed. However, the second attempt succeeded."),
)

NEGATIVE = (
    "Passed; however, the deploy failed.",
    "The build passed; however, failed.",
    "- The build passed; however, the deploy failed.",
    "* The build passed; however, the deploy failed.",
    "1. The build passed; however, the deploy failed.",
)


def _tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def _grammar(rule_hash: str) -> tuple[GrammarFixture, ...]:
    positives = tuple(
        GrammarFixture.candidate(rule_hash, f"syntax-positive-{index}", source, expected)
        for index, (source, expected) in enumerate(POSITIVE)
    )
    negatives = tuple(
        GrammarFixture.rejection(
            rule_hash,
            f"syntax-negative-{index}",
            source,
            CandidateRejectionReason.PRECONDITION_FAILED,
        )
        for index, source in enumerate(NEGATIVE)
    )
    return (*positives, *negatives)


def _human_audit(rule_hash: str, duplicate_pairs: bool = False):
    samples = []
    judgments = []
    for index in range(100):
        value = 0 if duplicate_pairs else index
        source = f"The build item {value} passed; however, the deploy item {value} failed."
        transformed = f"The build item {value} passed. However, the deploy item {value} failed."
        sample = FidelityReviewSample.create(rule_hash, f"syntax-human-{index:03d}", source, transformed)
        samples.append(sample)
        judgments.extend(
            (
                BlindReviewJudgment.create(sample, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
                BlindReviewJudgment.create(sample, "reviewer-b", FidelityLabel.EQUIVALENT_OR_MINOR),
            )
        )
    return create_blind_human_fidelity_audit(rule_hash, tuple(samples), tuple(judgments))


def _evidence(human_audit=None) -> SyntaxDevelopmentEvidence:
    rule = development_syntax_rules()[0]
    identity = model_identity()
    token_fixture = capture_syntax_retokenization_fixture(
        "source-grounded-syntax-tokenizer",
        rule,
        identity,
        POSITIVE[0][0],
        _tokenizer,
    )
    return SyntaxDevelopmentEvidence.create(
        rule,
        _grammar(rule.rule_hash),
        (token_fixture,),
        identity,
        human_audit or _human_audit(rule.rule_hash),
    )


def test_source_grounded_syntax_evidence_replays_to_development_complete_only() -> None:
    evidence = _evidence()
    summary = verify_syntax_development_evidence(evidence, _tokenizer)
    assert summary.development_audit_complete


def test_source_grounded_syntax_evidence_rejects_wrong_grammar_output() -> None:
    evidence = _evidence()
    grammar = list(evidence.grammar_fixtures)
    first = grammar[0]
    grammar[0] = GrammarFixture.candidate(
        first.rule_hash,
        first.fixture_id,
        first.source_text,
        "The build passed. Nevertheless, the deploy failed.",
    )
    forged = SyntaxDevelopmentEvidence.create(
        evidence.rule,
        tuple(grammar),
        evidence.retokenization_fixtures,
        evidence.model_tokenizer_identity,
        evidence.human_audit,
    )
    with pytest.raises(FidelityEvidenceVerificationError, match="output does not replay exactly"):
        verify_syntax_development_evidence(forged, _tokenizer)


def test_source_grounded_syntax_evidence_rejects_duplicate_reviewed_text_pairs() -> None:
    rule = development_syntax_rules()[0]
    evidence = _evidence(_human_audit(rule.rule_hash, duplicate_pairs=True))
    with pytest.raises(FidelityEvidenceVerificationError, match="duplicate reviewed text pairs"):
        verify_syntax_development_evidence(evidence, _tokenizer)
