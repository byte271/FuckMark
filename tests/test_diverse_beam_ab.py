from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from diverse_beam_helpers import (
    diverse_beam_failed_row,
    diverse_beam_fake_corpus,
    diverse_beam_fake_search_shards,
    diverse_beam_replace_row,
    diverse_beam_search_shard,
)

from fuckmark.durable_io import write_canonical_json_fsynced
from fuckmark.experiments.diverse_beam_ab import (
    KEEP_BEAM_V2_DIVERSE_LOSSES,
    KEEP_BEAM_V2_NO_MATCHED_GAIN,
    PROMOTE_DIVERSE_BEAM_V1,
    _registry,
    _run_strategy,
    analyze_diverse_beam_search,
    load_diverse_beam_analysis,
    load_diverse_beam_search_shard,
)
from fuckmark.geometry import GeometryConfig, PublicRepetitionGeometry
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.algorithm_ids import (
    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
)


class _ReplayTokenizer:
    def __init__(self, source_text: str, source_ids: tuple[int, ...]) -> None:
        self._source_text = source_text
        self._source_ids = source_ids

    def _pieces(self, text: str):
        return tuple(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\w\s]", text))

    def encode(self, text: str, add_special_tokens: bool = True):
        if text == self._source_text:
            return list(self._source_ids)
        return [
            int.from_bytes(hashlib.sha256(value.group(0).encode()).digest()[:4], "big")
            for value in self._pieces(text)
        ]

    def __call__(
        self,
        text: str,
        add_special_tokens: bool = True,
        return_offsets_mapping: bool = False,
    ):
        if text == self._source_text:
            ids = list(self._source_ids)
            width = max(1, len(text) // len(ids))
            offsets = [
                (
                    index * width,
                    len(text) if index == len(ids) - 1 else (index + 1) * width,
                )
                for index in range(len(ids))
            ]
        else:
            pieces = self._pieces(text)
            ids = [
                int.from_bytes(
                    hashlib.sha256(value.group(0).encode()).digest()[:4], "big"
                )
                for value in pieces
            ]
            offsets = [(value.start(), value.end()) for value in pieces]
        output = {"input_ids": ids}
        if return_offsets_mapping:
            output["offset_mapping"] = offsets
        return output


def test_diverse_beam_analysis_promotes_only_a_strict_zero_loss_gain(
    tmp_path: Path,
) -> None:
    corpus = diverse_beam_fake_corpus()
    shards = diverse_beam_fake_search_shards()
    analysis = analyze_diverse_beam_search(corpus, shards)
    assert analysis["sample_count"] == 500
    assert analysis["row_count"] == 4_000
    assert analysis["aggregate"]["diverse_gain_count"] == 1
    assert analysis["aggregate"]["diverse_loss_count"] == 0
    assert analysis["decision"] == PROMOTE_DIVERSE_BEAM_V1
    assert analysis["promoted"] is True
    assert analysis["cost_bound_passed"] is True
    assert analysis["runtime_bound_passed"] is True
    assert analysis["fidelity_gate_passed"] is True
    assert analysis["replay_gate_passed"] is True
    analysis_path = tmp_path / "analysis.json"
    shard_path = tmp_path / "shard.json"
    write_canonical_json_fsynced(analysis_path, analysis)
    write_canonical_json_fsynced(shard_path, shards[0].as_dict())
    loaded = load_diverse_beam_analysis(analysis_path)
    assert loaded["artifact_hash"] == analysis["artifact_hash"]
    assert loaded["decision"] == analysis["decision"]
    assert load_diverse_beam_search_shard(shard_path) == shards[0]


def test_diverse_beam_real_search_row_replays_exactly_without_detector_or_secret_access() -> (
    None
):
    corpus = diverse_beam_fake_corpus()
    source = corpus.samples[1]
    sample_payload = source.payload()
    text = "We do not agree."
    token_ids = (101, 102, 103, 104, 105)
    sample_payload.update(
        {
            "text": text,
            "text_hash": sha256_text(text),
            "text_only_token_ids": token_ids,
            "text_only_token_hash": sha256_json(token_ids),
        }
    )
    sample = type(source)(**sample_payload, record_hash=sha256_json(sample_payload))
    tokenizer = _ReplayTokenizer(sample.text, sample.text_only_token_ids)
    registry = _registry()
    repetition = PublicRepetitionGeometry.create(ngram_len=2, context_history_size=32)
    config = GeometryConfig.create(
        tokenizer_identity_hash=corpus.model_identity_hash,
        ngram_len=2,
        repetition_mask_policy_id=repetition.policy_id,
    )
    rows = _run_strategy(
        sample=sample,
        tokenizer=tokenizer,
        registry=registry,
        repetition=repetition,
        config=config,
        strategy=CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    )
    assert tuple(row.budget for row in rows) == (1, 2, 4, 6)
    assert all(row.deterministic_replay_passed for row in rows)
    assert all(not row.detector_access_observed for row in rows)
    assert all(not row.secret_access_observed for row in rows)
    assert all(row.hard_invariant_accepted_violation_count == 0 for row in rows)
    assert all(row.protected_content_accepted_violation_count == 0 for row in rows)


def test_diverse_beam_analysis_keeps_beam_v2_without_a_gain() -> None:
    corpus = diverse_beam_fake_corpus()
    shards = diverse_beam_fake_search_shards()
    gain_row = next(
        row
        for shard in shards
        for row in shard.rows
        if row.sample_id == corpus.samples[0].sample_id
        and row.budget == 6
        and row.strategy == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    )
    analysis = analyze_diverse_beam_search(
        corpus,
        diverse_beam_replace_row(shards, diverse_beam_failed_row(gain_row)),
    )
    assert analysis["aggregate"]["diverse_gain_count"] == 0
    assert analysis["aggregate"]["diverse_loss_count"] == 0
    assert analysis["decision"] == KEEP_BEAM_V2_NO_MATCHED_GAIN
    assert analysis["promoted"] is False


def test_diverse_beam_analysis_rejects_any_loss() -> None:
    corpus = diverse_beam_fake_corpus()
    shards = diverse_beam_fake_search_shards()
    loss_row = next(
        row
        for shard in shards
        for row in shard.rows
        if row.sample_id == corpus.samples[1].sample_id
        and row.budget == 6
        and row.strategy == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    )
    analysis = analyze_diverse_beam_search(
        corpus,
        diverse_beam_replace_row(shards, diverse_beam_failed_row(loss_row)),
    )
    assert analysis["aggregate"]["diverse_gain_count"] == 1
    assert analysis["aggregate"]["diverse_loss_count"] == 1
    assert analysis["decision"] == KEEP_BEAM_V2_DIVERSE_LOSSES
    assert analysis["promoted"] is False


def test_diverse_beam_analysis_rejects_wrong_shard_assignment() -> None:
    corpus = diverse_beam_fake_corpus()
    shards = list(diverse_beam_fake_search_shards())
    left = shards[0]
    right = shards[1]
    left_row = left.rows[0]
    right_row = right.rows[0]
    shards[0] = diverse_beam_search_shard(
        0,
        (right_row, *left.rows[1:]),
    )
    shards[1] = diverse_beam_search_shard(
        1,
        (left_row, *right.rows[1:]),
    )
    with pytest.raises(ValueError, match="wrong shard"):
        analyze_diverse_beam_search(corpus, tuple(shards))


def test_diverse_beam_row_rejects_nondeterministic_replay() -> None:
    row = diverse_beam_fake_search_shards()[0].rows[0]
    with pytest.raises(ValueError, match="replay deterministically"):
        type(row).create(
            row.structural_payload(),
            runtime_ns=row.runtime_ns,
            replay_structural_hash=sha256_text("different replay"),
        )


def test_diverse_beam_analysis_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    analysis = analyze_diverse_beam_search(
        diverse_beam_fake_corpus(),
        diverse_beam_fake_search_shards(),
    )
    analysis["unexpected"] = True
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(analysis), encoding="utf-8")
    with pytest.raises(ValueError, match="keys"):
        load_diverse_beam_analysis(path)
