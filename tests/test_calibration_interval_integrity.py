from dataclasses import replace

import pytest

from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.hashing import sha256_json
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


def test_calibration_threshold_rejects_rehashed_nonexact_confidence_interval() -> None:
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    threshold = binding.calibration_bundle.thresholds[-1]
    interval_field = next(
        name
        for name in ("confidence_interval", "fpr_interval")
        if hasattr(threshold, name)
    )
    interval = getattr(threshold, interval_field)
    payload = threshold._payload()
    interval_payload_key = next(key for key, value in payload.items() if value == interval)
    with pytest.raises(ValueError):
        forged_interval = replace(interval, lower=0.0, upper=1.0)
        forged_payload = dict(payload)
        forged_payload[interval_payload_key] = forged_interval
        replace(
            threshold,
            **{
                interval_field: forged_interval,
                "threshold_hash": sha256_json(forged_payload),
            },
        )
