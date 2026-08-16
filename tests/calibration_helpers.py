from dataclasses import replace

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors import CalibrationScope, mean_evidence, weighted_mean_evidence
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations


def _base_evidence(weighted: bool = False):
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    batch = build_native_observations("base", (1, 2, 3, 4, 5, 6), 999, adapter)
    return weighted_mean_evidence(batch) if weighted else mean_evidence(batch)

def _evidence_scores(scores, weighted: bool = False):
    base = _base_evidence(weighted)
    return tuple(
        replace(
            base,
            sample_id=f"negative-{index:05d}",
            observation_batch_hash=sha256_text(f"negative-observation-{index}"),
            raw_score=float(score),
        )
        for index, score in enumerate(scores)
    )

def _scope():
    return CalibrationScope.create(
        corpus_id="dev-control-v1",
        population_id="negative-calibration",
        length_policy_id="generated-256",
        token_track="original-generation-token-ids",
        prompt_boundary_mode="continuation-only",
    )
