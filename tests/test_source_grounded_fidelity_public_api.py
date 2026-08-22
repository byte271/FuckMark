from fuckmark.transforms import (
    FIDELITY_EVIDENCE_ALGORITHM_VERSION,
    BLIND_REVIEW_PACKET_ALGORITHM_VERSION,
    LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION,
    BlindHumanFidelityAudit,
    BlindReviewPacket,
    BlindReviewPacketEntry,
    BlindReviewPacketVerificationError,
    BlindReviewJudgment,
    FidelityAdjudication,
    FidelityEvidenceVerificationError,
    FidelityLabel,
    FidelityReviewSample,
    GrammarFixture,
    GrammarFixtureDisposition,
    LexicalPromotionEvidence,
    create_blind_human_fidelity_audit,
    bind_blind_review_judgment,
    bind_blind_review_judgments,
    build_blind_review_packet,
    source_verified_release_transform_registry,
    verify_fidelity_review_sample,
    verify_blind_review_packet,
    verify_grammar_fixture,
    verify_lexical_promotion_evidence,
)


def test_source_grounded_fidelity_api_is_exported_from_transforms_package() -> None:
    assert FIDELITY_EVIDENCE_ALGORITHM_VERSION == "fidelity-evidence-v2"
    assert BLIND_REVIEW_PACKET_ALGORITHM_VERSION == "blind-fidelity-review-packet-v1"
    assert LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION == "lexical-promotion-evidence-v1"
    values = (
        BlindHumanFidelityAudit,
        BlindReviewPacket,
        BlindReviewPacketEntry,
        BlindReviewPacketVerificationError,
        BlindReviewJudgment,
        FidelityAdjudication,
        FidelityEvidenceVerificationError,
        FidelityLabel,
        FidelityReviewSample,
        GrammarFixture,
        GrammarFixtureDisposition,
        LexicalPromotionEvidence,
        create_blind_human_fidelity_audit,
        bind_blind_review_judgment,
        bind_blind_review_judgments,
        build_blind_review_packet,
        source_verified_release_transform_registry,
        verify_fidelity_review_sample,
        verify_blind_review_packet,
        verify_grammar_fixture,
        verify_lexical_promotion_evidence,
    )
    assert all(value is not None for value in values)
