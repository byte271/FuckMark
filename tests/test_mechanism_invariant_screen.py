from types import SimpleNamespace

from fuckmark.transforms.mechanism_registry import mechanism_stress_transform_registry
from fuckmark.transforms.schema import InvariantStatus


def test_mechanism_registry_only_returns_individually_applicable_candidates() -> None:
    registry = mechanism_stress_transform_registry()
    enumeration = registry.enumerate(
        "It is useful, and we are careful. We must not drift; for example, we test again."
    )
    assert enumeration.candidates
    for candidate in enumeration.candidates:
        result = registry.apply(enumeration, (candidate.candidate_id,), seed=0)
        assert result.output_text != enumeration.input_text


def test_mechanism_registry_excludes_candidates_that_fail_hard_invariants(monkeypatch) -> None:
    import fuckmark.transforms.mechanism_registry as module

    calls = 0

    def reject_all(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(status=InvariantStatus.FAIL)

    monkeypatch.setattr(module, "validate_hard_invariants", reject_all)
    registry = mechanism_stress_transform_registry()
    enumeration = registry.enumerate("It is useful and we are careful.")
    assert calls > 0
    assert enumeration.candidates == ()
