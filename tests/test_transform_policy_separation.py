import pytest

from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    BLIND_HUMAN_REVIEW_POLICY_ID,
    LexicalRulePromotionError,
    create_lexical_rule_audit,
    default_contraction_rules,
    default_transform_registry,
    development_lexical_rules,
    development_syntax_rules,
    development_transform_registry,
    release_transform_registry,
)


def _hashes(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(sha256_text(f"{prefix}-{index}") for index in range(count))


def test_default_policy_excludes_all_development_only_rules() -> None:
    registry = default_transform_registry()
    assert registry.rules == default_contraction_rules()
    text = "Do not wait. For example, retry once. The build passed; however, the deploy failed."
    enumeration = registry.enumerate(text)
    assert tuple(candidate.rule_id for candidate in enumeration.candidates) == ("contract-do-not",)


def test_development_policy_combines_surface_lexical_and_syntax_rules() -> None:
    text = "Do not wait. For example, retry once. The build passed; however, the deploy failed."
    enumeration = development_transform_registry().enumerate(text)
    assert tuple(candidate.rule_id for candidate in enumeration.candidates) == (
        "contract-do-not",
        "lexical-for-example-for-instance",
        "syntax-semicolon-however-split",
    )


def test_release_policy_rejects_current_unaudited_lexical_rule() -> None:
    rule = development_lexical_rules()[0]
    pending = create_lexical_rule_audit(
        rule.rule_hash,
        _hashes("positive", 5),
        _hashes("negative", 5),
    )
    with pytest.raises(LexicalRulePromotionError, match="not release eligible"):
        release_transform_registry((rule,), (pending,))


def test_release_policy_accepts_only_explicit_release_eligible_lexical_audit() -> None:
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
    registry = release_transform_registry((rule,), (audit,))
    enumeration = registry.enumerate(
        "Do not wait. For example, retry once. The build passed; however, the deploy failed."
    )
    assert tuple(candidate.rule_id for candidate in enumeration.candidates) == (
        "contract-do-not",
        "lexical-for-example-for-instance",
    )


def test_release_policy_has_no_syntax_promotion_path() -> None:
    syntax_rule = development_syntax_rules()[0]
    with pytest.raises(TypeError, match="LexicalTemplateRule"):
        release_transform_registry((syntax_rule,), ())
