from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import normalize_token_sequence, require_int, require_sha256
from ..alignment import AlignmentResult, align_tokens
from ..hashing import sha256_json
from ..observations import StructuralObservationState, structural_observation_diff
from ..public_eligibility import (
    PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
    PublicEligibilityMask,
    build_huggingface_public_eligibility,
)


RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION = "residual-signal-geometry-v1"
RESIDUAL_SIGNAL_STRICT_VDR_MINIMUM = 0.90
RESIDUAL_SIGNAL_REFERENCE_MISMATCH = "RESIDUAL_SIGNAL_REFERENCE_MISMATCH"
FINAL_VALID_DENOMINATOR_COLLAPSE = "FINAL_VALID_DENOMINATOR_COLLAPSE"
REPETITION_MASK_GAMING = "REPETITION_MASK_GAMING"


@dataclass(frozen=True, slots=True)
class ResidualSignalGeometry:
    algorithm_version: str
    public_eligibility_algorithm_version: str
    ngram_len: int
    context_history_size: int
    eos_token_id: int
    root_token_hash: str
    final_token_hash: str
    root_valid_observation_count: int
    final_valid_observation_count: int
    exact_preserved_root_valid_before_final_mask_count: int
    preserved_root_valid_observation_count: int
    preserved_lost_to_repetition_only_count: int
    preserved_lost_to_eos_only_count: int
    preserved_lost_to_repetition_and_eos_count: int
    root_repeated_context_count: int
    final_repeated_context_count: int
    repetition_mask_delta: int
    root_post_eos_count: int
    final_post_eos_count: int
    eos_mask_delta: int
    root_survival_fraction: float
    root_destruction_fraction: float
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    alignment_distance: int
    alignment_ambiguous_ties: int
    preserved_pairs: tuple[tuple[int, int], ...]
    geometry_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported residual-signal geometry version")
        if self.public_eligibility_algorithm_version != PUBLIC_ELIGIBILITY_ALGORITHM_VERSION:
            raise ValueError("public eligibility algorithm version drifted")
        for name in (
            "ngram_len",
            "context_history_size",
            "eos_token_id",
            "root_valid_observation_count",
            "final_valid_observation_count",
            "exact_preserved_root_valid_before_final_mask_count",
            "preserved_root_valid_observation_count",
            "preserved_lost_to_repetition_only_count",
            "preserved_lost_to_eos_only_count",
            "preserved_lost_to_repetition_and_eos_count",
            "root_repeated_context_count",
            "final_repeated_context_count",
            "repetition_mask_delta",
            "root_post_eos_count",
            "final_post_eos_count",
            "eos_mask_delta",
            "alignment_distance",
            "alignment_ambiguous_ties",
        ):
            require_int(name, getattr(self, name))
        if self.ngram_len < 2 or self.context_history_size <= 0 or self.eos_token_id < 0:
            raise ValueError("invalid public geometry configuration")
        nonnegative = (
            self.root_valid_observation_count,
            self.final_valid_observation_count,
            self.exact_preserved_root_valid_before_final_mask_count,
            self.preserved_root_valid_observation_count,
            self.preserved_lost_to_repetition_only_count,
            self.preserved_lost_to_eos_only_count,
            self.preserved_lost_to_repetition_and_eos_count,
            self.root_repeated_context_count,
            self.final_repeated_context_count,
            self.root_post_eos_count,
            self.final_post_eos_count,
            self.alignment_distance,
            self.alignment_ambiguous_ties,
        )
        if any(value < 0 for value in nonnegative):
            raise ValueError("residual-signal counts must be non-negative")
        for name in ("root_token_hash", "final_token_hash", "geometry_hash"):
            require_sha256(name, getattr(self, name))
        if self.preserved_root_valid_observation_count > self.root_valid_observation_count:
            raise ValueError("preserved observations exceed root valid observations")
        if self.preserved_root_valid_observation_count > self.final_valid_observation_count:
            raise ValueError("preserved observations exceed final valid observations")
        lost = (
            self.preserved_lost_to_repetition_only_count
            + self.preserved_lost_to_eos_only_count
            + self.preserved_lost_to_repetition_and_eos_count
        )
        if self.exact_preserved_root_valid_before_final_mask_count != self.preserved_root_valid_observation_count + lost:
            raise ValueError("preserved final-mask decomposition does not sum")
        if len(self.preserved_pairs) != self.preserved_root_valid_observation_count:
            raise ValueError("preserved pair count does not match preserved observations")
        if tuple(sorted(self.preserved_pairs)) != self.preserved_pairs:
            raise ValueError("preserved pairs must be canonically ordered")
        if len(set(left for left, _ in self.preserved_pairs)) != len(self.preserved_pairs):
            raise ValueError("root preserved observation indices must be unique")
        if len(set(right for _, right in self.preserved_pairs)) != len(self.preserved_pairs):
            raise ValueError("final preserved observation indices must be unique")
        for pair in self.preserved_pairs:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("preserved_pairs must contain index pairs")
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in pair):
                raise ValueError("preserved pair indices must be non-negative integers")
        expected_rsf = self.preserved_root_valid_observation_count / max(1, self.root_valid_observation_count)
        expected_rdf = 1.0 - expected_rsf
        expected_rif = self.preserved_root_valid_observation_count / max(1, self.final_valid_observation_count)
        expected_ncf = (self.final_valid_observation_count - self.preserved_root_valid_observation_count) / max(
            1, self.final_valid_observation_count
        )
        expected_vdr = self.final_valid_observation_count / max(1, self.root_valid_observation_count)
        expected_values = {
            "root_survival_fraction": expected_rsf,
            "root_destruction_fraction": expected_rdf,
            "residual_inherited_fraction": expected_rif,
            "new_context_opportunity_fraction": expected_ncf,
            "valid_denominator_ratio": expected_vdr,
        }
        for name, expected in expected_values.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
            if float(value) != expected:
                raise ValueError(f"{name} does not match residual-signal counts")
        if self.geometry_hash != sha256_json(self.payload()):
            raise ValueError("geometry_hash does not match residual-signal geometry")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "geometry_hash"}


@dataclass(frozen=True, slots=True)
class ResidualSignalStrictGate:
    eligible: bool
    reason_codes: tuple[str, ...]
    vdr_minimum: float
    repetition_mask_growth_cap: int
    gate_hash: str

    def __post_init__(self) -> None:
        if type(self.eligible) is not bool:
            raise TypeError("eligible must be bool")
        if self.vdr_minimum != RESIDUAL_SIGNAL_STRICT_VDR_MINIMUM:
            raise ValueError("strict VDR minimum drifted")
        require_int("repetition_mask_growth_cap", self.repetition_mask_growth_cap)
        if self.repetition_mask_growth_cap < 0:
            raise ValueError("repetition mask growth cap must be non-negative")
        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("reason codes must be unique and sorted")
        if self.eligible != (not self.reason_codes):
            raise ValueError("eligible flag does not match reason codes")
        require_sha256("gate_hash", self.gate_hash)
        if self.gate_hash != sha256_json(self.payload()):
            raise ValueError("gate_hash does not match strict residual gate")

    def payload(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "reason_codes": self.reason_codes,
            "vdr_minimum": self.vdr_minimum,
            "repetition_mask_growth_cap": self.repetition_mask_growth_cap,
        }


def _masks(
    root_tokens: tuple[int, ...],
    final_tokens: tuple[int, ...],
    *,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int,
) -> tuple[PublicEligibilityMask, PublicEligibilityMask]:
    return (
        build_huggingface_public_eligibility(root_tokens, eos_token_id, ngram_len, context_history_size),
        build_huggingface_public_eligibility(final_tokens, eos_token_id, ngram_len, context_history_size),
    )


def _exact_counterpart_from_alignment(
    root_start: int,
    ngram_len: int,
    alignment: AlignmentResult,
) -> int | None:
    mapped = alignment.original_to_transformed[root_start : root_start + ngram_len]
    if any(value is None for value in mapped):
        return None
    values = tuple(int(value) for value in mapped)
    start = values[0]
    if values != tuple(range(start, start + ngram_len)):
        return None
    return start


def _build_geometry(
    root_tokens: tuple[int, ...],
    final_tokens: tuple[int, ...],
    root_mask: PublicEligibilityMask,
    final_mask: PublicEligibilityMask,
    alignment: AlignmentResult,
    exact_pairs_before_mask: Sequence[tuple[int, int]],
) -> ResidualSignalGeometry:
    kept: list[tuple[int, int]] = []
    repetition_only = 0
    eos_only = 0
    both = 0
    for root_index, final_index in exact_pairs_before_mask:
        if not root_mask.valid_mask[root_index]:
            continue
        context_valid = final_mask.context_mask[final_index]
        eos_valid = final_mask.eos_mask[final_index]
        if context_valid and eos_valid:
            kept.append((root_index, final_index))
        elif not context_valid and eos_valid:
            repetition_only += 1
        elif context_valid and not eos_valid:
            eos_only += 1
        else:
            both += 1
    preserved_pairs = tuple(kept)
    root_valid = root_mask.valid_count
    final_valid = final_mask.valid_count
    preserved = len(preserved_pairs)
    before_mask = preserved + repetition_only + eos_only + both
    rsf = preserved / max(1, root_valid)
    payload = {
        "algorithm_version": RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION,
        "public_eligibility_algorithm_version": PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        "ngram_len": root_mask.ngram_len,
        "context_history_size": root_mask.context_history_size,
        "eos_token_id": root_mask.eos_token_id,
        "root_token_hash": root_mask.token_hash,
        "final_token_hash": final_mask.token_hash,
        "root_valid_observation_count": root_valid,
        "final_valid_observation_count": final_valid,
        "exact_preserved_root_valid_before_final_mask_count": before_mask,
        "preserved_root_valid_observation_count": preserved,
        "preserved_lost_to_repetition_only_count": repetition_only,
        "preserved_lost_to_eos_only_count": eos_only,
        "preserved_lost_to_repetition_and_eos_count": both,
        "root_repeated_context_count": root_mask.repeated_count,
        "final_repeated_context_count": final_mask.repeated_count,
        "repetition_mask_delta": final_mask.repeated_count - root_mask.repeated_count,
        "root_post_eos_count": root_mask.post_eos_count,
        "final_post_eos_count": final_mask.post_eos_count,
        "eos_mask_delta": final_mask.post_eos_count - root_mask.post_eos_count,
        "root_survival_fraction": rsf,
        "root_destruction_fraction": 1.0 - rsf,
        "residual_inherited_fraction": preserved / max(1, final_valid),
        "new_context_opportunity_fraction": (final_valid - preserved) / max(1, final_valid),
        "valid_denominator_ratio": final_valid / max(1, root_valid),
        "alignment_distance": alignment.distance,
        "alignment_ambiguous_ties": alignment.ambiguous_ties,
        "preserved_pairs": preserved_pairs,
    }
    return ResidualSignalGeometry(**payload, geometry_hash=sha256_json(payload))


def compute_residual_signal_geometry(
    root_token_ids: Sequence[int],
    final_token_ids: Sequence[int],
    *,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int = 1024,
) -> ResidualSignalGeometry:
    root_tokens = normalize_token_sequence("root_token_ids", root_token_ids)
    final_tokens = normalize_token_sequence("final_token_ids", final_token_ids)
    root_mask, final_mask = _masks(
        root_tokens,
        final_tokens,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    alignment = align_tokens(root_tokens, final_tokens)
    diffs = structural_observation_diff(root_tokens, final_tokens, ngram_len, alignment)
    exact_pairs = tuple(
        (diff.original_index, int(diff.transformed_index))
        for diff in diffs
        if diff.state is StructuralObservationState.PRESERVED and diff.transformed_index is not None
    )
    return _build_geometry(root_tokens, final_tokens, root_mask, final_mask, alignment, exact_pairs)


def compute_residual_signal_geometry_reference(
    root_token_ids: Sequence[int],
    final_token_ids: Sequence[int],
    *,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int = 1024,
) -> ResidualSignalGeometry:
    root_tokens = normalize_token_sequence("root_token_ids", root_token_ids)
    final_tokens = normalize_token_sequence("final_token_ids", final_token_ids)
    root_mask, final_mask = _masks(
        root_tokens,
        final_tokens,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    alignment = align_tokens(root_tokens, final_tokens)
    pairs: list[tuple[int, int]] = []
    final_observation_count = max(0, len(final_tokens) - ngram_len + 1)
    for root_index in range(max(0, len(root_tokens) - ngram_len + 1)):
        if not root_mask.valid_mask[root_index]:
            continue
        root_ngram = root_tokens[root_index : root_index + ngram_len]
        for final_index in range(final_observation_count):
            if final_tokens[final_index : final_index + ngram_len] != root_ngram:
                continue
            mapped = alignment.original_to_transformed[root_index : root_index + ngram_len]
            if tuple(mapped) == tuple(range(final_index, final_index + ngram_len)):
                pairs.append((root_index, final_index))
                break
    return _build_geometry(root_tokens, final_tokens, root_mask, final_mask, alignment, tuple(pairs))


def assert_residual_signal_reference_match(
    root_token_ids: Sequence[int],
    final_token_ids: Sequence[int],
    *,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int = 1024,
) -> ResidualSignalGeometry:
    optimized = compute_residual_signal_geometry(
        root_token_ids,
        final_token_ids,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    reference = compute_residual_signal_geometry_reference(
        root_token_ids,
        final_token_ids,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    if optimized != reference:
        raise RuntimeError(RESIDUAL_SIGNAL_REFERENCE_MISMATCH)
    return optimized


def strict_residual_signal_gate(
    geometry: ResidualSignalGeometry,
    *,
    repetition_mask_growth_cap: int,
    protected_span_violation_count: int,
    hard_invariant_passed: bool,
    visible_fidelity_passed: bool,
) -> ResidualSignalStrictGate:
    if not isinstance(geometry, ResidualSignalGeometry):
        raise TypeError("geometry must be ResidualSignalGeometry")
    require_int("repetition_mask_growth_cap", repetition_mask_growth_cap)
    require_int("protected_span_violation_count", protected_span_violation_count)
    if repetition_mask_growth_cap < 0 or protected_span_violation_count < 0:
        raise ValueError("gate counts must be non-negative")
    if type(hard_invariant_passed) is not bool or type(visible_fidelity_passed) is not bool:
        raise TypeError("gate pass flags must be bool")
    reasons: list[str] = []
    if geometry.valid_denominator_ratio < RESIDUAL_SIGNAL_STRICT_VDR_MINIMUM:
        reasons.append(FINAL_VALID_DENOMINATOR_COLLAPSE)
    if geometry.repetition_mask_delta > repetition_mask_growth_cap:
        reasons.append(REPETITION_MASK_GAMING)
    if protected_span_violation_count:
        reasons.append("PROTECTED_SPAN_VIOLATION")
    if not hard_invariant_passed:
        reasons.append("HARD_FIDELITY_INVARIANT_FAILED")
    if not visible_fidelity_passed:
        reasons.append("VISIBLE_FIDELITY_LIMIT_EXCEEDED")
    reason_codes = tuple(sorted(set(reasons)))
    payload = {
        "eligible": not reason_codes,
        "reason_codes": reason_codes,
        "vdr_minimum": RESIDUAL_SIGNAL_STRICT_VDR_MINIMUM,
        "repetition_mask_growth_cap": repetition_mask_growth_cap,
    }
    return ResidualSignalStrictGate(**payload, gate_hash=sha256_json(payload))
