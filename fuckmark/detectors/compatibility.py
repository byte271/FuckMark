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


def evaluate_detector_compatibility(
    batch: NativeObservationBatch,
    detector_family: DetectorFamily,
) -> DetectorCompatibility:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(detector_family, DetectorFamily):
        raise TypeError("detector_family must be a DetectorFamily")
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
    return DetectorCompatibility(
        status=CompatibilityStatus.UNVERIFIED,
        detector_family=detector_family,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        source=f"{batch.source_id}@{batch.source_commit}",
        reason=(
            "Bayesian compatibility requires bound watermark mode, Bernoulli(0.5) distribution evidence, "
            "detector checkpoint metadata, and source-compatible configuration"
        ),
        validated_by=(),
    )


def require_supported_detector(
    batch: NativeObservationBatch,
    detector_family: DetectorFamily,
) -> DetectorCompatibility:
    compatibility = evaluate_detector_compatibility(batch, detector_family)
    if compatibility.status is not CompatibilityStatus.SUPPORTED:
        raise DetectorCompatibilityError(compatibility)
    return compatibility
