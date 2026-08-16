from dataclasses import replace

import pytest

from calibration_helpers import _base_evidence
from fuckmark.detectors import DetectorCalibrationIdentity
from fuckmark.hashing import sha256_json


def test_detector_calibration_identity_rejects_rehashed_config_hash_forgery() -> None:
    identity = DetectorCalibrationIdentity.from_evidence(_base_evidence())
    forged_config_hash = "f" * 64
    forged_payload = identity._payload(identity.normalized_weights)
    forged_payload["detector_config_hash"] = forged_config_hash
    with pytest.raises(ValueError, match="detector_config_hash does not match"):
        replace(
            identity,
            detector_config_hash=forged_config_hash,
            identity_hash=sha256_json(forged_payload),
        )


def test_detector_calibration_identity_rejects_rehashed_non_normalized_weights() -> None:
    identity = DetectorCalibrationIdentity.from_evidence(_base_evidence())
    forged_weights = tuple(2.0 if index == 0 else value for index, value in enumerate(identity.normalized_weights))
    forged_config_hash = sha256_json(
        {
            "detector_family": identity.detector_family.value,
            "algorithm_version": identity.detector_algorithm_version,
            "detector_source_commit": identity.detector_source_commit,
            "normalized_weights": forged_weights,
        }
    )
    forged_payload = identity._payload(forged_weights)
    forged_payload["detector_config_hash"] = forged_config_hash
    forged_payload["normalized_weights"] = forged_weights
    with pytest.raises(ValueError, match="normalized_weights must sum to depth"):
        replace(
            identity,
            normalized_weights=forged_weights,
            detector_config_hash=forged_config_hash,
            identity_hash=sha256_json(forged_payload),
        )
