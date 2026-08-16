from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus import CorpusDomain, CorpusManifest, CorpusSplit, KeySplit, WatermarkLabel
from ..hashing import sha256_json
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_keys import ConfirmatoryTestKeyManifest


CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION = "confirmatory-corpus-seal-v2"


class ConfirmatoryCorpusSealError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfirmatoryStratumCount:
    model_tokenizer_identity_hash: str
    domain: CorpusDomain
    target_length: int
    watermarked_count: int
    matched_negative_count: int
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("target_length", self.target_length)
        require_int("watermarked_count", self.watermarked_count)
        require_int("matched_negative_count", self.matched_negative_count)
        if self.watermarked_count <= 0 or self.matched_negative_count <= 0:
            raise ValueError("confirmatory stratum counts must be positive")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match confirmatory stratum count")

    def _payload(self) -> dict[str, object]:
        return {
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "domain": self.domain.value,
            "target_length": self.target_length,
            "watermarked_count": self.watermarked_count,
            "matched_negative_count": self.matched_negative_count,
        }

    @classmethod
    def create(
        cls,
        model_tokenizer_identity_hash: str,
        domain: CorpusDomain,
        target_length: int,
        watermarked_count: int,
        matched_negative_count: int,
    ) -> ConfirmatoryStratumCount:
        payload = {
            "model_tokenizer_identity_hash": model_tokenizer_identity_hash,
            "domain": domain.value if isinstance(domain, CorpusDomain) else domain,
            "target_length": target_length,
            "watermarked_count": watermarked_count,
            "matched_negative_count": matched_negative_count,
        }
        return cls(
            model_tokenizer_identity_hash,
            domain,
            target_length,
            watermarked_count,
            matched_negative_count,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class ConfirmatoryCorpusSeal:
    algorithm_version: str
    preregistration_hash: str
    corpus_manifest_hash: str
    test_key_manifest_hash: str
    strata: tuple[ConfirmatoryStratumCount, ...]
    watermarked_base_sample_count: int
    matched_negative_base_sample_count: int
    seal_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION:
            raise ValueError("unsupported confirmatory corpus seal algorithm version")
        require_sha256("preregistration_hash", self.preregistration_hash)
        require_sha256("corpus_manifest_hash", self.corpus_manifest_hash)
        require_sha256("test_key_manifest_hash", self.test_key_manifest_hash)
        if not isinstance(self.strata, tuple) or not self.strata:
            raise TypeError("strata must be a non-empty tuple")
        if any(not isinstance(value, ConfirmatoryStratumCount) for value in self.strata):
            raise TypeError("strata must contain ConfirmatoryStratumCount values")
        expected = tuple(sorted(self.strata, key=lambda value: (value.model_tokenizer_identity_hash, value.domain.value, value.target_length)))
        if self.strata != expected:
            raise ValueError("confirmatory strata must be canonically ordered")
        identities = tuple((value.model_tokenizer_identity_hash, value.domain, value.target_length) for value in self.strata)
        if len(set(identities)) != len(identities):
            raise ValueError("confirmatory strata must be unique")
        require_int("watermarked_base_sample_count", self.watermarked_base_sample_count)
        require_int("matched_negative_base_sample_count", self.matched_negative_base_sample_count)
        if self.watermarked_base_sample_count != sum(value.watermarked_count for value in self.strata):
            raise ValueError("watermarked_base_sample_count does not match strata")
        if self.matched_negative_base_sample_count != sum(value.matched_negative_count for value in self.strata):
            raise ValueError("matched_negative_base_sample_count does not match strata")
        require_sha256("seal_hash", self.seal_hash)
        if self.seal_hash != sha256_json(self._payload()):
            raise ValueError("seal_hash does not match confirmatory corpus seal")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "test_key_manifest_hash": self.test_key_manifest_hash,
            "strata": self.strata,
            "watermarked_base_sample_count": self.watermarked_base_sample_count,
            "matched_negative_base_sample_count": self.matched_negative_base_sample_count,
        }


def build_confirmatory_corpus_seal(
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> ConfirmatoryCorpusSeal:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(test_key_manifest, ConfirmatoryTestKeyManifest):
        raise TypeError("test_key_manifest must be a ConfirmatoryTestKeyManifest")
    if test_key_manifest.manifest_hash != preregistration.sealed_test_key_hash:
        raise ConfirmatoryCorpusSealError("test-key manifest hash does not match preregistration commitment")
    if corpus_manifest.manifest_hash != preregistration.sealed_test_corpus_hash:
        raise ConfirmatoryCorpusSealError("corpus manifest hash does not match preregistration commitment")
    allowed_models = {value.identity_hash: value for value in preregistration.model_tokenizers}
    sealed_conditions = set(test_key_manifest.condition_identities)
    used_conditions: set[tuple[str, str]] = set()
    counts: Counter[tuple[str, CorpusDomain, int, WatermarkLabel]] = Counter()
    for sample in corpus_manifest.samples:
        if sample.split is not CorpusSplit.FINAL_TEST:
            raise ConfirmatoryCorpusSealError("confirmatory corpus contains a non-final-test sample")
        if sample.watermark.key_split is not KeySplit.TEST:
            raise ConfirmatoryCorpusSealError("confirmatory corpus contains a non-TEST_KEYS sample")
        condition_identity = (sample.watermark.watermark_config_hash, sample.watermark.key_id)
        if condition_identity not in sealed_conditions:
            raise ConfirmatoryCorpusSealError("confirmatory corpus uses a TEST_KEYS condition that was not sealed")
        used_conditions.add(condition_identity)
        expected_model = allowed_models.get(sample.model.identity_hash)
        if expected_model is None or sample.model != expected_model:
            raise ConfirmatoryCorpusSealError("confirmatory corpus contains an unregistered model/tokenizer identity")
        if sample.domain not in preregistration.domains:
            raise ConfirmatoryCorpusSealError("confirmatory corpus contains an unregistered domain")
        if sample.target_length not in preregistration.length_buckets:
            raise ConfirmatoryCorpusSealError("confirmatory corpus contains an unregistered target length")
        counts[(sample.model.identity_hash, sample.domain, sample.target_length, sample.label)] += 1
    if used_conditions != sealed_conditions:
        raise ConfirmatoryCorpusSealError("sealed TEST_KEYS conditions must be used exactly by the confirmatory corpus")
    strata: list[ConfirmatoryStratumCount] = []
    for model in preregistration.model_tokenizers:
        for domain in preregistration.domains:
            for target_length in preregistration.length_buckets:
                watermarked = counts[(model.identity_hash, domain, target_length, WatermarkLabel.WATERMARKED)]
                negative = counts[(model.identity_hash, domain, target_length, WatermarkLabel.UNWATERMARKED)]
                expected_watermarked = preregistration.final_n_per_core_cell
                expected_negative = expected_watermarked * preregistration.matched_negative_ratio
                if watermarked != expected_watermarked or negative != expected_negative:
                    raise ConfirmatoryCorpusSealError(
                        "confirmatory corpus stratum count does not match preregistered final N and matched-negative ratio"
                    )
                strata.append(
                    ConfirmatoryStratumCount.create(
                        model.identity_hash,
                        domain,
                        target_length,
                        watermarked,
                        negative,
                    )
                )
    expected_total = preregistration.watermarked_base_sample_count + preregistration.matched_negative_base_sample_count
    if len(corpus_manifest.samples) != expected_total:
        raise ConfirmatoryCorpusSealError("confirmatory corpus contains samples outside the preregistered core matrix")
    ordered = tuple(sorted(strata, key=lambda value: (value.model_tokenizer_identity_hash, value.domain.value, value.target_length)))
    watermarked_total = sum(value.watermarked_count for value in ordered)
    negative_total = sum(value.matched_negative_count for value in ordered)
    payload = {
        "algorithm_version": CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "strata": ordered,
        "watermarked_base_sample_count": watermarked_total,
        "matched_negative_base_sample_count": negative_total,
    }
    return ConfirmatoryCorpusSeal(
        CONFIRMATORY_CORPUS_SEAL_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        corpus_manifest.manifest_hash,
        test_key_manifest.manifest_hash,
        ordered,
        watermarked_total,
        negative_total,
        sha256_json(payload),
    )


def verify_confirmatory_corpus_seal(
    seal: ConfirmatoryCorpusSeal,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
) -> None:
    if not isinstance(seal, ConfirmatoryCorpusSeal):
        raise TypeError("seal must be a ConfirmatoryCorpusSeal")
    expected = build_confirmatory_corpus_seal(preregistration, corpus_manifest, test_key_manifest)
    if seal != expected:
        raise ConfirmatoryCorpusSealError("confirmatory corpus seal does not replay exactly from preregistration and held-out manifests")
