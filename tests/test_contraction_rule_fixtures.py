import pytest

from fuckmark.transforms import CandidateRejectionReason, TransformRegistry, default_contraction_rules


@pytest.mark.parametrize("rule", default_contraction_rules(), ids=lambda rule: rule.rule_id)
def test_each_builtin_contraction_rule_has_positive_boundary_fixtures(rule) -> None:
    registry = TransformRegistry((rule,))
    source = rule.source
    capitalized = source[:1].upper() + source[1:]
    fixtures = (
        f"We {source} wait.",
        f"{capitalized} wait.",
        f"We {source}, ever.",
        f"- We {source} wait.",
        f"1. We {source} wait.",
    )
    for text in fixtures:
        enumeration = registry.enumerate(text)
        assert len(enumeration.candidates) == 1
        assert enumeration.rejections == ()


@pytest.mark.parametrize("rule", default_contraction_rules(), ids=lambda rule: rule.rule_id)
def test_each_builtin_contraction_rule_has_negative_context_fixtures(rule) -> None:
    registry = TransformRegistry((rule,))
    source = rule.source
    all_caps = source.upper()
    capitalized = source[:1].upper() + source[1:]
    fixtures = [
        f"{all_caps} NOW.",
        f'"{capitalized} change this."',
        f"`{source} change this`",
    ]
    if " " in source:
        left, right = source.split(" ", 1)
        fixtures.append(f"{left}\n{right} change this.")
    else:
        fixtures.append(f"{source}ary is not a word match.")
    for text in fixtures:
        enumeration = registry.enumerate(text)
        assert enumeration.candidates == ()
    identifier_registry = TransformRegistry((rule,), (source,))
    enumeration = identifier_registry.enumerate(f"We {source} wait.")
    assert enumeration.candidates == ()
    assert any(value.reason is CandidateRejectionReason.PROTECTED_OVERLAP for value in enumeration.rejections)
