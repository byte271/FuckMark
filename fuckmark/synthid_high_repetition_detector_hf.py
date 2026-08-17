from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import canonical_json_text
from .experiments.synthid_high_repetition_detector import (
    TARGET_STRATUM,
    build_high_repetition_detector_plan,
    score_high_repetition_detector_plan,
)
from .experiments.synthid_repetition_strata import RepetitionStratum, STRATIFICATION_POLICY_ID
from .hashing import sha256_json, sha256_text
from .public_eligibility import build_huggingface_public_eligibility
from .synthid_eligible_geometry_hf import HuggingFaceSynthIDEligibilityGeometryBackend
from .synthid_geometry_hf import _load_prompts, _parse_budgets, _registry
from .synthid_smoke_hf import DEFAULT_KEYS, DEFAULT_NGRAM_LEN


SOURCE_MANIFEST_ALGORITHM_VERSION = "synthid-high-repetition-source-manifest-v1"
RUN_BUNDLE_ALGORITHM_VERSION = "synthid-high-repetition-run-bundle-v1"
_STRATA = (
    RepetitionStratum.Q1_LOW,
    RepetitionStratum.Q2_MID_LOW,
    RepetitionStratum.Q3_MID_HIGH,
    RepetitionStratum.Q4_HIGH,
)


class _RecordingBackend:
    def __init__(self, backend: HuggingFaceSynthIDEligibilityGeometryBackend, prompt_ids: dict[tuple[str, int], str]) -> None:
        self._backend = backend
        self._prompt_ids = dict(prompt_ids)
        self.generated: list[dict[str, object]] = []

    @property
    def backend_id(self) -> str:
        return self._backend.backend_id

    @property
    def backend_version(self) -> str:
        return self._backend.backend_version

    @property
    def model_id(self) -> str:
        return self._backend.model_id

    @property
    def detector_id(self) -> str:
        return self._backend.detector_id

    @property
    def detector_config_hash(self) -> str:
        return self._backend.detector_config_hash

    @property
    def ngram_len(self) -> int:
        return self._backend.ngram_len

    @property
    def eos_token_id(self) -> int:
        return self._backend.eos_token_id

    @property
    def context_history_size(self) -> int:
        return self._backend.context_history_size

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
        prompt_id = self._prompt_ids.get((prompt, seed))
        if prompt_id is None:
            raise RuntimeError("generation request is not part of the frozen prompt set")
        text = self._backend.generate(prompt, seed, watermarked=watermarked)
        self.generated.append(
            {
                "prompt_id": prompt_id,
                "generation_seed": seed,
                "label": "WATERMARKED" if watermarked else "CONTROL",
                "source_text": text,
            }
        )
        return text

    def tokenize(self, text: str) -> tuple[int, ...]:
        return self._backend.tokenize(text)

    def score(self, text: str) -> float:
        return self._backend.score(text)


def _write_fsynced(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(canonical_json_text(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _build_source_manifest(backend: _RecordingBackend, expected_source_count: int) -> dict[str, object]:
    if len(backend.generated) != expected_source_count:
        raise RuntimeError("recorded source count does not match the frozen prompt plan")
    base_rows: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for generated in backend.generated:
        prompt_id = str(generated["prompt_id"])
        generation_seed = int(generated["generation_seed"])
        label = str(generated["label"])
        identity = (prompt_id, generation_seed, label)
        if identity in seen:
            raise RuntimeError("duplicate generated source identity")
        seen.add(identity)
        source_text = str(generated["source_text"])
        tokens = tuple(backend.tokenize(source_text))
        eligibility = build_huggingface_public_eligibility(
            tokens,
            backend.eos_token_id,
            backend.ngram_len,
            backend.context_history_size,
        )
        if eligibility.observation_count <= 0:
            raise RuntimeError("recorded source is too short for public repetition geometry")
        base_rows.append(
            {
                "prompt_id": prompt_id,
                "generation_seed": generation_seed,
                "label": label,
                "source_text": source_text,
                "source_hash": sha256_text(source_text),
                "token_hash": sha256_json(tokens),
                "token_count": len(tokens),
                "observation_count": eligibility.observation_count,
                "valid_count": eligibility.valid_count,
                "repeated_count": eligibility.repeated_count,
                "repeated_fraction": eligibility.repeated_count / eligibility.observation_count,
                "valid_fraction": eligibility.valid_count / eligibility.observation_count,
            }
        )
    rows: list[dict[str, object]] = []
    for label in ("CONTROL", "WATERMARKED"):
        label_rows = sorted(
            (row for row in base_rows if row["label"] == label),
            key=lambda row: (
                float(row["repeated_fraction"]),
                str(row["prompt_id"]),
                int(row["generation_seed"]),
                str(row["source_hash"]),
            ),
        )
        if not label_rows:
            raise RuntimeError("source manifest requires both control and watermarked sources")
        count = len(label_rows)
        for index, row in enumerate(label_rows):
            enriched = dict(row)
            enriched["rank_within_label"] = index + 1
            enriched["label_source_count"] = count
            enriched["stratum"] = _STRATA[min(3, index * 4 // count)].value
            row_payload = dict(enriched)
            enriched["source_manifest_row_hash"] = sha256_json(row_payload)
            rows.append(enriched)
    rows.sort(key=lambda row: (str(row["prompt_id"]), int(row["generation_seed"]), str(row["label"])))
    payload = {
        "algorithm_version": SOURCE_MANIFEST_ALGORITHM_VERSION,
        "stratification_policy_id": STRATIFICATION_POLICY_ID,
        "detector_scores_used": False,
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "ngram_len": backend.ngram_len,
        "eos_token_id": backend.eos_token_id,
        "context_history_size": backend.context_history_size,
        "source_count": len(rows),
        "sources": rows,
    }
    return {**payload, "source_manifest_hash": sha256_json(payload)}


def _validate_plan_against_source_manifest(plan, source_manifest: dict[str, object]) -> None:
    rows = source_manifest["sources"]
    if not isinstance(rows, list):
        raise TypeError("source manifest sources must be a list")
    manifest_q4 = {
        (str(row["prompt_id"]), str(row["label"]), str(row["source_hash"]))
        for row in rows
        if row["stratum"] == TARGET_STRATUM.value
    }
    plan_q4 = {
        (row.prompt_id, row.label.value, row.source_hash)
        for row in plan.sources
    }
    if manifest_q4 != plan_q4:
        raise RuntimeError("frozen Q4 plan does not match independently reconstructed source manifest")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-high-repetition-detector")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=24)
    parser.add_argument("--seed-base", type=int, default=279000)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--registry", choices=("release", "development", "mechanism"), default="mechanism")
    parser.add_argument("--budgets", type=_parse_budgets, default=(1, 2, 4))
    parser.add_argument("--schedule-seed", type=int, default=9800)
    parser.add_argument("--exact-max-candidates", type=int, default=16)
    parser.add_argument("--source-manifest-json", type=Path, default=Path("artifacts/synthid-high-repetition-source-manifest.json"))
    parser.add_argument("--plan-json", type=Path, default=Path("artifacts/synthid-high-repetition-detector-plan.json"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-high-repetition-detector.json"))
    parser.add_argument("--bundle-json", type=Path, default=Path("artifacts/synthid-high-repetition-run-bundle.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.schedule_seed < 0 or args.schedule_seed >= 1 << 64:
        raise ValueError("schedule-seed must fit in 64 bits")
    if not 1 <= args.exact_max_candidates <= 16:
        raise ValueError("exact-max-candidates must lie in [1, 16]")
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    prompt_ids = {(row.text, row.seed): row.prompt_id for row in prompts}
    if len(prompt_ids) != len(prompts):
        raise ValueError("prompt text/seed pairs must be unique for source recording")
    raw_backend = HuggingFaceSynthIDEligibilityGeometryBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        ngram_len=DEFAULT_NGRAM_LEN,
        keys=DEFAULT_KEYS,
    )
    backend = _RecordingBackend(raw_backend, prompt_ids)
    plan = build_high_repetition_detector_plan(
        prompts,
        backend,
        _registry(args.registry),
        budgets=args.budgets,
        schedule_seed=args.schedule_seed,
        exact_max_candidates=args.exact_max_candidates,
    )
    source_manifest = _build_source_manifest(backend, len(prompts) * 2)
    _validate_plan_against_source_manifest(plan, source_manifest)
    _write_fsynced(args.source_manifest_json, source_manifest)
    _write_fsynced(args.plan_json, plan)

    report = score_high_repetition_detector_plan(plan, backend)
    _write_fsynced(args.json, report)
    paired_high_sources = len({row.source_record_hash for row in plan.pairs})
    bundle_payload = {
        "algorithm_version": RUN_BUNDLE_ALGORITHM_VERSION,
        "selection_feedback_used": False,
        "source_manifest_hash": source_manifest["source_manifest_hash"],
        "repetition_report_hash": plan.repetition_report_hash,
        "plan_hash": plan.plan_hash,
        "report_hash": report.report_hash,
        "detector_id": report.detector_id,
        "detector_config_hash": report.detector_config_hash,
        "high_source_count": len(plan.sources),
        "paired_high_source_count": paired_high_sources,
        "unpaired_high_source_count": len(plan.sources) - paired_high_sources,
        "plan_pair_count": len(plan.pairs),
    }
    bundle = {**bundle_payload, "bundle_hash": sha256_json(bundle_payload)}
    _write_fsynced(args.bundle_json, bundle)

    summary = report.summary
    sys.stdout.write(f"source_manifest_hash={source_manifest['source_manifest_hash']}\n")
    sys.stdout.write(f"plan_hash={plan.plan_hash}\n")
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"bundle_hash={bundle['bundle_hash']}\n")
    sys.stdout.write(f"high_source_count={summary.high_source_count}\n")
    sys.stdout.write(f"paired_high_source_count={paired_high_sources}\n")
    sys.stdout.write(f"unpaired_high_source_count={len(plan.sources) - paired_high_sources}\n")
    sys.stdout.write(f"plan_pair_count={summary.plan_pair_count}\n")
    sys.stdout.write(f"matched_pair_count={summary.matched_pair_count}\n")
    sys.stdout.write(f"differing_selection_pair_count={summary.differing_selection_pair_count}\n")
    sys.stdout.write(f"control_differing_selection_pair_count={summary.control_differing_selection_pair_count}\n")
    sys.stdout.write(f"watermarked_differing_selection_pair_count={summary.watermarked_differing_selection_pair_count}\n")
    sys.stdout.write(f"mean_control_score_drop_advantage={summary.mean_control_score_drop_advantage}\n")
    sys.stdout.write(f"mean_watermarked_score_drop_advantage={summary.mean_watermarked_score_drop_advantage}\n")
    sys.stdout.write(
        "mean_control_score_drop_advantage_when_selection_differs="
        f"{summary.mean_control_score_drop_advantage_when_selection_differs}\n"
    )
    sys.stdout.write(
        "mean_watermarked_score_drop_advantage_when_selection_differs="
        f"{summary.mean_watermarked_score_drop_advantage_when_selection_differs}\n"
    )
    sys.stdout.write(
        "watermarked_direction_when_selection_differs="
        f"{summary.watermarked_better_count_when_selection_differs}/"
        f"{summary.watermarked_worse_count_when_selection_differs}/"
        f"{summary.watermarked_tie_count_when_selection_differs}\n"
    )
    sys.stdout.write(f"registry={args.registry}\n")
    sys.stdout.write(f"source_manifest_json={args.source_manifest_json.as_posix()}\n")
    sys.stdout.write(f"plan_json={args.plan_json.as_posix()}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"bundle_json={args.bundle_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
