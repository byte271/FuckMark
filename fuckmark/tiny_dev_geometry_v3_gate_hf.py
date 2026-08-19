from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_json
from .experiments.context_survival_plan import (
    INSUFFICIENT_CANDIDATES,
    NO_CANDIDATES,
    SUCCESS,
    _MemoizedExpander,
    _attack_samples,
    _context_registry,
    _select_result_state,
)
from .experiments.geometry_v3_gate import (
    GEOMETRY_V3_GATE_BUDGETS,
    GeometryV3GateRow,
    MatchedVisibleCostEnvelope,
    PublicResidualStateEvaluator,
    build_geometry_v3_gate_artifact,
)
from .geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from .search.beam_v3 import beam_search_v3
from .scheduling.beam_v2 import beam_search_v2
from .scheduling.context_survival import ContextSurvivalExpander
from .tiny_dev_context_survival_plan_hf import (
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    DEFAULT_NGRAM_LEN,
    runtime_tokenizer_identity_public,
)
from .transforms.contractions import contraction_inverse_semantic_resolver
from .transforms.hard_invariants import validate_hard_invariants


DEFAULT_BEAM_WIDTH = 32


def _tokenize(tokenizer, text: str) -> tuple[int, ...]:
    values = tokenizer(text, add_special_tokens=False)["input_ids"]
    if values and isinstance(values[0], list):
        if len(values) != 1:
            raise RuntimeError("unexpected batched tokenizer output")
        values = values[0]
    return tuple(int(value) for value in values)


def _hard_validator(registry, source_text: str):
    def validate(output_text: str) -> bool:
        report = validate_hard_invariants(source_text, output_text, registry.identifiers, ())
        status = getattr(report.status, "value", report.status)
        return status in ("PASS", "pass")

    return validate


def _select_v3(result, budget: int):
    full_depth = tuple(value for value in result.frontier if value.state.depth == budget)
    if full_depth:
        return full_depth[0], SUCCESS
    candidates = tuple(result.frontier or result.states)
    if candidates:
        return candidates[0], INSUFFICIENT_CANDIDATES
    return None, NO_CANDIDATES


def build_tiny_dev_geometry_v3_gate(
    corpus,
    tokenizer,
    *,
    source_code_commit: str,
    ngram_len: int = DEFAULT_NGRAM_LEN,
    context_history_size: int = DEFAULT_CONTEXT_HISTORY_SIZE,
    beam_width: int = DEFAULT_BEAM_WIDTH,
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
    eos_token_id = tokenizer.eos_token_id
    if eos_token_id is None:
        raise RuntimeError("runtime tokenizer must define eos_token_id")
    retokenize = lambda text: _tokenize(tokenizer, text)
    rows = []
    for source in _attack_samples(corpus):
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
            max_risk_tier=1,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        expander = _MemoizedExpander(base_expander)
        root = base_expander.root_state
        hard_validator = _hard_validator(registry, source.text)
        audit_evaluator = PublicResidualStateEvaluator(
            root_text=source.text,
            retokenize=retokenize,
            eos_token_id=int(eos_token_id),
            ngram_len=ngram_len,
            context_history_size=context_history_size,
            hard_invariant_validator=hard_validator,
        )
        for budget in GEOMETRY_V3_GATE_BUDGETS:
            v2_result = beam_search_v2(expander, root, budget=budget, beam_width=beam_width)
            v2_state, v2_status = _select_result_state(v2_result, budget)
            effective_v2_state = v2_state if v2_state is not None else root
            v2_metrics = audit_evaluator.evaluate(effective_v2_state)
            envelope = MatchedVisibleCostEnvelope.from_state(effective_v2_state, v2_metrics)
            v3_evaluator = PublicResidualStateEvaluator(
                root_text=source.text,
                retokenize=retokenize,
                eos_token_id=int(eos_token_id),
                ngram_len=ngram_len,
                context_history_size=context_history_size,
                hard_invariant_validator=hard_validator,
                cost_envelope=envelope,
            )
            v3_result = beam_search_v3(
                expander,
                v3_evaluator,
                root,
                budget=budget,
                beam_width=beam_width,
            )
            v3_ranked, v3_status = _select_v3(v3_result, budget)
            rows.append(
                GeometryV3GateRow.create(
                    source_sample_id=source.sample_id,
                    budget=budget,
                    v2_status=v2_status,
                    v3_status=v3_status,
                    v2_state=effective_v2_state,
                    v2_metrics=v2_metrics,
                    v3_state=v3_ranked.state if v3_ranked is not None else None,
                    v3_metrics=v3_ranked.metrics if v3_ranked is not None else None,
                )
            )
            if expander.detector_access_observed or expander.secret_access_observed:
                raise RuntimeError("geometry-v3 gate observed prohibited selection access")
    return build_geometry_v3_gate_artifact(
        source_code_commit=source_code_commit,
        source_corpus_hash=corpus.artifact_hash,
        candidate_registry_hash=registry.ruleset_hash,
        model_identity_hash=corpus.model_identity_hash,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
        beam_width=beam_width,
        rows=rows,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-geometry-v3-gate-hf")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--source-code-commit", required=True)
    parser.add_argument("--ngram-len", type=int, default=DEFAULT_NGRAM_LEN)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--beam-width", type=int, default=DEFAULT_BEAM_WIDTH)
    parser.add_argument(
        "--artifact-json",
        type=Path,
        default=Path("artifacts/tiny-dev-geometry-v3-gate.json"),
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
        raise RuntimeError("geometry-v3 gate requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if identity.identity_hash != corpus.model_identity_hash:
        raise RuntimeError("runtime tokenizer identity does not match frozen TinyDev corpus")
    artifact = build_tiny_dev_geometry_v3_gate(
        corpus,
        tokenizer,
        source_code_commit=args.source_code_commit,
        ngram_len=args.ngram_len,
        context_history_size=args.context_history_size,
        beam_width=args.beam_width,
    )
    args.artifact_json.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    by_budget = {}
    for budget in GEOMETRY_V3_GATE_BUDGETS:
        values = [row for row in artifact.rows if row.budget == budget]
        gains = [float(row.rif_improvement) for row in values if row.rif_improvement is not None]
        by_budget[budget] = {
            "row_count": len(values),
            "strict_gain_count": sum(value > 0 for value in gains),
            "residual_specific_win_count": sum(row.residual_specific_win for row in values),
            "matched_cost_count": sum(row.matched_cost_pass for row in values),
        }
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"decision={artifact.decision}\n")
    sys.stdout.write(f"row_count={len(artifact.rows)}\n")
    sys.stdout.write(f"budget_summary={json.dumps(by_budget, sort_keys=True)}\n")
    sys.stdout.write(f"artifact_json={args.artifact_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
