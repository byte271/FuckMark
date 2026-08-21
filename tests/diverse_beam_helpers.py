from functools import lru_cache

from corpus_helpers import model_identity, watermark

from fuckmark.corpus import GenerationParameters
from fuckmark.corpus.mid_dev_generation import MidDevGeneratedContinuation
from fuckmark.experiments.diverse_beam_ab import (
    DIVERSE_BEAM_AB_BEAM_WIDTH,
    DIVERSE_BEAM_AB_BUDGETS,
    DIVERSE_BEAM_AB_MAX_RISK_TIER,
    DIVERSE_BEAM_AB_SEARCH_ROW_VERSION,
    DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT,
    DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION,
    DiverseBeamSearchRow,
    DiverseBeamSearchShard,
)
from fuckmark.experiments.diverse_beam_corpus import (
    DIVERSE_BEAM_GENERATION_SEED_BASE,
    DIVERSE_BEAM_GENERATION_SHARD_COUNT,
    freeze_diverse_beam_corpus,
    generate_diverse_beam_shard,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.algorithm_ids import (
    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
)

_TEST_RULESET_HASH = sha256_text("diverse-beam-test-ruleset")
_TEST_GEOMETRY_HASH = sha256_text("diverse-beam-test-geometry")
_TEST_REPETITION_HASH = sha256_text("diverse-beam-test-repetition")


class DiverseBeamFakeBackend:
    @property
    def model_identity(self):
        return model_identity()

    @property
    def watermark_condition(self):
        return watermark()

    def generation_parameters(
        self, seed: int, target_length: int
    ) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id="diverse-beam-test-seed-v1",
            temperature=0.8,
            top_k=50,
            top_p=0.95,
            max_new_tokens=target_length,
            do_sample=True,
            dtype="float32",
            device="cpu",
            backend_id="diverse-beam-test-backend",
            backend_version="v1",
        )

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation:
        if not watermarked:
            raise AssertionError(
                "Diverse Beam corpus generation must request watermarking"
            )
        both_duplicate = seed in {
            DIVERSE_BEAM_GENERATION_SEED_BASE,
            DIVERSE_BEAM_GENERATION_SEED_BASE + 1,
        }
        text_duplicate = seed in {
            DIVERSE_BEAM_GENERATION_SEED_BASE + 2,
            DIVERSE_BEAM_GENERATION_SEED_BASE + 3,
        }
        token_duplicate = seed in {
            DIVERSE_BEAM_GENERATION_SEED_BASE + 4,
            DIVERSE_BEAM_GENERATION_SEED_BASE + 5,
        }
        continuation_seed = (
            DIVERSE_BEAM_GENERATION_SEED_BASE
            if both_duplicate
            else DIVERSE_BEAM_GENERATION_SEED_BASE + 4
            if token_duplicate
            else seed
        )
        text = (
            "Generated duplicate watermarked sample."
            if both_duplicate
            else "Generated text-only duplicate sample."
            if text_duplicate
            else f"Generated watermarked sample {seed}: {prompt}"
        )
        continuation = (continuation_seed, *range(target_length - 1))
        return MidDevGeneratedContinuation(
            text=text,
            input_token_ids=(11, 12),
            attention_mask=(1, 1),
            continuation_token_ids=continuation,
            text_only_token_ids=(len(text), int(sha256_text(text)[:8], 16)),
        )


@lru_cache(maxsize=1)
def diverse_beam_fake_shards():
    backend = DiverseBeamFakeBackend()
    return tuple(
        generate_diverse_beam_shard(
            backend,
            shard_index=index,
            shard_count=DIVERSE_BEAM_GENERATION_SHARD_COUNT,
            source_code_commit="a" * 40,
        )
        for index in range(DIVERSE_BEAM_GENERATION_SHARD_COUNT)
    )


@lru_cache(maxsize=1)
def diverse_beam_fake_corpus():
    return freeze_diverse_beam_corpus(diverse_beam_fake_shards())


def _search_row(
    sample, strategy: str, budget: int, success: bool
) -> DiverseBeamSearchRow:
    state_hash = sha256_text(f"state:{sample.sample_id}:{strategy}:{budget}")
    operation_hashes = tuple(
        sha256_text(f"operation:{sample.sample_id}:{strategy}:{budget}:{index}")
        for index in range(budget)
    )
    result_hashes = (state_hash,) if success else ()
    structural = {
        "algorithm_version": DIVERSE_BEAM_AB_SEARCH_ROW_VERSION,
        "sample_ordinal": sample.ordinal,
        "sample_id": sample.sample_id,
        "prompt_family_id": sample.prompt_family_id,
        "domain": sample.domain,
        "target_length": sample.target_length,
        "source_text_hash": sample.text_hash,
        "strategy": strategy,
        "budget": budget,
        "beam_width": DIVERSE_BEAM_AB_BEAM_WIDTH,
        "max_risk_tier": DIVERSE_BEAM_AB_MAX_RISK_TIER,
        "ruleset_hash": _TEST_RULESET_HASH,
        "geometry_config_hash": _TEST_GEOMETRY_HASH,
        "repetition_policy_hash": _TEST_REPETITION_HASH,
        "candidate_pool_hash": sha256_text(f"pool:{sample.sample_id}"),
        "root_state_hash": sha256_text(f"root:{sample.sample_id}"),
        "root_candidate_count": 12,
        "root_protected_span_count": 0,
        "exact_depth_success": success,
        "exact_state_count": int(success),
        "final_state_count": int(success),
        "frontier_state_count": int(success),
        "result_state_hashes": result_hashes,
        "frontier_state_hashes": result_hashes,
        "selected_state_hash": state_hash if success else None,
        "selected_text_hash": sha256_text(f"text:{state_hash}") if success else None,
        "selected_operation_hashes": operation_hashes if success else (),
        "highest_risk_tier": 1 if success else None,
        "visible_cost": budget if success else None,
        "token_edit_distance": budget if success else None,
        "unique_reachable_state_count": budget * 8,
        "dead_end_state_count": int(not success),
        "accepted_transition_count": budget * 10,
        "duplicate_state_suppression_count": budget * 2,
        "expanded_state_count": budget * 4,
        "pruned_state_count": budget,
        "expansion_cache_hit_count": budget,
        "expansion_cache_miss_count": budget * 3,
        "hard_invariant_accepted_violation_count": 0,
        "protected_content_accepted_violation_count": 0,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "search_result_hash": sha256_text(
            f"result:{sample.sample_id}:{strategy}:{budget}:{success}"
        ),
    }
    runtime_ns = (
        1_100 if strategy == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION else 1_000
    )
    structural_hash = sha256_json(structural)
    return DiverseBeamSearchRow.create(
        structural,
        runtime_ns=runtime_ns,
        replay_structural_hash=structural_hash,
    )


def diverse_beam_search_shard(
    shard_index: int,
    rows: tuple[DiverseBeamSearchRow, ...],
) -> DiverseBeamSearchShard:
    corpus = diverse_beam_fake_corpus()
    ordered = tuple(
        sorted(rows, key=lambda value: (value.sample_id, value.budget, value.strategy))
    )
    payload = {
        "algorithm_version": DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION,
        "source_code_commit": corpus.source_code_commit,
        "frozen_corpus_hash": corpus.artifact_hash,
        "runtime_tokenizer_identity_hash": corpus.model_identity_hash,
        "ruleset_hash": _TEST_RULESET_HASH,
        "geometry_config_hash": _TEST_GEOMETRY_HASH,
        "repetition_policy_hash": _TEST_REPETITION_HASH,
        "budgets": DIVERSE_BEAM_AB_BUDGETS,
        "beam_width": DIVERSE_BEAM_AB_BEAM_WIDTH,
        "max_risk_tier": DIVERSE_BEAM_AB_MAX_RISK_TIER,
        "shard_index": shard_index,
        "shard_count": DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "rows": tuple(value.as_dict() for value in ordered),
    }
    return DiverseBeamSearchShard(
        algorithm_version=DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION,
        source_code_commit=corpus.source_code_commit,
        frozen_corpus_hash=corpus.artifact_hash,
        runtime_tokenizer_identity_hash=corpus.model_identity_hash,
        ruleset_hash=_TEST_RULESET_HASH,
        geometry_config_hash=_TEST_GEOMETRY_HASH,
        repetition_policy_hash=_TEST_REPETITION_HASH,
        budgets=DIVERSE_BEAM_AB_BUDGETS,
        beam_width=DIVERSE_BEAM_AB_BEAM_WIDTH,
        max_risk_tier=DIVERSE_BEAM_AB_MAX_RISK_TIER,
        shard_index=shard_index,
        shard_count=DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT,
        detector_access_observed=False,
        secret_access_observed=False,
        rows=ordered,
        artifact_hash=sha256_json(payload),
    )


@lru_cache(maxsize=1)
def diverse_beam_fake_search_shards():
    corpus = diverse_beam_fake_corpus()
    by_shard = [[] for _ in range(DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT)]
    gain_sample_id = corpus.samples[0].sample_id
    for sample in corpus.samples:
        shard_rows = by_shard[sample.ordinal % DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT]
        for budget in DIVERSE_BEAM_AB_BUDGETS:
            beam_success = not (sample.sample_id == gain_sample_id and budget == 6)
            shard_rows.append(
                _search_row(
                    sample,
                    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
                    budget,
                    beam_success,
                )
            )
            shard_rows.append(
                _search_row(
                    sample,
                    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
                    budget,
                    True,
                )
            )
    return tuple(
        diverse_beam_search_shard(index, tuple(rows))
        for index, rows in enumerate(by_shard)
    )


def diverse_beam_failed_row(row: DiverseBeamSearchRow) -> DiverseBeamSearchRow:
    structural = row.structural_payload()
    structural.update(
        {
            "exact_depth_success": False,
            "exact_state_count": 0,
            "final_state_count": 0,
            "frontier_state_count": 0,
            "result_state_hashes": (),
            "frontier_state_hashes": (),
            "selected_state_hash": None,
            "selected_text_hash": None,
            "selected_operation_hashes": (),
            "highest_risk_tier": None,
            "visible_cost": None,
            "token_edit_distance": None,
            "dead_end_state_count": max(1, row.dead_end_state_count),
            "search_result_hash": sha256_text(f"failed:{row.row_hash}"),
        }
    )
    return DiverseBeamSearchRow.create(
        structural,
        runtime_ns=row.runtime_ns,
        replay_structural_hash=sha256_json(structural),
    )


def diverse_beam_replace_row(
    shards: tuple[DiverseBeamSearchShard, ...],
    replacement: DiverseBeamSearchRow,
) -> tuple[DiverseBeamSearchShard, ...]:
    shard_index = replacement.sample_ordinal % DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT
    output = list(shards)
    rows = tuple(
        replacement
        if (row.sample_id, row.budget, row.strategy)
        == (replacement.sample_id, replacement.budget, replacement.strategy)
        else row
        for row in output[shard_index].rows
    )
    output[shard_index] = diverse_beam_search_shard(shard_index, rows)
    return tuple(output)
