import pytest

from test_e21_rerun import _completed_e20, _rerun_manifest
from fuckmark.environment import capture_environment
from fuckmark.experiments.e21_execution import (
    E21InvalidationReason,
    E21RunState,
    E21RunTransitionError,
    complete_e21_run,
    create_e21_run_ledger,
    invalidate_e21_run,
    start_e21_run,
    verify_e21_run_ledger,
)
from fuckmark.experiments.e21_rerun import authorize_e21_execution, build_e21_rerun_seal
from fuckmark.hashing import sha256_text


T0 = "2026-08-16T21:00:00Z"
T1 = "2026-08-16T21:01:00Z"
T2 = "2026-08-16T21:02:00Z"
T3 = "2026-08-16T21:03:00Z"


def _e21_authorization():
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, common, e20_ledger = _completed_e20()
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    e21_authorization = authorize_e21_execution(
        seal,
        preregistration,
        authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
        capture_environment(),
        serialized_test_key_material=common["serialized_test_key_material"],
        dependency_lock_hash=sha256_text("e21-execution-lock"),
        worker_version="e21-execution-test-v1",
        shard_count=4,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    return e21_authorization


def test_e21_run_ledger_follows_authorized_started_completed_path() -> None:
    authorization = _e21_authorization()
    ledger = create_e21_run_ledger(authorization, T0)
    assert ledger.state is E21RunState.AUTHORIZED
    ledger = start_e21_run(ledger, T1)
    assert ledger.state is E21RunState.STARTED
    ledger = complete_e21_run(ledger, T2, sha256_text("e21-result-bundle"))
    assert ledger.state is E21RunState.COMPLETED
    assert ledger.events[-1].artifact_hash == sha256_text("e21-result-bundle")
    verify_e21_run_ledger(ledger, authorization)


def test_e21_cannot_complete_before_start() -> None:
    authorization = _e21_authorization()
    ledger = create_e21_run_ledger(authorization, T0)
    with pytest.raises(E21RunTransitionError, match="only from STARTED"):
        complete_e21_run(ledger, T1, sha256_text("e21-result-bundle"))


def test_outcome_influenced_e21_bug_requires_fresh_rerun_seal() -> None:
    authorization = _e21_authorization()
    ledger = start_e21_run(create_e21_run_ledger(authorization, T0), T1)
    with pytest.raises(ValueError, match="fresh rerun seal"):
        invalidate_e21_run(
            ledger,
            T2,
            E21InvalidationReason.SOFTWARE_BUG,
            sha256_text("e21-bug-evidence"),
            outcomes_could_influence_fix=True,
            fresh_rerun_seal_required=False,
        )
    invalidated = invalidate_e21_run(
        ledger,
        T2,
        E21InvalidationReason.SOFTWARE_BUG,
        sha256_text("e21-bug-evidence"),
        outcomes_could_influence_fix=True,
        fresh_rerun_seal_required=True,
    )
    assert invalidated.state is E21RunState.INVALIDATED


def test_seed_reuse_invalidation_always_requires_fresh_rerun_seal() -> None:
    authorization = _e21_authorization()
    ledger = start_e21_run(create_e21_run_ledger(authorization, T0), T1)
    with pytest.raises(ValueError, match="requires a fresh rerun seal"):
        invalidate_e21_run(
            ledger,
            T2,
            E21InvalidationReason.GENERATION_SEED_REUSE,
            sha256_text("seed-reuse-evidence"),
            outcomes_could_influence_fix=False,
            fresh_rerun_seal_required=False,
        )


def test_completed_e21_can_be_invalidated_without_patching_in_place() -> None:
    authorization = _e21_authorization()
    ledger = create_e21_run_ledger(authorization, T0)
    ledger = start_e21_run(ledger, T1)
    ledger = complete_e21_run(ledger, T2, sha256_text("e21-result-bundle"))
    invalidated = invalidate_e21_run(
        ledger,
        T3,
        E21InvalidationReason.POST_HOC_CHANGE,
        sha256_text("post-hoc-evidence"),
        outcomes_could_influence_fix=True,
        fresh_rerun_seal_required=True,
    )
    assert invalidated.state is E21RunState.INVALIDATED
    assert invalidated.events[-1].artifact_hash is None
