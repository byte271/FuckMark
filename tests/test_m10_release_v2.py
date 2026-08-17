from dataclasses import fields

from fuckmark.experiments.m10_release import (
    M10_RELEASE_ALGORITHM_VERSION,
    M10ReleaseManifest,
)


def test_m10_release_v2_binds_e21_fidelity_summary_hash() -> None:
    assert M10_RELEASE_ALGORITHM_VERSION == "m10-release-readiness-v2"
    names = tuple(value.name for value in fields(M10ReleaseManifest))
    assert "e20_fidelity_summary_hash" in names
    assert "e21_fidelity_summary_hash" in names
    assert names.index("e21_fidelity_summary_hash") < names.index("e21_replication_hash")
