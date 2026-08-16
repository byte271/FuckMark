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
    for old, new in (
        ('E09_ALGORITHM_VERSION = "e09-random-baseline-v1"', 'E09_ALGORITHM_VERSION = "e09-random-baseline-v2"'),
        ('E10_ALGORITHM_VERSION = "e10-spacing-comparison-v1"', 'E10_ALGORITHM_VERSION = "e10-spacing-comparison-v2"'),
        ('E11_ALGORITHM_VERSION = "e11-key-blind-greedy-v1"', 'E11_ALGORITHM_VERSION = "e11-key-blind-greedy-v2"'),
    ):
        if old in text:
            text = text.replace(old, new, 1)
    if "class E10Status(str, Enum):" not in text:
        text = replace_once(
            text,
            'class E10PairStatus(str, Enum):\n    MATCHED = "MATCHED"\n    UNMATCHED_COST = "UNMATCHED_COST"\n\n\nclass E11Status(str, Enum):\n',
            'class E10PairStatus(str, Enum):\n    MATCHED = "MATCHED"\n    UNMATCHED_COST = "UNMATCHED_COST"\n\n\nclass E10Status(str, Enum):\n    COMPLETE_MATCHED = "COMPLETE_MATCHED"\n    WITHHELD_UNMATCHED_COST = "WITHHELD_UNMATCHED_COST"\n    INCOMPLETE = "INCOMPLETE"\n\n\nclass E11Status(str, Enum):\n',
        )
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
    old_e09 = '    replacement_values = tuple(row.replacement_per_edit for row in rows)\n    margin_values = tuple(row.margin_drop for row in rows)\n    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E09)\n'
    if old_e09 in text:
        new_e09 = '    replacement_values = tuple(\n        sum(row.replacement_per_edit for row in rows if row.source_sample_id == source_id)\n        / sum(row.source_sample_id == source_id for row in rows)\n        for source_id in observed_ids\n    )\n    margin_values = tuple(\n        sum(row.margin_drop for row in rows if row.source_sample_id == source_id)\n        / sum(row.source_sample_id == source_id for row in rows)\n        for source_id in observed_ids\n    )\n    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E09)\n'
        text = replace_once(text, old_e09, new_e09)
    old_e10_fields = '    detector_identity_hash: str\n    threshold_hash: str\n    pair_hashes: tuple[str, ...]\n    matched_pair_count: int\n'
    if old_e10_fields in text:
        text = replace_once(
            text,
            old_e10_fields,
            '    detector_identity_hash: str\n    threshold_hash: str\n    pair_hashes: tuple[str, ...]\n    expected_source_count: int\n    observed_source_count: int\n    missing_source_ids: tuple[str, ...]\n    matched_pair_count: int\n',
        )
    old_e10_tail_fields = '    mean_margin_drop_difference_even_minus_clustered: float | None\n    comparison_withheld_for_unmatched_cost: bool\n    result_hash: str\n'
    if old_e10_tail_fields in text:
        text = replace_once(
            text,
            old_e10_tail_fields,
            '    mean_margin_drop_difference_even_minus_clustered: float | None\n    comparison_withheld_for_unmatched_cost: bool\n    status: E10Status\n    result_hash: str\n',
        )
    e10_validation_anchor = '        for value in self.pair_hashes:\n            require_sha256("pair_hash", value)\n        require_int("matched_pair_count", self.matched_pair_count)\n'
    if "tiny-dev E10 expects four watermarked attack sources" not in text:
        text = replace_once(
            text,
            e10_validation_anchor,
            '        for value in self.pair_hashes:\n            require_sha256("pair_hash", value)\n        require_int("expected_source_count", self.expected_source_count)\n        require_int("observed_source_count", self.observed_source_count)\n        if self.expected_source_count != 4:\n            raise ValueError("tiny-dev E10 expects four watermarked attack sources")\n        if not 0 <= self.observed_source_count <= self.expected_source_count:\n            raise ValueError("E10 observed_source_count is outside expected range")\n        if self.missing_source_ids != tuple(sorted(set(self.missing_source_ids))):\n            raise ValueError("E10 missing_source_ids must be unique and canonically ordered")\n        if len(self.missing_source_ids) != self.expected_source_count - self.observed_source_count:\n            raise ValueError("E10 missing source count does not match observed source count")\n        require_int("matched_pair_count", self.matched_pair_count)\n',
        )
    e10_status_anchor = '        require_bool("comparison_withheld_for_unmatched_cost", self.comparison_withheld_for_unmatched_cost)\n        if self.comparison_withheld_for_unmatched_cost != (self.unmatched_cost_pair_count > 0):\n            raise ValueError("E10 unmatched-cost withholding flag does not match pair count")\n        if self.result_hash != sha256_json(self._payload()):\n'
    if "E10 status does not match source completeness" not in text:
        text = replace_once(
            text,
            e10_status_anchor,
            '        require_bool("comparison_withheld_for_unmatched_cost", self.comparison_withheld_for_unmatched_cost)\n        if self.comparison_withheld_for_unmatched_cost != (self.unmatched_cost_pair_count > 0):\n            raise ValueError("E10 unmatched-cost withholding flag does not match pair count")\n        if not isinstance(self.status, E10Status):\n            raise TypeError("status must be an E10Status")\n        if self.missing_source_ids:\n            expected_status = E10Status.INCOMPLETE\n        elif self.unmatched_cost_pair_count:\n            expected_status = E10Status.WITHHELD_UNMATCHED_COST\n        else:\n            expected_status = E10Status.COMPLETE_MATCHED\n        if self.status is not expected_status:\n            raise ValueError("E10 status does not match source completeness and cost matching")\n        if self.result_hash != sha256_json(self._payload()):\n',
        )
    e10_payload_anchor = '            "threshold_hash": self.threshold_hash,\n            "pair_hashes": self.pair_hashes,\n            "matched_pair_count": self.matched_pair_count,\n'
    if '            "expected_source_count": self.expected_source_count,\n' not in text:
        text = replace_once(
            text,
            e10_payload_anchor,
            '            "threshold_hash": self.threshold_hash,\n            "pair_hashes": self.pair_hashes,\n            "expected_source_count": self.expected_source_count,\n            "observed_source_count": self.observed_source_count,\n            "missing_source_ids": self.missing_source_ids,\n            "matched_pair_count": self.matched_pair_count,\n',
        )
    e10_payload_status_anchor = '            "comparison_withheld_for_unmatched_cost": self.comparison_withheld_for_unmatched_cost,\n        }\n\n\ndef run_e10_spacing_comparison(\n'
    if '            "status": self.status.value,\n        }\n\n\ndef run_e10_spacing_comparison(' not in text:
        text = replace_once(
            text,
            e10_payload_status_anchor,
            '            "comparison_withheld_for_unmatched_cost": self.comparison_withheld_for_unmatched_cost,\n            "status": self.status.value,\n        }\n\n\ndef run_e10_spacing_comparison(\n',
        )
    e10_run_anchor = '    pair_tuple = tuple(pairs)\n    matched = tuple(value for value in pair_tuple if value.status is E10PairStatus.MATCHED)\n    unmatched_count = len(pair_tuple) - len(matched)\n'
    if "observed_source_ids = tuple(sorted({value.source_sample_id for value in pair_tuple}))" not in text:
        text = replace_once(
            text,
            e10_run_anchor,
            '    pair_tuple = tuple(pairs)\n    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))\n    observed_source_ids = tuple(sorted({value.source_sample_id for value in pair_tuple}))\n    missing = tuple(sorted(set(expected_ids) - set(observed_source_ids)))\n    matched = tuple(value for value in pair_tuple if value.status is E10PairStatus.MATCHED)\n    unmatched_count = len(pair_tuple) - len(matched)\n',
        )
    e10_definition_anchor = '    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E10)\n    pair_hashes = tuple(sorted(value.pair_hash for value in pair_tuple))\n    payload = {\n'
    if "status = E10Status.INCOMPLETE" not in text:
        text = replace_once(
            text,
            e10_definition_anchor,
            '    if missing:\n        status = E10Status.INCOMPLETE\n    elif unmatched_count:\n        status = E10Status.WITHHELD_UNMATCHED_COST\n    else:\n        status = E10Status.COMPLETE_MATCHED\n    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E10)\n    pair_hashes = tuple(sorted(value.pair_hash for value in pair_tuple))\n    payload = {\n',
        )
    e10_run_payload_anchor = '        "threshold_hash": threshold_hash,\n        "pair_hashes": pair_hashes,\n        "matched_pair_count": len(matched),\n'
    if '        "expected_source_count": len(expected_ids),\n        "observed_source_count": len(observed_source_ids),\n' not in text:
        text = replace_once(
            text,
            e10_run_payload_anchor,
            '        "threshold_hash": threshold_hash,\n        "pair_hashes": pair_hashes,\n        "expected_source_count": len(expected_ids),\n        "observed_source_count": len(observed_source_ids),\n        "missing_source_ids": missing,\n        "matched_pair_count": len(matched),\n',
        )
    e10_run_payload_tail = '        "comparison_withheld_for_unmatched_cost": unmatched_count > 0,\n    }\n    return E10SpacingComparisonResult(\n'
    if '        "status": status.value,\n    }\n    return E10SpacingComparisonResult(' not in text:
        text = replace_once(
            text,
            e10_run_payload_tail,
            '        "comparison_withheld_for_unmatched_cost": unmatched_count > 0,\n        "status": status.value,\n    }\n    return E10SpacingComparisonResult(\n',
        )
    e10_constructor_anchor = '        detector_identity_hash,\n        threshold_hash,\n        pair_hashes,\n        len(matched),\n'
    if '        pair_hashes,\n        len(expected_ids),\n        len(observed_source_ids),\n        missing,\n' not in text:
        text = replace_once(
            text,
            e10_constructor_anchor,
            '        detector_identity_hash,\n        threshold_hash,\n        pair_hashes,\n        len(expected_ids),\n        len(observed_source_ids),\n        missing,\n        len(matched),\n',
        )
    e10_constructor_tail = '        payload["mean_margin_drop_difference_even_minus_clustered"],\n        unmatched_count > 0,\n        sha256_json(payload),\n    )\n'
    if '        unmatched_count > 0,\n        status,\n        sha256_json(payload),\n    )\n' not in text:
        text = replace_once(
            text,
            e10_constructor_tail,
            '        payload["mean_margin_drop_difference_even_minus_clustered"],\n        unmatched_count > 0,\n        status,\n        sha256_json(payload),\n    )\n',
        )
    marker = "def run_e11_greedy_comparison("
    index = text.index(marker)
    head, tail = text[:index], text[index:]
    desired = "    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows, allow_secret_access=True)\n"
    if desired not in tail:
        tail = replace_once(tail, "    detector_identity_hash, threshold_hash, _ = _validate_schedule_rows(artifact, rows)\n", desired)
    if "E11 requires both random and greedy rows for every pair key" not in tail:
        tail = replace_once(
            tail,
            '    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))\n    paired_ids: set[str] = set()\n',
            '    incomplete = tuple(key for key, group in groups.items() if set(group) != allowed)\n    if incomplete:\n        raise TransformAnalysisInputError("E11 requires both random and greedy rows for every pair key")\n    expected_ids = tuple(sorted(_expected_attack_sources(artifact)))\n    paired_ids: set[str] = set()\n',
        )
        tail = replace_once(tail, '        if set(group) != allowed:\n            continue\n', '')
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


def export_experiment_api() -> None:
    path = Path("fuckmark/experiments/__init__.py")
    text = path.read_text()
    provenance_block = (
        'from .transform_provenance import (\n'
        '    DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION,\n'
        '    TransformProvenanceError,\n'
        '    VerifiedTransformProvenance,\n'
        '    build_verified_transform_row,\n'
        '    verify_transform_provenance,\n'
        ')\n'
    )
    if "from .transform_provenance import (" not in text:
        text = replace_once(text, "from .transform_analysis import (", provenance_block + "from .transform_analysis import (")
    schedule_block = (
        'from .schedule_analysis import (\n'
        '    E09_ALGORITHM_VERSION,\n'
        '    E10_ALGORITHM_VERSION,\n'
        '    E11_ALGORITHM_VERSION,\n'
        '    E09BaselineStatus,\n'
        '    E09RandomBaselineResult,\n'
        '    E10PairStatus,\n'
        '    E10SpacingComparisonResult,\n'
        '    E10SpacingPair,\n'
        '    E10Status,\n'
        '    E11GreedyComparisonResult,\n'
        '    E11GreedyPair,\n'
        '    E11Status,\n'
        '    HeldOutClaimStatus,\n'
        '    run_e09_random_baseline,\n'
        '    run_e10_spacing_comparison,\n'
        '    run_e11_greedy_comparison,\n'
        ')\n'
    )
    if "from .schedule_analysis import (" not in text:
        text = replace_once(text, "from .transform_analysis import (", schedule_block + "from .transform_analysis import (")
    verification_block = (
        'from .verification import (\n'
        '    ExperimentArtifactVerificationError,\n'
        '    verify_development_calibration_binding,\n'
        '    verify_e02_result,\n'
        '    verify_e03_result,\n'
        '    verify_e07_result,\n'
        '    verify_e08_result,\n'
        '    verify_e09_result,\n'
        '    verify_e10_result,\n'
        '    verify_e11_result,\n'
        '    verify_observation_mechanism_result,\n'
        ')\n'
    )
    if "from .verification import (" not in text:
        text = replace_once(text, "from .transform_analysis import (", verification_block + "from .transform_analysis import (")
    names = (
        "DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION",
        "TransformProvenanceError",
        "VerifiedTransformProvenance",
        "build_verified_transform_row",
        "verify_transform_provenance",
        "E09_ALGORITHM_VERSION",
        "E10_ALGORITHM_VERSION",
        "E11_ALGORITHM_VERSION",
        "E09BaselineStatus",
        "E09RandomBaselineResult",
        "E10PairStatus",
        "E10SpacingComparisonResult",
        "E10SpacingPair",
        "E10Status",
        "E11GreedyComparisonResult",
        "E11GreedyPair",
        "E11Status",
        "HeldOutClaimStatus",
        "run_e09_random_baseline",
        "run_e10_spacing_comparison",
        "run_e11_greedy_comparison",
        "ExperimentArtifactVerificationError",
        "verify_development_calibration_binding",
        "verify_e02_result",
        "verify_e03_result",
        "verify_e07_result",
        "verify_e08_result",
        "verify_e09_result",
        "verify_e10_result",
        "verify_e11_result",
        "verify_observation_mechanism_result",
    )
    for name in names:
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
    export_experiment_api()


if __name__ == "__main__":
    main()
