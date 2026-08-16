from collections.abc import Sequence

import pytest

from fuckmark.transforms.protected import PROTECTED_SPAN_ALGORITHM_VERSION, ProtectedSpanExtractor
from fuckmark.transforms.registry import TRANSFORM_APPLY_ALGORITHM_VERSION, TRANSFORM_REGISTRY_ALGORITHM_VERSION, default_transform_registry
from fuckmark.transforms.schema import ProtectedSpanKind
import fuckmark.transforms.protected as protected_module
import fuckmark.transforms.registry as registry_module


def test_transform_resource_hardening_versions_advance() -> None:
    assert PROTECTED_SPAN_ALGORITHM_VERSION == "protected-span-extractor-v4"
    assert TRANSFORM_REGISTRY_ALGORITHM_VERSION == "transform-registry-v5"
    assert TRANSFORM_APPLY_ALGORITHM_VERSION == "explicit-candidate-apply-v4"


def test_plain_close_paren_text_is_not_markdown_destination() -> None:
    text = "array](do not change)"
    manifest = ProtectedSpanExtractor().extract(text)
    assert all(ProtectedSpanKind.MARKDOWN_DESTINATION not in span.kinds for span in manifest.spans)
    assert tuple(candidate.source_text for candidate in default_transform_registry().enumerate(text).candidates) == ("do not",)


def test_real_markdown_destination_stays_protected() -> None:
    text = "[x](do not change)"
    manifest = ProtectedSpanExtractor().extract(text)
    assert any(ProtectedSpanKind.MARKDOWN_DESTINATION in span.kinds for span in manifest.spans)
    assert default_transform_registry().enumerate(text).candidates == ()


def test_identifier_limit_rejects_before_materialization(monkeypatch) -> None:
    monkeypatch.setattr(protected_module, "_MAX_PROTECTED_ITEMS", 1)

    class OversizedIdentifiers(Sequence):
        def __len__(self):
            return 2

        def __getitem__(self, index):
            raise AssertionError("oversized identifiers must not be materialized")

    with pytest.raises(ValueError, match="identifiers exceeded"):
        ProtectedSpanExtractor(OversizedIdentifiers())


def test_rule_scan_work_limit_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(registry_module, "_MAX_RULE_SCAN_WORK", 5)
    with pytest.raises(ValueError, match="rule scanning"):
        default_transform_registry().enumerate("abcdef")


def test_candidate_selection_limit_rejects_before_materialization() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("Do not wait.")

    class OversizedSelection(Sequence):
        def __len__(self):
            return 2

        def __getitem__(self, index):
            raise AssertionError("oversized selection must not be materialized")

    with pytest.raises(ValueError, match="cannot exceed"):
        registry.apply(enumeration, OversizedSelection())


def test_rule_limit_rejects_before_materialization(monkeypatch) -> None:
    import fuckmark.transforms.rules as rules_module
    monkeypatch.setattr(rules_module, "_MAX_RULES", 1)

    class OversizedRules(Sequence):
        def __len__(self):
            return 2

        def __getitem__(self, index):
            raise AssertionError("oversized rules must not be materialized")

    with pytest.raises(ValueError, match="rules exceeded"):
        rules_module.validate_rules(OversizedRules())
