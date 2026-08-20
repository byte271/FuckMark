from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev import MID_DEV_SOURCE_COUNT
from .corpus.mid_dev_generation import build_real_mid_dev_corpus
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.detector_opportunity_audit import build_detector_opportunity_audit_artifact
from .experiments.mid_dev_source_opportunity_coverage import (
    build_mid_dev_source_opportunity_coverage,
)
from .experiments.mid_dev_source_opportunity_coverage_io import (
    MID_DEV_SOURCE_OPPORTUNITY_PROVENANCE_VERSION,
)
from .experiments.mid_dev_vnext_artifact_io import (
    load_calibration_regime_decision_json,
    load_detector_opportunity_audit_json,
)
from .hashing import sha256_json
from .mid_dev_corpus_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    HuggingFaceMidDevBackend,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-source-opportunity-audit-hf")
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--source-corpus-json", type=Path, required=True)
    parser.add_argument("--source-opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def _encode_text_only(tokenizer, text: str) -> tuple[int, ...]:
    return tuple(
        int(value)
        for value in tokenizer.encode(text, add_special_tokens=False)
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    calibration_audit = load_detector_opportunity_audit_json(args.opportunity_audit_json)
    decision = load_calibration_regime_decision_json(args.regime_decision_json)
    if decision.opportunity_audit_hash != calibration_audit.artifact_hash:
        raise RuntimeError("regime decision does not bind supplied calibration opportunity audit")

    backend = HuggingFaceMidDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    source_corpus = build_real_mid_dev_corpus(backend)
    if source_corpus.source_count != MID_DEV_SOURCE_COUNT:
        raise RuntimeError("source opportunity corpus count drifted")
    if len(source_corpus.manifest.samples) != MID_DEV_SOURCE_COUNT * 2:
        raise RuntimeError("source opportunity sample count drifted")
    write_canonical_json_fsynced(args.source_corpus_json, source_corpus)

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before source opportunity audit") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("source opportunity audit requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if {sample.model.identity_hash for sample in source_corpus.manifest.samples} != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match source corpus")
    if identity.identity_hash != calibration_audit.model_tokenizer_identity_hash:
        raise RuntimeError("source runtime tokenizer identity differs from calibration opportunity audit")

    source_audit = build_detector_opportunity_audit_artifact(
        source_corpus.manifest.samples,
        ngram_len=calibration_audit.ngram_len,
        context_history_size=calibration_audit.context_history_size,
        retokenize=lambda text: _encode_text_only(tokenizer, text),
    )
    write_canonical_json_fsynced(args.source_opportunity_audit_json, source_audit)
    if not source_audit.tokenizer_round_trip_all_ok:
        raise RuntimeError("source opportunity audit contains tokenizer round-trip failures")

    coverage = build_mid_dev_source_opportunity_coverage(
        source_corpus,
        calibration_audit,
        source_audit,
        decision,
    )
    write_canonical_json_fsynced(args.coverage_json, coverage)

    payload = {
        "algorithm_version": MID_DEV_SOURCE_OPPORTUNITY_PROVENANCE_VERSION,
        "calibration_opportunity_audit_hash": calibration_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "source_corpus_artifact_hash": source_corpus.artifact_hash,
        "source_manifest_hash": source_corpus.manifest.manifest_hash,
        "source_profile_hash": source_corpus.source_profile_hash,
        "analysis_split_hash": source_corpus.analysis_split_hash,
        "source_opportunity_audit_hash": source_audit.artifact_hash,
        "coverage_artifact_hash": coverage.artifact_hash,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "source_count": source_corpus.source_count,
        "sample_count": len(source_corpus.manifest.samples),
        "required_regime_ids": coverage.required_regime_ids,
        "tokenizer_round_trip_all_ok": source_audit.tokenizer_round_trip_all_ok,
        "attack_transform_count": 0,
        "attack_score_count": 0,
        "detector_score_count": 0,
        "calibration_threshold_constructed": False,
        "cal_select_or_audit_samples_consumed": False,
        "source_corpus_fsync_success": True,
        "source_opportunity_audit_fsync_success": True,
        "coverage_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)

    sys.stdout.write(f"source_corpus_artifact_hash={source_corpus.artifact_hash}\n")
    sys.stdout.write(f"source_manifest_hash={source_corpus.manifest.manifest_hash}\n")
    sys.stdout.write(f"source_opportunity_audit_hash={source_audit.artifact_hash}\n")
    sys.stdout.write(f"coverage_artifact_hash={coverage.artifact_hash}\n")
    sys.stdout.write(f"regime_decision_hash={decision.decision_hash}\n")
    sys.stdout.write(f"required_regime_count={len(coverage.required_regime_ids)}\n")
    sys.stdout.write("required_regime_ids=" + ",".join(coverage.required_regime_ids) + "\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
