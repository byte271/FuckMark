from fuckmark.transforms import (
    FIDELITY_EVIDENCE_ALGORITHM_VERSION,
    LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION,
    BlindHumanFidelityAudit,
    BlindReviewJudgment,
    FidelityAdjudication,
    FidelityEvidenceVerificationError,
    FidelityLabel,
    FidelityReviewSample,
    GrammarFixture,
    GrammarFixtureDisposition,
    LexicalPromotionEvidence,
    create_blind_human_fidelity_audit,
    source_verified_release_transform_registry,
    verify_fidelity_review_sample,
    verify_grammar_fixture,
    verify_lexical_promotion_evidence,
)


def test_source_grounded_fidelity_api_is_exported_from_transforms_package() -> None:
    assert FIDELITY_EVIDENCE_ALGORITHM_VERSION == "fidelity-evidence-v2"
    assert LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION == "lexical-promotion-evidence-v1"
    values = (
        BlindHumanFidelityAudit,
        BlindReviewJudgment,
        FidelityAdjudication,
        FidelityEvidenceVerificationError,
        FidelityLabel,
        FidelityReviewSample,
        GrammarFixture,
        GrammarFixtureDisposition,
        LexicalPromotionEvidence,
        create_blind_human_fidelity_audit,
        source_verified_release_transform_registry,
        verify_fidelity_review_sample,
        verify_grammar_fixture,
        verify_lexical_promotion_evidence,
    )
    assert all(value is not None for value in values)
