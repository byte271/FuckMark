from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from .config import canonical_json_text
from .experiments.e26_open_adapter_transfer import build_e26_open_adapter_transfer
from .experiments.synthid_smoke import (
    SynthIDSmokePromptResult,
    SynthIDSmokeReport,
    SynthIDSmokeSummary,
)


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be strings")
    return value


def synthid_smoke_report_from_mapping(value: Mapping[str, object]) -> SynthIDSmokeReport:
    snapshot = dict(_mapping("smoke report", value))
    required = {
        "algorithm_version",
        "backend_id",
        "backend_version",
        "model_id",
        "detector_id",
        "detector_config_hash",
        "results",
        "summary",
        "report_hash",
    }
    if set(snapshot) != required:
        raise ValueError(
            "smoke report fields do not match schema: "
            f"missing={sorted(required - set(snapshot))}, extra={sorted(set(snapshot) - required)}"
        )
    raw_results = snapshot["results"]
    if not isinstance(raw_results, list):
        raise TypeError("smoke report results must be a JSON array")
    result_fields = {
        "prompt_id",
        "seed",
        "prompt_hash",
        "control_pristine_text",
        "control_transformed_text",
        "watermark_pristine_text",
        "watermark_transformed_text",
        "control_pristine_score",
        "control_transformed_score",
        "watermark_pristine_score",
        "watermark_transformed_score",
        "control_score_shift",
        "watermark_score_drop",
        "control_changed",
        "watermark_changed",
        "result_hash",
    }
    results = []
    for index, raw in enumerate(raw_results):
        row = dict(_mapping(f"smoke result {index}", raw))
        if set(row) != result_fields:
            raise ValueError(
                f"smoke result {index} fields do not match schema: "
                f"missing={sorted(result_fields - set(row))}, extra={sorted(set(row) - result_fields)}"
            )
        results.append(SynthIDSmokePromptResult(**row))

    raw_summary = dict(_mapping("smoke summary", snapshot["summary"]))
    summary_fields = {
        "prompt_count",
        "target_fpr",
        "threshold",
        "threshold_comparator",
        "pristine_control_detection_rate",
        "transformed_control_detection_rate",
        "pristine_watermark_detection_rate",
        "transformed_watermark_detection_rate",
        "watermark_detection_rate_drop",
        "mean_control_pristine_score",
        "mean_control_transformed_score",
        "mean_control_score_shift",
        "mean_watermark_pristine_score",
        "mean_watermark_transformed_score",
        "mean_watermark_score_drop",
        "median_watermark_score_drop",
        "control_transform_rate",
        "watermark_transform_rate",
    }
    if set(raw_summary) != summary_fields:
        raise ValueError(
            "smoke summary fields do not match schema: "
            f"missing={sorted(summary_fields - set(raw_summary))}, extra={sorted(set(raw_summary) - summary_fields)}"
        )
    summary = SynthIDSmokeSummary(**raw_summary)
    return SynthIDSmokeReport(
        algorithm_version=snapshot["algorithm_version"],
        backend_id=snapshot["backend_id"],
        backend_version=snapshot["backend_version"],
        model_id=snapshot["model_id"],
        detector_id=snapshot["detector_id"],
        detector_config_hash=snapshot["detector_config_hash"],
        results=tuple(results),
        summary=summary,
        report_hash=snapshot["report_hash"],
    )


def load_synthid_smoke_report(path: Path) -> SynthIDSmokeReport:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    value = json.loads(path.read_text(encoding="utf-8"))
    return synthid_smoke_report_from_mapping(_mapping("smoke report JSON", value))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-e26-open-adapter-transfer")
    parser.add_argument("--deepmind", type=Path, required=True)
    parser.add_argument("--huggingface", type=Path, required=True)
    parser.add_argument("--json", type=Path, default=Path("artifacts/e26-open-adapter-transfer.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    deepmind = load_synthid_smoke_report(args.deepmind)
    huggingface = load_synthid_smoke_report(args.huggingface)
    report = build_e26_open_adapter_transfer(deepmind, huggingface)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    summary = report.summary
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"deepmind_report_hash={report.deepmind_report_hash}\n")
    sys.stdout.write(f"huggingface_report_hash={report.huggingface_report_hash}\n")
    sys.stdout.write(f"prompt_count={summary.prompt_count}\n")
    sys.stdout.write(f"both_watermark_changed_count={summary.both_watermark_changed_count}\n")
    sys.stdout.write(f"direction_concordance_rate={summary.direction_concordance_rate}\n")
    sys.stdout.write(f"positive_drop_both_count={summary.positive_drop_both_count}\n")
    sys.stdout.write(f"positive_drop_deepmind_only_count={summary.positive_drop_deepmind_only_count}\n")
    sys.stdout.write(f"positive_drop_huggingface_only_count={summary.positive_drop_huggingface_only_count}\n")
    sys.stdout.write(f"nonpositive_drop_both_count={summary.nonpositive_drop_both_count}\n")
    sys.stdout.write(f"mean_deepmind_watermark_score_drop={summary.mean_deepmind_watermark_score_drop}\n")
    sys.stdout.write(f"mean_huggingface_watermark_score_drop={summary.mean_huggingface_watermark_score_drop}\n")
    sys.stdout.write(f"mean_absolute_watermark_drop_difference={summary.mean_absolute_watermark_drop_difference}\n")
    sys.stdout.write(f"watermark_drop_pearson={summary.watermark_drop_pearson}\n")
    sys.stdout.write(
        "deepmind_detection_before_after="
        f"{summary.deepmind_pristine_detection_rate}/{summary.deepmind_transformed_detection_rate}\n"
    )
    sys.stdout.write(
        "huggingface_detection_before_after="
        f"{summary.huggingface_pristine_detection_rate}/{summary.huggingface_transformed_detection_rate}\n"
    )
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
