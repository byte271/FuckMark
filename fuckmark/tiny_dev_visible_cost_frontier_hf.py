from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_json
from .experiments.candidate_density_diagnosis import STRICT_VISIBLE_COST_CEILING_DOMINATES
from .experiments.context_survival_plan import (
    DEFAULT_MAX_RISK_TIER,
    _MemoizedExpander,
    _attack_samples,
    _context_registry,
    _encode_with_offsets,
)
from .experiments.visible_cost_frontier import (
    VisibleCostFrontierRow,
    build_visible_cost_frontier_artifact,
)
from .geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from .scheduling.context_survival import ContextSurvivalExpander
from .search.visible_cost_budget import (
    RELAXED_VISIBLE_COST_POLICY,
    STRICT_VISIBLE_COST_POLICY,
    VisibleCostTier,
    assess_visible_cost,
    visible_cost_beam_search,
)
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    DEFAULT_NGRAM_LEN,
    runtime_tokenizer_identity_public,
)
from .transforms.contractions import contraction_inverse_semantic_resolver


def build_tiny_dev_visible_cost_frontier(
    corpus,
    tokenizer,
    *,
    source_code_commit: str,
    scarcity_diagnosis: dict,
    ngram_len: int = DEFAULT_NGRAM_LEN,
    context_history_size: int = DEFAULT_CONTEXT_HISTORY_SIZE,
    beam_width: int = 32,
    maximum_search_operations: int = 12,
):
    if scarcity_diagnosis.get("decision") != STRICT_VISIBLE_COST_CEILING_DOMINATES:
        raise RuntimeError("normalized budget controller requires frozen cost-ceiling diagnosis")
    if scarcity_diagnosis.get("family_expansion_permitted") is not False:
        raise RuntimeError("rule-family expansion must remain blocked for cost-ceiling diagnosis")
    diagnosis_hash = scarcity_diagnosis.get("artifact_hash")
    if not isinstance(diagnosis_hash, str):
        raise RuntimeError("scarcity diagnosis is missing artifact_hash")
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
        base = ContextSurvivalExpander(
            registry=registry,
            geometry_engine=geometry_engine,
            source_sample_id=source.sample_id,
            source_text=source.text,
            max_risk_tier=DEFAULT_MAX_RISK_TIER,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        root = base.root_state
        geometry_root = geometry_engine.build_root(
            source_sample_id=source.sample_id,
            source_text=source.text,
        )
        if tuple(geometry_root.root_tokens) != token_ids:
            raise RuntimeError(f"geometry root tokenization mismatch for {source.sample_id}")
        expander = _MemoizedExpander(base)
        strict = visible_cost_beam_search(
            expander,
            root,
            root_text=source.text,
            tier=VisibleCostTier.STRICT,
            beam_width=beam_width,
            maximum_search_operations=maximum_search_operations,
        )
        relaxed = visible_cost_beam_search(
            expander,
            root,
            root_text=source.text,
            tier=VisibleCostTier.RELAXED,
            beam_width=beam_width,
            maximum_search_operations=maximum_search_operations,
        )
        strict_state = strict.states[0]
        relaxed_state = relaxed.states[0]
        strict_assessment = assess_visible_cost(source.text, strict_state, STRICT_VISIBLE_COST_POLICY)
        relaxed_assessment = assess_visible_cost(source.text, relaxed_state, RELAXED_VISIBLE_COST_POLICY)
        rows.append(
            VisibleCostFrontierRow.create(
                source_sample_id=source.sample_id,
                source_character_count=len(source.text),
                root_surviving_observations=root.surviving_root_observations,
                strict_result=strict,
                strict_assessment=strict_assessment,
                relaxed_result=relaxed,
                relaxed_assessment=relaxed_assessment,
            )
        )
        if expander.detector_access_observed or expander.secret_access_observed:
            raise RuntimeError("normalized visible-cost search observed prohibited selection access")
    return build_visible_cost_frontier_artifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=corpus.artifact_hash,
        candidate_registry_hash=registry.ruleset_hash,
        scarcity_diagnosis_artifact_hash=diagnosis_hash,
        rows=rows,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-visible-cost-frontier-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--scarcity-diagnosis-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--ngram-len", type=int, default=DEFAULT_NGRAM_LEN)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--beam-width", type=int, default=32)
    parser.add_argument("--maximum-search-operations", type=int, default=12)
    parser.add_argument(
        "--artifact-json",
        type=Path,
        default=Path("artifacts/tiny-dev-visible-cost-frontier.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install the pinned public tokenizer dependencies first") from error
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    scarcity = json.loads(args.scarcity_diagnosis_json.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("visible-cost frontier requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen TinyDev corpus")
    artifact = build_tiny_dev_visible_cost_frontier(
        corpus,
        tokenizer,
        source_code_commit=args.source_code_commit,
        scarcity_diagnosis=scarcity,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
        beam_width=args.beam_width,
        maximum_search_operations=args.maximum_search_operations,
    )
    args.artifact_json.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    summary = {
        "source_count": len(artifact.rows),
        "strict_depths": [row.strict_reached_depth for row in artifact.rows],
        "relaxed_depths": [row.relaxed_reached_depth for row in artifact.rows],
        "strict_survivors": [row.strict_surviving_observations for row in artifact.rows],
        "relaxed_survivors": [row.relaxed_surviving_observations for row in artifact.rows],
    }
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"summary={json.dumps(summary, sort_keys=True)}\n")
    sys.stdout.write(f"artifact_json={args.artifact_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
