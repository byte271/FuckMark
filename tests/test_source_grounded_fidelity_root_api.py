import fuckmark


def test_source_grounded_fidelity_api_is_exported_from_root_package() -> None:
    expected = {
        "FIDELITY_EVIDENCE_ALGORITHM_VERSION",
        "LEXICAL_PROMOTION_EVIDENCE_ALGORITHM_VERSION",
        "SYNTAX_DEVELOPMENT_EVIDENCE_ALGORITHM_VERSION",
        "BlindHumanFidelityAudit",
        "BlindReviewJudgment",
        "FidelityAdjudication",
        "FidelityEvidenceVerificationError",
        "FidelityLabel",
        "FidelityReviewSample",
        "GrammarFixture",
        "GrammarFixtureDisposition",
        "LexicalPromotionEvidence",
        "SyntaxDevelopmentEvidence",
        "create_blind_human_fidelity_audit",
        "source_verified_release_transform_registry",
        "verify_fidelity_review_sample",
        "verify_grammar_fixture",
        "verify_lexical_promotion_evidence",
        "verify_syntax_development_evidence",
    }
    assert expected <= set(fuckmark.__all__)
    for name in expected:
        assert getattr(fuckmark, name) is not None
