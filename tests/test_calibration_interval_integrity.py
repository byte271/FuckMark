from dataclasses import replace

import pytest

from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.hashing import sha256_json
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


def test_calibration_threshold_rejects_rehashed_nonexact_confidence_interval() -> None:
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    threshold = binding.calibration_bundle.thresholds[-1]
    forged_interval = replace(threshold.fpr_interval, lower=0.0, upper=1.0)
    forged_payload = {
        "target_fpr": threshold.target_fpr,
        "comparison_operator": threshold.comparison_operator.value,
        "value": threshold.value,
        "false_positive_count": threshold.false_positive_count,
        "calibration_count": threshold.calibration_count,
        "achieved_fpr": threshold.achieved_fpr,
        "fpr_interval": forged_interval,
        "calibration_input_hash": threshold.calibration_input_hash,
    }
    with pytest.raises(ValueError, match="confidence interval does not match exact binomial interval"):
        replace(
            threshold,
            fpr_interval=forged_interval,
            threshold_hash=sha256_json(forged_payload),
        )
