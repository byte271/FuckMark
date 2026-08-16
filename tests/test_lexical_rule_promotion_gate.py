import pytest

from fuckmark.hashing import sha256_text
from fuckmark.transforms.lexical_audit import (
    BLIND_HUMAN_REVIEW_POLICY_ID,
    LexicalAuditStatus,
    LexicalRulePromotionError,
    create_lexical_rule_audit,
    require_release_eligible_lexical_rules,
)
from fuckmark.transforms.lexical_rules import development_lexical_rules


def _hashes(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(sha256_text(f"{prefix}-{index}") for index in range(count))


def test_lexical_audit_requires_five_positive_and_five_negative_fixtures() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(rule.rule_hash, _hashes("positive", 4), _hashes("negative", 5))
    assert audit.status is LexicalAuditStatus.GRAMMAR_FIXTURES_INCOMPLETE
    assert not audit.release_eligible


def test_current_development_lexical_rule_cannot_promote_without_tokenizer_fixtures() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(rule.rule_hash, _hashes("positive", 5), _hashes("negative", 5))
    assert audit.status is LexicalAuditStatus.TOKENIZER_FIXTURES_MISSING
    with pytest.raises(LexicalRulePromotionError, match="not release eligible"):
        require_release_eligible_lexical_rules((rule,), (audit,))


def test_tokenizer_evidence_without_human_fidelity_audit_cannot_promote() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
    )
    assert audit.status is LexicalAuditStatus.HUMAN_FIDELITY_AUDIT_MISSING


def test_hard_invariant_violation_blocks_otherwise_passing_human_audit() -> None:
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


def test_material_change_or_sub_95_percent_human_fidelity_blocks_promotion() -> None:
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


def test_only_complete_fidelity_evidence_is_release_eligible() -> None:
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
    assert audit.status is LexicalAuditStatus.RELEASE_ELIGIBLE
    assert require_release_eligible_lexical_rules((rule,), (audit,)) == (rule,)


def test_lexical_promotion_requires_exact_rule_to_audit_binding() -> None:
    rule = development_lexical_rules()[0]
    audit = create_lexical_rule_audit(
        sha256_text("other-rule"),
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
    )
    with pytest.raises(LexicalRulePromotionError, match="exactly match"):
        require_release_eligible_lexical_rules((rule,), (audit,))
