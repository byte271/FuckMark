from dataclasses import replace

import pytest

from confirmatory_helpers import (
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_corpus import (
    ConfirmatoryCorpusSeal,
    ConfirmatoryCorpusSealError,
    build_confirmatory_corpus_seal,
    verify_confirmatory_corpus_seal,
)
from fuckmark.hashing import sha256_json


def _sealed_fixture(omit_last_pair: bool = False):
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    key_manifest = confirmatory_test_key_manifest(inputs)
    manifest = confirmatory_manifest(inputs, omit_last_pair=omit_last_pair)
    inputs = replace(
        inputs,
        sealed_test_key_hash=key_manifest.manifest_hash,
        sealed_test_corpus_hash=manifest.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    return inputs, preregistration, manifest, key_manifest


def test_confirmatory_corpus_seal_accepts_exact_two_by_four_by_five_matrix() -> None:
    _, preregistration, manifest, key_manifest = _sealed_fixture()
    seal = build_confirmatory_corpus_seal(
        preregistration,
        manifest,
        key_manifest,
    )
    assert len(seal.strata) == 2 * 4 * 5
    assert seal.watermarked_base_sample_count == 40
    assert seal.matched_negative_base_sample_count == 40
    assert seal.test_key_manifest_hash == key_manifest.manifest_hash
    verify_confirmatory_corpus_seal(
        seal,
        preregistration,
        manifest,
        key_manifest,
    )


def test_confirmatory_corpus_seal_rejects_missing_preregistered_cell() -> None:
    _, preregistration, manifest, key_manifest = _sealed_fixture(omit_last_pair=True)
    with pytest.raises(ConfirmatoryCorpusSealError, match="stratum count"):
        build_confirmatory_corpus_seal(
            preregistration,
            manifest,
            key_manifest,
        )


def test_confirmatory_corpus_seal_rejects_corpus_commitment_mismatch() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    manifest = confirmatory_manifest(inputs)
    key_manifest = confirmatory_test_key_manifest(inputs)
    inputs = replace(inputs, sealed_test_key_hash=key_manifest.manifest_hash)
    preregistration = create_confirmatory_preregistration(inputs)
    with pytest.raises(ConfirmatoryCorpusSealError, match="corpus manifest hash"):
        build_confirmatory_corpus_seal(
            preregistration,
            manifest,
            key_manifest,
        )


def test_confirmatory_corpus_seal_rejects_test_key_commitment_mismatch() -> None:
    _, preregistration, manifest, _ = _sealed_fixture()
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    different_key_manifest = confirmatory_test_key_manifest(inputs, include_extra=True)
    with pytest.raises(ConfirmatoryCorpusSealError, match="test-key manifest hash"):
        build_confirmatory_corpus_seal(
            preregistration,
            manifest,
            different_key_manifest,
        )


def test_confirmatory_corpus_seal_rejects_corpus_condition_missing_from_sealed_test_keys() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    manifest = confirmatory_manifest(inputs)
    key_manifest = confirmatory_test_key_manifest(inputs, omit_last=True)
    inputs = replace(
        inputs,
        sealed_test_key_hash=key_manifest.manifest_hash,
        sealed_test_corpus_hash=manifest.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    with pytest.raises(ConfirmatoryCorpusSealError, match="was not sealed"):
        build_confirmatory_corpus_seal(preregistration, manifest, key_manifest)


def test_confirmatory_corpus_seal_rejects_sealed_but_unused_test_key_condition() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    manifest = confirmatory_manifest(inputs)
    key_manifest = confirmatory_test_key_manifest(inputs, include_extra=True)
    inputs = replace(
        inputs,
        sealed_test_key_hash=key_manifest.manifest_hash,
        sealed_test_corpus_hash=manifest.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    with pytest.raises(ConfirmatoryCorpusSealError, match="used exactly"):
        build_confirmatory_corpus_seal(preregistration, manifest, key_manifest)


def test_confirmatory_corpus_seal_replay_rejects_rehashed_wrong_preregistration_binding() -> None:
    _, preregistration, manifest, key_manifest = _sealed_fixture()
    seal = build_confirmatory_corpus_seal(
        preregistration,
        manifest,
        key_manifest,
    )
    payload = seal._payload()
    payload["preregistration_hash"] = "f" * 64
    forged = ConfirmatoryCorpusSeal(
        seal.algorithm_version,
        "f" * 64,
        seal.corpus_manifest_hash,
        seal.test_key_manifest_hash,
        seal.strata,
        seal.watermarked_base_sample_count,
        seal.matched_negative_base_sample_count,
        sha256_json(payload),
    )
    with pytest.raises(ConfirmatoryCorpusSealError, match="does not replay exactly"):
        verify_confirmatory_corpus_seal(
            forged,
            preregistration,
            manifest,
            key_manifest,
        )
