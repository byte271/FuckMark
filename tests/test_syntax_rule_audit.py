from fuckmark.hashing import sha256_text
from fuckmark.transforms.lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID
from fuckmark.transforms.syntax_audit import (
    MINIMUM_SYNTAX_HUMAN_AUDIT_SAMPLES,
    SyntaxAuditStatus,
    create_syntax_rule_audit,
)
from fuckmark.transforms.syntax_rules import development_syntax_rules


def _hashes(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(sha256_text(f"{prefix}-{index}") for index in range(count))


def test_syntax_audit_requires_five_positive_and_five_negative_fixtures() -> None:
    rule = development_syntax_rules()[0]
    audit = create_syntax_rule_audit(rule.rule_hash, _hashes("positive", 4), _hashes("negative", 5))
    assert audit.status is SyntaxAuditStatus.GRAMMAR_FIXTURES_INCOMPLETE


def test_syntax_audit_requires_tokenizer_evidence_before_human_review() -> None:
    rule = development_syntax_rules()[0]
    audit = create_syntax_rule_audit(rule.rule_hash, _hashes("positive", 5), _hashes("negative", 5))
    assert audit.status is SyntaxAuditStatus.TOKENIZER_FIXTURES_MISSING


def test_syntax_audit_uses_larger_human_sample_floor_than_lexical() -> None:
    assert MINIMUM_SYNTAX_HUMAN_AUDIT_SAMPLES == 100
    rule = development_syntax_rules()[0]
    audit = create_syntax_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=99,
        equivalent_or_minor_count=99,
    )
    assert audit.status is SyntaxAuditStatus.HUMAN_FIDELITY_AUDIT_MISSING


def test_syntax_audit_blocks_material_change_and_hard_invariant_violation() -> None:
    rule = development_syntax_rules()[0]
    material = create_syntax_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=100,
        equivalent_or_minor_count=99,
        material_change_count=1,
    )
    invariant = create_syntax_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 1),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=100,
        equivalent_or_minor_count=100,
        hard_invariant_violation_count=1,
    )
    assert material.status is SyntaxAuditStatus.BLOCKED_HUMAN_FIDELITY
    assert invariant.status is SyntaxAuditStatus.BLOCKED_HARD_INVARIANT


def test_complete_syntax_evidence_is_only_development_audit_complete() -> None:
    rule = development_syntax_rules()[0]
    audit = create_syntax_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
        _hashes("tokenizer", 2),
        human_review_policy_id=BLIND_HUMAN_REVIEW_POLICY_ID,
        human_sample_count=100,
        equivalent_or_minor_count=97,
        cannot_judge_count=3,
    )
    assert audit.status is SyntaxAuditStatus.DEVELOPMENT_AUDIT_COMPLETE
    assert audit.development_audit_complete
