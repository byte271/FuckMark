import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from fuckmark.detectors.bayesian import (
    BAYESIAN_CHECKPOINT_ALGORITHM_VERSION,
    BayesianCheckpoint,
    bayesian_posterior,
    load_bayesian_checkpoint,
)
from fuckmark.detectors.types import ZeroValidObservationsError
from fuckmark.hashing import sha256_json


_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


def _checkpoint_with_prior(base_rate: float) -> BayesianCheckpoint:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    data["base_rate"] = base_rate
    payload = dict(data)
    payload.pop("checkpoint_hash")
    data["checkpoint_hash"] = sha256_json(payload)
    return BayesianCheckpoint.from_mapping(data)


def test_small_bayesian_checkpoint_fixture_is_source_bound_and_self_validating() -> None:
    checkpoint = load_bayesian_checkpoint(_FIXTURE)
    assert checkpoint.checkpoint_algorithm_version == BAYESIAN_CHECKPOINT_ALGORITHM_VERSION
    assert checkpoint.source_id == "deepmind-synthid-text-reference"
    assert checkpoint.source_commit == "addb4a158143c7c6851a1308f78b89fceed59683"
    assert checkpoint.watermarking_depth == 3
    assert checkpoint.checkpoint_hash == sha256_json(checkpoint._payload())


def test_bayesian_fixture_matches_frozen_source_formula_golden() -> None:
    checkpoint = load_bayesian_checkpoint(_FIXTURE)
    score = bayesian_posterior(
        ((1, 0, 1), (0, 1, 1), (1, 1, 0)),
        (True, False, True),
        checkpoint,
    )
    assert math.isclose(score, 0.3729477730432752, rel_tol=1e-14, abs_tol=1e-14)


def test_bayesian_posterior_changes_when_prior_changes() -> None:
    rows = ((1, 0, 1), (1, 1, 0))
    mask = (True, True)
    low = bayesian_posterior(rows, mask, _checkpoint_with_prior(0.2))
    high = bayesian_posterior(rows, mask, _checkpoint_with_prior(0.8))
    assert low < high
    assert low != high


def test_bayesian_mask_excludes_rows_exactly() -> None:
    checkpoint = load_bayesian_checkpoint(_FIXTURE)
    masked = bayesian_posterior(
        ((1, 0, 1), (0, 1, 1), (1, 1, 0)),
        (True, False, True),
        checkpoint,
    )
    removed = bayesian_posterior(
        ((1, 0, 1), (1, 1, 0)),
        (True, True),
        checkpoint,
    )
    assert masked == removed


def test_bayesian_rejects_zero_valid_mask_and_bad_g_geometry() -> None:
    checkpoint = load_bayesian_checkpoint(_FIXTURE)
    with pytest.raises(ZeroValidObservationsError):
        bayesian_posterior(((1, 0, 1),), (False,), checkpoint)
    with pytest.raises(ValueError, match="depth"):
        bayesian_posterior(((1, 0),), (True,), checkpoint)
    with pytest.raises(ValueError, match="binary"):
        bayesian_posterior(((1, 2, 0),), (True,), checkpoint)
    with pytest.raises(ValueError, match="mask length"):
        bayesian_posterior(((1, 0, 1),), (True, False), checkpoint)


def test_bayesian_checkpoint_rejects_hash_source_and_dead_delta_tampering() -> None:
    checkpoint = load_bayesian_checkpoint(_FIXTURE)
    with pytest.raises(ValueError, match="checkpoint_hash"):
        replace(checkpoint, base_rate=0.4)
    with pytest.raises(ValueError, match="source_commit"):
        replace(checkpoint, source_commit="0" * 40, checkpoint_hash="0" * 64)
    bad_delta = (
        (0.1, 0.0, 0.0),
        (0.4, 0.0, 0.0),
        (-0.3, 0.2, 0.0),
    )
    with pytest.raises(ValueError, match="lower triangular"):
        replace(checkpoint, delta=bad_delta, checkpoint_hash="0" * 64)


def test_bayesian_checkpoint_schema_rejects_extra_or_missing_fields() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    data["extra"] = True
    with pytest.raises(ValueError, match="schema"):
        BayesianCheckpoint.from_mapping(data)


def test_load_bayesian_checkpoint_rejects_oversized_json(monkeypatch, tmp_path: Path) -> None:
    from fuckmark.detectors import bayesian as bayesian_module

    monkeypatch.setattr(bayesian_module, "BAYESIAN_CHECKPOINT_JSON_MAX_BYTES", 8)
    path = tmp_path / "oversized.json"
    path.write_text('{"too": "large"}', encoding="utf-8")
    with pytest.raises(ValueError, match="size limit"):
        load_bayesian_checkpoint(path)
