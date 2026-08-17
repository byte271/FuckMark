from dataclasses import replace

import pytest

from test_e20_execution import T0, T1, T2, _authorize
from fuckmark.corpus import CorpusSample, GenerationParameters, build_corpus_manifest
from fuckmark.environment import capture_environment
from fuckmark.experiments.e20_execution import (
    complete_e20_run,
    create_e20_run_ledger,
    start_e20_run,
)
from fuckmark.experiments.e21_rerun import (
    E21_EXPERIMENT_ID,
    E21RerunError,
    authorize_e21_execution,
    build_e21_rerun_seal,
    verify_e21_rerun_seal,
)
from fuckmark.hashing import sha256_text


def _rerun_manifest(e20_manifest, *, seed_offset: int = 10_000, drop_last: bool = False):
    samples = []
    source_samples = e20_manifest.samples[:-1] if drop_last else e20_manifest.samples
    for sample in source_samples:
        generation = GenerationParameters.create(
            seed=sample.generation.seed + seed_offset,
            seed_policy_id=sample.generation.seed_policy_id,
            temperature=sample.generation.temperature,
            top_k=sample.generation.top_k,
            top_p=sample.generation.top_p,
            max_new_tokens=sample.generation.max_new_tokens,
            do_sample=sample.generation.do_sample,
            dtype=sample.generation.dtype,
            device=sample.generation.device,
            backend_id=sample.generation.backend_id,
            backend_version=sample.generation.backend_version,
        )
        samples.append(
            CorpusSample.create(
                sample_id=f"e21-{sample.sample_id}",
                match_id=f"e21-{sample.match_id}",
                prompt_id=sample.prompt_id,
                prompt_family_id=sample.prompt_family_id,
                domain=sample.domain,
                split=sample.split,
                label=sample.label,
                text=sample.text,
                model=sample.model,
                generation=generation,
                watermark=sample.watermark,
                target_length=sample.target_length,
                generation_tokens=sample.generation_tokens,
            )
        )
    return build_corpus_manifest("confirmatory-e21-test-fixture", e20_manifest.prompts, samples)


def _completed_e20():
    (
        authorization,
        preregistration,
        condition_plan,
        corpus_seal,
        e20_manifest,
        key_manifest,
        environment,
        common,
    ) = _authorize()
    ledger = create_e20_run_ledger(authorization, T0)
    ledger = start_e20_run(ledger, T1)
    ledger = complete_e20_run(ledger, T2, sha256_text("e20-completed-result"))
    return (
        authorization,
        preregistration,
        condition_plan,
        corpus_seal,
        e20_manifest,
        key_manifest,
        environment,
        common,
        ledger,
    )


def test_e21_seal_requires_completed_e20_and_fresh_generation_seeds() -> None:
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, _, ledger = _completed_e20()
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        authorization,
        ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    assert seal.experiment_id == E21_EXPERIMENT_ID
    assert seal.e20_result_bundle_hash == sha256_text("e20-completed-result")
    assert seal.e20_seed_set_hash != seal.e21_seed_set_hash
    verify_e21_rerun_seal(
        seal,
        preregistration,
        authorization,
        ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )


def test_e21_seal_rejects_incomplete_e20() -> None:
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, _, _ = _completed_e20()
    ledger = create_e20_run_ledger(authorization, T0)
    e21_manifest = _rerun_manifest(e20_manifest)
    with pytest.raises(E21RerunError, match="only after"):
        build_e21_rerun_seal(
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            e21_manifest,
            key_manifest,
        )


def test_e21_seal_rejects_seed_reuse_and_structure_drift() -> None:
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, _, ledger = _completed_e20()
    reused = _rerun_manifest(e20_manifest, seed_offset=0)
    with pytest.raises(E21RerunError, match="fresh generation seed|disjoint"):
        build_e21_rerun_seal(
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            reused,
            key_manifest,
        )
    drifted = _rerun_manifest(e20_manifest, drop_last=True)
    with pytest.raises(E21RerunError, match="exact E20"):
        build_e21_rerun_seal(
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            drifted,
            key_manifest,
        )


def test_e21_authorization_reuses_e20_code_and_test_keys() -> None:
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, common, ledger = _completed_e20()
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        authorization,
        ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    e21 = authorize_e21_execution(
        seal,
        preregistration,
        authorization,
        ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
        capture_environment(),
        serialized_test_key_material=common["serialized_test_key_material"],
        dependency_lock_hash=sha256_text("e21-lock"),
        worker_version="e21-test-worker-v1",
        shard_count=4,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    assert e21.experiment_id == E21_EXPERIMENT_ID
    assert e21.output_namespace == f"e21/{e21.execution_id}"
    assert e21.e20_execution_id == authorization.execution_id
    wrong_keys = dict(common["serialized_test_key_material"])
    first = next(iter(wrong_keys))
    wrong_keys[first] = b"wrong-secret"
    with pytest.raises(E21RerunError, match="TEST_KEYS material"):
        authorize_e21_execution(
            seal,
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            e21_manifest,
            key_manifest,
            capture_environment(),
            serialized_test_key_material=wrong_keys,
            dependency_lock_hash=sha256_text("e21-lock"),
            worker_version="e21-test-worker-v1",
            shard_count=4,
            dirty_worktree=False,
            output_namespace_available=True,
            code_commit=preregistration.code_commit,
        )


def test_e21_authorization_rejects_code_drift_and_dirty_worktree() -> None:
    authorization, preregistration, _, _, e20_manifest, key_manifest, _, common, ledger = _completed_e20()
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        authorization,
        ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    with pytest.raises(E21RerunError, match="exact frozen code commit"):
        authorize_e21_execution(
            seal,
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            e21_manifest,
            key_manifest,
            capture_environment(),
            serialized_test_key_material=common["serialized_test_key_material"],
            dependency_lock_hash=sha256_text("e21-lock"),
            worker_version="e21-test-worker-v1",
            shard_count=4,
            dirty_worktree=False,
            output_namespace_available=True,
            code_commit="f" * 40,
        )
    with pytest.raises(E21RerunError, match="clean worktree"):
        authorize_e21_execution(
            seal,
            preregistration,
            authorization,
            ledger,
            e20_manifest,
            e21_manifest,
            key_manifest,
            capture_environment(),
            serialized_test_key_material=common["serialized_test_key_material"],
            dependency_lock_hash=sha256_text("e21-lock"),
            worker_version="e21-test-worker-v1",
            shard_count=4,
            dirty_worktree=True,
            output_namespace_available=True,
            code_commit=preregistration.code_commit,
        )
