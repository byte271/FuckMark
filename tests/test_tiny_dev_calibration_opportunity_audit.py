from __future__ import annotations

from fuckmark.experiments.tiny_dev_calibration_opportunity_audit import (
    OPPORTUNITY_CV_LIMIT,
    SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM,
    audit_frozen_tiny_dev_calibration_opportunity,
)
from fuckmark.experiments.tiny_dev_residual_replay import (
    FROZEN_TINY_DEV_CORPUS_HASH,
    FROZEN_TINY_DEV_EVIDENCE_HASH,
)


def _sample(index: int, tokens: tuple[int, ...]) -> dict[str, object]:
    return {
        "sample_id": f"cal-{index:03d}",
        "split": "threshold_calibration",
        "label": "unwatermarked",
        "text_only_tokens": {"token_ids": tokens},
        "model": {"eos_token_id": 50256},
    }


def _evidence() -> dict[str, object]:
    return {
        "artifact_hash": FROZEN_TINY_DEV_EVIDENCE_HASH,
        "primary_target_fpr": 0.01,
        "calibration_negative_count": 100,
        "achieved_calibration_fpr": 0.01,
        "primary_threshold_value": 0.5616883116883117,
        "calibration_fpr_interval": {
            "lower": 0.00025314603297742064,
            "upper": 0.05445938539208064,
        },
    }


def test_old_tinydev_calibration_is_below_serious_resolution_minimum() -> None:
    samples = tuple(_sample(index, tuple(range(index * 100 + 1, index * 100 + 65))) for index in range(100))
    corpus = {"artifact_hash": FROZEN_TINY_DEV_CORPUS_HASH, "manifest": {"samples": samples}}
    audit = audit_frozen_tiny_dev_calibration_opportunity(corpus, _evidence())
    assert audit.calibration_negative_count == 100
    assert audit.observed_calibration_false_positive_count == 1
    assert audit.serious_development_minimum == SERIOUS_DEVELOPMENT_CALIBRATION_MINIMUM == 1000
    assert not audit.calibration_resolution_pass
    assert audit.nominal_length_proxy_pass
    assert audit.valid_observations.coefficient_of_variation == 0.0


def test_effective_opportunity_variation_can_fail_nominal_length_proxy() -> None:
    samples = []
    for index in range(100):
        if index < 50:
            tokens = tuple(range(index * 100 + 1, index * 100 + 65))
        else:
            tokens = tuple((1, 2, 3, 4) * 16)
        samples.append(_sample(index, tokens))
    corpus = {"artifact_hash": FROZEN_TINY_DEV_CORPUS_HASH, "manifest": {"samples": tuple(samples)}}
    audit = audit_frozen_tiny_dev_calibration_opportunity(corpus, _evidence())
    assert audit.valid_observations.coefficient_of_variation > OPPORTUNITY_CV_LIMIT
    assert not audit.nominal_length_proxy_pass
    assert audit.repeated_context_masked.maximum > 0
