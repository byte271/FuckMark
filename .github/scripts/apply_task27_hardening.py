from __future__ import annotations

import ast
import sys
from dataclasses import fields, replace
from pathlib import Path


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"expected patch anchor not found: {old[:80]!r}")
    return text.replace(old, new, 1)


def patch_schedule_analysis() -> None:
    path = Path("fuckmark/experiments/schedule_analysis.py")
    text = path.read_text()
    if "from ..hashing import sha256_json, sha256_text" not in text:
        text = replace_once(text, "from ..hashing import sha256_json\n", "from ..hashing import sha256_json, sha256_text\n")
    if "schedule row source text hash does not match corpus source" not in text:
        text = replace_once(
            text,
            '        if row.prompt_family_id != sample.prompt_family_id:\n            raise TransformAnalysisInputError("schedule row prompt family does not match corpus source")\n        if row.key_split is not KeySplit.DEV:\n',
            '        if row.prompt_family_id != sample.prompt_family_id:\n            raise TransformAnalysisInputError("schedule row prompt family does not match corpus source")\n        if row.source_text_hash != sha256_text(sample.text):\n            raise TransformAnalysisInputError("schedule row source text hash does not match corpus source")\n        if row.key_split is not KeySplit.DEV:\n',
        )
    if "variants from one source must share one pristine score" not in text:
        text = replace_once(
            text,
            '    if not rows:\n        raise TransformAnalysisInputError("schedule analysis requires at least one row")\n    detector_ids = {row.detector_identity_hash for row in rows}\n',
            '    if not rows:\n        raise TransformAnalysisInputError("schedule analysis requires at least one row")\n    for source_sample_id in {row.source_sample_id for row in rows}:\n        source_rows = tuple(row for row in rows if row.source_sample_id == source_sample_id)\n        if len({row.pristine_score for row in source_rows}) != 1:\n            raise TransformAnalysisInputError("variants from one source must share one pristine score")\n    detector_ids = {row.detector_identity_hash for row in rows}\n',
        )
    pair_marker = '        row.candidate_pool_hash,\n        row.scheduler_input_hash,\n        row.budget,\n'
    if pair_marker not in text:
        text = replace_once(text, '        row.candidate_pool_hash,\n        row.budget,\n', pair_marker)
    signature = 'def _validate_schedule_rows(\n    artifact: TinyDevCorpusArtifact,\n    rows: tuple[DevelopmentTransformRow, ...],\n    *,\n    allow_secret_access: bool = False,\n) -> tuple[str, str, float]:\n'
    if signature not in text:
        text = replace_once(
            text,
            'def _validate_schedule_rows(\n    artifact: TinyDevCorpusArtifact,\n    rows: tuple[DevelopmentTransformRow, ...],\n) -> tuple[str, str, float]:\n',
            signature,
        )
    if "secret access contaminates key-blind schedule analysis" not in text:
        text = replace_once(
            text,
            '    if len({row.row_hash for row in rows}) != len(rows):\n        raise TransformAnalysisInputError("schedule analysis rows must not contain duplicate artifacts")\n    sample_by_id = _expected_attack_sources(artifact)\n',
            '    if len({row.row_hash for row in rows}) != len(rows):\n        raise TransformAnalysisInputError("schedule analysis rows must not contain duplicate artifacts")\n    if type(allow_secret_access) is not bool:\n        raise TypeError("allow_secret_access must be a bool")\n    if not allow_secret_access and any(row.secret_access_observed for row in rows):\n        raise TransformAnalysisInputError("secret access contaminates key-blind schedule analysis")\n    sample_by_id = _expected_attack_sources(artifact)\n',
        )
    marker = "def run_e11_greedy_comparison("
    index = text.index(marker)
    head, tail = text[:index], text[index:]
    desired = "    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows, allow_secret_access=True)\n"
    if desired not in tail:
        tail = replace_once(tail, "    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows)\n", desired)
        text = head + tail
    path.write_text(text)


def patch_transform_analysis() -> None:
    path = Path("fuckmark/experiments/transform_analysis.py")
    text = path.read_text()
    if "secret access contaminates E07/E08 key-blind analysis" not in text:
        text = replace_once(
            text,
            'def _validate_tiny_attack_rows(\n    artifact: TinyDevCorpusArtifact,\n    rows: tuple[DevelopmentTransformRow, ...],\n) -> tuple[str, str, tuple[str, ...]]:\n    expected_samples = tuple(\n',
            'def _validate_tiny_attack_rows(\n    artifact: TinyDevCorpusArtifact,\n    rows: tuple[DevelopmentTransformRow, ...],\n) -> tuple[str, str, tuple[str, ...]]:\n    if any(row.secret_access_observed for row in rows):\n        raise TransformAnalysisInputError("secret access contaminates E07/E08 key-blind analysis")\n    expected_samples = tuple(\n',
        )
    path.write_text(text)


def patch_calibration_interval_if_needed() -> None:
    sys.path.insert(0, "tests")
    from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact
    from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
    from fuckmark.hashing import sha256_json

    threshold = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence()).calibration_bundle.thresholds[-1]
    interval_field = next(name for name in ("confidence_interval", "fpr_interval") if hasattr(threshold, name))
    interval = getattr(threshold, interval_field)
    payload = threshold._payload()
    payload_key = next(key for key, value in payload.items() if value == interval)
    try:
        forged_interval = replace(interval, lower=0.0, upper=1.0)
        forged_payload = dict(payload)
        forged_payload[payload_key] = forged_interval
        replace(threshold, **{interval_field: forged_interval, "threshold_hash": sha256_json(forged_payload)})
    except ValueError:
        return
    threshold_fields = {field.name for field in fields(type(threshold))}
    if not {"false_positive_count", "calibration_count"} <= threshold_fields:
        raise RuntimeError("calibration threshold lacks count fields required for exact interval validation")
    confidence_attr = next(name for name in ("confidence_level", "confidence") if hasattr(interval, name))
    path = Path("fuckmark/detectors/calibration_threshold.py")
    text = path.read_text()
    marker = "confidence interval does not match exact binomial interval"
    if marker in text:
        return
    tree = ast.parse(text)
    target = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CalibrationThreshold":
            target = next(child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "__post_init__")
            break
    if target is None or target.end_lineno is None:
        raise RuntimeError("CalibrationThreshold.__post_init__ not found")
    insertion = (
        '        from .calibration_statistics import exact_binomial_interval\n'
        '        expected_interval = exact_binomial_interval(\n'
        '            self.false_positive_count,\n'
        '            self.calibration_count,\n'
        f'            self.{interval_field}.{confidence_attr},\n'
        '        )\n'
        f'        if self.{interval_field} != expected_interval:\n'
        '            raise ValueError("confidence interval does not match exact binomial interval")\n'
    )
    lines = text.splitlines(keepends=True)
    lines[target.end_lineno:target.end_lineno] = [insertion]
    path.write_text("".join(lines))


def patch_token_ngram_if_needed() -> None:
    from fuckmark.observations import build_token_ngrams

    ngram = build_token_ngrams((10, 20, 30, 40), 3)[0]
    try:
        replace(ngram, index=ngram.index + 1)
    except ValueError:
        return
    path = Path("fuckmark/observations.py")
    text = path.read_text()
    marker = "token n-gram index/start geometry mismatch"
    if marker in text:
        return
    tree = ast.parse(text)
    target = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "TokenNgram":
            target = next(child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "__post_init__")
            break
    if target is None or target.end_lineno is None:
        raise RuntimeError("TokenNgram.__post_init__ not found")
    insertion = '        if self.index != self.start:\n            raise ValueError("token n-gram index/start geometry mismatch")\n'
    lines = text.splitlines(keepends=True)
    lines[target.end_lineno:target.end_lineno] = [insertion]
    path.write_text("".join(lines))


def patch_e02_exact_intervals() -> None:
    path = Path("fuckmark/experiments/e02_pristine.py")
    text = path.read_text()
    marker = "E02 TPR interval does not match exact binomial interval"
    if marker in text:
        return
    tree = ast.parse(text)
    target = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "E02OperatingPoint":
            target = next(child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "__post_init__")
            break
    if target is None or target.end_lineno is None:
        raise RuntimeError("E02OperatingPoint.__post_init__ not found")
    insertion = (
        '        expected_tpr_interval = exact_binomial_interval(self.positive_detected_count, self.positive_count, 0.95)\n'
        '        if self.tpr_interval != expected_tpr_interval:\n'
        '            raise ValueError("E02 TPR interval does not match exact binomial interval")\n'
        '        expected_fpr_interval = exact_binomial_interval(self.negative_detected_count, self.negative_count, 0.95)\n'
        '        if self.evaluation_fpr_interval != expected_fpr_interval:\n'
        '            raise ValueError("E02 FPR interval does not match exact binomial interval")\n'
    )
    lines = text.splitlines(keepends=True)
    lines[target.end_lineno:target.end_lineno] = [insertion]
    path.write_text("".join(lines))


def export_provenance_api() -> None:
    path = Path("fuckmark/experiments/__init__.py")
    text = path.read_text()
    block = (
        'from .transform_provenance import (\n'
        '    DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION,\n'
        '    TransformProvenanceError,\n'
        '    VerifiedTransformProvenance,\n'
        '    build_verified_transform_row,\n'
        '    verify_transform_provenance,\n'
        ')\n'
    )
    if "from .transform_provenance import (" not in text:
        text = replace_once(text, "from .transform_analysis import (", block + "from .transform_analysis import (")
    for name in (
        "DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION",
        "TransformProvenanceError",
        "VerifiedTransformProvenance",
        "build_verified_transform_row",
        "verify_transform_provenance",
    ):
        entry = f'    "{name}",\n'
        if entry not in text:
            text = replace_once(text, '    "calibrate_tiny_dev_detector",\n', entry + '    "calibrate_tiny_dev_detector",\n')
    path.write_text(text)


def main() -> None:
    patch_schedule_analysis()
    patch_transform_analysis()
    patch_calibration_interval_if_needed()
    patch_token_ngram_if_needed()
    patch_e02_exact_intervals()
    export_provenance_api()


if __name__ == "__main__":
    main()
