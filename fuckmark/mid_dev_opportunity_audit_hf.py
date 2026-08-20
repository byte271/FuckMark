from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .corpus.mid_dev_calibration import (
    MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
    MID_DEV_CALIBRATION_SEED_BASE,
    MID_DEV_CALIBRATION_SOURCE_ID,
)
from .corpus.mid_dev_calibration_generation import build_real_mid_dev_calibration
from .corpus.mid_dev_calibration_shards import (
    CalibrationRole,
    calibration_prompt_source_id,
)
from .corpus.runtime_identity import runtime_tokenizer_identity_public
from .durable_io import write_canonical_json_fsynced
from .experiments.detector_opportunity_audit import (
    ELIGIBLE_IQR_OVERLAP_LIMIT,
    OPPORTUNITY_CV_LIMIT,
    build_detector_opportunity_audit_artifact,
    freeze_calibration_regime_decision,
)
from .experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
from .hashing import sha256_json
from .mid_dev_corpus_hf import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    DEFAULT_NGRAM_LEN,
    HuggingFaceMidDevBackend,
)


MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION = "mid-dev-pristine-opportunity-audit-provenance-v1"
MID_DEV_OPPORTUNITY_CONTEXT_HISTORY_SIZE = 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-opportunity-audit-hf")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--opportunity-audit-json", type=Path, required=True)
    parser.add_argument("--regime-decision-json", type=Path, required=True)
    parser.add_argument("--provenance-json", type=Path, required=True)
    return parser


def _encode_text_only(tokenizer, text: str) -> tuple[int, ...]:
    return tuple(
        int(value)
        for value in tokenizer.encode(text, add_special_tokens=False)
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    if MID_DEV_CALIBRATION_SOURCE_ID in {
        calibration_prompt_source_id(CalibrationRole.SELECT),
        calibration_prompt_source_id(CalibrationRole.AUDIT),
    }:
        raise RuntimeError("pristine opportunity source must remain distinct from CAL-SELECT/CAL-AUDIT")
    backend = HuggingFaceMidDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    pristine = build_real_mid_dev_calibration(backend)
    expected_count = 2 * MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH
    if len(pristine.manifest.samples) != expected_count:
        raise RuntimeError("pristine opportunity corpus count drifted")
    pristine_seeds = {sample.generation.seed for sample in pristine.manifest.samples}
    if len(pristine_seeds) != expected_count:
        raise RuntimeError("pristine opportunity corpus seed uniqueness drifted")
    if pristine_seeds & set(readiness.select_plan.seeds):
        raise RuntimeError("pristine opportunity seed domain overlaps CAL-SELECT")
    if pristine_seeds & set(readiness.audit_plan.seeds):
        raise RuntimeError("pristine opportunity seed domain overlaps CAL-AUDIT")
    if min(pristine_seeds) < MID_DEV_CALIBRATION_SEED_BASE:
        raise RuntimeError("pristine opportunity seed domain drifted")

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Install pinned Transformers dependencies before opportunity audit") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        revision=args.model_revision,
        use_fast=True,
        padding_side="left",
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("opportunity audit requires a fast tokenizer")
    identity = runtime_tokenizer_identity_public(tokenizer, args.model, args.model_revision)
    if {sample.model.identity_hash for sample in pristine.manifest.samples} != {identity.identity_hash}:
        raise RuntimeError("runtime tokenizer identity does not match pristine opportunity corpus")

    audit = build_detector_opportunity_audit_artifact(
        pristine.manifest.samples,
        ngram_len=DEFAULT_NGRAM_LEN,
        context_history_size=MID_DEV_OPPORTUNITY_CONTEXT_HISTORY_SIZE,
        retokenize=lambda text: _encode_text_only(tokenizer, text),
    )

    write_canonical_json_fsynced(args.corpus_json, pristine)
    write_canonical_json_fsynced(args.opportunity_audit_json, audit)

    if not audit.tokenizer_round_trip_all_ok:
        raise RuntimeError("pristine opportunity audit contains tokenizer round-trip failures")
    decision = freeze_calibration_regime_decision(audit)
    write_canonical_json_fsynced(args.regime_decision_json, decision)

    payload = {
        "algorithm_version": MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION,
        "model_tokenizer_identity_hash": identity.identity_hash,
        "model_revision": args.model_revision,
        "pristine_source_id": MID_DEV_CALIBRATION_SOURCE_ID,
        "pristine_seed_base": MID_DEV_CALIBRATION_SEED_BASE,
        "pristine_negatives_per_length": MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
        "pristine_corpus_artifact_hash": pristine.artifact_hash,
        "pristine_manifest_hash": pristine.manifest.manifest_hash,
        "pristine_source_profile_hash": pristine.source_profile_hash,
        "sample_count": len(pristine.manifest.samples),
        "opportunity_audit_hash": audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "regime_mode": decision.mode.value,
        "opportunity_cv_limit": OPPORTUNITY_CV_LIMIT,
        "eligible_iqr_overlap_limit": ELIGIBLE_IQR_OVERLAP_LIMIT,
        "tokenizer_round_trip_all_ok": audit.tokenizer_round_trip_all_ok,
        "attack_transform_count": 0,
        "attack_score_count": 0,
        "detector_score_count": 0,
        "calibration_threshold_constructed": False,
        "cal_select_or_audit_samples_consumed": False,
        "corpus_fsync_success": True,
        "opportunity_audit_fsync_success": True,
        "regime_decision_fsync_success": True,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "github_checkout_sha": os.environ.get("GITHUB_SHA"),
    }
    provenance = {**payload, "provenance_hash": sha256_json(payload)}
    write_canonical_json_fsynced(args.provenance_json, provenance)
    sys.stdout.write(f"pristine_corpus_artifact_hash={pristine.artifact_hash}\n")
    sys.stdout.write(f"opportunity_audit_hash={audit.artifact_hash}\n")
    sys.stdout.write(f"regime_decision_hash={decision.decision_hash}\n")
    sys.stdout.write(f"regime_mode={decision.mode.value}\n")
    sys.stdout.write(f"sample_count={len(pristine.manifest.samples)}\n")
    sys.stdout.write(f"provenance_hash={provenance['provenance_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
