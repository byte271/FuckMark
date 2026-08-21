from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from diverse_beam_helpers import diverse_beam_fake_corpus, diverse_beam_fake_shards

from fuckmark.durable_io import write_canonical_json_fsynced
from fuckmark.experiments.diverse_beam_corpus import (
    DIVERSE_BEAM_ANALYSIS_PER_LENGTH,
    DIVERSE_BEAM_GENERATED_PER_LENGTH,
    DIVERSE_BEAM_TARGET_LENGTHS,
    build_diverse_beam_prompt_specs,
    diverse_beam_prompt_profile_hash,
    load_diverse_beam_frozen_corpus,
    load_diverse_beam_generation_shard,
)


def test_diverse_beam_prompt_profile_is_frozen_and_balanced() -> None:
    prompts = build_diverse_beam_prompt_specs()
    assert (
        len(prompts)
        == len(DIVERSE_BEAM_TARGET_LENGTHS) * DIVERSE_BEAM_GENERATED_PER_LENGTH
    )
    assert len({value.sample_id for value in prompts}) == len(prompts)
    assert len({value.prompt_text_hash for value in prompts}) == len(prompts)
    assert Counter(value.target_length for value in prompts) == Counter(
        {
            value: DIVERSE_BEAM_GENERATED_PER_LENGTH
            for value in DIVERSE_BEAM_TARGET_LENGTHS
        }
    )
    assert len({value.prompt_family_id for value in prompts}) == 6
    assert len({value.domain for value in prompts}) == 4
    assert len(diverse_beam_prompt_profile_hash()) == 64


def test_generation_shards_freeze_500_independent_samples_before_search() -> None:
    corpus = diverse_beam_fake_corpus()
    assert corpus.generated_sample_count == 640
    assert corpus.duplicate_text_only_count == 1
    assert corpus.duplicate_token_only_count == 1
    assert corpus.duplicate_text_and_token_count == 1
    assert corpus.duplicate_excluded_count == 3
    assert corpus.surplus_unique_excluded_count == 137
    assert corpus.eligible_sample_count == 500
    assert Counter(value.target_length for value in corpus.samples) == Counter(
        {
            value: DIVERSE_BEAM_ANALYSIS_PER_LENGTH
            for value in DIVERSE_BEAM_TARGET_LENGTHS
        }
    )
    assert len({value.text_hash for value in corpus.samples}) == 500
    assert len({value.continuation_token_hash for value in corpus.samples}) == 500
    assert corpus.frozen_before_search is True
    assert corpus.detector_score_selection_observed is False
    assert corpus.planner_secret_access_observed is False


def test_diverse_beam_corpus_json_round_trip_and_unknown_field_rejection(
    tmp_path: Path,
) -> None:
    shards = diverse_beam_fake_shards()
    shard_path = tmp_path / "shard.json"
    corpus_path = tmp_path / "corpus.json"
    write_canonical_json_fsynced(shard_path, shards[0].as_dict())
    assert load_diverse_beam_generation_shard(shard_path) == shards[0]
    corpus = diverse_beam_fake_corpus()
    write_canonical_json_fsynced(corpus_path, corpus.as_dict())
    assert load_diverse_beam_frozen_corpus(corpus_path) == corpus
    value = json.loads(corpus_path.read_text(encoding="utf-8"))
    value["unexpected"] = True
    corpus_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="keys"):
        load_diverse_beam_frozen_corpus(corpus_path)
