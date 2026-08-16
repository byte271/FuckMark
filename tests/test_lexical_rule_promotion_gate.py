import pytest

from fuckmark.hashing import sha256_text
from fuckmark.transforms.lexical_audit import (
    BLIND_HUMAN_REVIEW_POLICY_ID,
    LexicalAuditStatus,
    LexicalRulePromotionError,
    create_lexical_rule_audit,
    require_complete_lexical_audit_summaries,
)
from fuckmark.transforms.lexical_rules import development_lexical_rules
from fuckmark.transforms.registry import release_transform_registry


def _hashes(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(sha256_text(f"{prefix}-{index}") for index in range(count))


def test_lexical_audit_requires_five_positive_and_five_negative_fixtures() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(rule.rule_hash, _hashes("positive", 4), _hashes("negative", 5))
    assert audit.status is LexicalAuditStatus.GRAMMAR_FIXTURES_INCOMPLETE
    assert not audit.evidence_summary_complete


def test_current_development_lexical_rule_summary_is_incomplete_without_tokenizer_fixtures() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(rule.rule_hash, _hashes("positive", 5), _hashes("negative", 5))
    assert audit.status is LexicalAuditStatus.TOKENIZER_FIXTURES_MISSING
    with pytest.raises(LexicalRulePromotionError, match="summaries are incomplete"):
        require_complete_lexical_audit_summaries((rule,), (audit,))


def test_tokenizer_evidence_without_human_fidelity_audit_is_incomplete() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
    )
    assert audit.status is LexicalAuditStatus.HUMAN_FIDELITY_AUDIT_MISSING


def test_hard_invariant_violation_blocks_otherwise_complete_human_summary() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=50,
        equivalent_or_minor_count=50,
        hard_invariant_violation_count=1,
    )
    assert audit.status is LexicalAuditStatus.BLOCKED_HARD_INVARIANT


def test_material_change_or_sub_95_percent_human_fidelity_blocks_summary() -> None:
    rule = development_lexical_rules()[0]
    material = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=50,
        equivalent_or_minor_count=49,
        material_change_count=1,
    )
    low_rate = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=50,
        equivalent_or_minor_count=47,
        cannot_judge_count=3,
    )
    assert material.status is LexicalAuditStatus.BLOCKED_HUMAN_FIDELITY
    assert low_rate.status is LexicalAuditStatus.BLOCKED_HUMAN_FIDELITY


def test_complete_summary_does_not_authorize_release_without_source_grounded_replay() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 2),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=50,
        equivalent_or_minor_count=48,
        cannot_judge_count=2,
    )
    assert audit.status is LexicalAuditStatus.EVIDENCE_SUMMARY_COMPLETE
    assert audit.evidence_summary_complete
    assert require_complete_lexical_audit_summaries((rule,), (audit,)) == (rule,)
    with pytest.raises(LexicalRulePromotionError, match="source-grounded verified fidelity evidence"):
        release_transform_registry((rule,), (audit,))


def test_lexical_summary_requires_exact_rule_to_audit_binding() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        sha256_text("other-rule"),
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
    )
    with pytest.raises(LexicalRulePromotionError, match="exactly match"):
        require_complete_lexical_audit_summaries((rule,), (audit,))
