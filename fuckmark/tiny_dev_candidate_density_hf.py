from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_json
from .experiments.candidate_density_audit import (
    STRICT_DENSITY_BEAM_WIDTH,
    audit_source_candidate_density,
    build_strict_candidate_density_artifact,
)
from .experiments.context_survival_plan import (
    DEFAULT_MAX_RISK_TIER,
    _MemoizedExpander,
    _attack_samples,
    _context_registry,
    _encode_with_offsets,
)
from .geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from .scheduling.context_survival import ContextSurvivalExpander
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    DEFAULT_NGRAM_LEN,
    runtime_tokenizer_identity_public,
)
from .transforms.contractions import contraction_inverse_semantic_resolver


def build_tiny_dev_strict_candidate_density(
    corpus,
    tokenizer,
    *,
    source_code_commit: str,
    ngram_len: int = DEFAULT_NGRAM_LEN,
    context_history_size: int = DEFAULT_CONTEXT_HISTORY_SIZE,
):
    registry = _context_registry()
    repetition = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    config = GeometryConfig.create(
        tokenizer_identity_hash=corpus.model_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=repetition.policy_id,
    )
    rows = []
    for source in _attack_samples(corpus):
        token_ids, _ = _encode_with_offsets(tokenizer, source)
        geometry_engine = CounterfactualGeometryEngine(
            tokenizer=tokenizer,
            config=config,
            eligibility_policy=repetition.eligibility_policy,
        )
        base_expander = ContextSurvivalExpander(
            registry=registry,
            geometry_engine=geometry_engine,
            source_sample_id=source.sample_id,
            source_text=source.text,
            max_risk_tier=DEFAULT_MAX_RISK_TIER,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        root_state = base_expander.root_state
        root = geometry_engine.build_root(
            source_sample_id=source.sample_id,
            source_text=source.text,
        )
        if tuple(root.root_tokens) != token_ids:
            raise RuntimeError(
                f"geometry root tokenization does not match frozen track for {source.sample_id}"
            )
        expander = _MemoizedExpander(base_expander)
        rows.append(
            audit_source_candidate_density(
                source_sample_id=source.sample_id,
                source_text=source.text,
                registry=registry,
                base_expander=expander,
                root_state=root_state,
            )
        )
        if expander.detector_access_observed or expander.secret_access_observed:
            raise RuntimeError("candidate-density audit observed prohibited selection access")
    return build_strict_candidate_density_artifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=corpus.artifact_hash,
        candidate_registry_hash=registry.ruleset_hash,
        rows=rows,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-strict-candidate-density-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--ngram-len", type=int, default=DEFAULT_NGRAM_LEN)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument(
        "--artifact-json",
        type=Path,
        default=Path("artifacts/tiny-dev-strict-candidate-density.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned public tokenizer dependencies first") from error
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("candidate-density audit requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen TinyDev corpus")
    artifact = build_tiny_dev_strict_candidate_density(
        corpus,
        tokenizer,
        source_code_commit=args.source_code_commit,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
    )
    args.artifact_json.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    summary = {
        "source_count": len(artifact.rows),
        "b4_reachable_count": sum(row.strict_b4_reachable for row in artifact.rows),
        "b6_reachable_count": sum(row.strict_b6_reachable for row in artifact.rows),
        "root_candidate_counts": [row.root_enumerated_candidate_count for row in artifact.rows],
        "root_strict_counts": [row.root_strict_transition_count for row in artifact.rows],
    }
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"decision={artifact.decision}\n")
    sys.stdout.write(f"beam_width={STRICT_DENSITY_BEAM_WIDTH}\n")
    sys.stdout.write(f"summary={json.dumps(summary, sort_keys=True)}\n")
    sys.stdout.write(f"artifact_json={args.artifact_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
