from __future__ import annotations

from fuckmark.geometry import (
    GeometryConfig,
    PromptBoundaryMode,
    SurvivalReportStatus,
    TokenTrack,
    build_root_observations,
    compute_observation_survival,
)
from fuckmark.alignment import align_tokens
from fuckmark.hashing import sha256_text


def _config(ngram_len: int = 3) -> GeometryConfig:
    return GeometryConfig.create(
        tokenizer_identity_hash=sha256_text("toy-tokenizer-v1"),
        ngram_len=ngram_len,
        repetition_mask_policy_id="all-eligible-v1",
    )


def test_root_observation_occurrences_are_distinct_even_for_duplicate_windows() -> None:
    config = _config(2)
    tokens = (1, 2, 9, 1, 2)
    root = build_root_observations(
        source_sample_id="duplicate-source",
        source_text="A B X A B",
        root_tokens=tokens,
        config=config,
    )
    assert root.observations[0].token_ids == (1, 2)
    assert root.observations[3].token_ids == (1, 2)
    assert root.observations[0].occurrence_hash != root.observations[3].occurrence_hash
    assert root.observations[0].observation_index == 0
    assert root.observations[3].observation_index == 3


def test_identity_survival_is_exactly_one() -> None:
    config = _config(3)
    tokens = (1, 2, 3, 4, 5)
    root = build_root_observations(
        source_sample_id="identity-source",
        source_text="A B C D E",
        root_tokens=tokens,
        config=config,
    )
    report = compute_observation_survival(
        root=root,
        root_tokens=tokens,
        transformed_tokens=tokens,
        transformed_eligible_windows=None,
        alignment=align_tokens(tokens, tokens),
    )
    assert report.status is SurvivalReportStatus.OK
    assert report.root_eligible_count == 3
    assert report.surviving_count == 3
    assert report.destroyed_count == 0
    assert report.survival_ratio == 1.0
    assert report.destruction_ratio == 0.0


def test_short_input_has_explicit_neutral_status() -> None:
    config = _config(3)
    tokens = (1, 2)
    root = build_root_observations(
        source_sample_id="short-source",
        source_text="A B",
        root_tokens=tokens,
        config=config,
    )
    report = compute_observation_survival(
        root=root,
        root_tokens=tokens,
        transformed_tokens=tokens,
        transformed_eligible_windows=None,
        alignment=align_tokens(tokens, tokens),
    )
    assert report.root_observation_count == 0
    assert report.root_eligible_count == 0
    assert report.status is SurvivalReportStatus.NO_ELIGIBLE_OBSERVATIONS
    assert report.survival_ratio == 1.0
    assert report.destruction_ratio == 0.0


def test_prompt_boundary_and_track_are_bound_into_occurrence_hash() -> None:
    config = _config(2)
    tokens = (1, 2, 3)
    root = build_root_observations(
        source_sample_id="prompt-source",
        source_text="generated only",
        root_tokens=tokens,
        config=config,
    )
    row = root.observations[0]
    assert row.token_track is TokenTrack.DECODED_TEXT
    assert row.prompt_boundary_mode is PromptBoundaryMode.GENERATED_ONLY
    other_config = GeometryConfig.create(
        tokenizer_identity_hash=config.tokenizer_identity_hash,
        ngram_len=2,
        repetition_mask_policy_id="different-public-mask-v1",
    )
    other = build_root_observations(
        source_sample_id="prompt-source",
        source_text="generated only",
        root_tokens=tokens,
        config=other_config,
    )
    assert other.observations[0].occurrence_hash == row.occurrence_hash
    assert other.root_hash != root.root_hash
