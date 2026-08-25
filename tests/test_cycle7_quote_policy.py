from fuckmark.cycle7.registry import (
    cycle7_combined_transform_registry,
    cycle7_durable_transform_registry,
)
from fuckmark.transforms import quote_safe_zrd_transform_registry
from fuckmark.transforms.cycle7_quote_policy import (
    CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID,
    CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID,
)
from fuckmark.transforms.schema import CandidateRejectionReason


QUOTE = 'He answered, "They are not finished and we do not agree."'


def test_cycle6_quote_safe_still_blocks_contractions_inside_quotes() -> None:
    enumeration = quote_safe_zrd_transform_registry().enumerate(QUOTE)
    assert any(
        rejection.rule_id == "contract-do-not"
        and rejection.reason is CandidateRejectionReason.QUOTE_POLICY_BLOCKED
        for rejection in enumeration.rejections
    )
    assert not any(candidate.rule_id == "contract-do-not" for candidate in enumeration.candidates)
    assert any(candidate.rule_id.startswith("surface-space-") for candidate in enumeration.candidates)


def test_cycle7_durable_policy_allows_contractions_inside_quotes() -> None:
    registry = cycle7_durable_transform_registry()
    assert registry.quote_policy_id == CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID
    enumeration = registry.enumerate(QUOTE)
    selected = tuple(
        candidate.candidate_id
        for candidate in enumeration.candidates
        if candidate.rule_id == "contract-do-not"
    )
    assert selected
    result = registry.apply(enumeration, selected)
    assert result.output_text.startswith('He answered, "')
    assert result.output_text.endswith('."')
    assert "don't" in result.output_text or "aren't" in result.output_text
    assert result.trace.selection_policy_id.endswith(f":{CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID}")


def test_cycle7_durable_policy_does_not_alter_quote_delimiters() -> None:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate(QUOTE)
    if enumeration.candidates:
        result = registry.apply(
            enumeration,
            (enumeration.candidates[0].candidate_id,),
        )
        assert result.output_text.count('"') == QUOTE.count('"')


def test_mixed_policy_allows_spacing_or_durable_inside_quotes() -> None:
    registry = cycle7_combined_transform_registry()
    assert registry.quote_policy_id == CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID
    enumeration = registry.enumerate(QUOTE)
    assert any(candidate.rule_id.startswith("surface-space-") for candidate in enumeration.candidates)
    assert any(candidate.rule_id == "contract-do-not" for candidate in enumeration.candidates)
