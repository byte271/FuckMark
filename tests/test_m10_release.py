import pytest

from fuckmark.experiments.m10_release import M10ReleaseError, build_m10_release_manifest
from fuckmark.experiments.m6_readiness import build_m6_readiness
from fuckmark.experiments.registry import default_development_experiment_registry


def test_m10_release_fails_closed_before_m6_is_ready() -> None:
    registry = default_development_experiment_registry()
    blocked_m6 = build_m6_readiness(registry, (), None)
    with pytest.raises(M10ReleaseError, match="M6 validation and power analysis"):
        build_m10_release_manifest(
            None,
            blocked_m6,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            release_code_commit="0" * 40,
        )
