from fuckmark.experiments.e21_fidelity_summary import (
    E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION,
)
from fuckmark.experiments.e21_human_audit_v2 import (
    E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
)
from fuckmark.experiments.e21_replication_verified import (
    E21_VERIFIED_REPLICATION_ALGORITHM_VERSION,
)
from fuckmark.experiments.m10_release import M10_RELEASE_ALGORITHM_VERSION


def test_e21_release_protocol_uses_label_blind_version_chain() -> None:
    assert E21_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION == "e21-human-audit-selection-v2"
    assert E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION == "e21-human-fidelity-summary-v3"
    assert E21_VERIFIED_REPLICATION_ALGORITHM_VERSION == "e21-verified-replication-v2"
    assert M10_RELEASE_ALGORITHM_VERSION == "m10-release-readiness-v3"
