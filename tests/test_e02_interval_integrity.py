from dataclasses import replace

import pytest

from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.e02_pristine import run_e02_pristine_detectability
from fuckmark.hashing import sha256_json
from tiny_dev_experiment_helpers import attack_evidence, calibration_evidence, tiny_dev_artifact


def _result():
    artifact = tiny_dev_artifact()
    calibration = calibrate_tiny_dev_detector(artifact, calibration_evidence())
    return run_e02_pristine_detectability(artifact, calibration, attack_evidence())


def test_e02_operating_point_rejects_rehashed_nonexact_tpr_interval() -> None:
    point = _result().operating_points[-1]
    forged_interval = replace(point.tpr_interval, lower=0.0, upper=1.0)
    payload = point._payload()
    payload["tpr_interval"] = forged_interval
    with pytest.raises(ValueError, match="exact|interval"):
        replace(
            point,
            tpr_interval=forged_interval,
            point_hash=sha256_json(payload),
        )


def test_e02_operating_point_rejects_rehashed_nonexact_fpr_interval() -> None:
    point = _result().operating_points[-1]
    forged_interval = replace(point.evaluation_fpr_interval, lower=0.0, upper=1.0)
    payload = point._payload()
    payload["evaluation_fpr_interval"] = forged_interval
    with pytest.raises(ValueError, match="exact|interval"):
        replace(
            point,
            evaluation_fpr_interval=forged_interval,
            point_hash=sha256_json(payload),
        )
