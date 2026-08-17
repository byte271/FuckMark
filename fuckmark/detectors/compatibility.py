from __future__ import annotations

from ..adapters import (
    DEEPMIND_REFERENCE_ADAPTER_ID,
    DEEPMIND_REFERENCE_ALGORITHM_VERSION,
    DEEPMIND_REFERENCE_SOURCE_PIN,
    HUGGINGFACE_SYNTHID_ADAPTER_ID,
    HUGGINGFACE_SYNTHID_ALGORITHM_VERSION,
    HUGGINGFACE_SYNTHID_SOURCE_PIN,
)
from ..native_observations import NativeObservationBatch
from .bayesian_training import BayesianConfirmatoryReadiness
from .types import (
    CompatibilityStatus,
    DetectorCompatibility,
    DetectorCompatibilityError,
    DetectorFamily,
)


_MEAN_VALIDATION_FIXTURES = (
    "T076",
    "T077",
    "T078",
    "T079",
    "T080",
    "T081",
    "T082",
    "T083",
    "T084",
    "T085",
    "T086",
    "T087",
)
_DETECTOR_SOURCE = (
    f"{DEEPMIND_REFERENCE_SOURCE_PIN.source_id}@{DEEPMIND_REFERENCE_SOURCE_PIN.commit}:"
    "src/synthid_text/detector_mean.py"
)
_BAYESIAN_DETECTOR_SOURCE = (
    f"{DEEPMIND_REFERENCE_SOURCE_PIN.source_id}@{DEEPMIND_REFERENCE_SOURCE_PIN.commit}:"
    "src/synthid_text/detector_bayesian.py"
)
_EXPECTED_ADAPTERS = {
    DEEPMIND_REFERENCE_ADAPTER_ID: (
        DEEPMIND_REFERENCE_ALGORITHM_VERSION,
        DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
        DEEPMIND_REFERENCE_SOURCE_PIN.commit,
    ),
    HUGGINGFACE_SYNTHID_ADAPTER_ID: (
        HUGGINGFACE_SYNTHID_ALGORITHM_VERSION,
        HUGGINGFACE_SYNTHID_SOURCE_PIN.source_id,
        HUGGINGFACE_SYNTHID_SOURCE_PIN.commit,
    ),
}


def _unverified_bayesian(batch: NativeObservationBatch, reason: str) -> DetectorCompatibility:
    return DetectorCompatibility(
        status=CompatibilityStatus.UNVERIFIED,
        detector_family=DetectorFamily.BAYESIAN,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        source=f"{batch.source_id}@{batch.source_commit}",
        reason=reason,
        validated_by=(),
    )


def evaluate_detector_compatibility(
    batch: NativeObservationBatch,
    detector_family: DetectorFamily,
    *,
    bayesian_readiness: BayesianConfirmatoryReadiness | None = None,
) -> DetectorCompatibility:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(detector_family, DetectorFamily):
        raise TypeError("detector_family must be a DetectorFamily")
    if bayesian_readiness is not None and not isinstance(bayesian_readiness, BayesianConfirmatoryReadiness):
        raise TypeError("bayesian_readiness must be BayesianConfirmatoryReadiness or None")
    if detector_family is not DetectorFamily.BAYESIAN and bayesian_readiness is not None:
        raise ValueError("bayesian_readiness may only be supplied for the Bayesian detector family")
    expected = _EXPECTED_ADAPTERS.get(batch.adapter_id)
    if expected is None:
        return DetectorCompatibility(
            status=CompatibilityStatus.UNVERIFIED,
            detector_family=detector_family,
            adapter_id=batch.adapter_id,
            adapter_algorithm_version=batch.adapter_algorithm_version,
            source=f"{batch.source_id}@{batch.source_commit}",
            reason="Adapter identity is not in the pinned open compatibility set",
            validated_by=(),
        )
    expected_algorithm, expected_source_id, expected_source_commit = expected
    if (
        batch.adapter_algorithm_version != expected_algorithm
        or batch.source_id != expected_source_id
        or batch.source_commit != expected_source_commit
    ):
        return DetectorCompatibility(
            status=CompatibilityStatus.UNVERIFIED,
            detector_family=detector_family,
            adapter_id=batch.adapter_id,
            adapter_algorithm_version=batch.adapter_algorithm_version,
            source=f"{batch.source_id}@{batch.source_commit}",
            reason="Adapter implementation identity does not match the pinned compatibility revision",
            validated_by=(),
        )
    if detector_family in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN):
        return DetectorCompatibility(
            status=CompatibilityStatus.SUPPORTED,
            detector_family=detector_family,
            adapter_id=batch.adapter_id,
            adapter_algorithm_version=batch.adapter_algorithm_version,
            source=_DETECTOR_SOURCE,
            reason="Binary g-values and the adapter-defined validity mask satisfy the Mean detector input contract",
            validated_by=_MEAN_VALIDATION_FIXTURES,
        )
    if bayesian_readiness is None:
        return _unverified_bayesian(
            batch,
            "Bayesian compatibility requires source-bound training, sanity, checkpoint, watermark-mode, distribution, and model/tokenizer readiness evidence",
        )
    if not bayesian_readiness.ready:
        detail = "; ".join(bayesian_readiness.blocking_reasons)
        return _unverified_bayesian(batch, f"Bayesian readiness is blocked: {detail}")
    if bayesian_readiness.adapter_id != batch.adapter_id:
        return _unverified_bayesian(batch, "Bayesian readiness adapter identity does not match the observation batch")
    if bayesian_readiness.adapter_config_hash != batch.adapter_config_hash:
        return _unverified_bayesian(batch, "Bayesian readiness adapter configuration does not match the observation batch")
    if bayesian_readiness.watermarking_depth != batch.depth:
        return _unverified_bayesian(batch, "Bayesian readiness watermark depth does not match the observation batch")
    if (
        bayesian_readiness.source_id != DEEPMIND_REFERENCE_SOURCE_PIN.source_id
        or bayesian_readiness.source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit
    ):
        return _unverified_bayesian(batch, "Bayesian readiness source identity does not match the pinned DeepMind detector")
    return DetectorCompatibility(
        status=CompatibilityStatus.SUPPORTED,
        detector_family=DetectorFamily.BAYESIAN,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        source=_BAYESIAN_DETECTOR_SOURCE,
        reason="Bayesian compatibility is bound to a source-compatible trained checkpoint and complete confirmatory readiness evidence",
        validated_by=(bayesian_readiness.readiness_hash,),
    )


def require_supported_detector(
    batch: NativeObservationBatch,
    detector_family: DetectorFamily,
    *,
    bayesian_readiness: BayesianConfirmatoryReadiness | None = None,
) -> DetectorCompatibility:
    compatibility = evaluate_detector_compatibility(
        batch,
        detector_family,
        bayesian_readiness=bayesian_readiness,
    )
    if compatibility.status is not CompatibilityStatus.SUPPORTED:
        raise DetectorCompatibilityError(compatibility)
    return compatibility
