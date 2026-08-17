from dataclasses import replace

import pytest

from confirmatory_helpers import calibration_materials, confirmatory_condition_plan, preregistration_inputs
from fuckmark.corpus import CorpusDomain
from fuckmark.coverage import Interval
from fuckmark.detectors import ComparisonOperator
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e23_human_control import (
    E23AuthorshipStatus,
    E23CellStatus,
    E23DetectorEvidencePair,
    E23FidelityStatus,
    E23HumanControlSample,
    E23LicenseStatus,
    E23ReportStatus,
    build_e23_human_control_manifest,
    build_e23_human_control_report,
    build_e23_transform_bundle,
    verify_e23_human_control_report,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import KeyBlindScheduleInput, ScheduleGeometryMode, default_transform_registry


def _human_sample(*, license_status=E23LicenseStatus.VERIFIED_DERIVATIVE_USE_ALLOWED, authorship_status=E23AuthorshipStatus.VERIFIED_HUMAN):
    return E23HumanControlSample.create(
        sample_id="human-control-001",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        source_id="e23-schema-test-fixture",
        source_revision_hash=sha256_text("e23-schema-test-fixture-revision"),
        source_content_hash=sha256_text("e23-schema-test-fixture-source"),
        license_id="CC0-1.0",
        license_evidence_hash=sha256_text("e23-schema-test-fixture-license-evidence"),
        license_status=license_status,
        authorship_evidence_hash=sha256_text("e23-schema-test-fixture-authorship-evidence"),
        authorship_status=authorship_status,
        text="We do not proceed, we cannot agree, and we will not stop.",
    )


def _experiment_fixture():
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    preregistration = create_confirmatory_preregistration(inputs)
    condition_plan = confirmatory_condition_plan(calibration_bundles=inputs.calibration_bundles)
    sample = _human_sample()
    manifest = build_e23_human_control_manifest("e23-human-control-test", (sample,))
    registry = default_transform_registry()
    enumeration = registry.enumerate(sample.text)
    geometry = {candidate.candidate_id: (Interval(candidate.start, candidate.end),) for candidate in enumeration.candidates}
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        budget_unit="operation",
        coverage_intervals=geometry,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    transform_ids = tuple(sorted({value.transform_condition_id for value in condition_plan.conditions}))
    schedule_inputs = {(sample.sample_id, transform_condition_id): scheduler_input for transform_condition_id in transform_ids}
    transform_bundle = build_e23_transform_bundle(manifest, preregistration, condition_plan, registry, schedule_inputs)
    _, calibration_evidence = calibration_materials()
    bundle_by_hash = {value.bundle_hash: value for value in preregistration.calibration_bundles}
    return preregistration, condition_plan, sample, manifest, registry, scheduler_input, schedule_inputs, transform_bundle, calibration_evidence, bundle_by_hash


def _score_pair(threshold):
    pristine = max(0.0, threshold.value - 0.25)
    transformed = threshold.value if threshold.comparison_operator is ComparisonOperator.GREATER_THAN_OR_EQUAL else min(1.0, threshold.value + 0.25)
    assert pristine < threshold.value
    if threshold.comparison_operator is ComparisonOperator.GREATER_THAN:
        assert transformed > threshold.value
    else:
        assert transformed >= threshold.value
    return pristine, transformed


def _detector_pairs(condition_plan, sample, transform_bundle, calibration_evidence, bundle_by_hash, fidelity_by_condition=None):
    fidelity_by_condition = fidelity_by_condition or {}
    pairs = []
    for condition in condition_plan.conditions:
        bundle = bundle_by_hash[condition.calibration_bundle_hash]
        threshold = next(value for value in bundle.thresholds if value.target_fpr == condition.target_fpr)
        pristine_score, transformed_score = _score_pair(threshold)
        base = calibration_evidence[bundle.bundle_hash][0]
        pristine = replace(base, sample_id=sample.sample_id, observation_batch_hash=sha256_text(f"e23-pristine:{condition.condition_id}"), raw_score=pristine_score)
        transformed = replace(base, sample_id=sample.sample_id, observation_batch_hash=sha256_text(f"e23-transformed:{condition.condition_id}"), raw_score=transformed_score)
        transform = transform_bundle.record_for(sample.sample_id, condition.transform_condition_id)
        fidelity_status = fidelity_by_condition.get(condition.condition_id, E23FidelityStatus.PASS)
        pairs.append(
            E23DetectorEvidencePair.create(
                sample.sample_id,
                condition.condition_id,
                sample.record_hash,
                transform.transform_hash,
                sample.text_sha256,
                transform.transformed_text_hash,
                fidelity_status,
                sha256_text(f"e23-fidelity:{condition.condition_id}:{fidelity_status.value}"),
                pristine,
                transformed,
            )
        )
    return tuple(pairs)


def test_e23_human_manifest_requires_verified_license_and_authorship() -> None:
    manifest = build_e23_human_control_manifest("e23-human-control-test", (_human_sample(),))
    assert len(manifest.samples) == 1
    with pytest.raises(ValueError, match="derivative-use permission"):
        build_e23_human_control_manifest("e23-human-control-test", (_human_sample(license_status=E23LicenseStatus.UNVERIFIED),))
    with pytest.raises(ValueError, match="verified human authorship"):
        build_e23_human_control_manifest("e23-human-control-test", (_human_sample(authorship_status=E23AuthorshipStatus.UNKNOWN),))


def test_e23_transform_bundle_reuses_frozen_plan_and_is_deterministic() -> None:
    preregistration, condition_plan, _, manifest, registry, _, schedule_inputs, transform_bundle, _, _ = _experiment_fixture()
    transform_ids = {value.transform_condition_id for value in condition_plan.conditions}
    assert len(transform_bundle.records) == len(transform_ids)
    assert all(value.ruleset_hash == preregistration.transform_ruleset_hash for value in transform_bundle.records)
    assert all(value.selected_candidate_ids for value in transform_bundle.records)
    assert build_e23_transform_bundle(manifest, preregistration, condition_plan, registry, schedule_inputs) == transform_bundle


def test_e23_transform_bundle_rejects_missing_or_wrong_geometry_inputs() -> None:
    preregistration, condition_plan, sample, manifest, registry, _, schedule_inputs, _, _, _ = _experiment_fixture()
    missing = dict(schedule_inputs)
    missing.pop(next(iter(missing)))
    with pytest.raises(ValueError, match="coverage mismatch"):
        build_e23_transform_bundle(manifest, preregistration, condition_plan, registry, missing)
    text_only = KeyBlindScheduleInput.from_enumeration(registry.enumerate(sample.text), budget_unit="operation", geometry_mode=ScheduleGeometryMode.TEXT_ONLY)
    wrong = dict(schedule_inputs)
    wrong[(sample.sample_id, next(iter({value.transform_condition_id for value in condition_plan.conditions})))] = text_only
    with pytest.raises(ValueError, match="geometry mode"):
        build_e23_transform_bundle(manifest, preregistration, condition_plan, registry, wrong)


def test_e23_report_quantifies_human_false_positive_shift_with_frozen_thresholds() -> None:
    preregistration, condition_plan, sample, manifest, _, _, _, transform_bundle, calibration_evidence, bundle_by_hash = _experiment_fixture()
    pairs = _detector_pairs(condition_plan, sample, transform_bundle, calibration_evidence, bundle_by_hash)
    report = build_e23_human_control_report(manifest, transform_bundle, preregistration, condition_plan, pairs)
    assert report.status is E23ReportStatus.COMPLETE
    assert len(report.rows) == len(condition_plan.conditions)
    assert report.maximum_positive_fpr_shift == 1.0
    assert all(value.status is E23CellStatus.ESTIMATED for value in report.conditions)
    assert all(value.pristine_fpr == 0.0 for value in report.conditions)
    assert all(value.transformed_fpr == 1.0 for value in report.conditions)
    assert all(value.false_to_true_count == 1 for value in report.conditions)
    verify_e23_human_control_report(report, manifest, transform_bundle, preregistration, condition_plan, pairs)


def test_e23_fidelity_gate_excludes_material_change_without_dropping_row() -> None:
    preregistration, condition_plan, sample, manifest, _, _, _, transform_bundle, calibration_evidence, bundle_by_hash = _experiment_fixture()
    excluded_condition = condition_plan.conditions[0]
    pairs = _detector_pairs(
        condition_plan,
        sample,
        transform_bundle,
        calibration_evidence,
        bundle_by_hash,
        {excluded_condition.condition_id: E23FidelityStatus.MATERIAL_CHANGE},
    )
    report = build_e23_human_control_report(manifest, transform_bundle, preregistration, condition_plan, pairs)
    summary = next(value for value in report.conditions if value.condition_id == excluded_condition.condition_id)
    assert summary.total_count == 1
    assert summary.included_count == 0
    assert summary.material_change_count == 1
    assert summary.status is E23CellStatus.NO_FIDELITY_PASS_ROWS
    assert summary.pristine_fpr is None
    row = next(value for value in report.rows if value.condition_id == excluded_condition.condition_id)
    assert row.fidelity_status is E23FidelityStatus.MATERIAL_CHANGE
    assert not row.included


def test_e23_detector_pair_rejects_cross_detector_identity() -> None:
    _, condition_plan, sample, _, _, _, _, transform_bundle, calibration_evidence, bundle_by_hash = _experiment_fixture()
    first_condition = condition_plan.conditions[0]
    first_bundle = bundle_by_hash[first_condition.calibration_bundle_hash]
    other_bundle = next(value for value in bundle_by_hash.values() if value.bundle_hash != first_bundle.bundle_hash)
    first_evidence = calibration_evidence[first_bundle.bundle_hash][0]
    other_evidence = calibration_evidence[other_bundle.bundle_hash][0]
    transform = transform_bundle.record_for(sample.sample_id, first_condition.transform_condition_id)
    pristine = replace(first_evidence, sample_id=sample.sample_id, observation_batch_hash=sha256_text("e23-cross-pristine"))
    transformed = replace(other_evidence, sample_id=sample.sample_id, observation_batch_hash=sha256_text("e23-cross-transformed"))
    with pytest.raises(ValueError, match="same detector identity"):
        E23DetectorEvidencePair.create(
            sample.sample_id,
            first_condition.condition_id,
            sample.record_hash,
            transform.transform_hash,
            sample.text_sha256,
            transform.transformed_text_hash,
            E23FidelityStatus.PASS,
            sha256_text("e23-cross-fidelity"),
            pristine,
            transformed,
        )
