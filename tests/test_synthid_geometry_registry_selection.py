from __future__ import annotations

import pytest

from fuckmark.synthid_geometry_hf import _registry


def test_geometry_runner_selects_isolated_mechanism_registry() -> None:
    mechanism = _registry("mechanism")
    release = _registry("release")
    development = _registry("development")
    mechanism_ids = {rule.rule_id for rule in mechanism.rules}
    release_ids = {rule.rule_id for rule in release.rules}
    development_ids = {rule.rule_id for rule in development.rules}
    assert any(rule_id.startswith("stress-") for rule_id in mechanism_ids)
    assert not any(rule_id.startswith("stress-") for rule_id in release_ids)
    assert not any(rule_id.startswith("stress-") for rule_id in development_ids)


def test_geometry_runner_rejects_unknown_registry() -> None:
    with pytest.raises(ValueError, match="unknown registry"):
        _registry("unknown")
