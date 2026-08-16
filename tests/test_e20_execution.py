from dataclasses import replace

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    preregistration_inputs,
)
from fuckmark.environment import capture_environment
from fuckmark.experiments import authorize_e20_execution, verify_e20_execution_authorization
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_corpus import build_confirmatory_corpus_seal
from fuckmark.experiments.confirmatory_keys import (
    ConfirmatoryTestKeyEntry,
    build_confirmatory_test_key_manifest,
)
from fuckmark.experiments.e20_execution import (
    E20AuthorizationError,
    E20ExecutionAuthorization,
    E20InvalidationReason,
    E20RunState,
    E20RunTransitionError,
    E20VerificationError,
    complete_e20_run,
    create_e20_run_ledger,
    derive_e20_condition_seed,
    e20_sample_shard,
    invalidate_e20_run,
    start_e20_run,
    verify_e20_run_history,
    verify_e20_run_ledger,
)
from fuckmark.hashing import sha256_bytes, sha256_json, sha256_text


T0 = "2026-08-16T20:00:00Z"
T1 = "2026-08-16T20:01:00Z"
T2 = "2026-08-16T20:02:00Z"
T3 = "2026-08-16T20:03:00Z"


def _sealed_execution_fixture():
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    condition_plan = confirmatory_condition_plan()
    corpus_manifest = confirmatory_manifest(inputs)
    materials = {
        0: b"secret-test-key-0",
        1: b"secret-test-key-1",
    }
    entries = tuple(
        ConfirmatoryTestKeyEntry.create(
            key_id=f"test-key-{index}",
            watermark_config_hash=sha256_text(f"watermark-config-{index}"),
            key_material_commitment_hash=sha256_bytes(materials[index]),
        )
        for index in range(2)
    )
    key_manifest = build_confirmatory_test_key_manifest(entries)
    inputs = replace(
        inputs,
        sealed_test_key_hash=key_manifest.manifest_hash,
        sealed_test_corpus_hash=corpus_manifest.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    corpus_seal = build_confirmatory_corpus_seal(
        preregistration,
        corpus_manifest,
        key_manifest,
    )
    _, calibration_evidence = calibration_materials()
    serialized = {
        entry.entry_hash: materials[index]
        for index, entry in enumerate(key_manifest.entries)
    }
    environment = capture_environment()
    common = {
        "serialized_test_key_material": serialized,
        "dependency_lock_hash": sha256_text("test-lockfile-v1"),
        "worker_version": "e20-test-worker-v1",
        "shard_count": 4,
        "dirty_worktree": False,
        "output_namespace_available": True,
        "prior_ledgers": (),
        "code_commit": preregistration.code_commit,
        "spec_revision_hash": preregistration.spec_revision_hash,
        "power_analysis_hash": preregistration.power_analysis_hash,
        "verification_test_hashes": preregistration.verification_test_hashes,
        "model_tokenizers": preregistration.model_tokenizers,
        "calibration_negative_evidence": calibration_evidence,
    }
    return (
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        key_manifest,
        environment,
        common,
    )


def _authorize():
    preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _sealed_execution_fixture()
    authorization = authorize_e20_execution(
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        key_manifest,
        environment,
        **common,
    )
    return (
        authorization,
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        key_manifest,
        environment,
        common,
    )


def test_e20_authorization_replays_all_sealed_inputs_and_runtime_keys() -> None:
    authorization, preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _authorize()
    assert authorization.experiment_id == "E20"
    assert authorization.output_namespace == f"e20/{authorization.execution_id}"
    verify_e20_execution_authorization(
        authorization,
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        key_manifest,
        environment,
        serialized_test_key_material=common["serialized_test_key_material"],
        dependency_lock_hash=common["dependency_lock_hash"],
        worker_version=common["worker_version"],
        shard_count=common["shard_count"],
        code_commit=common["code_commit"],
        spec_revision_hash=common["spec_revision_hash"],
        power_analysis_hash=common["power_analysis_hash"],
        verification_test_hashes=common["verification_test_hashes"],
        model_tokenizers=common["model_tokenizers"],
        calibration_negative_evidence=common["calibration_negative_evidence"],
    )


def test_public_e20_authorization_rejects_wrong_condition_plan_before_execution() -> None:
    preregistration, _, corpus_seal, corpus_manifest, key_manifest, environment, common = _sealed_execution_fixture()
    wrong_plan = confirmatory_condition_plan((0.05,))
    with pytest.raises(E20AuthorizationError, match="condition plan"):
        authorize_e20_execution(
            preregistration,
            wrong_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            **common,
        )


def test_e20_authorization_rejects_wrong_runtime_test_key_material() -> None:
    preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _sealed_execution_fixture()
    wrong = dict(common)
    material = dict(common["serialized_test_key_material"])
    first = next(iter(material))
    material[first] = b"wrong-secret"
    wrong["serialized_test_key_material"] = material
    with pytest.raises(E20AuthorizationError, match="TEST_KEYS material"):
        authorize_e20_execution(
            preregistration,
            condition_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            **wrong,
        )


def test_e20_authorization_rejects_dirty_tree_and_output_collision() -> None:
    preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _sealed_execution_fixture()
    dirty = dict(common)
    dirty["dirty_worktree"] = True
    with pytest.raises(E20AuthorizationError, match="clean worktree"):
        authorize_e20_execution(
            preregistration,
            condition_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            **dirty,
        )
    collision = dict(common)
    collision["output_namespace_available"] = False
    with pytest.raises(E20AuthorizationError, match="output namespace"):
        authorize_e20_execution(
            preregistration,
            condition_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            **collision,
        )


def test_e20_same_sealed_execution_cannot_be_authorized_twice() -> None:
    authorization, preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _authorize()
    ledger = create_e20_run_ledger(authorization, T0)
    duplicate = dict(common)
    duplicate["prior_ledgers"] = (ledger,)
    with pytest.raises(E20AuthorizationError, match="already has a run ledger"):
        authorize_e20_execution(
            preregistration,
            condition_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            **duplicate,
        )
    with pytest.raises(E20VerificationError, match="more than one ledger"):
        verify_e20_run_history((ledger, ledger))


def test_e20_normal_state_path_is_authorized_started_completed() -> None:
    authorization, *_ = _authorize()
    ledger = create_e20_run_ledger(authorization, T0)
    verify_e20_run_ledger(ledger, authorization)
    ledger = start_e20_run(ledger, T1)
    ledger = complete_e20_run(ledger, T2, sha256_text("result-bundle"))
    assert tuple(event.state for event in ledger.events) == (
        E20RunState.AUTHORIZED,
        E20RunState.STARTED,
        E20RunState.COMPLETED,
    )
    with pytest.raises(E20RunTransitionError, match="start only"):
        start_e20_run(ledger, T3)
    with pytest.raises(E20RunTransitionError, match="complete only"):
        complete_e20_run(ledger, T3, sha256_text("second-result"))


def test_e20_completed_run_can_be_invalidated_but_never_resumed() -> None:
    authorization, *_ = _authorize()
    ledger = create_e20_run_ledger(authorization, T0)
    ledger = start_e20_run(ledger, T1)
    ledger = complete_e20_run(ledger, T2, sha256_text("result-bundle"))
    ledger = invalidate_e20_run(
        ledger,
        T3,
        E20InvalidationReason.SOFTWARE_BUG,
        sha256_text("bug-report"),
        outcomes_could_influence_fix=True,
        fresh_seal_required=True,
    )
    assert ledger.state is E20RunState.INVALIDATED
    assert ledger.events[-1].fresh_seal_required is True
    with pytest.raises(E20RunTransitionError):
        start_e20_run(ledger, T3)
    with pytest.raises(E20RunTransitionError):
        complete_e20_run(ledger, T3, sha256_text("result"))
    with pytest.raises(E20RunTransitionError):
        invalidate_e20_run(
            ledger,
            T3,
            E20InvalidationReason.SOFTWARE_BUG,
            sha256_text("another-report"),
            outcomes_could_influence_fix=False,
            fresh_seal_required=False,
        )


def test_e20_invalidation_requires_fresh_seal_when_scientifically_contaminated() -> None:
    authorization, *_ = _authorize()
    ledger = start_e20_run(create_e20_run_ledger(authorization, T0), T1)
    with pytest.raises(ValueError, match="requires a fresh seal"):
        invalidate_e20_run(
            ledger,
            T2,
            E20InvalidationReason.CALIBRATION_LEAKAGE,
            sha256_text("calibration-leak"),
            outcomes_could_influence_fix=False,
            fresh_seal_required=False,
        )
    with pytest.raises(ValueError, match="outcome-influenced"):
        invalidate_e20_run(
            ledger,
            T2,
            E20InvalidationReason.SOFTWARE_BUG,
            sha256_text("bug-report"),
            outcomes_could_influence_fix=True,
            fresh_seal_required=False,
        )


def test_e20_source_replay_rejects_rehashed_forged_environment_binding() -> None:
    authorization, preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, environment, common = _authorize()
    payload = authorization._payload()
    payload["environment_snapshot_hash"] = sha256_text("forged-environment")
    forged = E20ExecutionAuthorization(
        authorization.algorithm_version,
        authorization.experiment_id,
        authorization.execution_id,
        authorization.preregistration_hash,
        authorization.corpus_seal_hash,
        authorization.corpus_manifest_hash,
        authorization.test_key_manifest_hash,
        authorization.code_commit,
        payload["environment_snapshot_hash"],
        authorization.dependency_lock_hash,
        authorization.worker_version,
        authorization.shard_count,
        authorization.output_namespace,
        authorization.seed_derivation_version,
        sha256_json(payload),
    )
    with pytest.raises(E20VerificationError, match="does not replay exactly"):
        verify_e20_execution_authorization(
            forged,
            preregistration,
            condition_plan,
            corpus_seal,
            corpus_manifest,
            key_manifest,
            environment,
            serialized_test_key_material=common["serialized_test_key_material"],
            dependency_lock_hash=common["dependency_lock_hash"],
            worker_version=common["worker_version"],
            shard_count=common["shard_count"],
            code_commit=common["code_commit"],
            spec_revision_hash=common["spec_revision_hash"],
            power_analysis_hash=common["power_analysis_hash"],
            verification_test_hashes=common["verification_test_hashes"],
            model_tokenizers=common["model_tokenizers"],
            calibration_negative_evidence=common["calibration_negative_evidence"],
        )


def test_e20_shards_and_condition_seeds_are_deterministic_and_corpus_bound() -> None:
    authorization, _, _, _, corpus_manifest, _, _, _ = _authorize()
    sample_id = corpus_manifest.samples[0].sample_id
    assert e20_sample_shard(authorization, corpus_manifest, sample_id) == e20_sample_shard(
        authorization,
        corpus_manifest,
        sample_id,
    )
    first = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        sample_id,
        "random-valid-budget-1",
        "schedule",
    )
    replay = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        sample_id,
        "random-valid-budget-1",
        "schedule",
    )
    different = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        sample_id,
        "random-valid-budget-1",
        "bootstrap",
    )
    assert first == replay
    assert first != different
    with pytest.raises(E20VerificationError, match="not part"):
        e20_sample_shard(authorization, corpus_manifest, "not-a-sealed-sample")
